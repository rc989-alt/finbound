from __future__ import annotations

import re
from typing import List, Optional

from ..types import StructuredRequest


class RequestParser:
    """
    Minimal parser that wraps the raw text and extracts a few simple fields.

    This is intentionally lightweight for the prototype; later you can
    replace this with a richer parser or LLM-based structuring.
    """

    SCENARIO_KEYWORDS = {
        "interest_rate_change": ["interest rate", "libor", "yield curve"],
        "liquidity_shock": ["liquidity", "cash burn", "funding stress"],
        "credit_risk": ["default risk", "credit spread", "downgrade"],
        "earnings_decline": ["earnings drop", "net income fall", "profit decline"],
        "regulatory_event": ["basel", "sr 11-7", "stress test"],
    }

    METRIC_KEYWORDS = {
        "interest_expense": ["interest expense", "borrowing cost"],
        "revenue": ["revenue", "sales"],
        "eps": ["eps", "earnings per share"],
        "ebitda": ["ebitda"],
        "cash_flow": ["cash flow", "operating cash"],
        "net_income": ["net income", "profit"],
    }

    RISK_TERMS = ["stress test", "scenario", "sensitivity", "risk", "exposure"]

    PERIOD_PATTERN = re.compile(
        r"(?:fy|fiscal)?\s*(q[1-4])\s*(20\d{2})?|(?:20\d{2})",
        re.IGNORECASE,
    )

    ENTITY_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9&]+\b")

    def parse(self, user_request: str) -> StructuredRequest:
        text = user_request.strip()
        if not text:
            raise ValueError("User request is empty.")

        lowered = text.lower()

        # Extract just the question for scenario/risk detection
        # to avoid false positives from evidence context mentioning terms like "interest rate"
        question_text = self._extract_question_text(lowered)

        scenario = self._detect_scenario(question_text)
        periods = self._extract_periods(text)
        period = periods[0] if periods else None
        time_horizon = self._detect_time_horizon(question_text)  # Only check question for time horizon
        metrics = self._detect_metrics(lowered)
        entities = self._extract_entities(text)
        # Only check question for risk terms to avoid false positives from evidence
        risk_terms = [term for term in self.RISK_TERMS if term in question_text]
        operations = self._detect_operations(question_text)  # Only check question for operations

        return StructuredRequest(
            raw_text=text,
            scenario=scenario,
            period=period,
            periods_detected=periods,
            time_horizon=time_horizon,
            metrics=metrics,
            entities=entities,
            risk_terms=risk_terms,
            requested_operations=operations,
        )

    def _extract_question_text(self, lowered: str) -> str:
        """Extract just the question part, excluding evidence context.

        This prevents false positives from terms like 'interest rate' appearing
        in evidence text when the actual question is about something else.
        """
        # Look for "question:" marker which separates evidence from question
        if "question:" in lowered:
            return lowered.split("question:")[-1].strip()

        # Look for common question patterns at end of text
        # Try to find the last sentence that looks like a question
        lines = lowered.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line and (line.endswith("?") or line.startswith("what ") or
                        line.startswith("how ") or line.startswith("calculate ")):
                return line

        # Fallback to last 500 chars if no clear question found
        # This handles cases where the question is at the end without markers
        return lowered[-500:] if len(lowered) > 500 else lowered

    def _detect_scenario(self, lowered: str) -> Optional[str]:
        for name, keywords in self.SCENARIO_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return name
        return None

    def _extract_periods(self, text: str) -> List[str]:
        periods: List[str] = []
        for match in self.PERIOD_PATTERN.finditer(text):
            quarter = match.group(1)
            year = match.group(2) or match.group(0)
            token_parts = []
            if quarter:
                token_parts.append(quarter.upper())
            if year:
                token_parts.append(year.upper())
            token = " ".join(token_parts).strip()
            if token:
                periods.append(token)
        return periods

    def _detect_time_horizon(self, lowered: str) -> Optional[str]:
        if "year-over-year" in lowered or "yoy" in lowered:
            return "year-over-year"
        if "sequential" in lowered or "quarter-over-quarter" in lowered:
            return "sequential"
        if "long-term" in lowered or "multi-year" in lowered:
            return "long-term"
        if "quarter" in lowered:
            return "quarterly"
        if "annual" in lowered or "year" in lowered:
            return "annual"
        return None

    def _detect_metrics(self, lowered: str) -> List[str]:
        metrics: List[str] = []
        for metric, keywords in self.METRIC_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                metrics.append(metric)
        return metrics

    def _extract_entities(self, text: str) -> List[str]:
        candidates = self.ENTITY_PATTERN.findall(text)
        stopwords = {"What", "How", "Why", "When", "With", "And"}
        entities = [
            token
            for token in candidates
            if token not in stopwords and len(token) > 2
        ]
        return entities[:5]

    def _detect_operations(self, lowered: str) -> List[str]:
        ops = []
        if any(keyword in lowered for keyword in ("compare", "versus", "vs", "difference")):
            ops.append("comparison")
        # Only detect explicit forecasting intent - avoid false positives from
        # "project" (noun: business project) or "projected/projections" (past/noun)
        # which are common in financial documents.
        # IMPORTANT: Only detect forecast if the QUESTION asks for forecasting,
        # not if "forecast" or "projection" appears in evidence text.
        # Check for imperative/question patterns that indicate forecasting intent.
        forecast_patterns = [
            "forecast the",
            "predict the",
            "estimate future",
            "project the",  # imperative form
            "what will",
            "what would",
            "going forward",
        ]
        if any(pattern in lowered for pattern in forecast_patterns):
            ops.append("forecast")
        if "scenario" in lowered or "stress test" in lowered:
            ops.append("scenario_analysis")
        if "explain" in lowered or "justify" in lowered:
            ops.append("explanation")
        if "calculate" in lowered or "compute" in lowered:
            ops.append("calculation")
        return ops
