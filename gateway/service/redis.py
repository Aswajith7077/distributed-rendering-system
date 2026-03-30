from redis.asyncio import Redis
import json

import time
import os
from typing import List, Optional


class RedisService:
    def __init__(self, redis_url=None):
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def initialize_job(self, job_id: str, config: dict, total_frames: int):
        """Initializes the parent job metadata."""
        job_data = {
            "job_id": job_id,
            "status": "running",
            "created_at": time.time(),
            "workflow": config,
            "total_frames": total_frames,
            "completed_frames": 0,
            "output_type": config.get("output_type", "video"),
        }

        await self.redis.hset(
            f"job_meta:{job_id}",
            mapping={
                "job_id": job_id,
                "data": json.dumps(job_data),
                "status": "running",
            },
        )

        # Add to all_jobs list if not already there
        # We use a set for "all_jobs_set" to check existence, or just lrem then lpush
        await self.redis.lrem("all_jobs", 0, job_id)
        await self.redis.lpush("all_jobs", job_id)

        # Also set the dedicated counters for atomic operations
        await self.redis.set(f"job:{job_id}:total_frames", total_frames)
        await self.redis.set(f"job:{job_id}:completed_frames", 0)

        # Notify frontend
        await self.redis.publish(
            "job_updates", json.dumps({"type": "job_created", "job": job_data})
        )

        return job_data

    async def add_task(self, job_id: str, task_data: dict):
        """Dispatches an individual frame task to the stream."""
        # We don't update job_meta here, the listener will do it as tasks complete
        stream_id = await self.redis.xadd(
            "jobs_stream", {"job_id": job_id, "payload": json.dumps(task_data)}
        )
        return stream_id

    async def get_job(self, job_id: str) -> Optional[dict]:
        data = await self.redis.hget(f"job_meta:{job_id}", "data")
        if data:
            return json.loads(data)
        return None

    async def list_jobs(self, limit: int = 50) -> List[dict]:
        job_ids = await self.redis.lrange("all_jobs", 0, limit - 1)
        jobs = []
        for jid in job_ids:
            job_data = await self.get_job(jid)
            if job_data:
                jobs.append(job_data)
        return jobs

    async def update_job_status(
        self, job_id: str, status: str, error: Optional[str] = None
    ):
        job_data = await self.get_job(job_id)
        if job_data:
            job_data["status"] = status
            if status == "completed":
                job_data["completed_at"] = time.time()
            if error:
                job_data["error"] = error

            await self.redis.hset(
                f"job_meta:{job_id}",
                mapping={"data": json.dumps(job_data), "status": status},
            )

            # Publish update for SSE
            await self.redis.publish(
                "job_updates", json.dumps({"type": "job_updated", "job": job_data})
            )

    async def update_job_progress(self, job_id: str, completed_frames: int):
        """Updates the progress count in the job metadata."""
        job_data = await self.get_job(job_id)
        if job_data:
            job_data["completed_frames"] = completed_frames

            await self.redis.hset(
                f"job_meta:{job_id}", mapping={"data": json.dumps(job_data)}
            )

            # Publish update for SSE
            await self.redis.publish(
                "job_updates", json.dumps({"type": "job_updated", "job": job_data})
            )

    async def delete_job(self, job_id: str):
        await self.redis.delete(f"job_meta:{job_id}")
        await self.redis.lrem("all_jobs", 0, job_id)
        # Also clean up progress counters
        await self.redis.delete(f"job:{job_id}:completed_frames")
        await self.redis.delete(f"job:{job_id}:total_frames")

        await self.redis.publish(
            "job_updates", json.dumps({"type": "job_deleted", "job_id": job_id})
        )
