"""Indexing service: embeds chunks and indexes into Qdrant + Elasticsearch."""
import logging
import time
from typing import Optional

from app.embeddings.embedding_service import embedding_service
from app.vectorstore.qdrant_client import qdrant_service
from app.search.elasticsearch import ElasticsearchService
from app.config.settings import settings

logger = logging.getLogger(__name__)


class IndexingService:
    """Orchestrates embedding generation and search index updates."""

    def __init__(self):
        self.es = ElasticsearchService(
            host=settings.ELASTICSEARCH_HOST,
            port=settings.ELASTICSEARCH_PORT,
            index_name=settings.ELASTICSEARCH_INDEX,
            password=settings.ELASTICSEARCH_PASSWORD,
        )
        self.qdrant = qdrant_service

    def ensure_indexes(self) -> None:
        """Ensure all search indexes exist."""
        try:
            self.qdrant.ensure_collection()
        except Exception as e:
            logger.warning(f"Qdrant collection setup failed: {e}")
        try:
            self.es.ensure_index()
        except Exception as e:
            logger.warning(f"Elasticsearch index setup failed: {e}")

    def index_chunks(
        self,
        chunks: list,
        document_id: str,
        document_version_id: str,
        user_id: Optional[str] = None,
    ) -> dict:
        """Generate embeddings and index chunks into both Qdrant and Elasticsearch."""
        start = time.time()
        stats = {"chunks": len(chunks), "qdrant_indexed": 0, "es_indexed": 0}

        if not chunks:
            return stats

        # Generate embeddings in batch
        texts = [c.text for c in chunks]
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        t0 = time.time()
        embeddings = embedding_service.embed_batch(texts)
        logger.info(f"Embeddings generated in {time.time() - t0:.2f}s")

        # Build page_number map
        page_ids = [c.page_id for c in chunks if getattr(c, "page_id", None)]
        page_map = {}
        if page_ids:
            try:
                from app.models.processing import Page
                from app.db.database import SessionLocal
                with SessionLocal() as db_sess:
                    db_pages = db_sess.query(Page).filter(Page.id.in_(page_ids)).all()
                    page_map = {p.id: p.page_number for p in db_pages}
            except Exception as e:
                logger.warning(f"Failed to lookup pages: {e}")

        qdrant_points = []
        es_docs = []

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(chunk.id)
            page_number = getattr(chunk, "page_number", None)
            if page_number is None and hasattr(chunk, "page") and chunk.page:
                page_number = chunk.page.page_number
            if page_number is None and getattr(chunk, "page_id", None) in page_map:
                page_number = page_map[chunk.page_id]

            payload = {
                "document_id": document_id,
                "document_version_id": document_version_id,
                "page_id": str(chunk.page_id) if chunk.page_id else None,
                "page_number": page_number,
                "chunk_index": chunk.chunk_index,
                "chunk_strategy": chunk.chunk_strategy or "recursive",
                "text": chunk.text,
            }
            if user_id:
                payload["user_id"] = user_id

            qdrant_points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": payload,
            })

            es_doc = {
                "_id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "document_version_id": document_version_id,
                "page_id": str(chunk.page_id) if chunk.page_id else None,
                "page_number": page_number,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "chunk_strategy": chunk.chunk_strategy or "recursive",
                "metadata": dict(chunk.chunk_metadata) if getattr(chunk, "chunk_metadata", None) else {},
            }
            if user_id:
                es_doc["user_id"] = user_id
            es_docs.append(es_doc)

        # Index into Qdrant
        try:
            count = self.qdrant.bulk_upsert(qdrant_points)
            stats["qdrant_indexed"] = count
        except Exception as e:
            logger.error(f"Qdrant indexing failed: {e}")

        # Index into Elasticsearch
        try:
            result = self.es.bulk_index(es_docs)
            stats["es_indexed"] = result.get("indexed", 0)
        except Exception as e:
            logger.error(f"Elasticsearch indexing failed: {e}")

        stats["duration_seconds"] = round(time.time() - start, 2)
        logger.info(f"Indexing complete: {stats}")
        return stats

    def delete_document_indexes(self, document_id: str) -> None:
        """Remove all index data for a document (for reprocessing)."""
        try:
            self.qdrant.delete_by_document_id(document_id)
        except Exception as e:
            logger.warning(f"Qdrant delete failed: {e}")
        try:
            self.es.delete_by_document_id(document_id)
        except Exception as e:
            logger.warning(f"ES delete failed: {e}")

    def delete_version_indexes(self, document_version_id: str) -> None:
        """Remove all index data for a document version."""
        try:
            self.qdrant.delete_by_version_id(document_version_id)
        except Exception as e:
            logger.warning(f"Qdrant delete failed: {e}")
        try:
            self.es.delete_by_version_id(document_version_id)
        except Exception as e:
            logger.warning(f"ES delete failed: {e}")
