import asyncio
import json
import socket
import os
from redis.asyncio import Redis


STREAM_NAME = "jobs_stream"
GROUP_NAME = "workers_group"


class RedisStreamWorker:
    def __init__(self, redis_url=None):
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"
        
        self.redis = Redis.from_url(redis_url, decode_responses=True,max_connections = 50)
        self.consumer_name = f"{socket.gethostname()}-{id(self)}"

    async def setup_group(self):
        retries = 10
        while retries > 0:
            try:
                # await self.redis.ping()
                print("[INIT] Connecting to Redis...")
                # Force a connection check before xgroup_create
                await self.redis.ping()
                print("[INIT] Redis reachable, creating consumer group...")
                await self.redis.xgroup_create(
                    name=STREAM_NAME, groupname=GROUP_NAME, id="0", mkstream=True
                )
                print("[INIT] Consumer group created")
                break
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    print("[INIT] Group already exists, continuing...")
                    break
                print(f"[INIT ERROR] {e}. Retrying... ({retries} left)")
                retries -= 1
                await asyncio.sleep(2)
        if retries == 0:
            raise Exception("Redis connection timeout")

    async def handle_job(self, job_id, data):
        print(f"[JOB] Processing {job_id} → {data}")
        await asyncio.sleep(2)

        # Master stores the full job under "payload" key
        raw = data.get("payload") or data.get("data") or "{}"
        job = json.loads(raw)  # {"job_id": ..., "type": ..., "payload": {...}}

        # The actual render params are nested inside
        render_payload = job.get("payload", job)
        print(f"[JOB] Render payload: {render_payload}")

        # TODO: call blender here with render_payload
        return {"status": "done", "result": render_payload}

    async def consume(self):
        print(f"[START] Consumer: {self.consumer_name}")

        try:
            print("[RECOVERY] Checking for pending messages...")
            response = await self.redis.xreadgroup(
                groupname=GROUP_NAME,
                consumername=self.consumer_name,
                streams={STREAM_NAME: "0"},
                count=10,
            )
            if response:
                for stream, messages in response:
                    for job_id, data in messages:
                        print(f"[RAW MESSAGE] {job_id} -> {data}")
                        try:
                            await self.handle_job(job_id, data)
                            await self.redis.xack(STREAM_NAME, GROUP_NAME, job_id)
                            print(f"[ACK] {job_id}")
                        except Exception as e:
                            print(f"[ERROR] {job_id}: {e}")
        except Exception as e:
            print(f"[RECOVERY ERROR] {e}")

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
                        print(f"[RAW MESSAGE] {job_id} -> {data}")
                        try:
                            result = await self.handle_job(job_id, data)

                            # ACK after success
                            await self.redis.xack(STREAM_NAME, GROUP_NAME, job_id)

                            print(f"[ACK] {job_id}")

                        except Exception as e:
                            print(f"[ERROR] {job_id}: {e}")
                            # Do NOT ack → stays pending for retry

            except Exception as e:
                print(f"[FATAL] {e}")
                await asyncio.sleep(2)

    async def ack_message(self, message_id):
        await self.redis.xack(STREAM_NAME, GROUP_NAME, message_id)

    async def close(self):
        await self.redis.close()


async def main():
    worker = RedisStreamWorker()
    await worker.setup_group()
    await worker.consume()


if __name__ == "__main__":
    asyncio.run(main())
