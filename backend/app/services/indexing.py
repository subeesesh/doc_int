from uuid import UUID

from app.embeddings.service import EmbeddingService
from app.vectorstore.qdrant import upsert_chunk


embedding_service = EmbeddingService()


def index_chunk(
    chunk_id: UUID,
    text: str,
    document_version_id: UUID,
    page_id: UUID,
    chunk_index: int,
    chunk_strategy: str,
) -> None:
    vector = embedding_service.embed_text(text)

    payload = {
        "document_version_id": str(document_version_id),
        "page_id": str(page_id),
        "chunk_index": chunk_index,
        "chunk_strategy": chunk_strategy,
    }

    upsert_chunk(
        chunk_id=chunk_id,
        vector=vector,
        payload=payload,
    )