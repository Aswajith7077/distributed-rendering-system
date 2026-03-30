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


class MetricsAggregator:
    def __init__(self, redis_url=None):
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.master_id = f"master:{socket.gethostname()}"
        self.start_time = time.time()

    async def get_master_metrics(self):
        """Collects metrics for the master node."""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            return {
                "node_id": self.master_id,
                "type": "master",
                "status": "online",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "uptime_seconds": int(time.time() - self.start_time),
                "timestamp": time.time(),
            }
        except Exception as e:
            log.error(f"Error collecting master metrics: {e}")
            return None

    async def get_all_node_metrics(self):
        """Aggregates metrics from master and all active slaves in Redis."""
        nodes = []

        # 1. Master
        master_stats = await self.get_master_metrics()
        if master_stats:
            nodes.append(master_stats)

        # 2. Slaves from Redis
        try:
            # We look for all keys matching our pattern
            keys = await self.redis.keys("health:node:slave:*")
            if keys:
                node_json_list = await self.redis.mget(keys)
                for node_json in node_json_list:
                    if node_json:
                        nodes.append(json.loads(node_json))
        except Exception as e:
            log.error(f"Error fetching slave metrics from Redis: {e}")

        return nodes

    async def close(self):
        await self.redis.close()
