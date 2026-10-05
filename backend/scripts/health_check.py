"""CLI Health Check script for all platform infrastructure and subsystems."""
import sys
from app.db.database import engine
from app.vectorstore.qdrant_client import qdrant_service
from app.search.elasticsearch import ElasticsearchService
from app.graph.neo4j_client import Neo4jService
from app.storage.minio_client import minio_service
from app.llm.factory import get_llm_provider
from app.config.settings import settings
import redis


def check_all():
    print("=" * 60)
    print("ENTERPRISE DOCUMENT INTELLIGENCE - HEALTH CHECK")
    print("=" * 60)

    results = {}

    # 1. PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        results["PostgreSQL"] = "[OK] Connected (Port 5433)"
    except Exception as e:
        results["PostgreSQL"] = f"[FAIL] {e}"

    # 2. Qdrant
    try:
        ok = qdrant_service.health_check()
        results["Qdrant"] = "[OK] Connected (Port 6335)" if ok else "[FAIL] Unhealthy"
    except Exception as e:
        results["Qdrant"] = f"[FAIL] {e}"

    # 3. Neo4j
    try:
        neo = Neo4jService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        ok = neo.health_check()
        results["Neo4j"] = "[OK] Connected (Port 7687)" if ok else "[FAIL] Unhealthy"
        neo.close()
    except Exception as e:
        results["Neo4j"] = f"[FAIL] {e}"

    # 4. Redis
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD)
        r.ping()
        results["Redis"] = "[OK] Connected (Port 6379)"
    except Exception as e:
        results["Redis"] = f"[FAIL] {e}"

    # 5. MinIO
    try:
        exists = minio_service.client.bucket_exists(settings.MINIO_BUCKET)
        results["MinIO"] = f"[OK] Connected (Bucket: {settings.MINIO_BUCKET})"
    except Exception as e:
        results["MinIO"] = f"[FAIL] {e}"

    # 6. Elasticsearch
    try:
        es = ElasticsearchService(host=settings.ELASTICSEARCH_HOST, port=settings.ELASTICSEARCH_PORT)
        ok = es.health_check()
        results["Elasticsearch"] = "[OK] Connected (Port 9200)" if ok else "[FAIL] Unhealthy"
    except Exception as e:
        results["Elasticsearch"] = f"[FAIL] {e}"

    # 7. LLM Provider
    try:
        llm = get_llm_provider()
        results["LLM Provider"] = f"[OK] Active: {type(llm).__name__} (Model: {getattr(llm, 'model', 'N/A')})"
    except Exception as e:
        results["LLM Provider"] = f"[FAIL] {e}"

    for service, status in results.items():
        print(f"  {service:<16}: {status}")

    print("=" * 60)
    return results


if __name__ == "__main__":
    check_all()
