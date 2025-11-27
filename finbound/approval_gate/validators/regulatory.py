from __future__ import annotations

from typing import List

from .base import BaseValidator
from ...types import StructuredRequest


class RegulatoryValidator(BaseValidator):
    name = "regulatory"

    _BANNED_TERMS = [
        "invent numbers",
        "make up numbers",
        "fabricate results",
        "hallucinate",
        "fake data",
    ]

    _NON_PUBLIC_TERMS = ["non-public", "insider", "material nonpublic"]
    _FORECAST_TERMS = ["forecast", "project", "predict"]

    def validate(self, request: StructuredRequest) -> List[str]:
        text = request.raw_text.lower()
        issues: List[str] = []

        if any(term in text for term in self._BANNED_TERMS):
            issues.append("Regulatory: explicit request to fabricate or invent data.")

        if any(term in text for term in self._NON_PUBLIC_TERMS):
            issues.append("Regulatory: references to non-public information are disallowed.")

        if any(term in text for term in self._FORECAST_TERMS) and not request.period:
            issues.append(
                "Regulatory: forecasting requests must specify a clear time period."
            )

        return issues
