from __future__ import annotations

import os
from typing import List

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from ...types import EvidenceContext, ReasoningResult, StructuredRequest
from .base import BaseVerifier


class LLMConsistencyVerifier(BaseVerifier):
    """
    Optional micro-LLM consistency check (falls back to heuristics).
    """

    def __init__(self) -> None:
        self._enabled = os.getenv("FINBOUND_ENABLE_LLM_VERIFIER", "0").lower() in (
            "1",
            "true",
            "yes",
        )
        self._model = os.getenv("FINBOUND_LLM_VERIFIER_MODEL", "gpt-4o-mini")
        self._client = OpenAI() if self._enabled and OpenAI else None

    def verify(
        self,
        request: StructuredRequest,
        reasoning_result: ReasoningResult,
        evidence_context: EvidenceContext | None,
    ) -> List[str]:
        issues: List[str] = []
        answer_lower = reasoning_result.answer.lower()
        reasoning_lower = reasoning_result.reasoning.lower()

        if "uncertain" in answer_lower and "uncertain" not in reasoning_lower:
            issues.append("Answer claims uncertainty but reasoning does not justify it.")

        if answer_lower.startswith("-") and "increase" in reasoning_lower:
            issues.append("Sign mismatch: answer negative but reasoning says increase.")

        if self._client and evidence_context and not issues:
            snippets = "\n".join(f"- {t}" for t in evidence_context.text_blocks[:3])
            prompt = (
                "You are a strict verifier. Determine if the proposed answer is consistent "
                "with the provided evidence. Respond with 'YES' or 'NO'.\n\n"
                f"Evidence:\n{snippets}\n\n"
                f"Answer: {reasoning_result.answer}\nReasoning: {reasoning_result.reasoning}\n"
            )
            try:
                response = self._client.responses.create(
                    model=self._model,
                    input=prompt,
                    max_output_tokens=10,
                )
                decision = (
                    response.output[0].content[0].text.strip()  # type: ignore[attr-defined]
                )
                if "no" in decision.lower():
                    issues.append("LLM verifier flagged inconsistency.")
            except Exception:
                # If verifier fails, fall back to heuristics only
                pass

        return issues
