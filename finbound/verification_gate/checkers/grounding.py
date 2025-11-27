from __future__ import annotations

from typing import List

from ...types import EvidenceContext


class GroundingChecker:
    """
    Verifies that citations reference text present in the evidence context.
    """

    def check(self, citations: List[str], context: EvidenceContext | None) -> List[str]:
        if context is None:
            return []
        snippets = set(context.text_blocks)

        issues: List[str] = []
        for citation in citations:
            if citation not in snippets:
                issues.append(f"Citation not found in evidence: {citation[:80]}")
        return issues
