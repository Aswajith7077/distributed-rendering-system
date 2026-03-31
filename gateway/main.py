import os
import asyncio
import time
import json
import logging
import uuid
from datetime import timedelta
from contextlib import asynccontextmanager
from typing import Any

if os.name == "nt":
    try:
        from asyncio import WindowsProactorEventLoopPolicy

        asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    Form,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis
from config import ConfigService

from utils import is_blend_file, is_valid_blend
from service import minio_service, redis_service
from service.task_splitter import split_and_dispatch_task
from service.redis_listener import RedisStatusStreamListener
from service.metrics_aggregator import MetricsAggregator
from utils import _build_aggregate
from utils import _persist_to_redis, _load_from_redis

config_service = ConfigService()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("gateway")


# REDIS_HOST: str = os.environ.get("REDIS_HOST", "redis")
# REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
# BROADCAST_INTERVAL: int = int(os.environ.get("BROADCAST_INTERVAL", "5"))
# SLAVE_TTL: int = int(os.environ.get("SLAVE_TTL", "15"))


_slave_registry: dict[str, dict[str, Any]] = {}
_frontend_clients: set[WebSocket] = set()
_redis: aioredis.Redis | None = None


SERVER_START_TIME = time.time()
UPLOAD_DIR = "uploads"
listener_task = None
listener = None

os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global listener_task, listener, _redis

    _redis = aioredis.Redis.from_url(
        f"redis://{config_service.REDIS_HOST}:{config_service.REDIS_PORT}",
        decode_responses=True,
    )

    log.info("[FASTAPI] Lifespan starting...")

    async def run_listener(listener_instance):
        try:
            log.info("listener STARTING")
            await asyncio.sleep(1)
            await listener_instance.setup_group()
            await listener_instance.consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"[listener CRASH] Unhandled exception: {e}")

    listener = RedisStatusStreamListener()
    listener_task = asyncio.create_task(run_listener(listener))

    # Start background components
    heartbeat_task = asyncio.create_task(_heartbeat_task())
    asyncio.create_task(_load_from_redis(_redis, _slave_registry, log))

    log.info("[FASTAPI] All background tasks created.")

    # Metrics Aggregator for WebSockets
    app.state.metrics_aggregator = MetricsAggregator()

    yield

    # Cleanup
    if listener_task:
        listener_task.cancel()
    if heartbeat_task:
        heartbeat_task.cancel()

    await _redis.close()
    await app.state.metrics_aggregator.close()
    log.info("[FASTAPI] Shutdown complete.")


app = FastAPI(title="Distributed Tile Renderer API", version="1.0.0", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Distributed Tile Renderer API", "version": "1.0.0"}


async def _broadcast(payload: dict[str, Any]) -> None:
    """Send the aggregate snapshot to all connected frontend clients."""
    if not _frontend_clients:
        return
    message = json.dumps(payload)
    dead: set[WebSocket] = set()
    for ws in list(_frontend_clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _frontend_clients.difference_update(dead)


async def _heartbeat_task() -> None:
    """Periodically broadcast to frontend clients even if no new slave data arrives."""
    while True:
        await asyncio.sleep(config_service.BROADCAST_INTERVAL)
        if _frontend_clients:
            await _broadcast(_build_aggregate(_slave_registry))


@app.websocket("/ws/slave")
async def slave_endpoint(websocket: WebSocket) -> None:
    """
    Each slave connects here and pushes JSON metrics frames.
    The gateway registers the node, persists to Redis, then
    immediately fans out the updated aggregate to frontend clients.
    """
    await websocket.accept()
    node_id: str | None = None

    try:
        async for raw in websocket.iter_text():
            try:
                data: dict = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Received non-JSON frame, skipping.")
                continue

            event = data.get("event")

            if event == "hello":
                # First frame: just registration, no metrics yet
                node_id = data["node_id"]
                log.info("Slave connected: %s", node_id)
                continue

            # Every subsequent frame is a full metrics snapshot
            node_id = data.get("node_id", node_id or "unknown")
            _slave_registry[node_id] = data

            # Fire-and-forget: persist + broadcast concurrently
            asyncio.create_task(
                _persist_to_redis(config_service, _redis, log, node_id, data)
            )
            asyncio.create_task(_broadcast(_build_aggregate(_slave_registry)))

    except WebSocketDisconnect:
        log.info("Slave disconnected: %s", node_id)
    except Exception as exc:
        log.error("Error on slave connection %s: %s", node_id, exc)
    finally:
        if node_id and node_id in _slave_registry:
            # Mark offline but keep the last snapshot for the frontend
            _slave_registry[node_id]["status"] = "offline"
            asyncio.create_task(_broadcast(_build_aggregate(_slave_registry)))


@app.websocket("/ws/metrics")
async def metrics_endpoint(websocket: WebSocket) -> None:
    """
    Frontend clients subscribe here. They receive the full aggregated
    snapshot every time any slave pushes new data, plus periodic heartbeats.
    """
    await websocket.accept()
    _frontend_clients.add(websocket)
    log.info("Frontend client connected. Total subscribers: %d", len(_frontend_clients))

    # Send the current state immediately so the dashboard doesn't start blank
    try:
        await websocket.send_text(json.dumps(_build_aggregate(_slave_registry)))
    except Exception:
        _frontend_clients.discard(websocket)
        return

    try:
        # Keep the connection alive; the gateway pushes — clients don't need to ask
        while True:
            # We still drain incoming frames (e.g. ping / filter requests)
            msg = await websocket.receive_text()
            try:
                cmd = json.loads(msg)
                if cmd.get("action") == "get_snapshot":
                    await websocket.send_text(
                        json.dumps(_build_aggregate(_slave_registry))
                    )
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        log.info("Frontend client disconnected.")
    except Exception as exc:
        log.error("Frontend WS error: %s", exc)
    finally:
        _frontend_clients.discard(websocket)
        log.info("Frontend clients remaining: %d", len(_frontend_clients))


@app.get("/health/nodes")
async def get_nodes() -> dict:
    """
    HTTP fallback so you can curl the current aggregate without a WS client.
    """
    return _build_aggregate(_slave_registry)


@app.get("/api/renderers")
async def get_available_renderers():
    """List available renderer types."""
    return {
        "renderers": [
            {
                "id": "blender",
                "name": "Blender",
                "description": "Blender headless CLI renderer (Cycles/Eevee)",
                "requires_scene_file": True,
                "options": [
                    {
                        "id": "blender_engine",
                        "name": "Engine",
                        "type": "select",
                        "options": ["CYCLES", "BLENDER_EEVEE_NEXT"],
                    },
                    {"id": "blender_samples", "name": "Samples", "type": "number"},
                    {"id": "frame_start", "name": "Start Frame", "type": "number"},
                    {"id": "frame_end", "name": "End Frame", "type": "number"},
                    {
                        "id": "output_type",
                        "name": "Output Type",
                        "type": "select",
                        "options": ["video", "single_frame"],
                    },
                ],
            },
        ]
    }


@app.get("/api/jobs")
async def list_jobs():
    jobs = await redis_service.list_jobs()
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = await redis_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    await redis_service.delete_job(job_id)
    # Optional: Clean up MinIO files too
    return {"message": "Job deleted", "job_id": job_id}


# @app.post("/api/jobs")
# async def create_job(config: dict):
#     # This matches the frontend's createJob call
#     # For now, let's assume the user uses the /api/upload endpoint for Blender

#     # For now, let's assume the user uses the /api/upload endpoint for Blender
#     # This endpoint can be used for non-file jobs or metadata-only
#     return JSONResponse(status_code=400, detail="Use /api/upload/ for Blender jobs")


@app.post("/api/upload/")
async def upload_file(file: UploadFile = File(...), config: str = Form(...)):
    if not is_blend_file(file.filename):
        raise HTTPException(status_code=400, detail="Only .blend files are allowed")

    if not is_valid_blend(file):
        raise HTTPException(status_code=400, detail="Invalid .blend file")

    try:
        config_data = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid config JSON format")

    job_id = str(uuid.uuid4())
    object_name = f"jobs/{job_id}/input/scene.blend"

    try:
        data = await file.read()
        minio_service.upload_bytes(
            data=data,
            object_name=object_name,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Trigger task splitter
    await split_and_dispatch_task(
        job_id=job_id,
        filename=file.filename,
        config=config_data,
        object_name=object_name,
    )

    return JSONResponse(
        content={"job_id": job_id, "filename": file.filename, "status": "pending"}
    )


@app.get("/api/events")
async def sse_events(request: Request):
    async def event_generator():
        pubsub = redis_service.redis.pubsub()
        await pubsub.subscribe("job_updates")

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    yield message["data"]

                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe("job_updates")

    return EventSourceResponse(event_generator())


@app.get("/api/download/{job_id}")
async def download_result(job_id: str):
    job = await redis_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not yet completed")

    output_type = job.get("output_type", "video")

    if output_type == "video":
        object_name = f"jobs/{job_id}/final_result.mp4"
    else:
        object_name = f"jobs/{job_id}/output/frame_0001.png"

    try:
        url = minio_service.client.presigned_get_object(
            minio_service.bucket_name, object_name, expires=timedelta(hours=1)
        )
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url)

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Result file not found: {e}")


@app.get("/api/tiles/{job_id}")
async def get_tiles_preview(job_id: str):
    return {"job_id": job_id, "tiles": []}


@app.get("/api/benchmark")
async def get_benchmark():
    jobs = await redis_service.list_jobs(limit=100)
    completed_jobs = [
        j for j in jobs if j.get("status") == "completed" and "completed_at" in j
    ]

    P_FRACTION = 0.95
    base_frame_time = 12.5

    actual_data = []

    for j in completed_jobs:
        duration = j.get("completed_at", 0) - j.get("created_at", 0)
        frames = j.get("total_frames", 1)
        if duration <= 0 or frames <= 0:
            continue

        workflow = j.get("workflow")
        if isinstance(workflow, str):
            import json

            try:
                workflow = json.loads(workflow)
            except Exception:
                workflow = {}
        elif not isinstance(workflow, dict):
            workflow = {}

        workers = workflow.get("workers", 0)
        if not workers:
            avg_time_per_frame = duration / frames
            if avg_time_per_frame < 5:
                workers = 4
            elif avg_time_per_frame < 8:
                workers = 2
            else:
                workers = 1

        actual_data.append(
            {
                "workers": int(workers),
                "duration": duration,
                "frames": frames,
                "job_id": j.get("job_id"),
            }
        )

    worker_groups = {}
    for d in actual_data:
        w = d["workers"]
        if w not in worker_groups:
            worker_groups[w] = []
        worker_groups[w].append(d)

    final_actual = []

    t1_jobs = worker_groups.get(1, [])
    if t1_jobs:
        total_dur = sum(j["duration"] for j in t1_jobs)
        total_frames = sum(j["frames"] for j in t1_jobs)
        base_frame_time = total_dur / total_frames
    elif actual_data:
        best_job = min(actual_data, key=lambda x: x["duration"] / x["frames"])
        base_frame_time = (best_job["duration"] * best_job["workers"] * 0.9) / best_job[
            "frames"
        ]

    for w, jobs_list in worker_groups.items():
        total_dur = sum(j["duration"] for j in jobs_list)
        total_frames = sum(j["frames"] for j in jobs_list)

        t1_theoretical = total_frames * base_frame_time
        speedup = t1_theoretical / total_dur if total_dur > 0 else 1

        final_actual.append(
            {
                "workers": w,
                "actual_time": round(total_dur / len(jobs_list), 2),
                "actual_speedup": round(speedup, 2),
                "job_count": len(jobs_list),
            }
        )

    final_actual.sort(key=lambda x: x["workers"])

    max_workers = max([d["workers"] for d in final_actual] + [4]) if final_actual else 4
    theoretical_data = []
    for n in range(1, max_workers + 3):
        s_n = 1 / ((1 - P_FRACTION) + (P_FRACTION / n))
        theoretical_data.append({"workers": n, "theoretical_speedup": round(s_n, 2)})

    return {
        "p_fraction": P_FRACTION,
        "base_frame_time": round(base_frame_time, 2),
        "actual_data": final_actual,
        "theoretical_data": theoretical_data,
        "total_jobs_analyzed": len(completed_jobs),
    }
