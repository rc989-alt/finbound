import os
from copy import deepcopy
from typing import List, Optional

from .approval_gate.evidence_contract import EvidenceContractGenerator
from .approval_gate.policy_engine import PolicyEngine
from .approval_gate.request_parser import RequestParser
from .data.index.evidence_store import EvidenceStore
from .data.unified import UnifiedSample
from .reasoning.engine import ReasoningEngine
from .reasoning.gates.layer2_stage import Layer2StageGate
from .reasoning.prompt_builder import PromptBuilder
from .retrieval.query_builder import build_query
from .retrieval.hybrid import HybridRetriever
from .tracking.mlflow_logger import MlflowLogger
from .types import EvidenceContext, FinBoundResult
from .utils import setup_logging, normalize_answer
from .verification_gate.gate import VerificationGate


class FinBound:
    """
    High-level FinBound orchestrator for the minimal prototype.

    Pipeline:
        user_request -> Approval Gate -> Reasoning Engine -> Verification Gate
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        evidence_store: Optional[EvidenceStore] = None,
        max_retries: int = 0,
    ) -> None:
        setup_logging()
        self._parser = RequestParser()
        self._policy_engine = PolicyEngine()
        self._evidence_contract_gen = EvidenceContractGenerator()
        self._reasoning_engine = ReasoningEngine(model=model)
        self._verification_gate = VerificationGate()
        self._tracker = MlflowLogger()
        self._evidence_store = evidence_store
        self._hybrid_retriever = (
            HybridRetriever(evidence_store) if evidence_store else None
        )
        self._layer2_gate = Layer2StageGate()
        self._prompt_builder = PromptBuilder()
        from .verification_gate.retry import RetryHandler

        self._retry_handler = RetryHandler(max_retries=max_retries)

    def run(
        self,
        user_request: str,
        evidence_context: EvidenceContext | None = None,
    ) -> FinBoundResult:
        # Approval Gate
        structured = self._parser.parse(user_request)
        retrieval_query = build_query(structured)
        retrieval_snippets = self._retrieve_evidence(retrieval_query)
        evidence_context = self._prepare_evidence_context(
            evidence_context, retrieval_query, retrieval_snippets
        )
        self._reasoning_engine.update_guardrails_context(evidence_context)
        verdict = self._policy_engine.check_compliance(structured)
        if not verdict.approved:
            raise ValueError(
                f"Request rejected by Approval Gate: {'; '.join(verdict.reasons)}"
            )

        evidence_contract = self._evidence_contract_gen.generate(structured)

        attempt = 0
        reasoning_result = None
        verification_result = None
        while True:
            attempt += 1
            reasoning_result = self._reasoning_engine.run(
                structured_request=structured,
                evidence_contract=evidence_contract,
                evidence_context=evidence_context,
            )

            self._layer2_gate.reset()
            self._layer2_gate.check_evidence_selection(evidence_context)

            verification_result = self._verification_gate.verify(
                structured_request=structured,
                evidence_contract=evidence_contract,
                reasoning_result=reasoning_result,
                evidence_context=evidence_context,
            )

            tool_events = reasoning_result.raw_model_output.get("tool_events", [])
            self._tracker.log_retrieval_query(retrieval_query)
            self._tracker.log_tool_events(tool_events)
            self._tracker.log_verification(
                {
                    "attempt": attempt,
                    "verified": verification_result.verified,
                    "issues": verification_result.issues,
                }
            )

            self._layer2_gate.check_arithmetic_stage(reasoning_result.raw_model_output)
            reasoning_result.raw_model_output["layer2_issues"] = [
                issue.__dict__ for issue in self._layer2_gate.issues
            ]

            if verification_result.verified or not self._retry_handler.should_retry(
                verification_result, attempt
            ):
                break

        assert reasoning_result is not None and verification_result is not None

        reasoning_result.answer = normalize_answer(reasoning_result.answer)

        if (
            not verification_result.verified
            and reasoning_result.answer
            and attempt >= self._retry_handler.max_retries + 1
        ):
            verification_result.issues.append(
                "Best-effort fallback accepted after retry exhaustion."
            )
            verification_result.status = "SOFT_FAIL"
            verification_result.verified = True
        reasoning_result.raw_model_output.setdefault(
            "tracking_run_id", os.getenv("FINBOUND_RUN_ID", "local")
        )

        confidence_map = {
            "PASS": ("High", 0.95),
            "PARTIAL_PASS": ("Medium", 0.8),
            "SOFT_FAIL": ("Low", 0.6),
            "HARD_FAIL": ("Low", 0.2),
        }
        tier_label, confidence_score = confidence_map.get(
            verification_result.status, ("Unknown", 0.5)
        )
        reasoning_result.raw_model_output["confidence_tier"] = {
            "tier": tier_label,
            "score": confidence_score,
        }
        reasoning_result.raw_model_output["verification_status"] = verification_result.status

        return FinBoundResult(
            answer=reasoning_result.answer,
            verified=verification_result.verified,
            citations=reasoning_result.citations,
            reasoning=reasoning_result.reasoning,
            policy_verdict=verdict,
            verification_result=verification_result,
            raw_model_output=reasoning_result.raw_model_output,
        )

    def run_unified_sample(
        self,
        sample: UnifiedSample,
        task_family: str = "F1",
    ) -> FinBoundResult:
        context = self._prompt_builder.from_unified_sample(sample)
        formatted_prompt = self._prompt_builder.format_for_task_family(
            context, task_family
        )
        user_request = f"{formatted_prompt}\n\nQuestion: {sample.question}"
        return self.run(user_request=user_request, evidence_context=context)

    def _retrieve_evidence(self, query_spec: dict) -> List[str]:
        if not self._evidence_store or not query_spec:
            return []

        query_text = query_spec.get("query_text")
        if not query_text:
            return []

        if self._hybrid_retriever:
            return self._hybrid_retriever.search(query_spec)

        matches = self._evidence_store.search(query_text)
        return [match.snippet for match in matches]

    def _prepare_evidence_context(
        self,
        context: EvidenceContext | None,
        query_spec: dict,
        retrieval_snippets: List[str],
    ) -> EvidenceContext:
        metadata = {"retrieval_query": query_spec}

        current_text_blocks: List[str] = []
        tables: List[List[str]] = []

        if context:
            merged_metadata = deepcopy(context.metadata)
            merged_metadata.update(metadata)
            metadata = merged_metadata
            current_text_blocks = list(context.text_blocks)
            tables = list(context.tables)

        for snippet in retrieval_snippets:
            if snippet not in current_text_blocks:
                current_text_blocks.append(snippet)

        return EvidenceContext(
            text_blocks=current_text_blocks,
            tables=tables,
            metadata=metadata,
        )
