from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

from ..utils.numeric_matcher import extract_numbers

PERCENTAGE_KEYWORDS = (
    "percentage",
    "percent",
    "% of",
)

# NOTE: These patterns must be specific enough to match actual proportion questions
# but NOT match generic prompt instructions like "express the proportion as a decimal"
# We only match when it's clearly asking FOR a proportion (e.g., "as a proportion of X")
PROPORTION_KEYWORDS = (
    "as a proportion of",  # "costs as a proportion of revenue"
    "proportion of total",  # "what proportion of total sales"
    "as a fraction of",  # "as a fraction of total"
    "share of total",  # "what share of total"
    "portion of total",  # "what portion of total"
)

RATIO_KEYWORDS = (
    "ratio",
)

ABSOLUTE_KEYWORDS = (
    "how much",
    "how many",
    "amount",
    "total",
    "sum",
)

# Patterns that indicate absolute change (NOT percentage change)
ABSOLUTE_CHANGE_PATTERNS = (
    r"what is the change in (?!.*percent)",
    r"what was the change in (?!.*percent)",
    r"change between .* and .* average",
    r"change between .* and .* (?:total|amount|value)",
    r"how much did .* change",
    r"difference (?:between|in|of)",
    r"what is the change between",
)

CURRENCY_KEYWORDS = (
    "$",
    "usd",
    "dollar",
    "million",
    "billion",
    "thousand",
)

POSITIVE_WORDS = (
    "increase",
    "growth",
    "gain",
    "rose",
    "higher",
    "up by",
    "grew",
)

NEGATIVE_WORDS = (
    "decrease",
    "decline",
    "loss",
    "fell",
    "lower",
    "down by",
    "reduction",
)


@dataclass
class Layer0Result:
    passed: bool
    issues: List[str]
    detected_type: str
    answer_format: str
    answer_value: Optional[float]
    # New fields for auto-correction
    corrected_answer: Optional[str] = None
    correction_applied: bool = False
    correction_type: Optional[str] = None
    confidence: str = "medium"  # "high", "medium", "low"
    fast_path_eligible: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def run_layer0_checks(
    question: str,
    answer_text: str,
    reasoning_text: str,
    evidence_text: str | None = None,
) -> Layer0Result:
    issues: List[str] = []
    expected_type = _detect_expected_type(question)
    answer_format = _detect_answer_format(answer_text)
    answer_value = _parse_answer_value(answer_text)

    # Auto-correction fields
    corrected_answer: Optional[str] = None
    correction_applied = False
    correction_type: Optional[str] = None

    # 1. Type mismatch - with auto-correction
    if expected_type == "percentage" and answer_format != "percentage":
        # NOTE: Previously auto-scaled decimal answers (0.25 → 25) for percentage questions
        # but this caused significant regressions. For example:
        # - Gold 0.51% (a small percentage change) was wrongly scaled to 51%
        # - Gold 0.18% was wrongly scaled to 18%
        # Small percentage values (0.51%, 0.18%) are VALID percentage answers.
        # The model computing 0.51 for "percentage change" may mean 0.51%, not 0.0051.
        # Disabled auto-scaling to avoid these false positives.
        if answer_value is not None and 0 < abs(answer_value) < 1:
            # Only log the potential issue, don't auto-correct
            issues.append("type_mismatch: percentage question with decimal answer (may be valid small %).")
        else:
            issues.append("type_mismatch: expected percentage answer.")
    elif expected_type in {"absolute", "currency"} and answer_format == "percentage":
        # AUTO-FIX: Strip % symbol for absolute questions
        corrected, corr_type = _strip_percentage_symbol(answer_text, answer_value)
        if corrected:
            corrected_answer = corrected
            correction_applied = True
            correction_type = corr_type
            issues.append(f"type_mismatch: auto-corrected by {corr_type}.")
        else:
            issues.append("type_mismatch: expected absolute value, got percentage.")

    # NOTE: Previously had evidence-based scaling logic here (lines 135-165) but it caused
    # significant regressions by incorrectly scaling correct answers. Examples:
    # - Gold 172 → 1.72 (wrongly scaled down)
    # - Gold -864 → -8.64 (wrongly scaled down)
    # - Gold 0.51 → 51 (wrongly scaled up)
    # The logic was too speculative - using evidence magnitudes to guess answer scale
    # is unreliable. Removed in favor of more precise type-based corrections only.

    # 2. Proportion questions - keep decimal scale (don't convert to percentage)
    if expected_type == "proportion" and answer_value is not None and not correction_applied:
        if abs(answer_value) > 1:
            # AUTO-FIX: Scale down from percentage to proportion
            corrected, corr_type = _scale_to_proportion(answer_text, answer_value)
            if corrected:
                corrected_answer = corrected
                correction_applied = True
                correction_type = corr_type
                issues.append(f"scale_mismatch: auto-corrected by {corr_type}.")

    # 3. Unit ambiguity (percentage expressed as decimal)
    if answer_format == "percentage" and answer_value is not None:
        if 0 < abs(answer_value) < 1 and "percent" not in answer_text.lower():
            issues.append("unit_ambiguous: percentage appears as decimal.")

    # 4. Sign check for explicit magnitude questions - with auto-correction
    expected_sign = _detect_expected_sign(question, reasoning_text)
    if expected_sign and answer_value is not None:
        if expected_sign == "positive" and answer_value < 0:
            # AUTO-FIX: Flip sign
            if not correction_applied:
                corrected, corr_type = _flip_sign(answer_text, answer_value)
                if corrected:
                    corrected_answer = corrected
                    correction_applied = True
                    correction_type = corr_type
            issues.append("sign_mismatch: expected positive value.")
        elif expected_sign == "negative" and answer_value > 0:
            # AUTO-FIX: Flip sign
            if not correction_applied:
                corrected, corr_type = _flip_sign(answer_text, answer_value)
                if corrected:
                    corrected_answer = corrected
                    correction_applied = True
                    correction_type = corr_type
            issues.append("sign_mismatch: expected negative value.")

    # 5. Range / scale sanity
    evidence_numbers = extract_numbers(evidence_text or "") if evidence_text else []
    max_evidence = max((abs(n) for n in evidence_numbers), default=None)

    if answer_value is not None:
        if answer_format == "percentage":
            if answer_value < -100:
                issues.append("range_violation: percentage below -100%.")
            if answer_value > 1_000 and "growth" not in question.lower():
                issues.append("range_violation: percentage above 1000%.")
        if max_evidence is not None and max_evidence > 0:
            if abs(answer_value) > max_evidence * 100:
                issues.append(
                    "range_violation: answer magnitude far exceeds evidence values."
                )

    # Determine confidence and fast-path eligibility
    passed = len([i for i in issues if "auto-corrected" not in i]) == 0
    confidence, fast_path = _compute_confidence(
        passed, correction_applied, issues, expected_type, answer_format
    )

    return Layer0Result(
        passed=passed,
        issues=issues,
        detected_type=expected_type,
        answer_format=answer_format,
        answer_value=answer_value,
        corrected_answer=corrected_answer,
        correction_applied=correction_applied,
        correction_type=correction_type,
        confidence=confidence,
        fast_path_eligible=fast_path,
    )


def _detect_expected_type(question: str) -> str:
    """Detect expected answer type from question.

    Returns:
        "proportion" - expects 0-1 scale (e.g., "as a proportion of")
        "percentage" - expects 0-100 scale with % (e.g., "percentage change")
        "absolute" - expects raw number (e.g., "what is the change in X")
        "currency" - expects monetary value
        "unknown" - cannot determine
    """
    q = question.lower()

    # Check for proportion FIRST (more specific than percentage)
    # "as a proportion of" should return decimal (0-1)
    if any(keyword in q for keyword in PROPORTION_KEYWORDS):
        return "proportion"

    # Check for absolute change patterns (before percentage keywords)
    # "what is the change in X" without "percentage" = absolute change
    for pattern in ABSOLUTE_CHANGE_PATTERNS:
        if re.search(pattern, q):
            return "absolute"

    # Check for percentage keywords
    if any(keyword in q for keyword in PERCENTAGE_KEYWORDS):
        return "percentage"

    # Ratio questions (like "liability to asset ratio") - return "ratio" type
    # Ratios can be any scale (0.18, 2.93, 18.34) - don't force percentage scale
    if any(keyword in q for keyword in RATIO_KEYWORDS):
        return "ratio"

    if any(keyword in q for keyword in CURRENCY_KEYWORDS):
        return "currency"
    if any(keyword in q for keyword in ABSOLUTE_KEYWORDS):
        return "absolute"
    return "unknown"


def _detect_answer_format(answer: str) -> str:
    lower = answer.lower()
    if "%" in answer or "percent" in lower:
        return "percentage"
    if any(keyword in lower for keyword in CURRENCY_KEYWORDS):
        return "currency"
    return "absolute"


def _parse_answer_value(answer: str) -> Optional[float]:
    cleaned = answer.strip()
    if not cleaned:
        return None
    # Handle accounting parentheses (e.g., $(9.8) million)
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    normalized = cleaned.replace(",", "")
    # Support values like ".42" that lack a leading zero
    match = re.search(r"-?(?:\d+(?:\.\d+)?|\.\d+)", normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _detect_expected_sign(question: str, reasoning: str) -> Optional[str]:
    text = f"{question} {reasoning}".lower()
    pos_count = sum(1 for word in POSITIVE_WORDS if word in text)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text)

    # Only enforce sign when direction cues are overwhelming
    if pos_count >= neg_count + 2:
        return "positive"
    if neg_count >= pos_count + 2:
        return "negative"
    return None


def _strip_percentage_symbol(
    answer_text: str, answer_value: Optional[float]
) -> Tuple[Optional[str], Optional[str]]:
    """Remove % symbol from answer for absolute-value questions.

    Returns:
        (corrected_answer, correction_type) or (None, None) if no correction needed.
    """
    if answer_value is None:
        return None, None

    # Remove % symbol and clean up
    corrected = answer_text.replace("%", "").replace("percent", "").strip()
    # Format the number cleanly
    corrected = _format_number(answer_value)

    return corrected, "strip_percentage"


def _scale_to_proportion(
    answer_text: str, answer_value: Optional[float]
) -> Tuple[Optional[str], Optional[str]]:
    """Scale percentage-scale answer (e.g., 95.5) to proportion (0.955).

    Returns:
        (corrected_answer, correction_type) or (None, None) if no correction needed.
    """
    if answer_value is None:
        return None, None

    # Scale down by 100
    proportion_value = answer_value / 100.0

    corrected = _format_number(proportion_value, max_decimals=4)

    return corrected, "scale_to_proportion"


def _scale_to_percentage(
    answer_text: str, answer_value: Optional[float]
) -> Tuple[Optional[str], Optional[str]]:
    """Scale decimal proportion (e.g., 0.2519) to percentage (25.19).

    This handles the common case where the model computes percentage change
    as a decimal (new-old)/old = 0.25 but the expected answer is 25.19%.

    Returns:
        (corrected_answer, correction_type) or (None, None) if no correction needed.
    """
    if answer_value is None:
        return None, None

    # Scale up by 100
    percentage_value = answer_value * 100.0

    corrected = _format_number(percentage_value, max_decimals=2)

    return corrected, "scale_to_percentage"


def _flip_sign(
    answer_text: str, answer_value: Optional[float]
) -> Tuple[Optional[str], Optional[str]]:
    """Flip the sign of the answer value.

    Returns:
        (corrected_answer, correction_type) or (None, None) if no correction needed.
    """
    if answer_value is None:
        return None, None

    flipped_value = -answer_value

    # Preserve the format (percentage or absolute)
    if "%" in answer_text:
        corrected_value = _format_number(flipped_value)
        corrected = f"{corrected_value}%"
    else:
        corrected = _format_number(flipped_value)

    return corrected, "flip_sign"


def _compute_confidence(
    passed: bool,
    correction_applied: bool,
    issues: List[str],
    expected_type: str,
    answer_format: str,
) -> Tuple[str, bool]:
    """Compute confidence level and fast-path eligibility.

    Returns:
        (confidence, fast_path_eligible)
        - confidence: "high", "medium", or "low"
        - fast_path_eligible: True if answer can bypass Layer 1/2 verification
    """
    # High confidence: no issues, types match perfectly
    if passed and not correction_applied:
        if expected_type == answer_format or expected_type == "unknown":
            return "high", True
        # Known type but matches
        if expected_type in {"percentage", "proportion"} and answer_format == "percentage":
            return "high", True
        if expected_type in {"absolute", "currency"} and answer_format in {"absolute", "currency"}:
            return "high", True

    # Medium confidence: passed after auto-correction
    if passed and correction_applied:
        return "medium", False

    # Low confidence: issues remain
    non_corrected_issues = [i for i in issues if "auto-corrected" not in i]
    if len(non_corrected_issues) > 0:
        return "low", False

    # Default medium
    return "medium", False


def _format_number(value: float, max_decimals: int = 3) -> str:
    """Format a numeric value without trailing zeros."""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    formatted = f"{value:.{max_decimals}f}".rstrip("0").rstrip(".")
    # Handle values like ".2" by ensuring leading zero
    if formatted.startswith("."):
        formatted = "0" + formatted
    if formatted.startswith("-.") and len(formatted) > 2:
        formatted = formatted.replace("-.", "-0.", 1)
    return formatted
