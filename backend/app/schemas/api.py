from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user_id: str
    email: str

class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime
    user_id: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    document_ids: Optional[list[str]] = None

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    text: str
    score: float
    source: str

class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int
    latency_ms: float

class QueryRequest(BaseModel):
    question: str
    document_ids: Optional[list[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_id: Optional[str] = None

class Citation(BaseModel):
    document_id: str
    page_number: Optional[int] = None
    chunk_id: str
    text_snippet: str

class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str
    confidence: float
    retrieval_method: str

class CompareRequest(BaseModel):
    document_id_a: str
    document_id_b: str

class Difference(BaseModel):
    category: str  # added, removed, modified, unchanged
    section: Optional[str] = None
    content_a: Optional[str] = None
    content_b: Optional[str] = None

class CompareResponse(BaseModel):
    document_a: str
    document_b: str
    differences: list[Difference]
    summary: str

class AnalysisResponse(BaseModel):
    document_id: str
    result: dict

class ProcessingStatusResponse(BaseModel):
    document_id: str
    version_id: str
    status: str
    job_type: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class HealthResponse(BaseModel):
    status: str
    services: dict
