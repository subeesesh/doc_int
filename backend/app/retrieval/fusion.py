from typing import List, Dict, Optional
from app.retrieval.base import RetrievalResult, RetrievalSource

def reciprocal_rank_fusion(
    result_lists: List[List[RetrievalResult]], 
    k: int = 60, 
    weights: Optional[Dict[RetrievalSource, float]] = None
) -> List[RetrievalResult]:
    """Fuse multiple ranked lists using RRF"""
    if weights is None:
        weights = {
            RetrievalSource.ELASTIC: 1.0, 
            RetrievalSource.VECTOR: 1.0, 
            RetrievalSource.GRAPH: 0.5
        }
    
    scores: Dict[str, float] = {}  # chunk_id -> fused_score
    result_map: Dict[str, RetrievalResult] = {}  # chunk_id -> best RetrievalResult
    
    for results in result_lists:
        source = results[0].source if results else None
        weight = weights.get(source, 1.0) if source else 1.0
        for rank, result in enumerate(results):
            rrf_score = weight * (1.0 / (k + rank + 1))
            if result.chunk_id in scores:
                scores[result.chunk_id] += rrf_score
            else:
                scores[result.chunk_id] = rrf_score
                result_map[result.chunk_id] = result
    
    # Sort by fused score
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    fused = []
    for chunk_id in sorted_ids:
        r = result_map[chunk_id].model_copy()
        r.score = scores[chunk_id]
        r.source = RetrievalSource.HYBRID
        fused.append(r)
    return fused
