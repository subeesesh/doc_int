from pydantic import BaseModel
from typing import Optional
from enum import Enum
import uuid

class RetrievalSource(str, Enum):
    ELASTIC = 'elastic'
    VECTOR = 'vector'
    GRAPH = 'graph'
    HYBRID = 'hybrid'

class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    document_version_id: str
    page_id: Optional[str] = None
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    text: str
    score: float
    source: RetrievalSource
    metadata: dict = {}

class RetrievalRequest(BaseModel):
    query: str
    top_k: int = 10
    user_id: Optional[str] = None
    document_ids: Optional[list[str]] = None
    sources: list[RetrievalSource] = [RetrievalSource.ELASTIC, RetrievalSource.VECTOR]
    enable_reranking: bool = True

class RetrievalResponse(BaseModel):
    results: list[RetrievalResult]
    query: str
    sources_used: list[RetrievalSource]
    total_candidates: int
    latency_ms: float
