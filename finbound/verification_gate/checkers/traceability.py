from __future__ import annotations

from typing import List

from ...types import ReasoningResult


class TraceabilityChecker:
    """
    Ensures chain-of-evidence metadata is present for audit.
    """

    def check(self, reasoning_result: ReasoningResult) -> List[str]:
        trace = reasoning_result.raw_model_output.get("chain_of_evidence")
        if not trace or not trace.get("steps"):
            return ["Missing chain-of-evidence for traceability."]
        return []
