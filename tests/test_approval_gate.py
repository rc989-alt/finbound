import pytest

from finbound.approval_gate import (
    EvidenceContractGenerator,
    PolicyEngine,
    RequestParser,
)


def test_request_parser_extracts_fields():
    parser = RequestParser()
    req = parser.parse(
        "Explain the year-over-year change in interest expense for Q4 2022 "
        "under an interest rate shock scenario for Contoso Corp."
    )
    assert req.scenario == "interest_rate_change"
    assert req.period == "Q4 2022"
    assert "interest_expense" in req.metrics
    assert "Contoso" in req.entities
    assert req.time_horizon == "year-over-year"


def test_policy_engine_flags_missing_period_for_forecast():
    parser = RequestParser()
    engine = PolicyEngine()
    req = parser.parse("Forecast EPS impact without specifying a period.")
    verdict = engine.check_compliance(req)
    assert not verdict.approved
    assert any("time period" in reason.lower() for reason in verdict.reasons)


def test_evidence_contract_reflects_metrics_and_period():
    parser = RequestParser()
    contract_gen = EvidenceContractGenerator()
    req = parser.parse("Compare Q1 2023 revenue and cash flow for Fabrikam Inc.")
    contract = contract_gen.generate(req)
    assert "revenue, cash_flow" in contract.description or "revenue" in contract.description
    assert "Q1 2023" in contract.description
    assert contract.required_citations >= 1
