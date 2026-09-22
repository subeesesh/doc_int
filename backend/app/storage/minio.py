from io import BytesIO

from minio import Minio

from app.config.settings import settings


class MinIOStorage:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        self.bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str,
    ) -> str:
        self.ensure_bucket()

        self.client.put_object(
            self.bucket,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

        return object_name

    def download_bytes(self, object_name: str) -> bytes:
        response = self.client.get_object(
            self.bucket,
            object_name,
        )

        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, object_name: str) -> None:
        self.client.remove_object(
            self.bucket,
            object_name,
        )