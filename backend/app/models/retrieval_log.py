"""Models for retrieval logging and evaluation tracking."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_method: Mapped[str] = mapped_column(String(50), nullable=False)  # elastic, vector, graph, hybrid
    top_k: Mapped[int] = mapped_column(Integer, default=10)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    total_candidates: Mapped[int] = mapped_column(Integer, default=0)
    filter_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    items: Mapped[list["RetrievedItem"]] = relationship(
        back_populates="log", cascade="all, delete-orphan", order_by="RetrievedItem.rank"
    )


class RetrievedItem(Base):
    __tablename__ = "retrieved_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    retrieval_source: Mapped[str] = mapped_column(String(50), nullable=False)  # elastic, vector, graph, hybrid
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rerank_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    text_snippet: Mapped[str] = mapped_column(Text, nullable=False)

    log: Mapped["RetrievalLog"] = relationship(back_populates="items")
