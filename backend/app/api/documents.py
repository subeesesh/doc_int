"""Document management endpoints."""
import uuid
import hashlib
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.document import Document, DocumentVersion, DocumentPermission
from app.models.processing import Page, ProcessingJob
from app.models.knowledge import Chunk
from app.storage.minio_client import minio_service
from app.auth.dependencies import get_current_user, get_optional_user, get_accessible_document_ids
from app.models.user import User
from app.config.settings import settings
from app.schemas.api import DocumentResponse, DocumentListResponse, ProcessingStatusResponse

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = settings.allowed_extensions_list
MAX_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")

    # Safe filename
    safe_name = Path(file.filename).name

    doc_hash = hashlib.sha256(content).hexdigest()
    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()
    storage_path = f"documents/{doc_id}/{version_id}/{safe_name}"

    # Create document
    user_id = user.id if user else uuid.uuid4()
    doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=safe_name,
        storage_path=storage_path,
        document_hash=doc_hash,
        status="uploaded",
    )
    db.add(doc)

    version = DocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=1,
        storage_path=storage_path,
        document_hash=doc_hash,
        status="uploaded",
    )
    db.add(version)

    # Upload to MinIO
    minio_service.upload_file(storage_path, content, file.content_type or "application/octet-stream")

    db.commit()
    logger.info(f"Uploaded document {doc_id}: {safe_name}")

    return DocumentResponse(
        id=str(doc_id),
        filename=safe_name,
        status="uploaded",
        created_at=doc.created_at,
        user_id=str(user_id),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    query = db.query(Document)
    if user:
        accessible = get_accessible_document_ids(user, db)
        if accessible is not None:
            query = query.filter(Document.id.in_([uuid.UUID(d) for d in accessible]))

    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=str(d.id),
                filename=d.filename,
                status=d.status,
                created_at=d.created_at,
                user_id=str(d.user_id),
            )
            for d in docs
        ],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        status=doc.status,
        created_at=doc.created_at,
        user_id=str(doc.user_id),
    )


@router.post("/{document_id}/process", response_model=ProcessingStatusResponse)
async def process_document(document_id: str, db: Session = Depends(get_db)):
    """Trigger document processing pipeline."""
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="No version found")

    # Run processing synchronously for now
    try:
        file_bytes = minio_service.download_file(version.storage_path)
        from app.services.document_processing_service import DocumentProcessingService

        service = DocumentProcessingService(db)
        result = service.process_document(version, file_bytes, doc.filename, user_id=str(doc.user_id))

        doc.status = "processed"
        db.commit()

        return ProcessingStatusResponse(
            document_id=str(doc.id),
            version_id=str(version.id),
            status="processed",
        )
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        doc.status = "failed"
        db.commit()
        return ProcessingStatusResponse(
            document_id=str(doc.id),
            version_id=str(version.id),
            status="failed",
            error_message=str(e),
        )


@router.get("/{document_id}/pages")
async def get_document_pages(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    if not version:
        return {"pages": [], "total": 0}

    pages = (
        db.query(Page)
        .filter(Page.document_version_id == version.id)
        .order_by(Page.page_number)
        .all()
    )
    return {
        "pages": [
            {
                "id": str(p.id),
                "page_number": p.page_number,
                "text": p.text,
                "extraction_type": p.extraction_type,
            }
            for p in pages
        ],
        "total": len(pages),
    }


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    if not version:
        return {"chunks": [], "total": 0}

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version.id)
        .order_by(Chunk.chunk_index)
        .all()
    )
    return {
        "chunks": [
            {
                "id": str(c.id),
                "chunk_index": c.chunk_index,
                "text": c.text,
                "token_count": c.token_count,
                "page_id": str(c.page_id),
            }
            for c in chunks
        ],
        "total": len(chunks),
    }


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )

    job = None
    if version:
        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.document_version_id == version.id)
            .order_by(ProcessingJob.started_at.desc())
            .first()
        )

    return ProcessingStatusResponse(
        document_id=str(doc.id),
        version_id=str(version.id) if version else "",
        status=doc.status,
        job_type=job.job_type if job else None,
        error_message=job.error_message if job else None,
        started_at=job.started_at if job else None,
        completed_at=job.completed_at if job else None,
    )
