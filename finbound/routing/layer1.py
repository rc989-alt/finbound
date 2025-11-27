from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import List, Optional

from .layer0_checks import _detect_expected_type, _parse_answer_value


ABS_CHANGE_PATTERNS = (
    r"change between",
    r"difference between",
    r"change in the average",
    r"change of the average",
    r"change between .* average",
    r"change in total",
)

PERCENTAGE_CHANGE_PATTERNS = (
    "percentage change",
    "percent change",
    "yoy",
    "year over year",
)

PROPORTION_PATTERNS = (
    "as a proportion",
    "proportion of",
    "fraction of",
)

PERCENTAGE_OF_PATTERNS = (
    "percentage of",
    "% of",
    "share of",
    "portion of",
)


@dataclass
class Layer1Input:
    question: str
    reasoning: str
    model_answer: str
    values_used: Optional[List[dict]] = None


@dataclass
class Layer1Result:
    formula_type: Optional[str]
    operands_complete: bool
    recomputed_value: Optional[float]
    correction_applied: bool
    final_answer: str
    confidence: str  # "low" | "medium" | "high"
    issues: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def run_layer1(input: Layer1Input) -> Layer1Result:
    """Detect formula type, evaluate operand completeness, attempt recompute."""
    formula_type = detect_formula_type(input.question)
    issues: List[str] = []
    operands_complete = False
    recomputed_value: Optional[float] = None
    correction_applied = False
    corrected_answer: Optional[str] = None
    confidence = "low"

    numeric_answer = _parse_answer_value(input.model_answer)
    numeric_operands = _extract_numeric_operands(input.values_used)

    if formula_type and numeric_operands:
        recomputed_value = _recompute(formula_type, numeric_operands)
        if recomputed_value is not None:
            operands_complete = True
            if numeric_answer is not None:
                diff = abs(recomputed_value - numeric_answer)
                rel = diff / max(abs(numeric_answer), 1e-6)
                if rel <= 0.01:
                    confidence = "high"
                elif rel <= 0.05:
                    confidence = "medium"
                else:
                    issues.append("recompute_mismatch: model answer deviates from formula recomputation.")
                    confidence = "low"

                # Check for operand order mismatch and auto-correct if detected
                corrected_answer, was_corrected = _check_and_correct_operand_order(
                    formula_type,
                    numeric_operands,
                    numeric_answer,
                    recomputed_value,
                    issues,
                )
                if was_corrected:
                    correction_applied = True
                    confidence = "medium"  # Corrected answers get medium confidence
            else:
                confidence = "medium"
        else:
            issues.append("recompute_failed: insufficient operands for formula type.")
    elif formula_type:
        issues.append(f"missing_operands: formula={formula_type}")

    # Use corrected answer if available, otherwise original
    final_answer = corrected_answer if corrected_answer else input.model_answer

    return Layer1Result(
        formula_type=formula_type,
        operands_complete=operands_complete,
        recomputed_value=recomputed_value,
        correction_applied=correction_applied,
        final_answer=final_answer,
        confidence=confidence if formula_type else "low",
        issues=issues,
    )


def detect_formula_type(question: str) -> Optional[str]:
    """Simple heuristic mapping from question text to formula type."""
    lowered = question.lower()

    if _matches_any(PERCENTAGE_CHANGE_PATTERNS, lowered):
        return "percentage_change"
    if any(pattern in lowered for pattern in PROPORTION_PATTERNS):
        return "proportion"
    if _matches_any(PERCENTAGE_OF_PATTERNS, lowered):
        return "percentage_of_total"
    if _matches_abs_change(lowered):
        return "absolute_change"
    if any(token in lowered for token in ("average", "avg", "mean")):
        return "average"
    if "ratio" in lowered:
        return "ratio"

    # Fallback to expected type from Layer 0 detection
    expected_type = _detect_expected_type(question)
    return expected_type if expected_type != "unknown" else None


def _extract_numeric_operands(values_used: Optional[List[dict]]) -> List[float]:
    if not values_used:
        return []
    operands: List[float] = []
    for item in values_used:
        value = item.get("value")
        if isinstance(value, (int, float)):
            operands.append(float(value))
    return operands


def _recompute(formula_type: str, operands: List[float]) -> Optional[float]:
    if formula_type == "percentage_change" and len(operands) >= 2:
        new = operands[-1]
        old = operands[-2]
        if old == 0:
            return None
        return (new - old) / old * 100
    if formula_type == "percentage_of_total" and len(operands) >= 2:
        part = operands[-2]
        total = operands[-1]
        if total == 0:
            return None
        return part / total * 100
    if formula_type == "proportion" and len(operands) >= 2:
        part = operands[-2]
        total = operands[-1]
        if total == 0:
            return None
        return part / total
    if formula_type == "average" and len(operands) >= 2:
        return sum(operands) / len(operands)
    if formula_type == "ratio" and len(operands) >= 2:
        denom = operands[-1]
        if denom == 0:
            return None
        return operands[-2] / denom
    if formula_type == "absolute_change" and len(operands) >= 2:
        return operands[-1] - operands[-2]
    return None


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(pattern in text for pattern in patterns)


def _matches_abs_change(text: str) -> bool:
    if any(keyword in text for keyword in ("percent", "percentage", "%")):
        return False
    return any(re.search(pattern, text) for pattern in ABS_CHANGE_PATTERNS)


def _within_tolerance(a: float, b: float, rel_tol: float = 0.05, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b), 1.0))


def _check_and_correct_operand_order(
    formula_type: str,
    operands: List[float],
    numeric_answer: float,
    recomputed: Optional[float],
    issues: List[str],
) -> tuple[Optional[str], bool]:
    """Detect and auto-correct swapped numerator/denominator for ratio/proportion calculations.

    Returns:
        (corrected_answer, was_corrected) - corrected answer string and whether correction was applied
    """
    if len(operands) < 2 or recomputed is None:
        return None, False

    if formula_type in {"ratio", "percentage_of_total", "proportion"}:
        swapped = _recompute_swapped(formula_type, operands)
        if swapped is None:
            return None, False

        matches_swapped = _within_tolerance(numeric_answer, swapped)
        matches_expected = _within_tolerance(numeric_answer, recomputed)

        if matches_swapped and not matches_expected:
            # Operand order mismatch detected - auto-correct!
            issues.append("operand_order_mismatch: numerator/denominator swapped, auto-corrected.")

            # Format the corrected answer
            if formula_type == "percentage_of_total":
                # Return as percentage
                corrected = f"{recomputed:.2f}%"
            elif formula_type == "ratio":
                # Check if original question expects percentage format
                # If recomputed is < 1, likely expects percentage
                if recomputed < 1:
                    corrected = f"{recomputed * 100:.1f}%"
                else:
                    corrected = _format_number(recomputed)
            else:
                corrected = _format_number(recomputed)

            return corrected, True

    return None, False


def _format_number(value: float) -> str:
    """Format a numeric value without unnecessary trailing zeros."""
    if value == int(value):
        return str(int(value))
    # Round to reasonable precision
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return formatted


def _recompute_swapped(formula_type: str, operands: List[float]) -> Optional[float]:
    if formula_type == "ratio" and len(operands) >= 2:
        numerator = operands[-1]
        denom = operands[-2]
        if denom == 0:
            return None
        return numerator / denom
    if formula_type == "percentage_of_total" and len(operands) >= 2:
        total = operands[-2]
        part = operands[-1]
        if part == 0:
            return None
        return total / part * 100
    if formula_type == "proportion" and len(operands) >= 2:
        total = operands[-2]
        part = operands[-1]
        if part == 0:
            return None
        return total / part
    return None
