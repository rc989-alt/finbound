"""DeepSeek zero-shot baseline for comparison with FinBound.

Uses the DeepSeek API (OpenAI-compatible) with deepseek-chat model.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from finbound.data import UnifiedSample
from finbound.types import EvidenceContext
from .rate_limiter import get_rate_limiter


class DeepSeekZeroShotBaseline:
    """
    DeepSeek zero-shot baseline.

    Uses DeepSeek's OpenAI-compatible API endpoint.
    """

    def __init__(self, model: str = "deepseek-chat") -> None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self._model = model
        self._limiter = get_rate_limiter()

    def run(
        self,
        sample: UnifiedSample,
        evidence_context: EvidenceContext,
        task_family: str,
    ) -> Dict[str, Any]:
        """Run zero-shot inference."""
        system_prompt = self._build_system_prompt(task_family)
        user_prompt = self._build_user_prompt(sample.question, evidence_context)

        response = self._limiter.call(
            self._client.chat.completions.create,
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content or ""
        parsed = self._parse_response(content)

        return {
            "answer": parsed.get("answer", content),
            "citations": parsed.get("citations", []),
            "verified": None,
            "raw_output": {"completion": response.model_dump()},
        }

    def _build_system_prompt(self, task_family: str) -> str:
        base = (
            "You are a financial analyst assistant. Answer questions using only "
            "the provided evidence. If you cannot answer from the evidence, say 'uncertain'.\n\n"
            "Return your response as JSON with keys:\n"
            "- answer: your final answer\n"
            "- reasoning: brief explanation\n"
            "- citations: list of evidence snippets you used"
        )

        task_instructions = {
            "F1": "Focus on numerical accuracy. Show your calculations.",
            "F2": "Select and cite the most relevant passages.",
            "F3": "Provide detailed justification with evidence references.",
            "F4": "Assess consistency with the financial scenario described.",
        }

        return f"{base}\n\nTask: {task_instructions.get(task_family, '')}"

    def _build_user_prompt(self, question: str, evidence: EvidenceContext) -> str:
        evidence_section = evidence.as_prompt_section()
        return f"Question: {question}\n\n{evidence_section}\n\nRespond with JSON only."

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response, handling markdown fences."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines)

        try:
            parsed = json.loads(text)
            citations = parsed.get("citations", [])
            if isinstance(citations, str):
                citations = [citations] if citations else []
            return {"answer": str(parsed.get("answer", "")), "citations": citations}
        except json.JSONDecodeError:
            return {"answer": content, "citations": []}


def create_runner(model: str = "deepseek-chat"):
    """Factory function for eval harness registration."""
    baseline = DeepSeekZeroShotBaseline(model=model)
    return baseline.run
