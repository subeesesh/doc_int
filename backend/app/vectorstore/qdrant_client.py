"""Qdrant vector store service for semantic search."""
import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)
from app.config.settings import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Manages Qdrant collection operations for document chunk vectors."""

    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self.collection = settings.QDRANT_COLLECTION
        self.dimension = settings.EMBEDDING_DIMENSION

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=30,
            )
        return self._client

    def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    def ensure_collection(self) -> None:
        """Create collection if it doesn't exist (idempotent)."""
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection for c in collections):
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=self.dimension, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection}")
            else:
                logger.info(f"Qdrant collection exists: {self.collection}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            raise

    def upsert(self, point_id: str, vector: list[float], payload: dict) -> None:
        """Upsert a single point."""
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def bulk_upsert(
        self, points: list[dict], batch_size: int = 100
    ) -> int:
        """Bulk upsert points. Each dict must have 'id', 'vector', 'payload'."""
        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            structs = [
                PointStruct(
                    id=p["id"], vector=p["vector"], payload=p["payload"]
                )
                for p in batch
            ]
            self.client.upsert(
                collection_name=self.collection, points=structs
            )
            total += len(structs)
        logger.info(f"Bulk upserted {total} points to Qdrant")
        return total

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[dict]:
        """Simple vector search."""
        results = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results.points
        ]

    def filtered_search(
        self,
        query_vector: list[float],
        limit: int = 10,
        document_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Vector search with metadata filters."""
        conditions = []
        if document_ids:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=document_ids),
                )
            )
        if user_id:
            conditions.append(
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                )
            )

        query_filter = Filter(must=conditions) if conditions else None

        results = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results.points
        ]

    def delete_by_document_id(self, document_id: str) -> None:
        """Delete all points for a document."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(f"Deleted Qdrant points for document: {document_id}")

    def delete_by_version_id(self, document_version_id: str) -> None:
        """Delete all points for a document version."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_version_id",
                        match=MatchValue(value=document_version_id),
                    )
                ]
            ),
        )

    def collection_info(self) -> dict:
        """Get collection info and stats."""
        try:
            info = self.client.get_collection(self.collection)
            return {
                "name": self.collection,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": str(info.status),
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"name": self.collection, "status": "unavailable", "error": str(e)}


qdrant_service = QdrantService()
