"""Process a document end-to-end: Docling -> Pages -> Chunks -> Embeddings -> Qdrant + ES -> Knowledge Extraction -> Neo4j."""
import sys
from uuid import UUID
from app.db.database import SessionLocal
from app.services.document_processing_service import DocumentProcessingService


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.process_document <document_id>")
        sys.exit(1)

    document_id = UUID(sys.argv[1])
    db = SessionLocal()

    try:
        service = DocumentProcessingService(db)
        result = service.process_by_id(document_id)

        print("=" * 70)
        print("DOCUMENT PROCESSING SUCCESSFUL")
        print("=" * 70)
        print(f"Document ID: {result.get('document_id')}")
        print(f"Filename:    {result.get('filename')}")
        print(f"Pages:       {result.get('pages')}")
        print(f"Chunks:      {result.get('chunks')}")
        print(f"Indexed:     {result.get('indexed')}")
        print(f"Knowledge:   {result.get('knowledge')}")
        print("=" * 70)

    except Exception as e:
        print("=" * 70)
        print("DOCUMENT PROCESSING FAILED")
        print("=" * 70)
        print(f"{type(e).__name__}: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()