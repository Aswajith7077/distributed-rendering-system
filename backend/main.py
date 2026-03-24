"""
FastAPI Backend for Distributed Tile Rendering Pipeline
========================================================
Provides REST API endpoints for managing render jobs and workflow configuration.
"""

import os
import json
import uuid
import shutil
import threading
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from PIL import Image
import asyncio
import psutil
import time

from metrics import metrics_aggregator

SERVER_START_TIME = time.time()

app = FastAPI(title="Distributed Tile Renderer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
JOBS_DIR = BASE_DIR / "jobs"
OUTPUT_DIR = BASE_DIR / "output"
WORKFLOW_PATH = BASE_DIR.parent / "server" / "workflow.json"

JOBS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


class RenderMode(str):
    COORDINATOR = "coordinator"
    SCHEDULER = "scheduler"


class WorkflowConfig(BaseModel):
    image_width: int = Field(default=1920, ge=100, le=8192)
    image_height: int = Field(default=1080, ge=100, le=8192)
    tiles_rows: int = Field(default=4, ge=1, le=32)
    tiles_cols: int = Field(default=4, ge=1, le=32)
    workers: int = Field(default=4, ge=1, le=128)
    renderer_type: str = Field(default="synthetic")
    blender_scene_file: Optional[str] = None
    blender_engine: Optional[str] = "CYCLES"
    blender_samples: Optional[int] = 128
    blender_device: Optional[str] = "CPU"
    render_mode: str = Field(default=RenderMode.COORDINATOR)


class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    workflow: dict
    result: Optional[dict] = None
    error: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


jobs_db: dict[str, dict] = {}


class PubSub:
    def __init__(self):
        self.queues = []
        self.loop = None

    def subscribe(self):
        q = asyncio.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q):
        if q in self.queues:
            self.queues.remove(q)

    def publish(self, message: dict):
        if not self.loop:
            return
        async def _publish():
            for q in self.queues:
                await q.put(json.dumps(message))
        asyncio.run_coroutine_threadsafe(_publish(), self.loop)

pubsub = PubSub()


@app.on_event("startup")
async def startup_event():
    try:
        loop = asyncio.get_running_loop()
        pubsub.loop = loop
        metrics_aggregator.set_loop(loop)
    except RuntimeError:
        pass


def save_workflow_to_json(config: WorkflowConfig) -> dict:
    """Convert workflow config to workflow.json format."""
    renderer_cfg = {"type": config.renderer_type}
    
    if config.renderer_type == "blender":
        if not config.blender_scene_file:
            raise ValueError("Blender scene file is required for blender renderer")
        renderer_cfg.update({
            "scene_file": config.blender_scene_file,
            "engine": config.blender_engine,
            "samples": config.blender_samples,
            "device": config.blender_device,
        })
    
    workflow = {
        "pipeline": [
            {"operator": "frame_split"},
            {"operator": "render", "parallel": True},
            {"operator": "stitch"}
        ],
        "image": {
            "width": config.image_width,
            "height": config.image_height
        },
        "tiles": {
            "rows": config.tiles_rows,
            "cols": config.tiles_cols
        },
        "workers": config.workers,
        "output": f"output/rendered_{uuid.uuid4().hex[:8]}.png",
        "renderer": renderer_cfg
    }
    return workflow


def run_render_job(job_id: str, workflow: dict, render_mode: str):
    """Execute render job in background thread."""
    try:
        jobs_db[job_id]["status"] = "running"
        jobs_db[job_id]["started_at"] = datetime.now().isoformat()
        pubsub.publish({"type": "job_updated", "job": jobs_db[job_id]})
        
        import sys
        sys.path.insert(0, str(BASE_DIR.parent / "server"))
        
        if render_mode == RenderMode.SCHEDULER:
            from managers.scheduler import Scheduler
            manager = Scheduler.__new__(Scheduler)
        else:
            from managers.coordinator import Coordinator
            manager = Coordinator.__new__(Coordinator)
        
        import json as json_mod
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_mod.dump(workflow, f)
            temp_workflow_path = f.name
        
        try:
            manager.workflow_path = temp_workflow_path
            manager.__load_workflow__() if hasattr(manager, '__load_workflow__') else None
            
            from managers.base_manager import BaseManager
            BaseManager.__init__(manager, temp_workflow_path)
            
            os.makedirs(JOBS_DIR / job_id / "tiles", exist_ok=True)
            
            actual_output = workflow["output"]
            output_dir = str(OUTPUT_DIR / job_id)
            workflow["output"] = f"{output_dir}/final.png"
            tiles_dir = f"{output_dir}/tiles"
            
            def handle_job_start(total_tiles):
                metrics_aggregator.record_job_start(workers=workflow.get("workers", 1), total_tiles=total_tiles)
                
            def handle_tile_complete(duration):
                metrics_aggregator.record_tile_complete(duration)
            
            result = manager.run_render(
                workers_override=workflow.get("workers"),
                rows_override=workflow.get("tiles", {}).get("rows"),
                cols_override=workflow.get("tiles", {}).get("cols"),
                verbose=False,
                on_job_start=handle_job_start,
                on_tile_complete=handle_tile_complete
            )
            
            metrics_aggregator.record_job_end(workers=workflow.get("workers", 1))
            
            jobs_db[job_id]["status"] = "completed"
            jobs_db[job_id]["completed_at"] = datetime.now().isoformat()
            jobs_db[job_id]["result"] = {
                "workers": result.get("workers"),
                "tiles": result.get("tiles"),
                "render_time_s": result.get("render_time_s"),
                "output_path": result["output"],
                "scheduler": result.get("scheduler", "coordinator"),
                "download_url": f"/api/download/{job_id}",
                "tiles_dir": tiles_dir,
            }
            jobs_db[job_id]["workflow"] = workflow
            pubsub.publish({"type": "job_updated", "job": jobs_db[job_id]})
            
        finally:
            os.unlink(temp_workflow_path)
            
    except Exception as e:
        import traceback
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)
        jobs_db[job_id]["traceback"] = traceback.format_exc()
        jobs_db[job_id]["failed_at"] = datetime.now().isoformat()
        metrics_aggregator.record_job_end(workers=workflow.get("workers", 1))
        pubsub.publish({"type": "job_updated", "job": jobs_db[job_id]})


@app.get("/")
async def root():
    return {"message": "Distributed Tile Renderer API", "version": "1.0.0"}


import subprocess

def get_gpu_info():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) == 4:
                        name, util, mem_used, mem_total = parts
                        gpus.append({
                            "name": name.strip(),
                            "utilization_percent": float(util.strip() or 0),
                            "memory_used_mb": float(mem_used.strip() or 0),
                            "memory_total_mb": float(mem_total.strip() or 0)
                        })
            return {"available": len(gpus) > 0, "gpus": gpus}
    except Exception:
        pass
    
    return {"available": False, "gpus": []}

@app.get("/api/health")
async def health_check():
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = time.time() - SERVER_START_TIME
    gpu_info = get_gpu_info()
    
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
            "free": memory.free
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        "gpu": gpu_info,
        "uptime_seconds": uptime
    }

@app.get("/api/benchmark")
async def get_benchmark():
    """
    Calculate and return Amdahl's Law benchmark stats based on past completed jobs.
    S(s) = 1 / ((1 - p) + (p / s))
    """
    completed_jobs = [j for j in jobs_db.values() if j["status"] == "completed" and j.get("result", {}).get("render_time_s")]
    
    # Group by workers
    worker_times = {}
    for job in completed_jobs:
        workers = job["result"]["workers"]
        duration = job["result"]["render_time_s"]
        if workers not in worker_times:
            worker_times[workers] = []
        worker_times[workers].append(duration)
        
    actual_data = []
    for w, times in worker_times.items():
        actual_data.append({"workers": w, "avg_time": sum(times) / len(times)})
    
    actual_data.sort(key=lambda x: x["workers"])
    
    # We estimate parallelizable portion `p`. For rendering, it's typically highly parallel.
    # Let's say 0.95 (95%)
    p_estimate = 0.95
    base_time = actual_data[0]["avg_time"] if actual_data else 100.0 # fallback base
    
    theoretical_data = []
    max_workers_to_plot = max([d["workers"] for d in actual_data]) if actual_data else 32
    max_workers_to_plot = max(max_workers_to_plot, 16) # Plot at least up to 16
    
    for s in range(1, max_workers_to_plot + 1):
        # Amdahl's law formula
        speedup = 1.0 / ((1.0 - p_estimate) + (p_estimate / s))
        theoretical_time = base_time / speedup
        theoretical_data.append({
            "workers": s,
            "theoretical_speedup": speedup,
            "theoretical_time": theoretical_time
        })
        
    return {
        "p_fraction": p_estimate,
        "base_time": base_time,
        "actual_data": actual_data,
        "theoretical_data": theoretical_data
    }


@app.get("/api/renderers")
async def get_available_renderers():
    """List available renderer types."""
    return {
        "renderers": [
            {
                "id": "synthetic",
                "name": "Synthetic (Tile-based)",
                "description": "Procedural gradient renderer - no external dependencies",
                "requires_scene_file": False,
                "options": []
            },
            {
                "id": "blender",
                "name": "Blender",
                "description": "Blender headless CLI renderer for real 3D scenes",
                "requires_scene_file": True,
                "options": [
                    {"id": "blender_scene_file", "name": "Scene File", "type": "file"},
                    {"id": "blender_engine", "name": "Render Engine", "type": "select", "options": ["CYCLES", "BLENDER_EEVEE_NEXT"]},
                    {"id": "blender_samples", "name": "Samples", "type": "number"},
                    {"id": "blender_device", "name": "Device", "type": "select", "options": ["CPU", "GPU"]}
                ]
            }
        ]
    }


@app.get("/api/workflow")
async def get_workflow():
    """Get current workflow configuration."""
    if WORKFLOW_PATH.exists():
        with open(WORKFLOW_PATH, "r") as f:
            return json.load(f)
    return {
        "pipeline": [
            {"operator": "frame_split"},
            {"operator": "render", "parallel": True},
            {"operator": "stitch"}
        ],
        "image": {"width": 1920, "height": 1080},
        "tiles": {"rows": 4, "cols": 4},
        "workers": 4,
        "output": "output/final.png",
        "renderer": {"type": "synthetic"}
    }


@app.get("/api/jobs", response_model=JobListResponse)
async def list_jobs():
    """List all render jobs."""
    jobs = []
    for job_id, job in jobs_db.items():
        jobs.append(JobResponse(**job))
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    return JobListResponse(jobs=jobs, total=len(jobs))


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get status of a specific render job."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**jobs_db[job_id])


@app.post("/api/jobs")
async def create_job(config: WorkflowConfig, background_tasks: BackgroundTasks):
    """Create and start a new render job."""
    job_id = uuid.uuid4().hex[:12]
    
    workflow = save_workflow_to_json(config)
    
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "workflow": workflow,
        "render_mode": config.render_mode,
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(run_render_job, job_id, workflow, config.render_mode)
    
    pubsub.publish({"type": "job_created", "job": jobs_db[job_id]})
    
    return JobResponse(**jobs_db[job_id])


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a render job and its output files."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_output_dir = OUTPUT_DIR / job_id
    if job_output_dir.exists():
        shutil.rmtree(job_output_dir)
    
    del jobs_db[job_id]
    pubsub.publish({"type": "job_deleted", "job_id": job_id})
    return {"message": "Job deleted", "job_id": job_id}


@app.get("/api/outputs/{job_id}")
async def get_job_outputs(job_id: str):
    """Get output files for a completed job."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    output_dir = OUTPUT_DIR / job_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")
    
    files = []
    for f in output_dir.rglob("*"):
        if f.is_file():
            rel_path = f.relative_to(output_dir)
            files.append({
                "name": str(rel_path),
                "path": str(f),
                "size": f.stat().st_size,
                "download_url": f"/api/files/{job_id}/{rel_path}"
            })
    
    return {"job_id": job_id, "files": files}


@app.get("/api/download/{job_id}")
async def download_final_image(job_id: str):
    """Download the final rendered image."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    output_path = Path(job["result"]["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    
    return FileResponse(
        path=output_path,
        filename=f"render_{job_id}.png",
        media_type="image/png"
    )


@app.get("/api/files/{job_id}/{filepath:path}")
async def download_file(job_id: str, filepath: str):
    """Download a specific file from job outputs."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    file_path = OUTPUT_DIR / job_id / filepath
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    media_type = "image/png" if file_path.suffix == ".png" else "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type
    )


@app.get("/api/tiles/{job_id}")
async def get_tiles_preview(job_id: str):
    """Get preview of rendered tiles as base64 thumbnails."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    tiles_dir = Path(job["result"]["tiles_dir"])
    if not tiles_dir.exists():
        raise HTTPException(status_code=404, detail="Tiles directory not found")
    
    tiles = []
    for tile_file in sorted(tiles_dir.glob("tile_*.png")):
        try:
            img = Image.open(tile_file)
            img.thumbnail((200, 200))
            import base64
            from io import BytesIO
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            tiles.append({
                "name": tile_file.name,
                "thumbnail": base64.b64encode(buffer.getvalue()).decode()
            })
        except Exception:
            continue
    
    return {"job_id": job_id, "tiles": tiles}


@app.get("/api/events")
async def get_events(request: Request):
    q = pubsub.subscribe()
    async def event_generator():
        try:
            while True:
                try:
                    message = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            pubsub.unsubscribe(q)
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/health")
async def websocket_health(websocket: WebSocket):
    await websocket.accept()
    q = asyncio.Queue()
    metrics_aggregator.subscribe(q)
    
    # Send initial snapshot immediately
    initial_snapshot = metrics_aggregator.get_snapshot()
    await websocket.send_json(initial_snapshot)
    
    # Also set up a periodic task to force updates if there are no events (e.g., system idle)
    # The aggregator doesn't trigger if nothing happens.
    async def ping_idle():
        while True:
            await asyncio.sleep(2.0)
            snapshot = metrics_aggregator.get_snapshot()
            try:
                await websocket.send_json(snapshot)
            except Exception:
                break

    ping_task = asyncio.create_task(ping_idle())

    try:
        while True:
            # Wait for events from the aggregator queue
            message_str = await q.get()
            await websocket.send_text(message_str)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        ping_task.cancel()
        metrics_aggregator.unsubscribe(q)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
