"""Qdrant retriever for semantic vector search."""
import logging
from typing import Optional

from app.retrieval.base import RetrievalResult, RetrievalSource
from app.vectorstore.qdrant_client import QdrantService
from app.embeddings.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class QdrantRetriever:
    def __init__(self, qdrant_service: QdrantService, embedding_service: EmbeddingService):
        self.qdrant = qdrant_service
        self.embedder = embedding_service

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
    ) -> list[RetrievalResult]:
        if not self.qdrant or not self.embedder:
            logger.warning("Qdrant or embedding service not available.")
            return []

        try:
            query_vector = self.embedder.embed(query)

            if document_ids or user_id:
                hits = self.qdrant.filtered_search(
                    query_vector=query_vector,
                    limit=top_k,
                    document_ids=document_ids,
                    user_id=user_id,
                )
            else:
                hits = self.qdrant.search(
                    query_vector=query_vector,
                    limit=top_k,
                )

            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append(
                    RetrievalResult(
                        chunk_id=hit.get("id", ""),
                        document_id=payload.get("document_id", ""),
                        document_version_id=payload.get("document_version_id", ""),
                        page_id=payload.get("page_id"),
                        page_number=payload.get("page_number"),
                        chunk_index=payload.get("chunk_index"),
                        text=payload.get("text", ""),
                        score=float(hit.get("score", 0.0)),
                        source=RetrievalSource.VECTOR,
                        metadata={},
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Qdrant retrieval failed: {e}")
            return []
