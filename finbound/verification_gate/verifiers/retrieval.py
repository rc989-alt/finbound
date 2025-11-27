from __future__ import annotations

from typing import List

from ...types import EvidenceContext, ReasoningResult, StructuredRequest
from .base import BaseVerifier


class RetrievalVerifier(BaseVerifier):
    """
    Ensures citations map to retrieved evidence.
    """

    def verify(
        self,
        request: StructuredRequest,
        reasoning_result: ReasoningResult,
        evidence_context: EvidenceContext | None,
    ) -> List[str]:
        if evidence_context is None:
            return []

        metadata = evidence_context.metadata or {}
        retrieval_query = metadata.get("retrieval_query")
        if not retrieval_query:
            return ["No retrieval query metadata recorded."]

        issues: List[str] = []
        text_blocks = set(evidence_context.text_blocks)
        for citation in reasoning_result.citations:
            if citation not in text_blocks:
                issues.append(f"Citation not in retrieved snippets: {citation[:80]}")
        return issues
