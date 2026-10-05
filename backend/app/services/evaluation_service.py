"""Evaluation engine for retrieval and RAG metrics."""
import uuid
import time
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationRun, EvaluationResult
from app.services.rag_service import RAGService
from app.retrieval.base import RetrievalRequest, RetrievalSource

logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.rag_service = RAGService(db)

    def create_dataset(self, name: str, description: Optional[str] = None) -> EvaluationDataset:
        ds = EvaluationDataset(name=name, description=description)
        self.db.add(ds)
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def add_question(
        self,
        dataset_id: str,
        question: str,
        ground_truth: str,
        expected_chunk_ids: Optional[list[str]] = None,
        expected_document_ids: Optional[list[str]] = None,
    ) -> EvaluationQuestion:
        q = EvaluationQuestion(
            dataset_id=uuid.UUID(dataset_id),
            question=question,
            ground_truth_answer=ground_truth,
            expected_chunk_ids=expected_chunk_ids or [],
            expected_document_ids=expected_document_ids or [],
        )
        self.db.add(q)
        self.db.commit()
        self.db.refresh(q)
        return q

    async def run_evaluation(
        self,
        dataset_id: str,
        run_name: str,
        retrieval_method: str = "hybrid",
        top_k: int = 5,
    ) -> EvaluationRun:
        ds = self.db.query(EvaluationDataset).filter(EvaluationDataset.id == uuid.UUID(dataset_id)).first()
        if not ds:
            raise ValueError("Dataset not found")

        run = EvaluationRun(
            dataset_id=ds.id,
            run_name=run_name,
            retrieval_method=retrieval_method,
        )
        self.db.add(run)
        self.db.flush()

        results = []
        recalls = []
        precisions = []
        mrrs = []
        latencies = []

        for q in ds.questions:
            start_t = time.perf_counter()

            # Execute RAG
            qa_res = await self.rag_service.answer_question(
                question=q.question,
                document_ids=q.expected_document_ids if q.expected_document_ids else None,
                top_k=top_k,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            retrieved_chunk_ids = [c["chunk_id"] for c in qa_res.get("citations", [])]

            # Compute retrieval metrics
            expected = set(q.expected_chunk_ids or [])
            retrieved = set(retrieved_chunk_ids)

            if expected:
                hits = expected.intersection(retrieved)
                recall = len(hits) / len(expected)
                precision = len(hits) / len(retrieved) if retrieved else 0.0

                # MRR
                mrr = 0.0
                for rank, cid in enumerate(retrieved_chunk_ids, start=1):
                    if cid in expected:
                        mrr = 1.0 / rank
                        break
            else:
                recall = 1.0 if retrieved else 0.0
                precision = 1.0 if retrieved else 0.0
                mrr = 1.0 if retrieved else 0.0

            # Simple answer overlap / correctness proxy
            gt_words = set(q.ground_truth_answer.lower().split())
            gen_words = set(qa_res["answer"].lower().split())
            correctness = len(gt_words.intersection(gen_words)) / len(gt_words) if gt_words else 0.5

            faithfulness = 1.0 if len(qa_res.get("citations", [])) > 0 else 0.0
            citation_correct = 1.0 if len(qa_res.get("citations", [])) > 0 else 0.0

            res = EvaluationResult(
                run_id=run.id,
                question_id=q.id,
                generated_answer=qa_res["answer"],
                retrieved_chunk_ids=retrieved_chunk_ids,
                recall_at_k=round(recall, 4),
                precision_at_k=round(precision, 4),
                mrr=round(mrr, 4),
                faithfulness=round(faithfulness, 4),
                answer_correctness=round(min(correctness, 1.0), 4),
                citation_correctness=round(citation_correct, 4),
                latency_ms=round(elapsed_ms, 2),
            )
            self.db.add(res)
            results.append(res)

            recalls.append(recall)
            precisions.append(precision)
            mrrs.append(mrr)
            latencies.append(elapsed_ms)

        mean_metrics = {
            "mean_recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
            "mean_precision_at_k": round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
            "mean_mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else 0.0,
            "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "total_questions": len(results),
        }
        run.metrics = mean_metrics
        self.db.commit()
        self.db.refresh(run)
        return run
