"""Test keyword (Elasticsearch) and semantic (Qdrant) search."""
import sys
from app.db.database import SessionLocal
from app.search.elasticsearch import ElasticsearchService
from app.vectorstore.qdrant_client import qdrant_service
from app.embeddings.embedding_service import embedding_service
from app.config.settings import settings


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "annual leave days remote work"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print("=" * 70)
    print(f"SEARCH TEST - Query: '{query}'")
    print("=" * 70)

    # 1. Semantic Search (Qdrant)
    print("\n--- 1. SEMANTIC VECTOR SEARCH (Qdrant) ---")
    try:
        query_vector = embedding_service.embed(query)
        hits = qdrant_service.search(query_vector=query_vector, limit=top_k)
        if not hits:
            print("No semantic results found.")
        for idx, hit in enumerate(hits, 1):
            payload = hit.get("payload", {})
            print(f"[{idx}] Score: {hit.get('score'):.4f} | Chunk ID: {hit.get('id')} | Page: {payload.get('page_number')}")
            snippet = payload.get("text", "")[:180].replace("\n", " ")
            print(f"     Text: {snippet}...\n")
    except Exception as e:
        print(f"Semantic search error: {e}")

    # 2. Keyword Search (Elasticsearch)
    print("\n--- 2. KEYWORD BM25 SEARCH (Elasticsearch) ---")
    try:
        es = ElasticsearchService(
            host=settings.ELASTICSEARCH_HOST,
            port=settings.ELASTICSEARCH_PORT,
            index_name=settings.ELASTICSEARCH_INDEX,
            password=settings.ELASTICSEARCH_PASSWORD,
        )
        es_hits = es.search(query=query, top_k=top_k)
        if not es_hits:
            print("No keyword results found.")
        for idx, hit in enumerate(es_hits, 1):
            print(f"[{idx}] Score: {hit.get('_score', 0):.4f} | Chunk ID: {hit.get('chunk_id')} | Page: {hit.get('page_number')}")
            snippet = hit.get("text", "")[:180].replace("\n", " ")
            print(f"     Text: {snippet}...\n")
    except Exception as e:
        print(f"Keyword search error: {e}")

    print("=" * 70)


if __name__ == "__main__":
    main()
