from __future__ import annotations

import re
from typing import List

from ...types import EvidenceContext, ReasoningResult, StructuredRequest
from .base import BaseVerifier


class RuleBasedVerifier(BaseVerifier):
    """
    Simple rule-based checks for formatting and sign consistency.
    """

    def verify(
        self,
        request: StructuredRequest,
        reasoning_result: ReasoningResult,
        evidence_context: EvidenceContext | None,
    ) -> List[str]:
        issues: List[str] = []
        answer = reasoning_result.answer.strip()

        if answer and not re.match(r"^-?\d+(\.\d+)?( million| billion| thousand|%)?$", answer, re.IGNORECASE):
            issues.append("Answer format unexpected (expect numeric with optional scale).")

        if answer.startswith("-") and "decrease" not in reasoning_result.reasoning.lower():
            issues.append("Negative answer but reasoning does not mention decrease.")

        return issues
