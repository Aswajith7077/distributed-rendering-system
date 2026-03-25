from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse

from utils import is_blend_file
from utils import is_valid_blend
from service import minio_service
from service.task_splitter import split_and_dispatch_task

import os
import psutil
import time
import json

SERVER_START_TIME = time.time()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Distributed Tile Renderer API", version="1.0.0")


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
                "id": "synthetic",
                "name": "Synthetic (Tile-based)",
                "description": "Procedural gradient renderer - no external dependencies",
                "requires_scene_file": False,
                "options": [],
            },
            {
                "id": "blender",
                "name": "Blender",
                "description": "Blender headless CLI renderer for real 3D scenes",
                "requires_scene_file": True,
                "options": [
                    {"id": "blender_scene_file", "name": "Scene File", "type": "file"},
                    {
                        "id": "blender_engine",
                        "name": "Render Engine",
                        "type": "select",
                        "options": ["CYCLES", "BLENDER_EEVEE_NEXT"],
                    },
                    {"id": "blender_samples", "name": "Samples", "type": "number"},
                    {
                        "id": "blender_device",
                        "name": "Device",
                        "type": "select",
                        "options": ["CPU", "GPU"],
                    },
                ],
            },
        ]
    }


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

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    data = await file.read()
    
    import uuid
    job_id = str(uuid.uuid4())
    object_name = f"jobs/{job_id}/input/scene.blend"

    try:
        minio_service.upload_bytes(
            data=data,
            object_name=object_name,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e.args))

    # Trigger task splitter
    split_and_dispatch_task(job_id=job_id, filename=file.filename, config=config_data, object_name=object_name)

    return JSONResponse(
        content={
            "job_id": job_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "saved_to": file_path,
        }
    )
