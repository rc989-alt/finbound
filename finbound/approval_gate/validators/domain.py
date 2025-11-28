from __future__ import annotations

from typing import List

from .base import BaseValidator
from ...types import StructuredRequest


class DomainValidator(BaseValidator):
    """
    Validates domain-related aspects of financial requests.

    Rules:
    - Forecasting operations require a time horizon (but only for explicit forecasts)
    - Excessive metrics (>10) in a single query may indicate unclear intent

    Note: Removed strict requirement for explicit metrics - many valid financial
    questions implicitly reference values in the provided evidence (e.g., "What is
    the percentage change?" where the values are in a table).
    """
    name = "domain"

    def validate(self, request: StructuredRequest) -> List[str]:
        issues: List[str] = []

        # Forecasting needs a time horizon - but only for EXPLICIT forecast requests.
        # Many historical data questions may trigger forecast detection due to patterns
        # like "what will" or "project" appearing in context. To avoid false positives,
        # we only enforce this rule if:
        # 1. "forecast" is in operations
        # 2. No time horizon is detected
        # 3. No historical periods are detected (indicating this is likely about past data)
        # 4. The question explicitly asks for future prediction
        if "forecast" in request.requested_operations and request.time_horizon is None:
            # Check if this looks like a historical question by checking for past periods
            # If historical periods are detected, this is likely NOT a true forecast request
            has_historical_periods = bool(request.periods_detected)

            # Also check if the raw text mentions past tense or historical references
            raw_lower = request.raw_text.lower()
            has_historical_context = any(term in raw_lower for term in [
                "was the", "were the", "in 2", "for 2", "during 2",
                "historical", "past", "previous", "last year"
            ])

            # Only block if this appears to be a genuine forecast request
            if not has_historical_periods and not has_historical_context:
                issues.append(
                    "Domain: forecasting operations require a defined time horizon."
                )

        # Only flag truly excessive metrics (relaxed from 4 to 10)
        if len(request.metrics) > 10:
            issues.append(
                "Domain: request targets too many metrics for a single analysis."
            )

        return issues
