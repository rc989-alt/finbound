from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..types import EvidenceContext
from ..data.unified import UnifiedSample


@dataclass
class PromptBuilder:
    """
    Build reasoning prompts/evidence contexts from UnifiedSample or raw contexts.
    """

    def from_unified_sample(
        self,
        sample: UnifiedSample,
        question: Optional[str] = None,
    ) -> EvidenceContext:
        context = sample.to_evidence_context()
        if question:
            context.metadata["question_override"] = question
        return context

    def format_for_task_family(self, context: EvidenceContext, task: str) -> str:
        task = task.upper()
        base = context.as_prompt_section()

        if task == "F1":
            return (
                "Task: F1 - Financial Ground-Truth Reasoning\n"
                "Use tables and text to compute numeric answers with citations.\n\n"
                f"{base}"
            )
        if task == "F2":
            return (
                "Task: F2 - Long-Context Retrieval\n"
                "Select and cite the most relevant paragraphs answering the query.\n\n"
                f"{base}"
            )
        if task == "F3":
            return (
                "Task: F3 - Explanation Verification\n"
                "Verify explanations with explicit evidence references.\n\n"
                f"{base}"
            )
        if task == "F4":
            return (
                "Task: F4 - Scenario Consistency Checking\n"
                "Judge scenario narratives against macro/financial context.\n\n"
                f"{base}"
            )
        return base

