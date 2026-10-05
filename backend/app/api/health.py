"""Health check endpoints."""
import logging
from fastapi import APIRouter
from app.config.settings import settings
from app.schemas.api import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    services = {}

    # PostgreSQL
    try:
        from app.db.database import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        services["postgres"] = "healthy"
    except Exception as e:
        services["postgres"] = f"unhealthy: {e}"

    # Qdrant
    try:
        from app.vectorstore.qdrant_client import qdrant_service
        services["qdrant"] = "healthy" if qdrant_service.health_check() else "unhealthy"
    except Exception:
        services["qdrant"] = "unavailable"

    # Elasticsearch
    try:
        from app.search.elasticsearch import ElasticsearchService
        es = ElasticsearchService(
            host=settings.ELASTICSEARCH_HOST,
            port=settings.ELASTICSEARCH_PORT,
        )
        services["elasticsearch"] = "healthy" if es.health_check() else "unhealthy"
    except Exception:
        services["elasticsearch"] = "unavailable"

    # Neo4j
    try:
        from app.graph.neo4j_client import Neo4jService
        neo4j = Neo4jService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        services["neo4j"] = "healthy" if neo4j.health_check() else "unhealthy"
        neo4j.close()
    except Exception:
        services["neo4j"] = "unavailable"

    # Redis
    try:
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD)
        r.ping()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unavailable"

    # MinIO
    try:
        from app.storage.minio_client import minio_service
        services["minio"] = "healthy"
    except Exception:
        services["minio"] = "unavailable"

    # LLM
    try:
        from app.llm.factory import get_llm_provider
        llm = get_llm_provider()
        services["llm"] = f"available ({type(llm).__name__})"
    except Exception:
        services["llm"] = "unavailable"

    all_healthy = all("healthy" in str(v) or "available" in str(v) for v in services.values())
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        services=services,
    )
