from .redis import RedisStreamWorker
from .minio import MinioService
import os

minio_service = MinioService(
    endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "password123"),
)


__all__ = ["RedisStreamWorker", "minio_service"]
