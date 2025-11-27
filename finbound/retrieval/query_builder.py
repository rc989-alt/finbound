from __future__ import annotations

from typing import Any, Dict, List

from ..types import StructuredRequest


def build_query(request: StructuredRequest) -> Dict[str, Any]:
    keywords: List[str] = []

    def add_keyword(token: str) -> None:
        token = token.strip()
        if not token:
            return
        if token not in keywords:
            keywords.append(token)

    if request.scenario:
        add_keyword(request.scenario.replace("_", " "))

    for metric in request.metrics:
        add_keyword(metric.replace("_", " "))

    for entity in request.entities:
        add_keyword(entity)

    for term in request.risk_terms:
        add_keyword(term)

    for op in request.requested_operations:
        add_keyword(op.replace("_", " "))

    if request.period:
        add_keyword(request.period)

    filters = []
    if request.period:
        filters.append({"field": "period", "value": request.period})
    if request.time_horizon:
        filters.append({"field": "horizon", "value": request.time_horizon})
    if request.scenario:
        filters.append({"field": "scenario", "value": request.scenario})

    query_text = " ".join(keywords) if keywords else request.raw_text

    return {
        "query_text": query_text,
        "keywords": keywords,
        "filters": filters,
        "metrics": request.metrics,
        "entities": request.entities,
        "operations": request.requested_operations,
    }

