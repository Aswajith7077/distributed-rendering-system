import json
from typing import Any
from config import ConfigService
import redis.asyncio as aioredis


async def _persist_to_redis(
    config_service: ConfigService,
    redis: aioredis.Redis,
    log,
    node_id: str,
    metrics: dict[str, Any],
) -> None:
    """Write the slave snapshot to Redis with a TTL."""
    if redis is None:
        return
    try:
        key = f"health:node:{node_id}"
        await redis.set(key, json.dumps(metrics), ex=config_service.SLAVE_TTL)
        await redis.sadd("health:active_nodes", node_id)
    except Exception as exc:
        log.warning("Redis write failed for %s: %s", node_id, exc)


async def _load_from_redis(redis, slave_registry, log) -> None:
    """
    On startup, hydrate the in-memory registry from Redis so the first
    broadcast includes any nodes that were reporting before a gateway restart.
    """
    if redis is None:
        return
    try:
        node_ids: set[str] = await redis.smembers("health:active_nodes")
        for node_id in node_ids:
            raw = await redis.get(f"health:node:{node_id}")
            if raw:
                slave_registry[node_id] = json.loads(raw)
        log.info("Hydrated %d node(s) from Redis on startup.", len(slave_registry))
    except Exception as exc:
        log.warning("Could not hydrate from Redis: %s", exc)
