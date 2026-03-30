from pydantic import BaseModel, Field
from typing import Optional, Literal
from enums import RenderEngine
from enums import JobStatus
import uuid


class RenderJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # MinIO reference
    input_bucket: str = "renders"
    input_object: str  # path to .blend file

    # Frame range
    start_frame: int = 1
    end_frame: int = 1

    # Render settings
    engine: RenderEngine = RenderEngine.CYCLES
    resolution_x: int = 1920
    resolution_y: int = 1080
    samples: Optional[int] = 128

    # Output config
    output_format: str = "PNG"
    output_bucket: str = "renders"
    output_type: Literal["video", "single_frame"] = "video"

    # Metadata
    priority: int = 1
    status: JobStatus = JobStatus.PENDING
    created_at: float = Field(default_factory=lambda: 0.0)  # Will be set on creation
    ttl: int = 5
