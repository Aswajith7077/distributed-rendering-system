from pydantic import BaseModel
from typing import Optional


class Acknowledgement(BaseModel):
    status: str
    job_id: str
    error: Optional[str] = None
