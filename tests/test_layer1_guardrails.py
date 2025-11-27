from finbound.reasoning.chain_of_evidence import ChainOfEvidence
from finbound.reasoning.gates import Layer1Guardrails


def test_layer1_guardrails_detect_missing_citations():
    chain = ChainOfEvidence()
    chain.add_step("Interest expense increased.", citations=[])
    guardrails = Layer1Guardrails()
    guardrails.run_checks(chain)
    assert guardrails.issues
    assert guardrails.issues[0].step_index == 0


def test_layer1_guardrails_check_numeric_citation():
    chain = ChainOfEvidence()
    chain.add_step("Interest expense increased to 380.", citations=["Interest expense snippet contains 380"])
    guardrails = Layer1Guardrails()
    guardrails.update_evidence(["Interest expense snippet contains 380"])
    guardrails.run_checks(chain)
    assert not guardrails.issues


def test_layer1_guardrails_detects_year_mismatch():
    snippet = "Revenue for 2012 was 100."
    chain = ChainOfEvidence()
    chain.add_step("Revenue for 2013 was 120.", citations=[snippet])
    guardrails = Layer1Guardrails()
    guardrails.update_evidence([snippet])
    guardrails.run_checks(chain)
    assert any("year tokens" in issue.message for issue in guardrails.issues)


def test_layer1_guardrails_detects_metric_keyword_mismatch():
    snippet = "Operating expense for widgets was 200."
    chain = ChainOfEvidence()
    chain.add_step("Defined contribution schemes averaged 166.", citations=[snippet])
    guardrails = Layer1Guardrails()
    guardrails.update_evidence([snippet])
    guardrails.run_checks(chain)
    assert any("metric keywords" in issue.message for issue in guardrails.issues)
