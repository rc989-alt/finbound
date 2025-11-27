from __future__ import annotations

from typing import List

from .base import BaseValidator
from ...types import StructuredRequest


class ScenarioValidator(BaseValidator):
    """
    Validates scenario-related aspects of requests.

    Rules:
    - Risk-focused requests should specify a scenario (warning, not blocking)
    - Interest rate change scenarios need a time horizon (warning, not blocking)

    Note: Time period limits removed as they were too strict for legitimate
    historical financial analysis questions (e.g., "What was revenue in 2015-2019?")
    """
    name = "scenario"

    def validate(self, request: StructuredRequest) -> List[str]:
        issues: List[str] = []

        # Risk terms without scenario - only block if explicitly asking for
        # forward-looking risk projections (not historical risk metrics)
        forward_looking_terms = {"projection", "forecast", "predict", "estimate future"}
        raw_lower = request.raw_text.lower()
        is_forward_looking = any(term in raw_lower for term in forward_looking_terms)

        if request.risk_terms and not request.scenario and is_forward_looking:
            issues.append(
                "Scenario: forward-looking risk requests must specify a scenario (e.g., interest rate change)."
            )

        # Interest rate scenario without horizon - only enforce for forward-looking
        if (
            request.scenario == "interest_rate_change"
            and is_forward_looking
            and request.time_horizon not in ("quarterly", "year-over-year", "annual")
        ):
            issues.append(
                "Scenario: interest-rate projections must declare a quarterly or annual horizon."
            )

        return issues
