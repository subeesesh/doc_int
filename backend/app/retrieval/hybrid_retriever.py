import time
import logging
from typing import List
from app.retrieval.base import RetrievalRequest, RetrievalResponse, RetrievalResult, RetrievalSource
from app.retrieval.elasticsearch_retriever import ElasticsearchRetriever
from app.retrieval.qdrant_retriever import QdrantRetriever
from app.retrieval.neo4j_retriever import Neo4jRetriever
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import ScoreReranker

logger = logging.getLogger(__name__)

class HybridRetriever:
    def __init__(
        self,
        es_retriever: ElasticsearchRetriever,
        qdrant_retriever: QdrantRetriever,
        neo4j_retriever: Neo4jRetriever
    ):
        self.es_retriever = es_retriever
        self.qdrant_retriever = qdrant_retriever
        self.neo4j_retriever = neo4j_retriever
        self.reranker = ScoreReranker()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        start_time = time.perf_counter()
        
        result_lists: List[List[RetrievalResult]] = []
        sources_used: List[RetrievalSource] = []
        
        # Execute Elasticsearch
        if RetrievalSource.ELASTIC in request.sources:
            try:
                es_res = self.es_retriever.retrieve(
                    query=request.query,
                    top_k=request.top_k * 2,  # Fetch more for fusion/reranking
                    document_ids=request.document_ids,
                    user_id=request.user_id
                )
                if es_res:
                    result_lists.append(es_res)
                    sources_used.append(RetrievalSource.ELASTIC)
            except Exception as e:
                logger.error(f"Elasticsearch retriever failed: {e}")

        # Execute Qdrant
        if RetrievalSource.VECTOR in request.sources:
            try:
                vec_res = self.qdrant_retriever.retrieve(
                    query=request.query,
                    top_k=request.top_k * 2,
                    document_ids=request.document_ids,
                    user_id=request.user_id
                )
                if vec_res:
                    result_lists.append(vec_res)
                    sources_used.append(RetrievalSource.VECTOR)
            except Exception as e:
                logger.error(f"Qdrant retriever failed: {e}")

        # Execute Neo4j
        if RetrievalSource.GRAPH in request.sources:
            try:
                graph_res = self.neo4j_retriever.retrieve(
                    query=request.query,
                    top_k=request.top_k,
                    document_ids=request.document_ids
                )
                if graph_res:
                    result_lists.append(graph_res)
                    sources_used.append(RetrievalSource.GRAPH)
            except Exception as e:
                logger.error(f"Neo4j retriever failed: {e}")

        # Reciprocal Rank Fusion
        fused_results = reciprocal_rank_fusion(result_lists)
        total_candidates = len(fused_results)

        # Reranking
        if request.enable_reranking and fused_results:
            try:
                final_results = self.reranker.rerank(request.query, fused_results, request.top_k)
            except Exception as e:
                logger.error(f"Reranking failed: {e}. Falling back to fused results.")
                final_results = fused_results[:request.top_k]
        else:
            final_results = fused_results[:request.top_k]

        latency_ms = (time.perf_counter() - start_time) * 1000

        return RetrievalResponse(
            results=final_results,
            query=request.query,
            sources_used=sources_used,
            total_candidates=total_candidates,
            latency_ms=latency_ms
        )
