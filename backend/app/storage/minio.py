"""Backward compatible MinIOStorage wrapper."""
from app.storage.minio_client import MinIOService, minio_service

MinIOStorage = MinIOService
__all__ = ["MinIOStorage", "MinIOService", "minio_service"]