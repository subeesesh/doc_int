"""Celery application configuration."""
from celery import Celery
from app.config.settings import settings

celery_app = Celery(
    "edi_worker",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max for big docs
)
