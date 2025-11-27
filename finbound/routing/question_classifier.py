"""
Question Classifier for Intelligent Routing.

Classifies financial questions into difficulty levels based on historical failure patterns.
Uses pattern matching to predict which questions need full verification vs fast-path.

Difficulty levels:
- easy: Lookup and simple delta questions (GPT ~80% correct)
- medium: Ratios and percentage changes (GPT ~60% correct)
- hard: Temporal averages, multi-step aggregations (GPT ~40% correct)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class QuestionHints:
    """Hints extracted from question for downstream processing."""
    expected_unit: Optional[str] = None  # "percentage", "absolute", "proportion", "currency"
    needs_average: bool = False  # Temporal average pattern detected
    multi_year: bool = False  # Multiple years referenced
    multi_row: bool = False  # Multiple rows/items to aggregate
    sign_sensitive: bool = False  # Change/difference question where sign matters
    formula_type: Optional[str] = None  # "percentage_change", "absolute_change", "ratio", etc.


@dataclass
class ClassificationResult:
    """Result of question classification."""
    difficulty: Difficulty
    hints: QuestionHints
    reason: str
    confidence: float  # 0-1, how confident we are in this classification


# =============================================================================
# Hard Question Patterns (GPT ~40% correct - need full verification)
# =============================================================================

# Temporal average: "2019 average X" means (X_2019 + X_2018) / 2
# This is a common misunderstanding - GPT often just returns X_2019
TEMPORAL_AVERAGE_PATTERNS = [
    r"\b(\d{4})\s+average\b",  # "2019 average"
    r"\baverage\s+(?:for\s+)?(\d{4})\b",  # "average for 2019"
    r"\baverage\b.*\b(\d{4})\b.*(?:and|to)\s*\b(\d{4})\b",  # "average from 2018 to 2019"
]

# Multi-step aggregation: Need to sum/average multiple items then compute change
MULTI_STEP_AGGREGATION_PATTERNS = [
    r"total\s+.+\s+(?:change|growth|difference)",  # "total revenue change"
    r"(?:change|growth|difference)\s+in\s+total",  # "change in total"
    r"sum\s+of\s+.+\s+(?:between|from)",  # "sum of X between years"
    r"combined\s+.+\s+(?:change|growth)",  # "combined growth"
    r"aggregate\s+.+\s+(?:change|growth)",  # "aggregate change"
]

# Difference of averages: Compare averages across periods
DIFFERENCE_OF_AVERAGES_PATTERNS = [
    r"change\s+(?:in|between)\s+.+\s+average",  # "change in average"
    r"difference\s+between\s+.+\s+average",  # "difference between averages"
    r"average\s+.+\s+(?:change|difference|growth)",  # "average X change"
]

# Multi-row operations: Need to aggregate across multiple table rows
MULTI_ROW_PATTERNS = [
    r"total\s+(?:of\s+)?(?:all|both)",  # "total of all"
    r"sum\s+(?:of\s+)?(?:all|both)",  # "sum of all"
    r"(?:all|both)\s+.+\s+combined",  # "all items combined"
    r"including\s+.+\s+and\s+",  # "including X and Y"
]

# =============================================================================
# Medium Question Patterns (GPT ~60% correct - need Layer 1 verification)
# =============================================================================

# Percentage change: (new - old) / old * 100
PERCENTAGE_CHANGE_PATTERNS = [
    r"(?:percentage|percent)\s+(?:change|growth|increase|decrease)",
    r"(?:change|growth|increase|decrease)\s+(?:in\s+)?percent",
    r"\%\s+(?:change|growth|increase|decrease)",
    r"by\s+what\s+percent",
    r"rate\s+of\s+(?:change|growth)",
]

# Ratio calculations
RATIO_PATTERNS = [
    r"\bratio\b",  # "debt ratio"
    r"as\s+a\s+(?:percent|percentage|proportion)\s+of",  # "as a percentage of"
    r"\bdivide\b",  # explicit division
    r"per\s+\w+",  # "per share", "per unit"
]

# Year-over-year comparison (single step, but can have sign issues)
YOY_COMPARISON_PATTERNS = [
    r"from\s+(\d{4})\s+to\s+(\d{4})",  # "from 2018 to 2019"
    r"between\s+(\d{4})\s+and\s+(\d{4})",  # "between 2018 and 2019"
    r"(\d{4})\s+(?:compared|versus|vs)\s+(\d{4})",  # "2019 compared to 2018"
    r"year\s*-?\s*over\s*-?\s*year",  # "year-over-year"
]

# =============================================================================
# Easy Question Patterns (GPT ~80% correct - Layer 0 + fast path)
# =============================================================================

# Simple lookup: Just find a value in the table
LOOKUP_PATTERNS = [
    r"what\s+(?:is|was|were)\s+(?:the\s+)?(?:value|amount|total|number)\s+(?:of\s+)?\w+\s+(?:in|for)\s+\d{4}",
    r"(?:in|for)\s+\d{4},?\s+what\s+(?:is|was)",
    r"how\s+much\s+(?:is|was)\s+.+\s+(?:in|for)\s+\d{4}",
]

# Simple delta: Direct subtraction (not percentage)
SIMPLE_DELTA_PATTERNS = [
    r"what\s+(?:is|was)\s+the\s+(?:change|difference)\s+in\s+\w+\s+(?:from|between)",
    r"by\s+how\s+much\s+did\s+.+\s+(?:change|increase|decrease)",
]


def classify_question(question: str) -> ClassificationResult:
    """
    Classify a financial question into difficulty level.

    Args:
        question: The financial question text

    Returns:
        ClassificationResult with difficulty, hints, and reasoning
    """
    q = question.lower().strip()
    hints = QuestionHints()

    # Extract hints from question
    hints.expected_unit = _detect_expected_unit(q)
    hints.needs_average = _detect_temporal_average(q)
    hints.multi_year = _detect_multi_year(q)
    hints.multi_row = _detect_multi_row(q)
    hints.sign_sensitive = _detect_sign_sensitivity(q)
    hints.formula_type = _detect_formula_type(q)

    # Check HARD patterns first (most specific)
    for pattern in TEMPORAL_AVERAGE_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.HARD,
                hints=hints,
                reason="Temporal average pattern - requires averaging across periods",
                confidence=0.9,
            )

    for pattern in MULTI_STEP_AGGREGATION_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.HARD,
                hints=hints,
                reason="Multi-step aggregation - requires multiple operations",
                confidence=0.85,
            )

    for pattern in DIFFERENCE_OF_AVERAGES_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.HARD,
                hints=hints,
                reason="Difference of averages - requires computing averages then comparing",
                confidence=0.9,
            )

    if hints.multi_row and hints.multi_year:
        return ClassificationResult(
            difficulty=Difficulty.HARD,
            hints=hints,
            reason="Multi-row + multi-year - complex aggregation required",
            confidence=0.8,
        )

    # Check MEDIUM patterns
    for pattern in PERCENTAGE_CHANGE_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.MEDIUM,
                hints=hints,
                reason="Percentage change - requires formula verification",
                confidence=0.85,
            )

    for pattern in RATIO_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.MEDIUM,
                hints=hints,
                reason="Ratio calculation - requires formula verification",
                confidence=0.8,
            )

    if hints.sign_sensitive:
        # Sign-sensitive questions need Layer 1 to verify direction
        return ClassificationResult(
            difficulty=Difficulty.MEDIUM,
            hints=hints,
            reason="Sign-sensitive question - change direction matters",
            confidence=0.75,
        )

    # Check for YOY patterns (medium complexity)
    for pattern in YOY_COMPARISON_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.MEDIUM,
                hints=hints,
                reason="Year-over-year comparison - requires correct baseline",
                confidence=0.7,
            )

    # Check EASY patterns
    for pattern in LOOKUP_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.EASY,
                hints=hints,
                reason="Simple lookup - direct value extraction",
                confidence=0.85,
            )

    for pattern in SIMPLE_DELTA_PATTERNS:
        if re.search(pattern, q):
            return ClassificationResult(
                difficulty=Difficulty.EASY,
                hints=hints,
                reason="Simple delta - direct subtraction",
                confidence=0.8,
            )

    # Default: MEDIUM (conservative choice)
    return ClassificationResult(
        difficulty=Difficulty.MEDIUM,
        hints=hints,
        reason="Unknown pattern - defaulting to medium difficulty",
        confidence=0.5,
    )


def _detect_expected_unit(q: str) -> Optional[str]:
    """Detect expected answer unit from question."""
    if any(kw in q for kw in ["proportion", "as a proportion"]):
        return "proportion"
    if any(kw in q for kw in ["percentage", "percent", "% of"]):
        return "percentage"
    if any(kw in q for kw in ["$", "dollar", "million", "billion"]):
        return "currency"
    if any(kw in q for kw in ["how much", "how many", "amount", "total"]):
        return "absolute"
    return None


def _detect_temporal_average(q: str) -> bool:
    """Detect if question requires temporal averaging."""
    for pattern in TEMPORAL_AVERAGE_PATTERNS:
        if re.search(pattern, q):
            return True
    # Also check for "average" with a specific year
    if re.search(r"\baverage\b", q) and re.search(r"\b\d{4}\b", q):
        return True
    return False


def _detect_multi_year(q: str) -> bool:
    """Detect if question references multiple years."""
    years = re.findall(r"\b(19|20)\d{2}\b", q)
    return len(set(years)) >= 2


def _detect_multi_row(q: str) -> bool:
    """Detect if question requires aggregating multiple table rows."""
    for pattern in MULTI_ROW_PATTERNS:
        if re.search(pattern, q):
            return True
    # Check for "and" between items
    if re.search(r"\w+\s+and\s+\w+\s+(?:combined|together|total)", q):
        return True
    return False


def _detect_sign_sensitivity(q: str) -> bool:
    """Detect if question is sensitive to sign/direction."""
    sign_words = [
        "increase", "decrease", "growth", "decline",
        "change", "difference", "gain", "loss",
        "rise", "fall", "up", "down",
    ]
    return any(word in q for word in sign_words)


def _detect_formula_type(q: str) -> Optional[str]:
    """Detect the formula type needed for the question."""
    if any(re.search(p, q) for p in PERCENTAGE_CHANGE_PATTERNS):
        return "percentage_change"
    if any(re.search(p, q) for p in SIMPLE_DELTA_PATTERNS):
        return "absolute_change"
    if any(re.search(p, q) for p in RATIO_PATTERNS):
        return "ratio"
    if any(re.search(p, q) for p in TEMPORAL_AVERAGE_PATTERNS):
        return "temporal_average"
    return None


def get_routing_recommendation(
    classification: ClassificationResult,
    layer0_passed: bool = True,
    layer0_confidence: str = "medium",
) -> str:
    """
    Get routing recommendation based on classification and Layer 0 results.

    Returns:
        "fast_path" - Skip Layer 1/2, use answer directly
        "layer1_only" - Use Layer 0 + Layer 1, skip LLM verification
        "full_verification" - Run full pipeline including multi-pass verification
    """
    # If Layer 0 failed, always escalate regardless of difficulty
    if not layer0_passed:
        return "full_verification"

    # Hard questions always get full verification
    if classification.difficulty == Difficulty.HARD:
        return "full_verification"

    # Easy questions with high Layer 0 confidence can use fast path
    if classification.difficulty == Difficulty.EASY:
        if layer0_confidence == "high":
            return "fast_path"
        return "layer1_only"

    # Medium questions: Layer 1 verification
    return "layer1_only"
