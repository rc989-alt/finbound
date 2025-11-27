from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvidenceStep:
    """Representation of a single reasoning step tied to evidence."""

    index: int
    statement: str
    citations: List[str] = field(default_factory=list)
    parent_indices: List[int] = field(default_factory=list)
    tool_result: Optional[dict] = None

    def add_citation(self, citation: str) -> None:
        if citation not in self.citations:
            self.citations.append(citation)

