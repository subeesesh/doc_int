import sys
from uuid import UUID

from app.db.database import SessionLocal
from app.services.document_processing_service import (
    DocumentProcessingService,
)


def main():

    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/process_document.py <document_id>"
        )
        sys.exit(1)

    document_id = UUID(sys.argv[1])

    db = SessionLocal()

    try:
        service = DocumentProcessingService()

        result = service.process_document(
            db,
            document_id,
        )

        print("=" * 70)
        print("DOCUMENT PROCESSING SUCCESSFUL")
        print("=" * 70)

        print("Document ID:")
        print(result["document_id"])

        print("\nFilename:")
        print(result["filename"])

        print("\nMarkdown length:")
        print(result["markdown_length"])

        print("\nExtracted content:")
        print("-" * 70)
        print(result["markdown"][:10000])

    except Exception as e:
        print("=" * 70)
        print("DOCUMENT PROCESSING FAILED")
        print("=" * 70)
        print(type(e).__name__)
        print(str(e))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()