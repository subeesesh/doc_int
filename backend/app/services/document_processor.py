from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter


class DocumentProcessor:

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
            "markdown": document.export_to_markdown(),
        }

    def process(self, file_bytes: bytes, filename: str) -> str:
        """Process document from raw bytes safely on Windows using tempfile.mkstemp."""
        suffix = os.path.splitext(filename)[1]
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
            result = self.converter.convert(tmp_path)
            return result.document.export_to_markdown()
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass