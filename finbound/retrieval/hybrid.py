from __future__ import annotations

from typing import Dict, List, Optional

from .query_builder import build_query
from ..data.index.evidence_store import EvidenceStore


class HybridRetriever:
    """
    Simple hybrid retriever that combines lexical overlap with store scores.
    """

    def __init__(self, evidence_store: EvidenceStore, top_k: int = 5) -> None:
        self.store = evidence_store
        self.top_k = top_k

    def search(self, query_spec: Dict) -> List[str]:
        query_text = query_spec.get("query_text", "")
        keywords = [kw.lower() for kw in query_spec.get("keywords", [])]
        matches = self.store.search(query_text, top_k=self.top_k * 3)
        ranked = sorted(
            matches,
            key=lambda match: self._score_match(match.snippet, keywords, match.score),
            reverse=True,
        )
        return [m.snippet for m in ranked[: self.top_k]]

    def _score_match(self, snippet: str, keywords: List[str], base_score: float) -> float:
        snippet_lower = snippet.lower()
        overlap = sum(1 for kw in keywords if kw and kw in snippet_lower)
        return base_score + overlap
