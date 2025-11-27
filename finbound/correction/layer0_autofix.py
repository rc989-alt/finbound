"""
Layer 0: Auto-Fix Checks

Fast, deterministic corrections for format/scale/type errors.
Target latency: ~10ms

Fixes:
- Scale errors: proportion (0-1) vs percentage (0-100)
- Format errors: strip % symbol when absolute value expected
- Type detection: absolute vs percentage vs proportion questions
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Layer0Input:
    """Input for Layer 0 auto-fix."""
    question: str
    answer: float
    answer_str: str  # Original string representation (e.g., "95.5", "-10.5%")


@dataclass
class Layer0Result:
    """Result from Layer 0 auto-fix."""
    original_answer: float
    corrected_answer: float
    correction_applied: bool
    correction_type: Optional[str]  # "scale_to_proportion", "scale_to_percentage", "strip_percentage", None
    question_type: str  # "absolute", "percentage", "proportion", "ratio", "unknown"
    needs_layer1: bool  # True if can't auto-fix, needs recomputation
    confidence: str  # "high", "medium", "low"


# Patterns for question type detection
PERCENTAGE_PATTERNS = [
    r"percentage change",
    r"percent change",
    r"% change",
    r"percentage of (?:total|the total)",
    r"% of total",
    r"as a percentage of",
    r"what (?:is|was) the percentage",
    r"expressed as a percentage",
]

PROPORTION_PATTERNS = [
    r"as a proportion of",
    r"proportion of .* (?:to|over|of)",
    r"what (?:is|was|were) .* as a proportion",
]

RATIO_PATTERNS = [
    r"(?:liability to asset|asset to liability) ratio",
    r"ratio of .* to",
    r"ratio between",
    r"what (?:is|was) the .* ratio",
]

ABSOLUTE_CHANGE_PATTERNS = [
    r"what (?:is|was) the change in",
    r"what (?:is|was) the difference",
    r"change between .* and .* (?:average|total)",
    r"how much (?:did|was|were|is)",
    r"difference between",
    r"what (?:is|was) the .* for \d{4}",  # Direct value lookup
    r"how (?:much|many|long)",
]

ABSOLUTE_VALUE_PATTERNS = [
    r"what (?:is|was|were) (?:the )?(?:total|amount|value|sum)",
    r"how much (?:of|was|were|is|did)",
    r"what (?:is|was) .* in (?:millions|billions|thousands)",
    r"(?:total|amount) .* in \d{4}",
]


def detect_question_type(question: str) -> str:
    """
    Detect whether a question expects an absolute value, percentage, proportion, or ratio.

    Returns:
        "percentage" - Question asks for a percentage (0-100 range with %)
        "proportion" - Question asks for a proportion (0-1 range)
        "ratio" - Question asks for a ratio (could be >1)
        "absolute" - Question asks for an absolute number
        "unknown" - Cannot determine

    Examples:
        >>> detect_question_type("What is the percentage change in revenue?")
        'percentage'
        >>> detect_question_type("What was the employee termination costs as a proportion of total costs?")
        'proportion'
        >>> detect_question_type("What is the change in the average total current tax expense?")
        'absolute'
        >>> detect_question_type("What is the liability to asset ratio?")
        'ratio'
    """
    q = question.lower()

    # Check for explicit percentage keywords first
    for pattern in PERCENTAGE_PATTERNS:
        if re.search(pattern, q):
            return "percentage"

    # Check for proportion keywords (more specific than percentage)
    for pattern in PROPORTION_PATTERNS:
        if re.search(pattern, q):
            return "proportion"

    # Check for ratio keywords
    for pattern in RATIO_PATTERNS:
        if re.search(pattern, q):
            return "ratio"

    # Check for absolute change patterns (must NOT contain percentage words)
    if "percentage" not in q and "percent" not in q and "%" not in q:
        for pattern in ABSOLUTE_CHANGE_PATTERNS:
            if re.search(pattern, q):
                return "absolute"

    # Check for absolute value patterns
    for pattern in ABSOLUTE_VALUE_PATTERNS:
        if re.search(pattern, q):
            return "absolute"

    # Default to unknown if no pattern matches
    return "unknown"


def scale_autoconvert(
    answer: float,
    question_type: str
) -> Tuple[float, bool, str]:
    """
    Automatically convert between proportion (0-1) and percentage (0-100) based on question type.

    Args:
        answer: The model's numeric answer
        question_type: From detect_question_type()

    Returns:
        Tuple of (corrected_answer, correction_applied, correction_type)

    Examples:
        >>> scale_autoconvert(95.5, "proportion")
        (0.955, True, 'scale_to_proportion')
        >>> scale_autoconvert(0.18, "percentage")
        (18.0, True, 'scale_to_percentage')
        >>> scale_autoconvert(0.18, "ratio")
        (18.0, True, 'scale_to_percentage')
        >>> scale_autoconvert(56.0, "absolute")
        (56.0, False, 'none')
    """
    if question_type == "proportion":
        # Proportion should be in 0-1 range
        # If answer > 1, it's likely a percentage that needs to be converted
        if abs(answer) > 1:
            return answer / 100, True, "scale_to_proportion"

    elif question_type == "percentage":
        # Percentage should be in 0-100 range (typically)
        # If 0 < answer < 1, it's likely a proportion that needs to be converted
        if 0 < abs(answer) < 1:
            return answer * 100, True, "scale_to_percentage"

    elif question_type == "ratio":
        # Ratio questions are tricky - "liability to asset ratio" could be expressed
        # as a percentage (18.34%) or decimal (0.1834) depending on context
        # If answer is very small (< 1) and context suggests percentage, convert
        if 0 < abs(answer) < 1:
            return answer * 100, True, "scale_to_percentage"

    return answer, False, "none"


def strip_format(
    answer_str: str,
    question_type: str
) -> Tuple[float, bool, bool]:
    """
    Strip percentage symbols and extract numeric value.

    Args:
        answer_str: The model's answer as string (e.g., "467%", "-10.5%")
        question_type: From detect_question_type()

    Returns:
        Tuple of (numeric_value, had_percentage, correction_applied)
        - numeric_value: The extracted numeric value
        - had_percentage: Whether % was present in the string
        - correction_applied: Whether we stripped % for an absolute question

    Examples:
        >>> strip_format("467%", "absolute")
        (467.0, True, True)
        >>> strip_format("-10.5%", "percentage")
        (-10.5, True, False)
        >>> strip_format("1320.8", "absolute")
        (1320.8, False, False)
    """
    # Check if answer has percentage symbol
    has_percent = "%" in answer_str

    # Extract numeric value
    # Remove common suffixes/prefixes: %, $, S$, million, billion, etc.
    cleaned = answer_str
    cleaned = re.sub(r'[%$£€¥]', '', cleaned)
    cleaned = re.sub(r'S\$', '', cleaned)  # Singapore dollar
    cleaned = re.sub(r'\s*(million|billion|thousand|mn|bn|k)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*(increase|decrease)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    try:
        # Handle negative numbers with various formats
        cleaned = cleaned.replace(',', '')  # Remove thousands separator
        cleaned = cleaned.replace('(', '-').replace(')', '')  # Accounting negative format
        numeric_value = float(cleaned)
    except ValueError:
        # If we can't parse, return 0 and mark as needing Layer 1
        return 0.0, has_percent, False

    # Determine if correction should be applied
    # Only strip % if question expects absolute value
    correction_applied = has_percent and question_type == "absolute"

    return numeric_value, has_percent, correction_applied


def run_layer0(input: Layer0Input) -> Layer0Result:
    """
    Run the complete Layer 0 auto-fix pipeline.

    Pipeline:
    1. Detect question type (absolute, percentage, proportion, ratio)
    2. Try format stripping (remove % if absolute expected)
    3. Try scale conversion (proportion ↔ percentage)
    4. Determine if Layer 1 is needed

    Args:
        input: Layer0Input with question, answer, and answer_str

    Returns:
        Layer0Result with corrected answer and metadata

    Examples:
        >>> result = run_layer0(Layer0Input(
        ...     question="What was the employee termination costs as a proportion of total costs?",
        ...     answer=95.5,
        ...     answer_str="95.5"
        ... ))
        >>> result.corrected_answer
        0.955
        >>> result.correction_type
        'scale_to_proportion'
    """
    # Step 1: Detect question type
    question_type = detect_question_type(input.question)

    # Step 2: Try format stripping first
    numeric, had_pct, format_corrected = strip_format(input.answer_str, question_type)

    if format_corrected:
        # Format stripping was applied (% stripped for absolute question)
        return Layer0Result(
            original_answer=input.answer,
            corrected_answer=numeric,
            correction_applied=True,
            correction_type="strip_percentage",
            question_type=question_type,
            needs_layer1=False,
            confidence="high"
        )

    # Step 3: Try scale conversion
    # Use the numeric value from strip_format if parsing succeeded, otherwise use input.answer
    answer_to_convert = numeric if numeric != 0.0 else input.answer
    corrected, scaled, scale_type = scale_autoconvert(answer_to_convert, question_type)

    if scaled:
        return Layer0Result(
            original_answer=input.answer,
            corrected_answer=corrected,
            correction_applied=True,
            correction_type=scale_type,
            question_type=question_type,
            needs_layer1=False,
            confidence="high"
        )

    # Step 4: Determine if Layer 1 is needed
    # Layer 1 is needed when:
    # - Question type is unknown
    # - Answer format suggests calculation error (not just scale/format)
    needs_layer1 = (
        question_type == "unknown" or
        (question_type == "absolute" and had_pct and not format_corrected) or
        (question_type == "percentage" and not had_pct and abs(input.answer) > 100)
    )

    # Determine confidence
    if question_type == "unknown":
        confidence = "low"
    elif needs_layer1:
        confidence = "medium"
    else:
        confidence = "high"

    return Layer0Result(
        original_answer=input.answer,
        corrected_answer=input.answer,
        correction_applied=False,
        correction_type=None,
        question_type=question_type,
        needs_layer1=needs_layer1,
        confidence=confidence
    )


def apply_layer0_correction(
    question: str,
    answer: float,
    answer_str: str
) -> Tuple[float, bool, Optional[str]]:
    """
    Convenience function for quick Layer 0 correction.

    Args:
        question: The financial question
        answer: Numeric answer value
        answer_str: Original answer string

    Returns:
        Tuple of (final_answer, was_corrected, correction_type)
    """
    result = run_layer0(Layer0Input(
        question=question,
        answer=answer,
        answer_str=answer_str
    ))
    return result.corrected_answer, result.correction_applied, result.correction_type
