"""MinIO object storage client service."""
import io
import logging
from minio import Minio
from app.config.settings import settings

logger = logging.getLogger(__name__)


class MinIOService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
        except Exception as e:
            logger.warning(f"MinIO bucket check failed: {e}")

    def ensure_bucket(self):
        self._ensure_bucket()

    def upload_file(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )
        return object_name

    def upload_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return self.upload_file(object_name, data, content_type)

    def download_file(self, object_name: str) -> bytes:
        response = self.client.get_object(self.bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def download_bytes(self, object_name: str) -> bytes:
        return self.download_file(object_name)

    def delete_file(self, object_name: str):
        self.client.remove_object(self.bucket, object_name)

    def delete(self, object_name: str):
        self.delete_file(object_name)


minio_service = MinIOService()
