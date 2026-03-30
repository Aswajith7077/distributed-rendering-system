from enum import Enum


class RenderEngine(str, Enum):
    CYCLES = "CYCLES"
    EEVEE = "BLENDER_EEVEE_NEXT"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
