"""Service for persisting conversations, messages, answers, citations, and retrieval logs."""
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message, Answer, CitationModel
from app.models.retrieval_log import RetrievalLog, RetrievedItem
from app.retrieval.base import RetrievalResult

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        title: str = "New Conversation",
    ) -> Conversation:
        if conversation_id:
            try:
                conv = (
                    self.db.query(Conversation)
                    .filter(Conversation.id == uuid.UUID(conversation_id))
                    .first()
                )
                if conv:
                    return conv
            except Exception:
                pass

        conv = Conversation(
            user_id=uuid.UUID(user_id) if user_id else None,
            title=title,
        )
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def save_qa_turn(
        self,
        conversation_id: uuid.UUID,
        question: str,
        answer_text: str,
        citations_data: list[dict],
        retrieval_method: str = "hybrid",
        confidence: Optional[float] = None,
        model_name: Optional[str] = None,
    ) -> Answer:
        # Save user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        self.db.add(user_msg)
        self.db.flush()

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer_text,
        )
        self.db.add(assistant_msg)
        self.db.flush()

        # Save Answer
        ans = Answer(
            message_id=assistant_msg.id,
            content=answer_text,
            confidence=confidence,
            retrieval_method=retrieval_method,
            model_name=model_name,
        )
        self.db.add(ans)
        self.db.flush()

        # Save Citations
        for c in citations_data:
            doc_id = c.get("document_id")
            chunk_id = c.get("chunk_id")
            page_id = c.get("page_id")
            cit = CitationModel(
                answer_id=ans.id,
                document_id=uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id,
                chunk_id=uuid.UUID(chunk_id) if isinstance(chunk_id, str) and chunk_id else None,
                page_id=uuid.UUID(page_id) if isinstance(page_id, str) and page_id else None,
                page_number=c.get("page_number"),
                text_snippet=c.get("text_snippet", "")[:1000],
            )
            self.db.add(cit)

        self.db.commit()
        self.db.refresh(ans)
        return ans

    def log_retrieval(
        self,
        query: str,
        retrieval_method: str,
        top_k: int,
        latency_ms: float,
        results: list[RetrievalResult],
        user_id: Optional[str] = None,
        filter_metadata: Optional[dict] = None,
    ) -> RetrievalLog:
        log_entry = RetrievalLog(
            query=query,
            retrieval_method=retrieval_method,
            top_k=top_k,
            latency_ms=latency_ms,
            user_id=uuid.UUID(user_id) if user_id else None,
            total_candidates=len(results),
            filter_metadata=filter_metadata,
        )
        self.db.add(log_entry)
        self.db.flush()

        for rank, res in enumerate(results, start=1):
            item = RetrievedItem(
                log_id=log_entry.id,
                chunk_id=uuid.UUID(res.chunk_id) if res.chunk_id else None,
                document_id=uuid.UUID(res.document_id) if res.document_id else None,
                retrieval_source=res.source.value if hasattr(res.source, "value") else str(res.source),
                rank=rank,
                initial_score=res.score,
                rerank_score=res.score,
                text_snippet=res.text[:500],
            )
            self.db.add(item)

        self.db.commit()
        return log_entry

    def get_conversation_history(self, conversation_id: str) -> list[dict]:
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == uuid.UUID(conversation_id))
            .order_by(Message.created_at)
            .all()
        )
        history = []
        for m in messages:
            msg_dict = {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            if m.answer and m.answer.citations:
                msg_dict["citations"] = [
                    {
                        "document_id": str(c.document_id),
                        "chunk_id": str(c.chunk_id) if c.chunk_id else None,
                        "page_number": c.page_number,
                        "text_snippet": c.text_snippet,
                    }
                    for c in m.answer.citations
                ]
            history.append(msg_dict)
        return history
