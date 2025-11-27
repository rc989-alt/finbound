from finbound.reasoning.gates.layer2_stage import Layer2StageGate
from finbound.types import EvidenceContext, EvidenceContract, PolicyVerdict, StructuredRequest


def test_layer2_stage_detects_missing_evidence():
    gate = Layer2StageGate()
    gate.check_evidence_selection(EvidenceContext())
    assert gate.issues


def test_layer2_stage_checks_arithmetic_chain():
    gate = Layer2StageGate()
    chain = {
        "steps": [
            {
                "citations": [],
                "tool_result": {"result": 123},
            }
        ]
    }
    gate.check_arithmetic_stage({"chain_of_evidence": chain})
    assert gate.issues
