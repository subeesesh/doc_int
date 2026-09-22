from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from app.config.settings import settings


client = QdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
)


def ensure_collection() -> None:
    collections = client.get_collections().collections

    if settings.qdrant_collection in {
        collection.name for collection in collections
    }:
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.embedding_dimension,
            distance=Distance.COSINE,
        ),
    )


def upsert_chunk(
    chunk_id: UUID,
    vector: list[float],
    payload: dict,
) -> None:
    if len(vector) != settings.embedding_dimension:
        raise ValueError(
            f"Expected vector dimension "
            f"{settings.embedding_dimension}, "
            f"got {len(vector)}"
        )

    point = PointStruct(
        id=str(chunk_id),
        vector=vector,
        payload={
            "chunk_id": str(chunk_id),
            **payload,
        },
    )

    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[point],
    )


def search_chunks(
    vector: list[float],
    limit: int = 5,
):
    if len(vector) != settings.embedding_dimension:
        raise ValueError(
            f"Expected vector dimension "
            f"{settings.embedding_dimension}, "
            f"got {len(vector)}"
        )

    return client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=limit,
    )