"""Elasticsearch retriever for BM25 keyword search."""
import logging
from typing import Optional

from app.retrieval.base import RetrievalResult, RetrievalSource
from app.search.elasticsearch import ElasticsearchService

logger = logging.getLogger(__name__)


class ElasticsearchRetriever:
    def __init__(self, es_service: ElasticsearchService):
        self.es_service = es_service

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
    ) -> list[RetrievalResult]:
        if not self.es_service:
            logger.warning("ElasticsearchService not available.")
            return []

        try:
            hits = self.es_service.search(
                query=query,
                top_k=top_k,
                document_ids=document_ids,
                user_id=user_id,
            )
            results = []
            for hit in hits:
                results.append(
                    RetrievalResult(
                        chunk_id=hit.get("chunk_id", hit.get("_id", "")),
                        document_id=hit.get("document_id", ""),
                        document_version_id=hit.get("document_version_id", ""),
                        page_id=hit.get("page_id"),
                        page_number=hit.get("page_number"),
                        chunk_index=hit.get("chunk_index"),
                        text=hit.get("text", ""),
                        score=float(hit.get("_score", 0.0)),
                        source=RetrievalSource.ELASTIC,
                        metadata=hit.get("metadata", {}),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Elasticsearch retrieval failed: {e}")
            return []
