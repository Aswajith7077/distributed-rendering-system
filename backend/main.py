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

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

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
            
            result = manager.run_render(
                workers_override=workflow.get("workers"),
                rows_override=workflow.get("tiles", {}).get("rows"),
                cols_override=workflow.get("tiles", {}).get("cols"),
                verbose=False,
            )
            
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
            
        finally:
            os.unlink(temp_workflow_path)
            
    except Exception as e:
        import traceback
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)
        jobs_db[job_id]["traceback"] = traceback.format_exc()
        jobs_db[job_id]["failed_at"] = datetime.now().isoformat()


@app.get("/")
async def root():
    return {"message": "Distributed Tile Renderer API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
