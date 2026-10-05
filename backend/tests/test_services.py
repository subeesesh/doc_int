"""Tests for core service unit logic — pure unit tests, no DB required."""
import pytest
from unittest.mock import MagicMock, patch


# ─── Chunking ─────────────────────────────────────────────────────────────────
class TestChunking:
    def test_split_text_basic(self):
        from app.services.chunking import RecursiveChunker
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        text = "Hello world. " * 20  # 260 chars
        chunks = chunker.split_text(text)
        assert len(chunks) >= 1
        for c in chunks:
            assert len(c) <= 120  # chunk_size + some tolerance

    def test_split_text_empty(self):
        from app.services.chunking import RecursiveChunker
        chunker = RecursiveChunker(chunk_size=200, chunk_overlap=20)
        chunks = chunker.split_text("")
        assert chunks == []

    def test_chunk_alias(self):
        from app.services.chunking import RecursiveChunker
        chunker = RecursiveChunker(chunk_size=200, chunk_overlap=20)
        text = "This is a test document with enough content to chunk."
        result_a = chunker.split_text(text)
        result_b = chunker.chunk(text)
        assert result_a == result_b


# ─── Page Extractor ───────────────────────────────────────────────────────────
class TestPageExtractor:
    def test_extract_pages_from_markdown(self):
        from app.services.page_extractor import PageExtractor
        extractor = PageExtractor()
        md = "# Section 1\n\nContent for section one.\n\n# Section 2\n\nContent for section two."
        pages = extractor.extract_pages(md)
        assert len(pages) >= 1
        for p in pages:
            assert "text" in p
            assert "page_number" in p
            assert p["text"].strip() != ""

    def test_extract_pages_plain_text(self):
        from app.services.page_extractor import PageExtractor
        extractor = PageExtractor()
        text = "Simple text without headers. " * 10
        pages = extractor.extract_pages(text)
        assert len(pages) >= 1


# ─── Knowledge Extraction ─────────────────────────────────────────────────────
class TestKnowledgeExtraction:
    def _make_service(self, db=None):
        from app.services.knowledge_extraction_service import KnowledgeExtractionService
        mock_db = db or MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.flush = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        return KnowledgeExtractionService(mock_db)

    def test_extract_amounts(self):
        svc = self._make_service()
        result = svc._extract_from_text("The reimbursement limit is $500 per month.")
        entity_types = [e['type'] for e in result['entities']]
        assert 'AMOUNT' in entity_types

    def test_extract_time_periods(self):
        svc = self._make_service()
        result = svc._extract_from_text("Employees must submit claims within 30 days.")
        entity_types = [e['type'] for e in result['entities']]
        assert 'TIME_PERIOD' in entity_types

    def test_extract_requirements(self):
        svc = self._make_service()
        result = svc._extract_from_text("Employees must obtain prior approval before travelling.")
        # Should extract facts with 'must' predicate
        predicates = [f['predicate'] for f in result['facts']]
        assert 'must' in predicates


# ─── RRF Fusion ───────────────────────────────────────────────────────────────
class TestFusion:
    def test_rrf_basic(self):
        from app.retrieval.fusion import reciprocal_rank_fusion
        from app.retrieval.base import RetrievalResult, RetrievalSource

        def make_result(chunk_id, score, source):
            return RetrievalResult(
                chunk_id=chunk_id, document_id="doc1", document_version_id="ver1",
                text="some text", score=score, source=source,
            )

        list1 = [make_result("c1", 0.9, RetrievalSource.VECTOR),
                 make_result("c2", 0.7, RetrievalSource.VECTOR)]
        list2 = [make_result("c2", 0.85, RetrievalSource.ELASTIC),
                 make_result("c3", 0.6, RetrievalSource.ELASTIC)]

        fused = reciprocal_rank_fusion([list1, list2])
        chunk_ids = [r.chunk_id for r in fused]

        # c2 appears in both lists → should rank high
        assert "c2" in chunk_ids
        c2_idx = chunk_ids.index("c2")
        assert c2_idx <= 1  # Should be in top 2

    def test_rrf_empty_lists(self):
        from app.retrieval.fusion import reciprocal_rank_fusion
        result = reciprocal_rank_fusion([[], []])
        assert result == []

    def test_rrf_single_list(self):
        from app.retrieval.fusion import reciprocal_rank_fusion
        from app.retrieval.base import RetrievalResult, RetrievalSource

        items = [RetrievalResult(
            chunk_id=f"c{i}", document_id="doc1", document_version_id="ver1",
            text="text", score=float(1 - i * 0.1), source=RetrievalSource.VECTOR,
        ) for i in range(3)]
        fused = reciprocal_rank_fusion([items])
        assert len(fused) == 3


# ─── Security ─────────────────────────────────────────────────────────────────
class TestSecurity:
    def test_hash_and_verify_password(self):
        from app.auth.security import hash_password, verify_password
        pw = "securepassword123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_create_and_decode_token(self):
        from app.auth.security import create_access_token, decode_access_token
        data = {"sub": "user-uuid-123", "email": "test@example.com"}
        token = create_access_token(data)
        assert isinstance(token, str)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-uuid-123"

    def test_invalid_token_returns_none(self):
        from app.auth.security import decode_access_token
        result = decode_access_token("not.a.valid.token")
        assert result is None
