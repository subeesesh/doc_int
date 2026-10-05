"""Query API router for RAG question answering and conversation management."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.auth.dependencies import get_optional_user, get_accessible_document_ids
from app.models.user import User
from app.models.conversation import Conversation
from app.schemas.api import QueryRequest, QueryResponse, Citation
from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    body: QueryRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    rag_service = RAGService(db)

    # Resolve document accessibility
    filtered_doc_ids = body.document_ids
    if user:
        allowed = get_accessible_document_ids(user, db)
        if allowed is not None:
            if filtered_doc_ids:
                filtered_doc_ids = [d for d in filtered_doc_ids if d in allowed]
            else:
                filtered_doc_ids = allowed

    result = await rag_service.answer_question(
        question=body.question,
        document_ids=filtered_doc_ids,
        user_id=str(user.id) if user else None,
        top_k=body.top_k,
        conversation_id=body.conversation_id,
    )

    citations = [
        Citation(
            document_id=c["document_id"],
            page_number=c.get("page_number"),
            chunk_id=c.get("chunk_id", ""),
            text_snippet=c.get("text_snippet", ""),
        )
        for c in result.get("citations", [])
    ]

    return QueryResponse(
        answer=result["answer"],
        citations=citations,
        conversation_id=result["conversation_id"],
        confidence=result.get("confidence", 0.0),
        retrieval_method=result.get("retrieval_method", "hybrid"),
    )


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    query = db.query(Conversation)
    if user:
        query = query.filter(Conversation.user_id == user.id)
    convs = query.order_by(Conversation.updated_at.desc()).limit(limit).all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    conv_service = ConversationService(db)
    history = conv_service.get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": history}
