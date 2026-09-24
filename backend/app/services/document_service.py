import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentVersion
from app.storage.minio import MinIOStorage


class DocumentService:
    def __init__(self, storage: MinIOStorage | None = None) -> None:
        self.storage = storage or MinIOStorage()

    @staticmethod
    def calculate_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def create_document(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> Document:
        document_hash = self.calculate_hash(data)

        document = Document(
            id=uuid.uuid4(),
            user_id=user_id,
            filename=filename,
            storage_path="",
            document_hash=document_hash,
            status="uploaded",
        )

        db.add(document)
        db.flush()

        object_name = (
            f"documents/{document.id}/"
            f"versions/1/original/{filename}"
        )

        self.storage.upload_bytes(
            object_name=object_name,
            data=data,
            content_type=content_type,
        )

        document.storage_path = object_name

        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=document.id,
            version_number=1,
            storage_path=object_name,
            document_hash=document_hash,
            status="uploaded",
        )

        db.add(version)
        db.commit()
        db.refresh(document)

        return document