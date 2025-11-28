from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .corpus_builder import CorpusDocument


@dataclass
class EvidenceMatch:
    doc_id: str
    score: float
    snippet: str


class EvidenceStore:
    """
    Very small keyword-based evidence store.
    """

    def __init__(self) -> None:
        self._documents: Dict[str, CorpusDocument] = {}

    def add(self, document: CorpusDocument) -> None:
        self._documents[document.doc_id] = document

    def bulk_add(self, documents: List[CorpusDocument]) -> None:
        for document in documents:
            self.add(document)

    def search(self, query: str, top_k: int = 5) -> List[EvidenceMatch]:
        query_terms = set(query.lower().split())
        matches: List[Tuple[float, CorpusDocument]] = []
        for doc in self._documents.values():
            doc_terms = set(doc.text.lower().split())
            overlap = len(query_terms & doc_terms)

            if overlap == 0:
                continue
            score = overlap / (len(query_terms) + 1e-6)
            matches.append((score, doc))

        matches.sort(key=lambda pair: pair[0], reverse=True)
        results: List[EvidenceMatch] = []
        for score, doc in matches[:top_k]:
            snippet = doc.text[:200]
            results.append(EvidenceMatch(doc_id=doc.doc_id, score=score, snippet=snippet))
        return results
