from pydantic import BaseModel, Field
from typing import Optional
from enums import RenderEngine
from enums import JobStatus
import uuid



class RenderJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # MinIO reference
    input_bucket: str
    input_object: str   # path to .blend file

    # Frame range
    start_frame: int
    end_frame: int

    # Render settings
    engine: RenderEngine = RenderEngine.CYCLES
    resolution_x: int = 1920
    resolution_y: int = 1080
    samples: Optional[int] = 128  # useful for cycles

    # Output config
    output_format: str = "PNG"
    output_bucket: str

    # Metadata
    priority: int = 1
    status: JobStatus = JobStatus.PENDING