from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StructuredRequest:
    raw_text: str
    scenario: Optional[str] = None
    period: Optional[str] = None
    periods_detected: List[str] = field(default_factory=list)
    time_horizon: Optional[str] = None
    metrics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    risk_terms: List[str] = field(default_factory=list)
    requested_operations: List[str] = field(default_factory=list)


@dataclass
class PolicyVerdict:
    approved: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class EvidenceContract:
    description: str
    required_citations: int = 1


@dataclass
class EvidenceContext:
    """
    Collection of textual and tabular evidence used by the reasoning engine.
    """

    text_blocks: List[str] = field(default_factory=list)
    tables: List[List[str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_prompt_section(self) -> str:
        sections: List[str] = []

        if self.text_blocks:
            sections.append(
                "Evidence Text:\n"
                + "\n".join(f"- {block}" for block in self.text_blocks)
            )

        if self.tables:
            formatted_rows = []
            for row in self.tables:
                formatted_rows.append("  | " + " | ".join(str(cell) for cell in row) + " |")
            sections.append("Evidence Tables:\n" + "\n".join(formatted_rows))

        if self.metadata:
            meta_lines = [f"{key}: {value}" for key, value in self.metadata.items()]
            sections.append("Metadata:\n" + "\n".join(meta_lines))

        return "\n\n".join(sections)


@dataclass
class ReasoningResult:
    answer: str
    reasoning: str
    citations: List[str]
    raw_model_output: Dict[str, Any]


@dataclass
class VerificationResult:
    verified: bool
    issues: List[str] = field(default_factory=list)
    status: str = "PASS"


@dataclass
class FinBoundResult:
    answer: str
    verified: bool
    citations: List[str]
    reasoning: str
    policy_verdict: PolicyVerdict
    verification_result: VerificationResult
    raw_model_output: Dict[str, Any]
