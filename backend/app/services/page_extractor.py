from __future__ import annotations

import re
from typing import Any


class PageExtractor:

    def extract_pages(self, document: Any) -> list[dict]:
        """
        Convert a DoclingDocument OR markdown text into our internal page representation.

        Returns:
            [
                {
                    "page_number": 1,
                    "text": "...",
                    "extraction_type": "docling",
                    "assets": []
                },
                ...
            ]
        """
        # Case 1: Markdown string passed
        if isinstance(document, str):
            return self._extract_from_markdown(document)

        # Case 2: Docling document object with iterate_items
        if hasattr(document, "iterate_items"):
            return self._extract_from_docling(document)

        # Case 3: Dict with 'markdown' or 'document'
        if isinstance(document, dict):
            if "document" in document and hasattr(document["document"], "iterate_items"):
                return self._extract_from_docling(document["document"])
            if "markdown" in document:
                return self._extract_from_markdown(document["markdown"])

        # Fallback
        return [{"page_number": 1, "text": str(document), "extraction_type": "text", "assets": []}]

    def _extract_from_docling(self, docling_doc: Any) -> list[dict]:
        page_map: dict[int, list[str]] = {}

        for item, level in docling_doc.iterate_items():
            if not getattr(item, "prov", None):
                continue

            for provenance in item.prov:
                page_no = getattr(provenance, "page_no", None)
                if page_no is None:
                    continue

                text = self._extract_text(item)
                if text:
                    page_texts = page_map.setdefault(page_no, [])
                    if not page_texts or page_texts[-1] != text:
                        page_texts.append(text)

        pages = []
        for page_number in sorted(page_map):
            pages.append({
                "page_number": page_number,
                "text": "\n\n".join(page_map[page_number]),
                "extraction_type": "docling",
                "assets": [],
            })

        if not pages:
            # If provenance wasn't found, try export_to_markdown
            if hasattr(docling_doc, "export_to_markdown"):
                return self._extract_from_markdown(docling_doc.export_to_markdown())

        return pages

    def _extract_from_markdown(self, markdown: str) -> list[dict]:
        sections = markdown.split("\n## ")
        pages = []
        if sections:
            first = sections[0].strip()
            if first:
                pages.append({"page_number": 1, "text": first, "extraction_type": "docling", "assets": []})
            for i, section in enumerate(sections[1:], start=2):
                text = "## " + section.strip()
                pages.append({"page_number": i, "text": text, "extraction_type": "docling", "assets": []})
        if not pages and markdown.strip():
            pages.append({"page_number": 1, "text": markdown.strip(), "extraction_type": "docling", "assets": []})
        return pages

    @staticmethod
    def _extract_text(item: Any) -> str | None:
        text = getattr(item, "text", None)
        if text:
            return str(text).strip()
        return None