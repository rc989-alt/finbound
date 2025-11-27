from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ...types import EvidenceContext, FinBoundResult


@dataclass
class StageIssue:
    stage: str
    message: str


class Layer2StageGate:
    """
    Stage-critical gate checks: evidence selection, arithmetic aggregation, etc.
    """

    def __init__(self) -> None:
        self._issues: List[StageIssue] = []

    @property
    def issues(self) -> List[StageIssue]:
        return self._issues

    def reset(self) -> None:
        self._issues.clear()

    def check_evidence_selection(self, context: EvidenceContext) -> None:
        if not context.text_blocks and not context.tables:
            self._issues.append(
                StageIssue(stage="evidence_selection", message="No evidence provided.")
            )

    def check_arithmetic_stage(self, reasoning_output: Dict) -> None:
        chain = reasoning_output.get("chain_of_evidence", {}).get("steps", [])
        if not chain:
            self._issues.append(
                StageIssue(
                    stage="arithmetic",
                    message="No chain of evidence captured for arithmetic validation.",
                )
            )
            return

        final_step = chain[-1]
        if "result" in (final_step.get("tool_result") or {}):
            if not final_step.get("citations"):
                self._issues.append(
                    StageIssue(
                        stage="arithmetic",
                        message="Arithmetic step missing citations.",
                    )
                )
