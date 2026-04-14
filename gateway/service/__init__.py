import os
from .minio import MinioService
from .redis import RedisService

minio_service = MinioService(
    endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "password123"),
)

redis_host = os.environ.get("REDIS_HOST", "redis")
redis_service = RedisService(redis_url=f"redis://{redis_host}:6379")


__all__ = ["minio_service", "redis_service"]
