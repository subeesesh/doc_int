"""Centralized application configuration using pydantic-settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "enterprise_intelligence"
    POSTGRES_USER: str = "enterprise_user"
    POSTGRES_PASSWORD: str = "enterprise_password"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6335
    QDRANT_COLLECTION: str = "document_chunks"

    # Elasticsearch
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    ELASTICSEARCH_INDEX: str = "document_chunks"
    ELASTICSEARCH_PASSWORD: str = ""

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "enterprise_neo4j_password"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "redispassword"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadminpassword"
    MINIO_BUCKET: str = "enterprise-documents"
    MINIO_SECURE: bool = False

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # LLM
    LLM_PROVIDER: str = "local"
    LLM_MODEL: str = "qwen3:1.7b"
    OLLAMA_URL: str = "http://localhost:11434"

    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # Auth
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # File upload
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: str = ".pdf,.docx,.doc,.txt,.xlsx,.xls,.pptx,.png,.jpg,.jpeg,.tiff"

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()