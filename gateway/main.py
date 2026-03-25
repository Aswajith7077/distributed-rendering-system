import os
import asyncio
if os.name == "nt":
    try:
        from asyncio import WindowsProactorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request


from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from utils import is_blend_file
from utils import is_valid_blend
from service import minio_service, redis_service
from service.task_splitter import split_and_dispatch_task

import psutil
import time
import json
import logging
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from service.redis_listener import RedisStatusStreamListener
from sse_starlette.sse import EventSourceResponse




logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger(__name__)

SERVER_START_TIME = time.time()
UPLOAD_DIR = "uploads"
listener_task = None
listener = None

os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global listener_task, listener

    print(
        f"[FASTAPI] Lifespan starting... (log level: {logging.getLevelName(log.getEffectiveLevel())})",
        flush=True,
    )
    log.info("[FASTAPI] Lifespan starting...")

    async def run_listener(listener_instance):
        try:
            print("listener STARTING", flush=True)
            log.info("listener STARTING")
            await asyncio.sleep(1)
            await listener_instance.setup_group()
            await listener_instance.consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.info(f"[listener CRASH] Unhandled exception: {e}")
            import traceback
            traceback.print_exc()

    listener = RedisStatusStreamListener()
    listener_task = asyncio.create_task(run_listener(listener))
    log.info("[FASTAPI] listener task created")

    yield
    
    if listener_task:
        listener_task.cancel()


app = FastAPI(title="Distributed Tile Renderer API", version="1.0.0", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Distributed Tile Renderer API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = time.time() - SERVER_START_TIME

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        },
        "uptime_seconds": uptime,
    }


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
                    {"id": "blender_engine", "name": "Engine", "type": "select", "options": ["CYCLES", "BLENDER_EEVEE_NEXT"]},
                    {"id": "blender_samples", "name": "Samples", "type": "number"},
                    {"id": "frame_start", "name": "Start Frame", "type": "number"},
                    {"id": "frame_end", "name": "End Frame", "type": "number"},
                    {"id": "output_type", "name": "Output Type", "type": "select", "options": ["video", "single_frame"]},
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

@app.post("/api/jobs")
async def create_job(config: dict):
    # This matches the frontend's createJob call
    # For now, let's assume the user uses the /api/upload endpoint for Blender


    # For now, let's assume the user uses the /api/upload endpoint for Blender
    # This endpoint can be used for non-file jobs or metadata-only
    return JSONResponse(status_code=400, detail="Use /api/upload/ for Blender jobs")

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
        content={
            "job_id": job_id,
            "filename": file.filename,
            "status": "pending"
        }
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
        content_type = "video/mp4"
    else:
        # Default to first frame
        object_name = f"jobs/{job_id}/output/frame_0001.png"
        content_type = "image/png"
        
    try:
        # Get a presigned URL or stream the bytes
        # Presigned URL is easier for frontends
        url = minio_service.client.presigned_get_object(
            minio_service.bucket_name,
            object_name,
            expires=timedelta(hours=1)
        )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url)


    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Result file not found: {e}")

@app.get("/api/tiles/{job_id}")
async def get_tiles_preview(job_id: str):
    # For now return an empty list or mock until we have thumbnails
    return {"job_id": job_id, "tiles": []}

@app.get("/api/benchmark")
async def get_benchmark():
    return {
        "p_fraction": 0.9,
        "base_time": 100,
        "actual_data": [],
        "theoretical_data": []
    }
