from .minio import MinioService
from dotenv import load_dotenv
import os

load_dotenv()

minio_service = MinioService(
    endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.environ.get("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.environ.get("MINIO_SECRET_KEY", "password123"),
)

from .redis import RedisStreamWorker


__all__ = ["RedisStreamWorker", "minio_service"]
