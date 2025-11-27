from __future__ import annotations

from typing import List

from ...types import StructuredRequest


class ScenarioChecker:
    """
    Checks that reasoning aligns with the declared scenario.
    """

    def check(self, request: StructuredRequest, reasoning_text: str) -> List[str]:
        if not request.scenario:
            return []
        normalized = request.scenario.replace("_", " ").lower()
        if normalized not in reasoning_text.lower():
            return [f"Scenario '{normalized}' not referenced in reasoning."]
        return []
