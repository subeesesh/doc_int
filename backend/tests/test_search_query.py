"""Tests for search and query endpoints."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.retrieval.base import RetrievalResult, RetrievalSource


MOCK_RESULT = RetrievalResult(
    chunk_id="chunk-abc-123",
    document_id="doc-xyz-456",
    document_version_id="ver-000-001",
    page_number=3,
    chunk_index=0,
    text="Full-time employees receive 20 days of annual leave per calendar year.",
    score=0.92,
    source=RetrievalSource.VECTOR,
)


def _mock_hybrid_retriever(results=None):
    """Patch HybridRetriever.retrieve to return canned results."""
    if results is None:
        results = [MOCK_RESULT]
    mock = MagicMock()
    mock.retrieve.return_value = MagicMock(
        results=results,
        sources_used=[RetrievalSource.VECTOR],
        total_candidates=len(results),
        latency_ms=42.0,
    )
    return patch("app.api.search.HybridRetriever", return_value=mock)


def test_semantic_search_returns_results(client):
    with _mock_hybrid_retriever():
        resp = client.post("/search/semantic", json={"query": "annual leave", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    assert data["results"][0]["text"] != ""


def test_keyword_search_returns_results(client):
    with _mock_hybrid_retriever():
        resp = client.post("/search/keyword", json={"query": "leave policy", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


def test_hybrid_search_returns_results(client):
    with _mock_hybrid_retriever():
        resp = client.post("/search/hybrid", json={"query": "expense reimbursement", "top_k": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "query" in data
    assert "latency_ms" in data


def test_search_empty_results(client):
    with _mock_hybrid_retriever(results=[]):
        resp = client.post("/search/hybrid", json={"query": "zzznomatch", "top_k": 5})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_ask_question(client):
    mock_answer = {
        "answer": "Full-time employees receive 20 days of annual leave.",
        "citations": [{"document_id": "doc-xyz-456", "page_number": 3, "chunk_id": "chunk-abc-123", "text_snippet": "20 days of annual leave"}],
        "conversation_id": "conv-test-001",
        "confidence": 0.88,
        "retrieval_method": "hybrid",
    }
    with patch("app.api.query.RAGService") as MockRAG:
        instance = MockRAG.return_value
        instance.answer_question = AsyncMock(return_value=mock_answer)
        resp = client.post("/query/ask", json={"question": "How many annual leave days?"})
    
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data
    assert "conversation_id" in data
    assert len(data["answer"]) > 0


def test_list_conversations_empty(client):
    resp = client.get("/query/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_conversation_not_found(client):
    with patch("app.api.query.ConversationService") as MockSvc:
        MockSvc.return_value.get_conversation_history.return_value = []
        resp = client.get("/query/conversations/nonexistent-id")
    assert resp.status_code == 200  # Returns empty history, not 404
