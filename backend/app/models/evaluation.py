"""Models for evaluation datasets, questions, runs, and results."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    runs: Mapped[list["EvaluationRun"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_chunk_ids: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    expected_document_ids: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    dataset: Mapped["EvaluationDataset"] = relationship(back_populates="questions")
    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="question_rel", cascade="all, delete-orphan"
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    retrieval_method: Mapped[str] = mapped_column(String(50), default="hybrid")
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Mean metrics: recall, precision, mrr, faithfulness, latency
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dataset: Mapped["EvaluationDataset"] = relationship(back_populates="runs")
    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    recall_at_k: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_k: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mrr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    faithfulness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    answer_correctness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    citation_correctness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    run: Mapped["EvaluationRun"] = relationship(back_populates="results")
    question_rel: Mapped["EvaluationQuestion"] = relationship(back_populates="results")
