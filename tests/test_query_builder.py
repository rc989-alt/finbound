from finbound.retrieval import build_query
from finbound.types import StructuredRequest


def test_build_query_assembles_keywords_and_filters():
    request = StructuredRequest(
        raw_text="Explain interest expense change for Contoso in Q4 2022",
        scenario="interest_rate_change",
        period="Q4 2022",
        periods_detected=["Q4 2022"],
        time_horizon="quarterly",
        metrics=["interest_expense"],
        entities=["Contoso"],
        risk_terms=["scenario"],
        requested_operations=["explanation", "calculation"],
    )

    query = build_query(request)

    assert "interest rate change" in query["query_text"]
    assert "Contoso" in query["keywords"]
    assert {"field": "period", "value": "Q4 2022"} in query["filters"]
    assert query["operations"] == ["explanation", "calculation"]
