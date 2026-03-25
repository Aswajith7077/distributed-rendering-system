from minio import Minio
from minio.error import S3Error
import io
import logging

log = logging.getLogger(__name__)


class MinioService:
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "admin",
        secret_key: str = "password123",
        bucket_name: str = "blender-files",
        secure: bool = False,
    ):
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket_name = bucket_name

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            log.info(f"Created MinIO bucket: {self.bucket_name}")

    def download(self, object_name: str, file_path: str):
        self.client.fget_object(self.bucket_name, object_name, file_path)
        log.info(f"Downloaded file from MinIO: {object_name} to {file_path}")

    def upload_file(
        self, file_obj, object_name: str, content_type: str = "application/octet-stream"
    ):
        """
        Upload file-like object (UploadFile.file or BytesIO)
        """
        try:
            file_obj.seek(0, 2)  # Move to end
            file_size = file_obj.tell()
            file_obj.seek(0)

            log.info(f"Uploading file to MinIO: {object_name}")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_obj,
                length=file_size,
                content_type=content_type,
            )
            log.info(f"Successfully uploaded file to MinIO: {object_name}")

            return {"bucket": self.bucket_name, "object_name": object_name}

        except S3Error as e:
            log.error(f"MinIO upload failed: {str(e)}")
            raise Exception(f"MinIO upload failed: {str(e)}")

    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ):
        """
        Upload raw bytes
        """
        try:
            byte_stream = io.BytesIO(data)

            log.info(f"Uploading bytes to MinIO: {object_name}")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=byte_stream,
                length=len(data),
                content_type=content_type,
            )
            log.info(f"Successfully uploaded bytes to MinIO: {object_name}")

            return {"bucket": self.bucket_name, "object_name": object_name}

        except S3Error as e:
            log.error(f"MinIO upload failed: {str(e)}")
            raise Exception(f"MinIO upload failed: {str(e)}")

    def get_file_url(self, object_name: str):
        """
        Generate a presigned URL (temporary access)
        """
        try:
            log.info(f"Generating presigned URL for object: {object_name}")
            url = self.client.presigned_get_object(self.bucket_name, object_name)
            log.info(f"Generated presigned URL: {url}")
            return url
        except S3Error as e:
            log.error(f"Failed to generate URL: {str(e)}")
            raise Exception(f"Failed to generate URL: {str(e)}")
