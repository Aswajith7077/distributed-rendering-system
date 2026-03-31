import asyncio
import json
import os
import psutil
import socket
import time
import logging
from redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


class MetricsService:
    def __init__(self, node_type="slave", redis_url=None):
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.node_id = f"{node_type}:{socket.gethostname()}"
        self.node_type = node_type
        self.start_time = time.time()

    async def get_metrics(self):
        """Collects system metrics using psutil."""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()

            # Basic GPU check (can be improved with GPUtil if available)
            gpu_info = "N/A"

            metrics = {
                "node_id": self.node_id,
                "type": self.node_type,
                "status": "online",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "gpu_info": gpu_info,
                "uptime_seconds": int(time.time() - self.start_time),
                "timestamp": time.time(),
            }
            return metrics
        except Exception as e:
            log.error(f"Error collecting metrics: {e}")
            return None

    async def report_loop(self, interval=5):
        """Periodically reports metrics to Redis."""
        log.info(f"Starting metrics reporting loop for {self.node_id}")
        while True:
            metrics = await self.get_metrics()
            if metrics:
                try:
                    # Store as a JSON string in a key with 15s TTL
                    key = f"health:node:{self.node_id}"
                    await self.redis.set(key, json.dumps(metrics), ex=15)
                    # Also add to a set of active nodes for easy discovery
                    await self.redis.sadd("health:active_nodes", self.node_id)
                except Exception as e:
                    log.error(f"Error reporting metrics to Redis: {e}")

            await asyncio.sleep(interval)

    async def close(self):
        await self.redis.close()
