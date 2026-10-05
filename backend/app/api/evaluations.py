"""Evaluation API router."""
import uuid
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.evaluation_service import EvaluationService
from app.models.evaluation import EvaluationDataset, EvaluationRun

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateDatasetRequest(BaseModel):
    name: str
    description: Optional[str] = None


class AddQuestionRequest(BaseModel):
    question: str
    ground_truth: str
    expected_chunk_ids: Optional[list[str]] = None
    expected_document_ids: Optional[list[str]] = None


class RunEvalRequest(BaseModel):
    run_name: str
    retrieval_method: str = "hybrid"
    top_k: int = 5


@router.post("/datasets")
async def create_dataset(body: CreateDatasetRequest, db: Session = Depends(get_db)):
    svc = EvaluationService(db)
    ds = svc.create_dataset(body.name, body.description)
    return {"id": str(ds.id), "name": ds.name}


@router.get("/datasets")
async def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(EvaluationDataset).all()
    return [{"id": str(d.id), "name": d.name, "questions_count": len(d.questions)} for d in datasets]


@router.post("/datasets/{dataset_id}/questions")
async def add_question(dataset_id: str, body: AddQuestionRequest, db: Session = Depends(get_db)):
    svc = EvaluationService(db)
    q = svc.add_question(
        dataset_id=dataset_id,
        question=body.question,
        ground_truth=body.ground_truth,
        expected_chunk_ids=body.expected_chunk_ids,
        expected_document_ids=body.expected_document_ids,
    )
    return {"id": str(q.id), "question": q.question}


@router.post("/datasets/{dataset_id}/run")
async def run_evaluation(dataset_id: str, body: RunEvalRequest, db: Session = Depends(get_db)):
    svc = EvaluationService(db)
    try:
        run = await svc.run_evaluation(
            dataset_id=dataset_id,
            run_name=body.run_name,
            retrieval_method=body.retrieval_method,
            top_k=body.top_k,
        )
        return {
            "id": str(run.id),
            "run_name": run.run_name,
            "metrics": run.metrics,
            "results_count": len(run.results),
        }
    except Exception as e:
        logger.error(f"Evaluation run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
