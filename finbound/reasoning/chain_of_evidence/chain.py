from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .step import EvidenceStep


@dataclass
class ChainOfEvidence:
    """Mutable chain-of-evidence tracker."""

    steps: List[EvidenceStep] = field(default_factory=list)

    def add_step(
        self,
        statement: str,
        citations: Optional[Iterable[str]] = None,
        parent_indices: Optional[Iterable[int]] = None,
        tool_result: Optional[dict] = None,
    ) -> EvidenceStep:
        step = EvidenceStep(
            index=len(self.steps),
            statement=statement.strip(),
            citations=list(citations or []),
            parent_indices=list(parent_indices or []),
            tool_result=tool_result,
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> Dict[str, List[dict]]:
        return {
            "steps": [
                {
                    "index": step.index,
                    "statement": step.statement,
                    "citations": step.citations,
                    "parents": step.parent_indices,
                    "tool_result": step.tool_result,
                }
                for step in self.steps
            ]
        }

