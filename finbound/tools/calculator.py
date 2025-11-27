from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional, Tuple


SCALE_MAP = {
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "bn": 1_000_000_000,
    "k": 1_000,
}


@dataclass
class ParsedNumber:
    value: float
    scale: float = 1.0

    @property
    def scaled(self) -> float:
        return self.value * self.scale


class Calculator:
    """
    Tiny calculator utility that supports basis-point conversions and
    simple arithmetic, used by both the reasoning and verification stages.
    """

    number_pattern = re.compile(r"-?\d+(?:\.\d+)?")

    def divide(self, numerator: float, denominator: float) -> float:
        if denominator == 0:
            raise ValueError("Denominator cannot be zero.")
        return numerator / denominator

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    @staticmethod
    def percentage_to_decimal(value: float) -> float:
        return value / 100.0

    @staticmethod
    def basis_points_to_decimal(basis_points: float) -> float:
        return basis_points / 10_000.0

    @staticmethod
    def near(a: float, b: float, tol: float = 1e-3) -> bool:
        return math.isclose(a, b, rel_tol=tol, abs_tol=tol)

    def parse_number_with_scale(self, text: str) -> Optional[ParsedNumber]:
        cleaned = text.lower().replace(",", "").replace("$", "")
        match = self.number_pattern.search(cleaned)
        if not match:
            return None

        value = float(match.group(0))
        scale = 1.0
        for token, factor in SCALE_MAP.items():
            if token in cleaned:
                scale = factor
                break

        if "basis point" in cleaned or "bps" in cleaned:
            # When explicitly referring to basis points, prefer raw value.
            scale = 1.0

        return ParsedNumber(value=value, scale=scale)

    def infer_from_basis_point_change(
        self,
        change_text: str,
        basis_point_text: str,
    ) -> Optional[Tuple[float, ParsedNumber]]:
        """
        Given phrases describing a change amount and the basis-point delta,
        compute the implied base value. Returns a tuple of:
          (base_value_in_change_units, parsed_change_value)
        """
        change = self.parse_number_with_scale(change_text)
        basis = self.parse_number_with_scale(basis_point_text)
        if not change or not basis:
            return None

        basis_decimal = self.basis_points_to_decimal(basis.value)
        if basis_decimal == 0:
            return None

        base_value = change.scaled / basis_decimal
        # Express back in the same scale as the change value for easy comparison
        base_in_change_units = base_value / change.scale
        return base_in_change_units, change

