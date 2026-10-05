from typing import List
from app.retrieval.base import RetrievalResult
import re

class ScoreReranker:
    """A lightweight text overlap based reranker."""
    def __init__(self):
        pass

    def rerank(self, query: str, results: List[RetrievalResult], top_k: int) -> List[RetrievalResult]:
        if not results:
            return []

        # Simple text overlap scoring
        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return results[:top_k]

        scored_results = []
        max_score = 0.0

        for res in results:
            text_terms = set(re.findall(r'\w+', res.text.lower()))
            overlap = len(query_terms.intersection(text_terms))
            # Calculate a normalized overlap score
            overlap_score = overlap / len(query_terms)
            
            # Combine original score (normalized assumption or naive weighted addition)
            # In a real system, you'd normalize original scores before adding
            combined_score = (res.score * 0.5) + (overlap_score * 0.5)
            
            if combined_score > max_score:
                max_score = combined_score
                
            scored_results.append((combined_score, res))

        # Normalize final scores to 0-1
        normalized_results = []
        for score, res in scored_results:
            final_score = score / max_score if max_score > 0 else 0.0
            r = res.model_copy()
            r.score = final_score
            normalized_results.append(r)

        # Sort by new score
        normalized_results.sort(key=lambda x: x.score, reverse=True)
        return normalized_results[:top_k]
