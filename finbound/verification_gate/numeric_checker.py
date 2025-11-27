from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

from ..tools.calculator import Calculator
from ..utils.numeric_matcher import within_tolerance

NUM_TOKEN = r"[$]?\s*-?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|thousand|m|bn|k|%)?)?"


class NumericChecker:
    """
    Heuristic numeric consistency checker.

    Covers:
      - Basis-point driven deltas (change per basis point)
      - Explicit binary operations described in reasoning text (sum, difference,
        product, ratio)
    """

    CHANGE_PATTERN = re.compile(
        rf"(?:change[d]?|increase[d]?|decrease[d]?|shift)\s+by\s+({NUM_TOKEN})",
        re.IGNORECASE,
    )
    BASIS_PATTERN = re.compile(
        r"([\d,\.]+\s*(?:basis points|bps))",
        re.IGNORECASE,
    )

    BINARY_PATTERNS: List[Tuple[str, List[re.Pattern[str]], Callable[[Calculator, float, float], float]]] = []

    def __init__(self, calculator: Calculator | None = None) -> None:
        self.calculator = calculator or Calculator()
        if not self.BINARY_PATTERNS:
            self._init_binary_patterns()

    def _init_binary_patterns(self) -> None:
        num = f"({NUM_TOKEN})"
        sum_patterns = [
            re.compile(rf"sum of\s+{num}\s+and\s+{num}", re.IGNORECASE),
            re.compile(rf"adding\s+{num}\s+and\s+{num}", re.IGNORECASE),
            re.compile(rf"{num}\s*(?:\+|plus|added to)\s*{num}", re.IGNORECASE),
        ]
        diff_patterns = [
            re.compile(rf"difference between\s+{num}\s+and\s+{num}", re.IGNORECASE),
            re.compile(rf"{num}\s*(?:-|minus|less)\s*{num}", re.IGNORECASE),
        ]
        product_patterns = [
            re.compile(rf"{num}\s*(?:\*|×|times|multiplied by)\s*{num}", re.IGNORECASE),
        ]
        ratio_patterns = [
            re.compile(rf"{num}\s*/\s*{num}", re.IGNORECASE),
            re.compile(rf"{num}\s*(?:divided by|over|per)\s*{num}", re.IGNORECASE),
        ]
        self.BINARY_PATTERNS = [
            ("addition", sum_patterns, lambda calc, a, b: calc.add(a, b)),
            ("subtraction", diff_patterns, lambda calc, a, b: calc.subtract(a, b)),
            ("multiplication", product_patterns, lambda calc, a, b: calc.multiply(a, b)),
            ("division", ratio_patterns, lambda calc, a, b: calc.divide(a, b)),
        ]

    def _parse_scaled_number(self, text: str | None) -> Optional[float]:
        if not text:
            return None
        parsed = self.calculator.parse_number_with_scale(text)
        return parsed.scaled if parsed else None

    def _check_basis_points(self, answer: str, reasoning: str) -> List[str]:
        issues: List[str] = []

        change_match = self.CHANGE_PATTERN.search(reasoning)
        basis_match = self.BASIS_PATTERN.search(reasoning)
        if not change_match or not basis_match:
            return issues

        inferred = self.calculator.infer_from_basis_point_change(
            change_match.group(1), basis_match.group(1)
        )
        if not inferred:
            return issues

        inferred_value, change = inferred

        candidates = {
            inferred_value,
            inferred_value * change.scale,
            inferred_value / max(change.scale, 1.0),
        }
        if change.scale in (1_000, 1_000_000, 1_000_000_000):
            candidates.add(inferred_value * (change.scale / 1_000_000))

        answer_value = self._parse_scaled_number(answer)
        if answer_value is None:
            issues.append(
                "Answer is missing a numeric value even though the reasoning "
                "derives one from basis-point changes."
            )
            return issues

        if not any(within_tolerance(answer_value, candidate) for candidate in candidates):
            issues.append(
                "Numeric mismatch: basis-point change implies "
                f"{round(inferred_value, 4)} (relative units) but answer reported {answer_value}."
            )

        return issues

    def _check_binary_operations(self, answer: str, reasoning: str) -> List[str]:
        issues: List[str] = []
        answer_value = self._parse_scaled_number(answer)
        if answer_value is None:
            return issues

        for name, patterns, op in self.BINARY_PATTERNS:
            for pattern in patterns:
                match = pattern.search(reasoning)
                if not match:
                    continue
                left = self._parse_scaled_number(match.group(1))
                right = self._parse_scaled_number(match.group(2))
                if left is None or right is None:
                    continue

                try:
                    expected = op(self.calculator, left, right)
                except ValueError:
                    continue

                if not within_tolerance(answer_value, expected):
                    issues.append(
                        f"Numeric mismatch for {name}: expected {expected} based on reasoning, "
                        f"but answer reported {answer_value}."
                    )
                # Whether or not mismatch, stop after first detected operation to avoid duplicates
                return issues

        return issues

    def _extract_numeric_values(self, text: str) -> List[float]:
        tokens = re.findall(NUM_TOKEN, text)
        values: List[float] = []
        for token in tokens:
            value = self._parse_scaled_number(token)
            if value is not None:
                values.append(value)
        return values

    def _check_magnitude(self, answer: str, reasoning: str) -> List[str]:
        """Heuristic check for obvious 10x/100x/1000x scale errors."""
        issues: List[str] = []
        answer_value = self._parse_scaled_number(answer)
        if answer_value is None:
            return issues

        context_values = self._extract_numeric_values(reasoning)
        context_values = [
            abs(v)
            for v in context_values
            if v and not within_tolerance(v, answer_value)
        ]
        # Require at least 3 distinct context values (after removing answer)
        if len(context_values) < 3:
            return issues

        context_values.sort()
        median_index = len(context_values) // 2
        median_value = context_values[median_index]
        if median_value == 0:
            return issues

        ratio = abs(answer_value) / median_value
        candidate_factors = [0.01, 0.1, 10, 100, 1000]
        for factor in candidate_factors:
            rel_diff = abs(ratio - factor) / factor
            # Require both a close ratio AND reasonably large numbers to avoid
            # flagging simple 3.8 -> 380 style operations in isolation.
            if rel_diff <= 0.25 and max(abs(answer_value), median_value) >= 100:
                issues.append(
                    f"Answer magnitude appears off by ~{factor}x relative to typical values "
                    f"in reasoning (answer={answer_value}, median={median_value})."
                )
                break

        return issues

    def check(self, answer: str, reasoning: str) -> List[str]:
        issues: List[str] = []
        issues.extend(self._check_basis_points(answer, reasoning))
        issues.extend(self._check_binary_operations(answer, reasoning))
        issues.extend(self._check_magnitude(answer, reasoning))
        return issues
