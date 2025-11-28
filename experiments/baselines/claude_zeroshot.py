"""Claude zero-shot baseline for comparison with FinBound.

Uses the Anthropic API with Claude models.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import anthropic

from finbound.data import UnifiedSample
from finbound.types import EvidenceContext
from .rate_limiter import get_rate_limiter


class ClaudeZeroShotBaseline:
    """
    Claude zero-shot baseline.

    Uses Anthropic's Claude API.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self._client = anthropic.Anthropic(api_key=api_key)
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
            self._client.messages.create,
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.content[0].text if response.content else ""
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


def create_runner(model: str = "claude-sonnet-4-20250514"):
    """Factory function for eval harness registration."""
    baseline = ClaudeZeroShotBaseline(model=model)
    return baseline.run
