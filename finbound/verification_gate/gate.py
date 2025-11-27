from __future__ import annotations

import logging
import os
from typing import List, Optional

from ..tools.calculator import Calculator
from ..types import (
    EvidenceContext,
    EvidenceContract,
    ReasoningResult,
    StructuredRequest,
    VerificationResult,
)
from .checkers import GroundingChecker, ScenarioChecker, TraceabilityChecker
from .numeric_checker import NumericChecker
from .verifiers import (
    LLMConsistencyVerifier,
    RetrievalVerifier,
    RuleBasedVerifier,
)
from ..routing.layer0_checks import run_layer0_checks
from ..routing.layer1 import Layer1Input, run_layer1
from ..correction.layer2 import Layer2Input, Layer2Corrector, should_trigger_layer2

logger = logging.getLogger(__name__)


class VerificationGate:
    """
    Verification gate with fast-path optimization.

    For high-confidence answers (Layer 0 fast_path_eligible=True), skip expensive
    Layer 1 and LLM verification to reduce latency.

    Checks:
      - Answer is non-empty.
      - Number of citations >= evidence_contract.required_citations.
      - Reasoning is present.
    """

    def __init__(self) -> None:
        self._calculator = Calculator()
        self._numeric_checker = NumericChecker(self._calculator)
        self._grounding_checker = GroundingChecker()
        self._scenario_checker = ScenarioChecker()
        self._traceability_checker = TraceabilityChecker()
        self._rule_verifier = RuleBasedVerifier()
        self._retrieval_verifier = RetrievalVerifier()
        self._llm_verifier = LLMConsistencyVerifier()
        self._layer2_corrector = Layer2Corrector()
        # Allow early-exit from expensive verification when Layer 0 passes with
        # high confidence. Enabled by default for latency optimization.
        self._enable_fast_path = os.getenv(
            "FINBOUND_FAST_PATH_VERIFICATION", "1"
        ).lower() in ("1", "true", "yes")
        # Legacy: allow early-exit from expensive LLM verification when
        # all cheaper checks pass. Disabled by default for maximum safety.
        self._enable_early_exit = os.getenv(
            "FINBOUND_EARLY_EXIT_VERIFICATION", "0"
        ).lower() in ("1", "true", "yes")
        # Enable Layer 2 LLM-guided re-extraction for complex errors.
        # Disabled by default due to added latency (~5-10s per triggered sample).
        self._enable_layer2 = os.getenv(
            "FINBOUND_ENABLE_LAYER2", "0"
        ).lower() in ("1", "true", "yes")

    def verify(
        self,
        structured_request: StructuredRequest,
        evidence_contract: EvidenceContract,
        reasoning_result: ReasoningResult,
        evidence_context: Optional[EvidenceContext] = None,
    ) -> VerificationResult:
        issues: List[str] = []

        if not reasoning_result.answer:
            issues.append("Answer is empty.")

        if len(reasoning_result.citations) < evidence_contract.required_citations:
            issues.append(
                f"Expected at least {evidence_contract.required_citations} citation(s), "
                f"but got {len(reasoning_result.citations)}."
            )

        if not reasoning_result.reasoning:
            issues.append("Reasoning trace is empty.")

        grounding_issues = self._grounding_checker.check(
            reasoning_result.citations, evidence_context
        )
        issues.extend(grounding_issues)

        evidence_text = ""
        if evidence_context:
            evidence_text = "\n".join(evidence_context.text_blocks)

        # Check if Layer 0 was already run by the reasoning engine
        layer0_from_engine = reasoning_result.raw_model_output.get("layer0_result")
        if layer0_from_engine and isinstance(layer0_from_engine, dict):
            # Use the cached result from engine
            layer0_passed = layer0_from_engine.get("passed", False)
            layer0_fast_path = layer0_from_engine.get("fast_path_eligible", False)
            layer0_confidence = layer0_from_engine.get("confidence", "low")
            for msg in layer0_from_engine.get("issues", []):
                if "auto-corrected" not in msg:  # Don't report corrected issues
                    issues.append(f"Layer0: {msg}")
        else:
            # Run Layer 0 checks
            layer0 = run_layer0_checks(
                question=structured_request.raw_text,
                answer_text=reasoning_result.answer,
                reasoning_text=reasoning_result.reasoning,
                evidence_text=evidence_text,
            )
            layer0_passed = layer0.passed
            layer0_fast_path = layer0.fast_path_eligible
            layer0_confidence = layer0.confidence
            for msg in layer0.issues:
                if "auto-corrected" not in msg:  # Don't report corrected issues
                    issues.append(f"Layer0: {msg}")
            reasoning_result.raw_model_output["layer0_result"] = layer0.to_dict()

        # Fast-path: Skip expensive Layer 1 and LLM verification for high-confidence answers
        use_fast_path = (
            self._enable_fast_path
            and layer0_passed
            and layer0_fast_path
            and layer0_confidence == "high"
            and not issues  # No issues so far
        )

        if use_fast_path:
            logger.info("Fast-path: skipping Layer 1 and LLM verification (high confidence)")
            reasoning_result.raw_model_output["fast_path_used"] = True
        else:
            # Full verification path
            calculation_trace = reasoning_result.raw_model_output.get("calculation_trace", {})
            values_used = calculation_trace.get("values_used")
            layer1_input = Layer1Input(
                question=structured_request.raw_text,
                reasoning=reasoning_result.reasoning,
                model_answer=reasoning_result.answer,
                values_used=values_used,
            )
            layer1_result = run_layer1(layer1_input)
            reasoning_result.raw_model_output["layer1_result"] = layer1_result.to_dict()
            for msg in layer1_result.issues:
                issues.append(f"Layer1: {msg}")

            # Apply Layer 1 correction if operand order was auto-corrected
            if layer1_result.correction_applied and layer1_result.final_answer != reasoning_result.answer:
                logger.info(f"Layer1 auto-correction: {reasoning_result.answer} -> {layer1_result.final_answer}")
                reasoning_result.answer = layer1_result.final_answer
                reasoning_result.raw_model_output["layer1_corrected_answer"] = layer1_result.final_answer

            # Layer 2: LLM-guided re-extraction for complex errors
            if self._enable_layer2 and not layer1_result.correction_applied:
                # Combine Layer 0 and Layer 1 issues for trigger detection
                # Layer 0 issues with type_mismatch indicate wrong formula was used
                layer0_issues = layer0_from_engine.get("issues", []) if layer0_from_engine else []
                all_issues_for_trigger = layer1_result.issues + layer0_issues

                # Check if Layer 2 should be triggered
                if should_trigger_layer2(
                    layer1_issues=all_issues_for_trigger,
                    formula_type=layer1_result.formula_type,
                    confidence=layer1_result.confidence,
                ):
                    logger.info(f"Layer2: Triggered for formula_type={layer1_result.formula_type}, confidence={layer1_result.confidence}")

                    # Prepare Layer 2 input with combined issues
                    layer2_input = Layer2Input(
                        question=structured_request.raw_text,
                        evidence_text=evidence_text,
                        evidence_tables=self._extract_tables(evidence_context),
                        formula_type=layer1_result.formula_type,
                        original_answer=reasoning_result.answer,
                        original_operands=values_used,
                        layer1_issues=all_issues_for_trigger,  # Include Layer 0 issues
                    )

                    # Run Layer 2 re-extraction
                    layer2_result = self._layer2_corrector.run(layer2_input)
                    reasoning_result.raw_model_output["layer2_result"] = layer2_result.to_dict()

                    # Apply Layer 2 correction if confident enough
                    if layer2_result.correction_applied and layer2_result.confidence >= 0.7:
                        logger.info(f"Layer2 auto-correction: {reasoning_result.answer} -> {layer2_result.corrected_answer} (confidence={layer2_result.confidence:.2f})")
                        reasoning_result.answer = layer2_result.corrected_answer
                        reasoning_result.raw_model_output["layer2_corrected_answer"] = layer2_result.corrected_answer
                        # Remove recompute_mismatch issues since we corrected
                        issues = [i for i in issues if "recompute_mismatch" not in i]
                    else:
                        for msg in ["Layer2: re-extraction attempted but confidence too low"]:
                            if layer2_result.corrected_answer:
                                issues.append(f"Layer2: suggested {layer2_result.corrected_answer} (confidence={layer2_result.confidence:.2f})")

        numeric_issues = self._numeric_checker.check(
            answer=reasoning_result.answer,
            reasoning=reasoning_result.reasoning,
        )
        issues.extend(numeric_issues)

        rule_issues = self._rule_verifier.verify(
            structured_request, reasoning_result, evidence_context
        )
        issues.extend(rule_issues)

        retrieval_issues = self._retrieval_verifier.verify(
            structured_request, reasoning_result, evidence_context
        )
        issues.extend(retrieval_issues)

        # Skip LLM verification on fast-path or early-exit
        if use_fast_path or (self._enable_early_exit and not issues):
            llm_issues: List[str] = []
        else:
            llm_issues = self._llm_verifier.verify(
                structured_request, reasoning_result, evidence_context
            )
        issues.extend(llm_issues)

        issues.extend(self._scenario_checker.check(structured_request, reasoning_result.reasoning))
        issues.extend(self._traceability_checker.check(reasoning_result))

        if issues:
            if reasoning_result.answer and reasoning_result.citations:
                status = "PARTIAL_PASS"
                verified = True
            else:
                status = "HARD_FAIL"
                verified = False
        else:
            status = "PASS"
            verified = True

        return VerificationResult(verified=verified, issues=issues, status=status)

    def _extract_tables(self, evidence_context: Optional[EvidenceContext]) -> List[List[List[str]]]:
        """Extract tables from evidence context for Layer 2."""
        if not evidence_context:
            return []

        tables = []

        # EvidenceContext has a 'tables' attribute (List[List[str]])
        # which is a flat list of rows. We wrap it as a single table.
        if evidence_context.tables:
            # The tables attribute is a flat list of rows - wrap as single table
            tables.append([[str(cell) for cell in row] for row in evidence_context.tables])

        # Also check metadata for structured table data
        if evidence_context.metadata:
            meta_tables = evidence_context.metadata.get("tables", [])
            for table in meta_tables:
                if isinstance(table, list):
                    tables.append([[str(cell) for cell in row] for row in table])
                elif isinstance(table, dict) and "rows" in table:
                    tables.append([[str(cell) for cell in row] for row in table["rows"]])

        return tables
