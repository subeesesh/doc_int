import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services.document_service import DocumentService


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post("/upload")
async def upload_document(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    service = DocumentService()

    document = service.create_document(
        db,
        user_id=user_id,
        filename=file.filename,
        data=data,
        content_type=file.content_type or "application/octet-stream",
    )

    return {
        "id": str(document.id),
        "filename": document.filename,
        "document_hash": document.document_hash,
        "storage_path": document.storage_path,
        "status": document.status,
    }