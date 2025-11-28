"""GPT-4 few-shot baseline for fair comparison with FinBound.

This baseline receives the SAME evidence context as FinBound plus
a few demonstration examples, but:
- No verification gates
- No retry mechanism
- No chain-of-evidence tracking
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from finbound.data import UnifiedSample
from finbound.types import EvidenceContext
from .rate_limiter import get_rate_limiter


# Few-shot examples per task family
FEW_SHOT_EXAMPLES = {
    "F1": [
        {
            "question": "What is the year-over-year change in revenue?",
            "evidence": "Revenue was $500M in 2022 and $550M in 2023.",
            "answer": {
                "answer": "$50M increase (10%)",
                "reasoning": "550 - 500 = 50. 50/500 = 0.10 = 10%",
                "citations": ["Revenue was $500M in 2022 and $550M in 2023."],
            },
        },
        {
            "question": "Calculate the gross margin percentage.",
            "evidence": "Revenue: $1,000M. Cost of goods sold: $600M.",
            "answer": {
                "answer": "40%",
                "reasoning": "Gross profit = 1000 - 600 = 400. Margin = 400/1000 = 0.40 = 40%",
                "citations": ["Revenue: $1,000M", "Cost of goods sold: $600M"],
            },
        },
    ],
    "F2": [
        {
            "question": "What are the main risk factors?",
            "evidence": "Risk factors include: (1) market volatility, (2) regulatory changes, (3) supply chain disruption.",
            "answer": {
                "answer": "Market volatility, regulatory changes, and supply chain disruption",
                "reasoning": "The document explicitly lists three risk factors.",
                "citations": ["Risk factors include: (1) market volatility, (2) regulatory changes, (3) supply chain disruption."],
            },
        },
    ],
    "F3": [
        {
            "question": "Explain why net income decreased.",
            "evidence": "Net income fell from $100M to $80M. Operating expenses increased by $30M due to expansion costs.",
            "answer": {
                "answer": "Net income decreased by $20M primarily due to $30M increase in operating expenses from expansion costs.",
                "reasoning": "The $30M expense increase more than explains the $20M income decrease.",
                "citations": ["Net income fell from $100M to $80M", "Operating expenses increased by $30M due to expansion costs"],
            },
        },
    ],
    "F4": [
        {
            "question": "Is the company's optimistic revenue forecast consistent with market conditions?",
            "evidence": "Company forecasts 15% revenue growth. Industry average is 3%. No major product launches planned.",
            "answer": {
                "answer": "Inconsistent - the 15% forecast significantly exceeds the 3% industry average without clear justification.",
                "reasoning": "Without new products or market expansion, 15% growth vs 3% industry average appears unrealistic.",
                "citations": ["Company forecasts 15% revenue growth", "Industry average is 3%", "No major product launches planned"],
            },
        },
    ],
}


class GPT4FewShotBaseline:
    """
    GPT-4 few-shot baseline with task-specific examples.

    Receives identical evidence as FinBound plus demonstration examples.
    No verification, no retry, no chain tracking.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        examples: Optional[Dict[str, List[Dict]]] = None,
    ) -> None:
        self._client = OpenAI()
        self._model = model
        self._examples = examples or FEW_SHOT_EXAMPLES
        self._limiter = get_rate_limiter()

    def run(
        self,
        sample: UnifiedSample,
        evidence_context: EvidenceContext,
        task_family: str,
    ) -> Dict[str, Any]:
        """Run few-shot inference."""
        messages = self._build_messages(sample.question, evidence_context, task_family)

        response = self._limiter.call(
            self._client.chat.completions.create,
            model=self._model,
            messages=messages,
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

    def _build_messages(
        self,
        question: str,
        evidence: EvidenceContext,
        task_family: str,
    ) -> List[Dict[str, str]]:
        """Build message list with few-shot examples."""
        messages = [
            {"role": "system", "content": self._build_system_prompt(task_family)},
        ]

        # Add few-shot examples
        examples = self._examples.get(task_family, [])
        for ex in examples:
            messages.append({
                "role": "user",
                "content": f"Question: {ex['question']}\n\nEvidence: {ex['evidence']}\n\nRespond with JSON.",
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(ex["answer"]),
            })

        # Add actual question
        messages.append({
            "role": "user",
            "content": f"Question: {question}\n\n{evidence.as_prompt_section()}\n\nRespond with JSON only.",
        })

        return messages

    def _build_system_prompt(self, task_family: str) -> str:
        return (
            "You are a financial analyst assistant. Answer questions using only "
            "the provided evidence. Follow the format shown in the examples.\n\n"
            "Return your response as JSON with keys:\n"
            "- answer: your final answer\n"
            "- reasoning: brief explanation\n"
            "- citations: list of evidence snippets you used"
        )

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response."""
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


def create_runner(model: str = "gpt-4o"):
    """Factory function for eval harness registration."""
    baseline = GPT4FewShotBaseline(model=model)
    return baseline.run
