"""Central API router - aggregates all sub-routers."""
from fastapi import APIRouter
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.query import router as query_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.evaluations import router as evaluations_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(search_router, prefix="/search", tags=["Search"])
api_router.include_router(query_router, prefix="/query", tags=["Query"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["Evaluations"])
