"""FinBound runner for evaluation harness.

This wraps FinBound to match the eval harness interface, enabling
fair comparison against baselines.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from finbound import FinBound
from finbound.data import UnifiedSample
from finbound.data.index.evidence_store import EvidenceStore
from finbound.types import EvidenceContext


class FinBoundRunner:
    """
    FinBound runner for evaluation harness.

    Unlike baselines, FinBound includes:
    - Verification gates (grounding, consistency, etc.)
    - Retry mechanism on verification failure
    - Chain-of-evidence tracking
    - Layer-1 guardrails
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        max_retries: int = 2,
        evidence_store: Optional[EvidenceStore] = None,
        low_latency_mode: bool = False,
    ) -> None:
        self._finbound = FinBound(
            model=model,
            max_retries=max_retries,
            evidence_store=evidence_store,
            low_latency_mode=low_latency_mode,
        )

    def run(
        self,
        sample: UnifiedSample,
        evidence_context: EvidenceContext,
        task_family: str,
    ) -> Dict[str, Any]:
        """Run FinBound with full verification pipeline."""
        # Use run_unified_sample if available, else standard run
        if hasattr(self._finbound, "run_unified_sample"):
            result = self._finbound.run_unified_sample(sample, task_family=task_family)
        else:
            result = self._finbound.run(sample.question, evidence_context=evidence_context)

        return {
            "answer": result.answer,
            "citations": result.citations,
            "verified": result.verified,
            "raw_output": result.raw_model_output,
        }


def create_runner(
    model: str = "gpt-4o",
    max_retries: int = 2,
    evidence_store: Optional[EvidenceStore] = None,
    low_latency_mode: bool = False,
):
    """Factory function for eval harness registration."""
    runner = FinBoundRunner(
        model=model,
        max_retries=max_retries,
        evidence_store=evidence_store,
        low_latency_mode=low_latency_mode,
    )
    return runner.run
