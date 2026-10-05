"""Celery background tasks for document processing and indexing."""
import uuid
import logging
from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.services.document_processing_service import DocumentProcessingService
from app.storage.minio_client import minio_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_document_task")
def process_document_task(self, document_id: str, version_id: str, user_id: str = None):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        version = db.query(DocumentVersion).filter(DocumentVersion.id == uuid.UUID(version_id)).first()
        if not version:
            raise ValueError(f"DocumentVersion {version_id} not found")

        file_bytes = minio_service.download_file(version.storage_path)
        service = DocumentProcessingService(db)
        result = service.process_document(version, file_bytes, doc.filename, user_id=user_id)

        doc.status = "processed"
        db.commit()
        return result
    except Exception as e:
        logger.error(f"Async document processing error: {e}")
        if 'doc' in locals() and doc:
            doc.status = "failed"
            db.commit()
        raise e
    finally:
        db.close()
