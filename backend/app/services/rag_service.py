"""RAG service for grounded answering, citation tracking, and provenance logging."""
import logging
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.retrieval.base import RetrievalRequest, RetrievalSource
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.elasticsearch_retriever import ElasticsearchRetriever
from app.retrieval.qdrant_retriever import QdrantRetriever
from app.retrieval.neo4j_retriever import Neo4jRetriever
from app.search.elasticsearch import ElasticsearchService
from app.vectorstore.qdrant_client import qdrant_service
from app.embeddings.embedding_service import embedding_service
from app.graph.neo4j_client import Neo4jService
from app.llm.factory import get_llm_provider
from app.services.conversation_service import ConversationService
from app.config.settings import settings

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """You are an Enterprise Document Intelligence assistant.
Answer the user's question based strictly and ONLY on the provided context evidence.
If the evidence does not contain sufficient information to answer the question, state:
"Insufficient evidence in the documents to answer this question."
Do not extrapolate or speculate.
Always cite your sources inline using [Page X, Chunk Y] or [Source N].
"""


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.conv_service = ConversationService(db)
        self._retriever = None

    @property
    def retriever(self) -> HybridRetriever:
        if self._retriever is None:
            es_service = ElasticsearchService(
                host=settings.ELASTICSEARCH_HOST,
                port=settings.ELASTICSEARCH_PORT,
                index_name=settings.ELASTICSEARCH_INDEX,
                password=settings.ELASTICSEARCH_PASSWORD,
            )
            neo4j = Neo4jService(
                settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD
            )

            self._retriever = HybridRetriever(
                es_retriever=ElasticsearchRetriever(es_service),
                qdrant_retriever=QdrantRetriever(qdrant_service, embedding_service),
                neo4j_retriever=Neo4jRetriever(neo4j),
            )
        return self._retriever

    async def answer_question(
        self,
        question: str,
        document_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        top_k: int = 5,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Full RAG pipeline: query understanding -> retrieval -> rerank -> LLM -> citation."""
        # 1. Retrieve
        request = RetrievalRequest(
            query=question,
            top_k=top_k,
            user_id=user_id,
            document_ids=document_ids,
            sources=[RetrievalSource.ELASTIC, RetrievalSource.VECTOR, RetrievalSource.GRAPH],
            enable_reranking=True,
        )
        retrieval_response = self.retriever.retrieve(request)

        # 2. Log retrieval metrics for provenance and evaluation
        try:
            self.conv_service.log_retrieval(
                query=question,
                retrieval_method="hybrid",
                top_k=top_k,
                latency_ms=retrieval_response.latency_ms,
                results=retrieval_response.results,
                user_id=user_id,
                filter_metadata={"document_ids": document_ids},
            )
        except Exception as e:
            logger.warning(f"Failed to log retrieval metrics: {e}")

        # 3. Handle empty retrieval
        if not retrieval_response.results:
            answer_text = "I could not find any relevant information in the authorized documents to answer your question."
            conv = self.conv_service.get_or_create_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                title=question[:60],
            )
            self.conv_service.save_qa_turn(
                conversation_id=conv.id,
                question=question,
                answer_text=answer_text,
                citations_data=[],
                retrieval_method="hybrid",
                confidence=0.0,
            )
            return {
                "answer": answer_text,
                "citations": [],
                "conversation_id": str(conv.id),
                "confidence": 0.0,
                "retrieval_method": "hybrid",
                "latency_ms": retrieval_response.latency_ms,
            }

        # 4. Context assembly
        context_blocks = []
        citations_data = []
        for i, r in enumerate(retrieval_response.results, start=1):
            page_str = f"Page {r.page_number}" if r.page_number else "Page N/A"
            chunk_str = f"Chunk {r.chunk_index}" if r.chunk_index is not None else "Chunk N/A"
            context_blocks.append(f"[Source {i} - {page_str}, {chunk_str} (Doc ID: {r.document_id})]:\n{r.text}")

            citations_data.append({
                "document_id": r.document_id,
                "page_number": r.page_number,
                "chunk_id": r.chunk_id,
                "page_id": r.page_id,
                "text_snippet": r.text[:300],
            })

        evidence_context = "\n\n".join(context_blocks)
        prompt = f"""EVIDENCE CONTEXT:
{evidence_context}

USER QUESTION:
{question}

Please answer the question accurately based on the evidence above. Cite the source numbers [Source N] or [Page X, Chunk Y] directly after the relevant claims."""

        # 5. LLM Answering
        llm = get_llm_provider()
        model_name = getattr(llm, "model", "local")
        try:
            resp = await llm.generate(
                prompt=prompt,
                system_prompt=RAG_SYSTEM_PROMPT,
                temperature=0.1,
            )
            answer_text = resp.text.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Deterministic evidence fallback
            top_evidence = retrieval_response.results[0]
            answer_text = f"Based on retrieved evidence from {top_evidence.document_id} (Page {top_evidence.page_number}):\n\n{top_evidence.text}"

        # 6. Confidence estimate
        max_score = max([r.score for r in retrieval_response.results]) if retrieval_response.results else 0.0

        # 7. Persist conversation turn
        conv = self.conv_service.get_or_create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=question[:60],
        )
        try:
            self.conv_service.save_qa_turn(
                conversation_id=conv.id,
                question=question,
                answer_text=answer_text,
                citations_data=citations_data,
                retrieval_method="hybrid",
                confidence=float(max_score),
                model_name=model_name,
            )
        except Exception as e:
            logger.warning(f"Failed to persist QA turn: {e}")

        return {
            "answer": answer_text,
            "citations": citations_data,
            "conversation_id": str(conv.id),
            "confidence": round(float(max_score), 4),
            "retrieval_method": "hybrid",
            "latency_ms": round(retrieval_response.latency_ms, 2),
        }
