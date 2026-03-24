from redis import Redis
import json
import uuid
import time
import os

class RedisService:

    def __init__(self, redis_url=None):
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"
        
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    def add_job(self, payload: dict, job_type="generic", priority=1):
        job_id = str(uuid.uuid4())

        job = {
            "job_id": job_id,
            "type": job_type,
            "priority": priority,
            "created_at": time.time(),
            "payload": payload
        }

        stream_id = self.redis.xadd(
            "jobs_stream",
            {
                "job_id": job_id,
                "payload": json.dumps(job)
            }
        )

        return {
            "stream_id": stream_id,
            "job_id": job_id
        }