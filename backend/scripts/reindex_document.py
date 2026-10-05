"""Reindex chunks from database to Qdrant, Elasticsearch, and Neo4j without re-running OCR."""
import sys
import uuid
from app.db.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.models.knowledge import Chunk
from app.services.indexing_service import IndexingService
from app.services.knowledge_extraction_service import KnowledgeExtractionService
from app.graph.neo4j_client import Neo4jService
from app.config.settings import settings


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.reindex_document <document_id>")
        sys.exit(1)

    doc_id = uuid.UUID(sys.argv[1])
    db = SessionLocal()

    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            print(f"Document {doc_id} not found.")
            sys.exit(1)

        version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not version:
            print("No document version found.")
            sys.exit(1)

        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_version_id == version.id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        print(f"Found {len(chunks)} chunks in PostgreSQL for document {doc.filename}")

        # Re-index search engines
        indexing_svc = IndexingService()
        indexing_svc.ensure_indexes()
        indexing_svc.delete_version_indexes(str(version.id))
        stats = indexing_svc.index_chunks(
            chunks=chunks,
            document_id=str(doc.id),
            document_version_id=str(version.id),
            user_id=str(doc.user_id),
        )
        print(f"Search indexing stats: {stats}")

        # Re-index knowledge graph
        neo4j = Neo4jService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        if neo4j.health_check():
            ke_svc = KnowledgeExtractionService(db, neo4j)
            ke_svc.delete_document_knowledge(str(version.id))
            neo4j.delete_version_data(str(version.id))
            ke_stats = ke_svc.extract_from_chunks(chunks, str(doc.id), str(version.id))
            print(f"Knowledge graph extraction stats: {ke_stats}")
        else:
            print("Neo4j not reachable, skipping graph reindexing.")

        print("=" * 60)
        print("REINDEXING COMPLETED SUCCESSFULLY")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
