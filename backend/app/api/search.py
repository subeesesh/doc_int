"""Search API endpoints for keyword, semantic, and hybrid retrieval."""
import logging
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.auth.dependencies import get_optional_user, get_accessible_document_ids
from app.models.user import User
from app.schemas.api import SearchRequest, SearchResponse, SearchResult
from app.retrieval.base import RetrievalRequest, RetrievalSource
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.elasticsearch_retriever import ElasticsearchRetriever
from app.retrieval.qdrant_retriever import QdrantRetriever
from app.retrieval.neo4j_retriever import Neo4jRetriever
from app.search.elasticsearch import ElasticsearchService
from app.vectorstore.qdrant_client import qdrant_service
from app.embeddings.embedding_service import embedding_service
from app.graph.neo4j_client import Neo4jService
from app.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_hybrid_retriever() -> HybridRetriever:
    es_service = ElasticsearchService(
        host=settings.ELASTICSEARCH_HOST,
        port=settings.ELASTICSEARCH_PORT,
        index_name=settings.ELASTICSEARCH_INDEX,
        password=settings.ELASTICSEARCH_PASSWORD,
    )
    neo4j = Neo4jService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)

    return HybridRetriever(
        es_retriever=ElasticsearchRetriever(es_service),
        qdrant_retriever=QdrantRetriever(qdrant_service, embedding_service),
        neo4j_retriever=Neo4jRetriever(neo4j),
    )


def _resolve_document_filters(
    user: Optional[User],
    db: Session,
    requested_doc_ids: Optional[list[str]] = None,
) -> Optional[list[str]]:
    """Merges requested doc IDs with RBAC permissions."""
    if not user:
        return requested_doc_ids

    allowed_ids = get_accessible_document_ids(user, db)
    if allowed_ids is None:
        # Admin - no restriction
        return requested_doc_ids

    if requested_doc_ids:
        # Filter down requested doc IDs to only permitted ones
        return [doc_id for doc_id in requested_doc_ids if doc_id in allowed_ids]
    return allowed_ids


@router.post("/keyword", response_model=SearchResponse)
async def keyword_search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    start_time = time.perf_counter()
    filtered_doc_ids = _resolve_document_filters(user, db, body.document_ids)

    es_service = ElasticsearchService(
        host=settings.ELASTICSEARCH_HOST,
        port=settings.ELASTICSEARCH_PORT,
        index_name=settings.ELASTICSEARCH_INDEX,
        password=settings.ELASTICSEARCH_PASSWORD,
    )
    retriever = ElasticsearchRetriever(es_service)
    raw_results = retriever.retrieve(
        query=body.query,
        top_k=body.top_k,
        document_ids=filtered_doc_ids,
        user_id=str(user.id) if user and filtered_doc_ids is None else None,
    )

    results = [
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
            text=r.text,
            score=r.score,
            source=r.source.value if hasattr(r.source, "value") else str(r.source),
        )
        for r in raw_results
    ]

    latency = (time.perf_counter() - start_time) * 1000
    return SearchResponse(
        results=results,
        query=body.query,
        total=len(results),
        latency_ms=round(latency, 2),
    )


@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    start_time = time.perf_counter()
    filtered_doc_ids = _resolve_document_filters(user, db, body.document_ids)

    retriever = QdrantRetriever(qdrant_service, embedding_service)
    raw_results = retriever.retrieve(
        query=body.query,
        top_k=body.top_k,
        document_ids=filtered_doc_ids,
        user_id=str(user.id) if user and filtered_doc_ids is None else None,
    )

    results = [
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
            text=r.text,
            score=r.score,
            source=r.source.value if hasattr(r.source, "value") else str(r.source),
        )
        for r in raw_results
    ]

    latency = (time.perf_counter() - start_time) * 1000
    return SearchResponse(
        results=results,
        query=body.query,
        total=len(results),
        latency_ms=round(latency, 2),
    )


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    start_time = time.perf_counter()
    filtered_doc_ids = _resolve_document_filters(user, db, body.document_ids)

    retriever = _get_hybrid_retriever()
    req = RetrievalRequest(
        query=body.query,
        top_k=body.top_k,
        user_id=str(user.id) if user and filtered_doc_ids is None else None,
        document_ids=filtered_doc_ids,
        sources=[RetrievalSource.ELASTIC, RetrievalSource.VECTOR, RetrievalSource.GRAPH],
        enable_reranking=True,
    )
    response = retriever.retrieve(req)

    results = [
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
            text=r.text,
            score=r.score,
            source=r.source.value if hasattr(r.source, "value") else str(r.source),
        )
        for r in response.results
    ]

    latency = (time.perf_counter() - start_time) * 1000
    return SearchResponse(
        results=results,
        query=body.query,
        total=len(results),
        latency_ms=round(latency, 2),
    )
