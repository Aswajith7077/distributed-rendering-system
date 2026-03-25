import asyncio
import json
import socket
import os
from redis.asyncio import Redis
import redis.exceptions
import logging
from dotenv import load_dotenv

from models import Acknowledgement

load_dotenv()
log = logging.getLogger(__name__)


STREAM_NAME = "jobs_stream"
STREAM_RESPONSE_NAME = "jobs_stream_ack"
GROUP_NAME = "workers_group"


class RedisStreamWorker:
    def __init__(self, redis_url=None):
        if redis_url is None:
            load_dotenv()
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        self.redis_url = redis_url
        self.redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            max_connections=10,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30,
        )
        self.consumer_name = f"{socket.gethostname()}-{id(self)}"

    async def setup_group(self):
        retries = 15
        while retries > 0:
            try:
                log.info("[INIT] Connecting to Redis...")
                # Force a connection check before xgroup_create
                await self.redis.ping()
                log.info("[INIT] Redis reachable, creating consumer group...")
                await self.redis.xgroup_create(
                    name=STREAM_NAME, groupname=GROUP_NAME, id="0", mkstream=True
                )
                log.info("[INIT] Consumer group created")
                break
            except redis.exceptions.ConnectionError as e:
                log.error(f"[INIT CONNECTION ERROR] {e}. Retrying... ({retries} left)")
                retries -= 1
                await asyncio.sleep(3)
                # Try to reconnect
                try:
                    await self.redis.close()
                    self.redis = Redis.from_url(
                        self.redis_url,
                        decode_responses=True,
                        max_connections=10,
                        socket_keepalive=True,
                        socket_keepalive_options={},
                        health_check_interval=30,
                    )
                except Exception as e:
                    log.error(f"[RECONNECT FAILED] {e}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    log.info("[INIT] Group already exists, continuing...")
                    break
                log.info(f"[INIT ERROR] {e}. Retrying... ({retries} left)")
                retries -= 1
                await asyncio.sleep(2)
        if retries == 0:
            raise Exception("Redis connection timeout after multiple retries")

    async def handle_job(self, job_id, data):
        log.info(f"[JOB] Processing {job_id} → {data}")
        await asyncio.sleep(2)

        # Master stores the full job under "payload" key
        raw = data.get("payload") or data.get("data") or "{}"
        job = json.loads(raw)  # {"job_id": ..., "type": ..., "payload": {...}}

        # The actual render params are nested inside
        render_payload = job.get("payload", job)
        log.info(f"[JOB] Render payload: {render_payload}")

        # Import here to avoid circular imports
        from renderers.blender import BlenderRenderer
        from service import minio_service

        renderer = BlenderRenderer(minio_service)
        result = renderer.process_job(render_payload)
        log.info(f"[JOB] Result: {result}")

        return result

    async def consume(self):
        log.info(f"[START] Consumer: {self.consumer_name}")

        try:
            log.info("[RECOVERY] Checking for pending messages...")
            response = await self.redis.xreadgroup(
                groupname=GROUP_NAME,
                consumername=self.consumer_name,
                streams={STREAM_NAME: "0"},
                count=10,
            )
            if response:
                for stream, messages in response:
                    for job_id, data in messages:
                        log.info(f"[RAW MESSAGE] {job_id} -> {data}")
                        try:
                            result = await self.handle_job(job_id, data)
                            await self.send_response(result)
                            await self.redis.xack(STREAM_NAME, GROUP_NAME, job_id)
                            log.info(f"[ACK] {job_id}")
                        except Exception as e:
                            log.error(f"[ERROR] {job_id}: {e}")
        except Exception as e:
            log.error(f"[RECOVERY ERROR] {e}")

        while True:
            try:
                response = await self.redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self.consumer_name,
                    streams={STREAM_NAME: ">"},
                    count=1,
                    block=5000,  # 5 sec blocking
                )

                if not response:
                    continue

                for stream, messages in response:
                    for job_id, data in messages:
                        log.info(f"[RAW MESSAGE] {job_id} -> {data}")
                        try:
                            result = await self.handle_job(job_id, data)

                            await self.send_response(result)
                            await self.redis.xack(STREAM_NAME, GROUP_NAME, job_id)

                            log.info(f"[ACK] {job_id}")

                        except Exception as e:
                            log.error(f"[ERROR] {job_id}: {e}")
                            # Do NOT ack → stays pending for retry

            except (ConnectionError, redis.exceptions.ConnectionError) as e:
                log.error(f"[CONNECTION ERROR] {e}. Reconnecting...")
                await asyncio.sleep(5)
                try:
                    await self.redis.close()
                    self.redis = Redis.from_url(
                        self.redis_url,
                        decode_responses=True,
                        max_connections=10,
                        socket_keepalive=True,
                        socket_keepalive_options={},
                        health_check_interval=30,
                    )
                    await self.redis.ping()
                    log.info("[RECONNECT] Successfully reconnected to Redis")
                except Exception as reconnect_error:
                    log.error(f"[RECONNECT FAILED] {reconnect_error}")
                    await asyncio.sleep(10)
            except Exception as e:
                log.error(f"[FATAL] {e}")
                await asyncio.sleep(2)

    async def ack_message(self, message_id):
        await self.redis.xack(STREAM_NAME, GROUP_NAME, message_id)

    async def close(self):
        await self.redis.close()

    async def send_response(self, result: Acknowledgement):
        job = {
            "job_id": result.job_id,
            "status": result.status,
            "error": result.error or "",
        }

        stream_id = await self.redis.xadd(STREAM_RESPONSE_NAME, job)

        return {"stream_id": stream_id, "job_id": result.job_id}
