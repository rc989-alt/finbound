"""Unified sample type for cross-dataset evaluation.

This module provides a common interface for samples from FinQA, TAT-QA,
and SEC filings, enabling consistent evaluation across all task families.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Union

from .loaders.finqa import FinQASample
from .loaders.tatqa import TATQASample


@dataclass
class UnifiedSample:
    """
    Unified sample format for all FinBound datasets.

    This provides a consistent interface for:
    - F1: Financial Ground-Truth Reasoning (table-text numerical QA)
    - F2: Long-Context Retrieval (evidence selection from full filings)
    - F3: Explanation Verification (evidence-linked justification)
    - F4: Scenario Consistency Checking (macro/financial narrative alignment)
    """

    # Core fields
    id: str
    question: str
    gold_answer: str
    source: Literal["finqa", "tatqa", "sec"]

    # Evidence
    text_evidence: List[str]
    table_evidence: List[List[str]]

    # Answer metadata
    answer_type: str  # span, multi-span, count, arithmetic, numeric, text
    scale: str  # "", thousand, million, billion, percent
    derivation: str  # arithmetic expression if applicable

    # Provenance
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_table(self) -> bool:
        return len(self.table_evidence) > 0

    @property
    def has_text(self) -> bool:
        return len(self.text_evidence) > 0

    @property
    def evidence_type(self) -> Literal["table", "text", "table-text"]:
        if self.has_table and self.has_text:
            return "table-text"
        elif self.has_table:
            return "table"
        return "text"

    def to_evidence_context(self) -> "EvidenceContext":
        """Convert to EvidenceContext for use with FinBound pipeline."""
        from ..types import EvidenceContext

        return EvidenceContext(
            text_blocks=self.text_evidence,
            tables=self.table_evidence,
            metadata={
                "source": self.source,
                "sample_id": self.id,
                **self.metadata,
            },
        )


def to_unified(sample: Union[FinQASample, TATQASample]) -> UnifiedSample:
    """Convert a dataset-specific sample to UnifiedSample."""
    if isinstance(sample, FinQASample):
        return _from_finqa(sample)
    elif isinstance(sample, TATQASample):
        return _from_tatqa(sample)
    else:
        raise TypeError(f"Cannot convert {type(sample)} to UnifiedSample")


def _from_finqa(sample: FinQASample) -> UnifiedSample:
    """Convert FinQASample to UnifiedSample."""
    # Combine context snippets and evidence texts
    text_evidence = list(sample.context_snippets)
    if sample.evidence_texts:
        text_evidence.extend(sample.evidence_texts)

    # Determine answer type from program
    answer_type = "arithmetic" if sample.program else "span"

    return UnifiedSample(
        id=sample.id,
        question=sample.question,
        gold_answer=sample.answer,
        source="finqa",
        text_evidence=text_evidence,
        table_evidence=sample.table,
        answer_type=answer_type,
        scale="",
        derivation=sample.program,
        metadata={
            "filename": sample.filename,
            "issuer": sample.issuer,
            "steps": sample.steps,
            "program_result": sample.program_result,
        },
    )


def _from_tatqa(sample: TATQASample) -> UnifiedSample:
    """Convert TATQASample to UnifiedSample."""
    return UnifiedSample(
        id=sample.question_id,
        question=sample.question,
        gold_answer=sample.answer,
        source="tatqa",
        text_evidence=sample.paragraphs,
        table_evidence=sample.table,
        answer_type=sample.answer_type,
        scale=sample.scale,
        derivation=sample.derivation,
        metadata={
            "table_id": sample.table_id,
            "doc_id": sample.doc_id,
            "answer_from": sample.answer_from,
        },
    )
