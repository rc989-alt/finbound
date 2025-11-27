from finbound.types import EvidenceContext, EvidenceContract, ReasoningResult, StructuredRequest, VerificationResult
from finbound.verification_gate.checkers import ScenarioChecker, TraceabilityChecker
from finbound.verification_gate.verifiers import RetrievalVerifier, LLMConsistencyVerifier
from finbound.verification_gate.retry import RetryHandler


def _dummy_reasoning(answer: str = "10", reasoning: str = "It increased.", citations=None):
    return ReasoningResult(
        answer=answer,
        reasoning=reasoning,
        citations=citations or [],
        raw_model_output={"chain_of_evidence": {"steps": [{"statement": reasoning}]}},
    )


def test_retrieval_verifier_flags_missing_metadata():
    verifier = RetrievalVerifier()
    issues = verifier.verify(
        StructuredRequest(raw_text=""),
        _dummy_reasoning(citations=["c1"]),
        EvidenceContext(text_blocks=["c1"], metadata={}),
    )
    assert issues


def test_llm_consistency_verifier_detects_uncertainty_mismatch():
    verifier = LLMConsistencyVerifier()
    issues = verifier.verify(
        StructuredRequest(raw_text=""),
        _dummy_reasoning(answer="uncertain", reasoning="Confident answer."),
        None,
    )
    assert issues


def test_scenario_checker():
    checker = ScenarioChecker()
    req = StructuredRequest(raw_text="", scenario="interest_rate_change")
    issues = checker.check(req, "No mention here.")
    assert issues


def test_traceability_checker():
    checker = TraceabilityChecker()
    reasoning = _dummy_reasoning()
    reasoning.raw_model_output = {}
    issues = checker.check(reasoning)
    assert issues


def test_retry_handler():
    handler = RetryHandler(max_retries=1)
    result = VerificationResult(verified=False, issues=["x"], status="HARD_FAIL")
    assert handler.should_retry(result, attempt=1)
    assert not handler.should_retry(result, attempt=2)
