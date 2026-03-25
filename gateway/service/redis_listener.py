import asyncio
import json
import socket
import os
from redis.asyncio import Redis
import redis.exceptions
import logging
import subprocess
import shutil
from service import minio_service
from dotenv import load_dotenv


log = logging.getLogger(__name__)

STREAM_RESPONSE_NAME = "jobs_stream_ack"
GROUP_NAME = "workers_group"

class RedisStatusStreamListener:
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
    
    async def compile_video(self, job_id: str):
        log.info(f"[{job_id}] All frames completed! Starting video compilation...")
        local_dir = f"/tmp/{job_id}_frames"
        final_video = f"/tmp/{job_id}_final.mp4"
        os.makedirs(local_dir, exist_ok=True)
        
        try:
            # 1. Download all frames
            prefix = f"jobs/{job_id}/output/"
            objects = minio_service.list_objects(prefix=prefix, recursive=True)
            files_downloaded = 0
            
            for obj in objects:
                # obj.object_name is like 'jobs/123/output/frame_0001.png'
                filename = os.path.basename(obj.object_name)
                local_path = os.path.join(local_dir, filename)
                minio_service.download(obj.object_name, local_path)
                files_downloaded += 1
            
            log.info(f"[{job_id}] Downloaded {files_downloaded} frames for compilation.")
                
            # 2. Run ffmpeg
            if not shutil.which("ffmpeg"):
                error_msg = "FFmpeg executable not found. Please install FFmpeg and add it to your system PATH."
                log.error(f"[{job_id}] {error_msg}")
                raise RuntimeError(error_msg)

            # Blender outputs frame_0001.png, frame_0002.png...
            # We use the sequence pattern which is more cross-platform than globbing
            cmd = [
                "ffmpeg", "-y",
                "-framerate", "24",
                "-i", os.path.join(local_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                final_video
            ]
            
            log.info(f"[{job_id}] Running ffmpeg compilation...")
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if process.returncode != 0:
                log.error(f"[{job_id}] ffmpeg failed with return code {process.returncode}")
                log.error(f"[{job_id}] STDOUT: {process.stdout}")
                log.error(f"[{job_id}] STDERR: {process.stderr}")
                raise RuntimeError(f"FFmpeg compilation failed for {job_id}")

            log.info(f"[{job_id}] ffmpeg compilation successful.")
            
            # 3. Upload final result
            object_name = f"jobs/{job_id}/final_result.mp4"
            with open(final_video, "rb") as f:
                minio_service.upload_file(file_obj=f, object_name=object_name, content_type="video/mp4")
            
            log.info(f"[{job_id}] Uploaded final result to MinIO at {object_name}.")
            
            # Clean up redis completion keys
            await self.redis.delete(f"job:{job_id}:completed_frames")
            await self.redis.delete(f"job:{job_id}:total_frames")
            
        except Exception as e:
            log.error(f"[{job_id}] Error compiling video: {e}")
            raise
        finally:
            if os.path.exists(local_dir):
                shutil.rmtree(local_dir)
            if os.path.exists(final_video):
                os.remove(final_video)

    async def handle_job(self, message_id, data):
        job_id = data.get("job_id")
        status = data.get("status")
        
        if not job_id:
            log.error(f"Missing job_id in ack message {message_id}: {data}")
            return
            
        log.info(f"Start compiling the video for job {job_id}")
        if status == "done":
            # Increment completed frames
            completed = await self.redis.incr(f"job:{job_id}:completed_frames")
            total_frames_str = await self.redis.get(f"job:{job_id}:total_frames")
            
            if total_frames_str:
                total_frames = int(total_frames_str)
                log.info(f"[{job_id}] Progress: {completed}/{total_frames} frames completed.")
                if completed >= total_frames:
                    await self.compile_video(job_id)
            else:
                log.warning(f"[{job_id}] Received done ack but total_frames not found. Assuming singular task.")
                # We don't compile if we don't know total_frames, or we could force it?
        else:
            log.error(f"[{job_id}] Received failed status from worker: {data.get('error')}")
            # Could increment a failed frames counter, etc.
        log.info(f"Completed compiling the video for job {job_id}")
    
    async def setup_group(self):
        retries = 15
        while retries > 0:
            try:
                log.info("[INIT] Connecting to Redis...")
                # Force a connection check before xgroup_create
                await self.redis.ping()
                log.info("[INIT] Redis reachable, creating consumer group...")
                await self.redis.xgroup_create(
                    name=STREAM_RESPONSE_NAME, groupname=GROUP_NAME, id="0", mkstream=True
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

    
    async def consume(self):
        log.info(f"[START] Consumer: {self.consumer_name}")

        try:
            log.info("[RECOVERY] Checking for pending messages...")
            response = await self.redis.xreadgroup(
                groupname=GROUP_NAME,
                consumername=self.consumer_name,
                streams={STREAM_RESPONSE_NAME: "0"},
                count=10,
            )
            if response:
                for stream, messages in response:
                    for message_id, data in messages:
                        log.info(f"[RAW MESSAGE] {message_id} -> {data}")
                        try:
                            await self.handle_job(message_id, data)
                            await self.redis.xack(STREAM_RESPONSE_NAME, GROUP_NAME, message_id)
                            log.info(f"[ACK] {message_id}")
                        except Exception as e:
                            log.error(f"[ERROR] {message_id}: {e}")
        except Exception as e:
            log.error(f"[RECOVERY ERROR] {e}")

        while True:
            try:
                response = await self.redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self.consumer_name,
                    streams={STREAM_RESPONSE_NAME: ">"},
                    count=1,
                    block=5000,  # 5 sec blocking
                )

                if not response:
                    continue

                for stream, messages in response:
                    for message_id, data in messages:
                        log.info(f"[RAW MESSAGE] {message_id} -> {data}")
                        try:
                            await self.handle_job(message_id, data)
                            await self.redis.xack(STREAM_RESPONSE_NAME, GROUP_NAME, message_id)

                            log.info(f"[ACK] {message_id}")

                        except Exception as e:
                            log.error(f"[ERROR] {message_id}: {e}")
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