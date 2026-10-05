"""Test hybrid retrieval (BM25 + Vector + Graph + RRF + Reranker)."""
import sys
from app.retrieval.base import RetrievalRequest, RetrievalSource
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.elasticsearch_retriever import ElasticsearchRetriever
from app.retrieval.qdrant_retriever import QdrantRetriever
from app.retrieval.neo4j_retriever import Neo4jRetriever
from app.search.elasticsearch import ElasticsearchService
from app.vectorstore.qdrant_client import qdrant_service
from app.embeddings.embedding_service import embedding_service
from app.graph.neo4j_client import Neo4jService
from app.config.settings import settings


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "How many annual leave days does an employee receive?"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print("=" * 70)
    print(f"HYBRID RETRIEVAL TEST - Query: '{query}'")
    print("=" * 70)

    es_service = ElasticsearchService(
        host=settings.ELASTICSEARCH_HOST,
        port=settings.ELASTICSEARCH_PORT,
        index_name=settings.ELASTICSEARCH_INDEX,
        password=settings.ELASTICSEARCH_PASSWORD,
    )
    neo4j = Neo4jService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)

    retriever = HybridRetriever(
        es_retriever=ElasticsearchRetriever(es_service),
        qdrant_retriever=QdrantRetriever(qdrant_service, embedding_service),
        neo4j_retriever=Neo4jRetriever(neo4j),
    )

    req = RetrievalRequest(
        query=query,
        top_k=top_k,
        sources=[RetrievalSource.ELASTIC, RetrievalSource.VECTOR, RetrievalSource.GRAPH],
        enable_reranking=True,
    )

    resp = retriever.retrieve(req)

    print(f"Sources used:     {[s.value for s in resp.sources_used]}")
    print(f"Total candidates: {resp.total_candidates}")
    print(f"Latency:          {resp.latency_ms:.2f} ms")
    print(f"Results returned: {len(resp.results)}")
    print("-" * 70)

    for idx, r in enumerate(resp.results, start=1):
        print(f"[{idx}] Score: {r.score:.4f} | Source: {r.source.value} | Page: {r.page_number} | Chunk: {r.chunk_index}")
        snippet = r.text[:200].replace("\n", " ")
        print(f"     Text: {snippet}...\n")

    print("=" * 70)


if __name__ == "__main__":
    main()
