"""Analysis and comparison API endpoints."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.analysis_service import AnalysisService
from app.services.comparison_service import ComparisonService
from app.schemas.api import CompareRequest, CompareResponse, Difference

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary/{document_id}")
async def summarize_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    analysis_svc = AnalysisService(db)
    result = analysis_svc.summarize_document(document_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/entities/{document_id}")
async def extract_entities(
    document_id: str,
    db: Session = Depends(get_db),
):
    analysis_svc = AnalysisService(db)
    result = analysis_svc.extract_entities(document_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/facts/{document_id}")
async def extract_facts(
    document_id: str,
    db: Session = Depends(get_db),
):
    analysis_svc = AnalysisService(db)
    result = analysis_svc.extract_facts(document_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/compare", response_model=CompareResponse)
async def compare_documents(
    body: CompareRequest,
    db: Session = Depends(get_db),
):
    comp_svc = ComparisonService(db)
    result = comp_svc.compare_documents(body.document_id_a, body.document_id_b)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    diffs = [
        Difference(
            category=d["category"],
            section=d.get("section"),
            content_a=d.get("content_a"),
            content_b=d.get("content_b"),
        )
        for d in result.get("differences", [])
    ]

    return CompareResponse(
        document_a=result["document_a"],
        document_b=result["document_b"],
        differences=diffs,
        summary=result["summary"],
    )
