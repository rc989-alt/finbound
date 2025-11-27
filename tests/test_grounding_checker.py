from finbound.types import EvidenceContext
from finbound.verification_gate.checkers import GroundingChecker


def test_grounding_checker_flags_missing_citation():
    checker = GroundingChecker()
    context = EvidenceContext(text_blocks=["snippet A"])
    issues = checker.check(["snippet B"], context)
    assert issues
