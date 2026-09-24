from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter


class DocumentProcessor:
    """
    Converts an enterprise document into a structured representation
    using Docling.

    This layer is intentionally independent of PostgreSQL, Qdrant,
    MinIO, and the API layer.
    """

    def __init__(self):
        self.converter = DocumentConverter()

    def process_file(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        result = self.converter.convert(str(path))
        document = result.document

        return {
            "document": document,
            "source_path": str(path),
        }

    def export_markdown(self, file_path: str) -> str:
        processed = self.process_file(file_path)
        document = processed["document"]

        return document.export_to_markdown()