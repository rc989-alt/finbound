from __future__ import annotations

from typing import List

from .base import BaseValidator
from ...types import StructuredRequest


class DomainValidator(BaseValidator):
    """
    Validates domain-related aspects of financial requests.

    Rules:
    - Forecasting operations require a time horizon
    - Excessive metrics (>10) in a single query may indicate unclear intent

    Note: Removed strict requirement for explicit metrics - many valid financial
    questions implicitly reference values in the provided evidence (e.g., "What is
    the percentage change?" where the values are in a table).
    """
    name = "domain"

    def validate(self, request: StructuredRequest) -> List[str]:
        issues: List[str] = []

        # Forecasting needs a time horizon - this is still important for safety
        if "forecast" in request.requested_operations and request.time_horizon is None:
            issues.append(
                "Domain: forecasting operations require a defined time horizon."
            )

        # Only flag truly excessive metrics (relaxed from 4 to 10)
        if len(request.metrics) > 10:
            issues.append(
                "Domain: request targets too many metrics for a single analysis."
            )

        return issues
