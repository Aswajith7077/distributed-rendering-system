from minio import Minio
from minio.error import S3Error
import io


class MinioService:
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "admin",
        secret_key: str = "password123",
        bucket_name: str = "blender-files",
        secure: bool = False
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file(self, file_obj, object_name: str, content_type: str = "application/octet-stream"):
        """
        Upload file-like object (UploadFile.file or BytesIO)
        """
        try:
            file_obj.seek(0, 2)  # Move to end
            file_size = file_obj.tell()
            file_obj.seek(0)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_obj,
                length=file_size,
                content_type=content_type
            )

            return {
                "bucket": self.bucket_name,
                "object_name": object_name
            }

        except S3Error as e:
            raise Exception(f"MinIO upload failed: {str(e)}")

    def upload_bytes(self, data: bytes, object_name: str, content_type: str = "application/octet-stream"):
        """
        Upload raw bytes
        """
        try:
            byte_stream = io.BytesIO(data)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=byte_stream,
                length=len(data),
                content_type=content_type
            )

            return {
                "bucket": self.bucket_name,
                "object_name": object_name
            }

        except S3Error as e:
            raise Exception(f"MinIO upload failed: {str(e)}")

    def get_file_url(self, object_name: str):
        """
        Generate a presigned URL (temporary access)
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name
            )
            return url
        except S3Error as e:
            raise Exception(f"Failed to generate URL: {str(e)}")