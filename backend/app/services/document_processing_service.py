from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.document_processor import DocumentProcessor
from app.storage.minio import MinIOStorage


class DocumentProcessingService:

    def __init__(
        self,
        storage: MinIOStorage | None = None,
        processor: DocumentProcessor | None = None,
    ):
        self.storage = storage or MinIOStorage()
        self.processor = processor or DocumentProcessor()

    def process_document(
        self,
        db: Session,
        document_id: UUID,
    ):
        # 1. Find document metadata in PostgreSQL
        document = (
            db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

        if document is None:
            raise ValueError(
                f"Document {document_id} not found"
            )

        if not document.storage_path:
            raise ValueError(
                f"Document {document_id} has no storage path"
            )

        # 2. Download original document from MinIO
        data = self.storage.download_bytes(
            document.storage_path
        )

        suffix = Path(document.filename).suffix or ".bin"

        temp_path = None

        try:
            # 3. Create a temporary file
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix,
                prefix="edi_",
            )

            # 4. Close the OS file handle immediately.
            #    This is important on Windows because Docling
            #    must be able to open the file itself.
            os.close(fd)

            # 5. Write the downloaded MinIO bytes
            with open(temp_path, "wb") as temp_file:
                temp_file.write(data)

            # 6. Process the now-closed file with Docling
            result = self.processor.process_file(
                temp_path
            )

            docling_document = result["document"]

            # 7. Export normalized representation
            markdown = docling_document.export_to_markdown()

            return {
                "document_id": str(document.id),
                "filename": document.filename,
                "markdown": markdown,
                "markdown_length": len(markdown),
            }

        finally:
            # 8. Remove temporary file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)