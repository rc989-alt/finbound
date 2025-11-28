"""RAG baseline without verification gates.

This baseline implements a standard RAG pipeline:
- Evidence retrieval (same as FinBound)
- LLM reasoning with retrieved context
- NO verification gates
- NO retry mechanism
- NO chain-of-evidence tracking

This isolates the contribution of FinBound's verification-gated approach.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from finbound.data import UnifiedSample
from finbound.data.index.evidence_store import EvidenceStore
from finbound.retrieval.query_builder import build_query
from finbound.types import EvidenceContext, StructuredRequest
from .rate_limiter import get_rate_limiter


class RAGNoVerifyBaseline:
    """
    Standard RAG baseline without verification.

    Pipeline:
    1. Parse request → structured query
    2. Retrieve from evidence store (if provided)
    3. Augment context with retrieved snippets
    4. LLM generates answer
    5. Return (NO verification step)
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        evidence_store: Optional[EvidenceStore] = None,
        top_k: int = 5,
    ) -> None:
        self._client = OpenAI()
        self._model = model
        self._evidence_store = evidence_store
        self._top_k = top_k
        self._limiter = get_rate_limiter()

    def run(
        self,
        sample: UnifiedSample,
        evidence_context: EvidenceContext,
        task_family: str,
    ) -> Dict[str, Any]:
        """Run RAG pipeline without verification."""
        # Step 1: Build retrieval query
        structured = StructuredRequest(raw_text=sample.question)
        query_spec = build_query(structured)

        # Step 2: Retrieve additional evidence (if store available)
        retrieved_snippets = self._retrieve(query_spec)

        # Step 3: Augment context
        augmented_context = self._augment_context(evidence_context, retrieved_snippets)

        # Step 4: Generate answer
        response = self._generate(sample.question, augmented_context, task_family)

        # Step 5: Return WITHOUT verification
        return {
            "answer": response.get("answer", ""),
            "citations": response.get("citations", []),
            "verified": None,  # No verification in this baseline
            "raw_output": {
                "completion": response.get("raw", {}),
                "retrieved_snippets": retrieved_snippets,
            },
        }

    def _retrieve(self, query_spec: Dict[str, Any]) -> List[str]:
        """Retrieve evidence snippets."""
        if not self._evidence_store:
            return []

        query_text = query_spec.get("query_text", "")
        if not query_text:
            return []

        matches = self._evidence_store.search(query_text, top_k=self._top_k)
        return [m.snippet for m in matches]

    def _augment_context(
        self,
        base_context: EvidenceContext,
        retrieved: List[str],
    ) -> EvidenceContext:
        """Merge retrieved snippets into context."""
        text_blocks = list(base_context.text_blocks)
        for snippet in retrieved:
            if snippet not in text_blocks:
                text_blocks.append(snippet)

        return EvidenceContext(
            text_blocks=text_blocks,
            tables=base_context.tables,
            metadata={**base_context.metadata, "retrieved_count": len(retrieved)},
        )

    def _generate(
        self,
        question: str,
        context: EvidenceContext,
        task_family: str,
    ) -> Dict[str, Any]:
        """Generate answer using LLM."""
        system_prompt = (
            "You are a financial analyst. Answer the question using only the "
            "provided evidence. Show your reasoning and cite your sources.\n\n"
            "Return JSON with keys: answer, reasoning, citations"
        )

        user_prompt = f"Question: {question}\n\n{context.as_prompt_section()}\n\nRespond with JSON only."

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
            "raw": response.model_dump(),
        }

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


def create_runner(
    model: str = "gpt-4o",
    evidence_store: Optional[EvidenceStore] = None,
):
    """Factory function for eval harness registration."""
    baseline = RAGNoVerifyBaseline(model=model, evidence_store=evidence_store)
    return baseline.run
