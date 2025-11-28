"""
Layer 2: LLM-Guided Re-extraction

Handles cases where Layer 0/1 detection indicates a problem but cannot auto-correct:
- Wrong values extracted from tables/text
- Missing operands for the formula
- Formula type confusion

Uses targeted LLM prompts to re-extract values with explicit guidance.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..utils.openai_client import get_client, get_model_name

logger = logging.getLogger(__name__)


@dataclass
class Layer2Input:
    """Input for Layer 2 re-extraction."""
    question: str
    evidence_text: str
    evidence_tables: List[List[List[str]]]  # Structured tables
    formula_type: Optional[str]
    original_answer: str
    original_operands: Optional[List[dict]]  # From Layer 1
    layer1_issues: List[str]


@dataclass
class Layer2Result:
    """Result from Layer 2 re-extraction."""
    corrected_answer: Optional[str]
    extracted_values: List[dict]  # {"label": ..., "value": ..., "source": ...}
    calculation_trace: str
    confidence: float  # 0-1 based on extraction quality
    correction_applied: bool
    strategy_used: str  # "focused", "table_sum", "formula_guided", "multi_pass"

    def to_dict(self) -> dict:
        return asdict(self)


# Trigger conditions for Layer 2
LAYER2_TRIGGER_ISSUES = {
    "recompute_mismatch",
    "missing_operands",
    "type_mismatch",  # Model answered with wrong format (e.g., % for absolute question)
    "formula_confusion",  # Model used wrong formula type
}

# Formula types that benefit from Layer 2
LAYER2_FORMULA_TYPES = {
    "average",
    "total",
    "percentage_change",
    "absolute_change",
    "change_of_averages",
    "difference_of_averages",
}


class Layer2Corrector:
    """LLM-guided re-extraction for complex calculation errors."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self._client = None
        self._model = model

    @property
    def client(self):
        """Lazy-load OpenAI/Azure client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    def should_trigger(self, layer1_issues: List[str], formula_type: Optional[str], confidence: str) -> bool:
        """Determine if Layer 2 should be triggered."""
        # Check for explicit trigger issues
        for issue in layer1_issues:
            for trigger in LAYER2_TRIGGER_ISSUES:
                if trigger in issue:
                    return True

        # Trigger on low confidence for certain formula types
        if confidence == "low" and formula_type in LAYER2_FORMULA_TYPES:
            return True

        return False

    def run(self, input: Layer2Input) -> Layer2Result:
        """Run Layer 2 re-extraction."""
        # Select strategy based on formula type and issues
        strategy = self._select_strategy(input)

        logger.info(f"Layer2: Using {strategy} strategy for formula_type={input.formula_type}")

        if strategy == "absolute_change":
            return self._run_absolute_change_extraction(input)
        elif strategy == "table_sum":
            return self._run_table_sum_extraction(input)
        elif strategy == "formula_guided":
            return self._run_formula_guided_extraction(input)
        else:
            return self._run_focused_extraction(input)

    def _select_strategy(self, input: Layer2Input) -> str:
        """Select the best extraction strategy."""
        q = input.question.lower()

        # Check for type_mismatch in issues - model used wrong formula type
        has_type_mismatch = any("type_mismatch" in issue for issue in input.layer1_issues)

        # Absolute change questions where model computed percentage
        if input.formula_type == "absolute_change" or (
            has_type_mismatch and "change" in q and "percent" not in q
        ):
            return "absolute_change"

        # Table sum for total/sum questions
        if input.formula_type == "total" or "total" in q or "sum" in q:
            return "table_sum"

        # Formula-guided for complex multi-step
        if input.formula_type in {"change_of_averages", "difference_of_averages"}:
            return "formula_guided"

        if "average" in q and ("change" in q or "between" in q):
            return "formula_guided"

        # Default to focused extraction
        return "focused"

    def _run_absolute_change_extraction(self, input: Layer2Input) -> Layer2Result:
        """Extract values and compute ABSOLUTE change (not percentage).

        This handles the common error where the model computes percentage change
        when the question asks for absolute change (e.g., "What is the change in X").
        """
        prompt = self._build_absolute_change_prompt(input)

        try:
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response)

            if parsed and "answer" in parsed:
                # Verify the calculation makes sense
                values = parsed.get("values", [])
                if len(values) >= 2:
                    # Check if we have the expected operands
                    confidence = 0.8
                else:
                    confidence = 0.6

                return Layer2Result(
                    corrected_answer=str(parsed["answer"]),
                    extracted_values=values,
                    calculation_trace=parsed.get("calculation", ""),
                    confidence=confidence,
                    correction_applied=True,
                    strategy_used="absolute_change",
                )
        except Exception as e:
            logger.warning(f"Layer2 absolute_change extraction failed: {e}")

        return Layer2Result(
            corrected_answer=None,
            extracted_values=[],
            calculation_trace="",
            confidence=0.0,
            correction_applied=False,
            strategy_used="absolute_change",
        )

    def _run_focused_extraction(self, input: Layer2Input) -> Layer2Result:
        """Focused extraction with explicit value guidance."""
        prompt = self._build_focused_prompt(input)

        try:
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response)

            if parsed and "answer" in parsed:
                return Layer2Result(
                    corrected_answer=str(parsed["answer"]),
                    extracted_values=parsed.get("values", []),
                    calculation_trace=parsed.get("calculation", ""),
                    confidence=0.7,
                    correction_applied=True,
                    strategy_used="focused",
                )
        except Exception as e:
            logger.warning(f"Layer2 focused extraction failed: {e}")

        return Layer2Result(
            corrected_answer=None,
            extracted_values=[],
            calculation_trace="",
            confidence=0.0,
            correction_applied=False,
            strategy_used="focused",
        )

    def _run_table_sum_extraction(self, input: Layer2Input) -> Layer2Result:
        """Table-aware sum extraction."""
        prompt = self._build_table_sum_prompt(input)

        try:
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response)

            if parsed and "answer" in parsed:
                # Verify the sum matches
                values = parsed.get("values", [])
                if values:
                    computed_sum = sum(v for v in values if isinstance(v, (int, float)))
                    reported_sum = parsed.get("sum", parsed["answer"])

                    # Check if sum is reasonable
                    if abs(computed_sum - float(reported_sum)) < 0.01 * abs(computed_sum):
                        confidence = 0.85
                    else:
                        confidence = 0.5
                else:
                    confidence = 0.6

                return Layer2Result(
                    corrected_answer=str(parsed["answer"]),
                    extracted_values=[{"label": r, "value": v} for r, v in zip(
                        parsed.get("rows_included", []),
                        parsed.get("values", [])
                    )],
                    calculation_trace=f"Sum of {len(values)} values: {parsed.get('values', [])}",
                    confidence=confidence,
                    correction_applied=True,
                    strategy_used="table_sum",
                )
        except Exception as e:
            logger.warning(f"Layer2 table_sum extraction failed: {e}")

        return Layer2Result(
            corrected_answer=None,
            extracted_values=[],
            calculation_trace="",
            confidence=0.0,
            correction_applied=False,
            strategy_used="table_sum",
        )

    def _run_formula_guided_extraction(self, input: Layer2Input) -> Layer2Result:
        """Formula-guided extraction for complex calculations."""
        prompt = self._build_formula_guided_prompt(input)

        try:
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response)

            if parsed and "answer" in parsed:
                # Verify the calculation
                values = parsed.get("values", [])
                confidence = 0.75 if len(values) >= 2 else 0.5

                return Layer2Result(
                    corrected_answer=str(parsed["answer"]),
                    extracted_values=values,
                    calculation_trace=parsed.get("calculation", ""),
                    confidence=confidence,
                    correction_applied=True,
                    strategy_used="formula_guided",
                )
        except Exception as e:
            logger.warning(f"Layer2 formula_guided extraction failed: {e}")

        return Layer2Result(
            corrected_answer=None,
            extracted_values=[],
            calculation_trace="",
            confidence=0.0,
            correction_applied=False,
            strategy_used="formula_guided",
        )

    def _build_absolute_change_prompt(self, input: Layer2Input) -> str:
        """Build prompt for ABSOLUTE change extraction (NOT percentage change).

        This prompt explicitly instructs the LLM to compute absolute difference,
        not percentage change. Critical for questions like:
        - "What is the change in X between Y and Z?"
        - "What is the change in the average X?"
        """
        tables_str = self._format_tables(input.evidence_tables)

        # Parse years from question if present
        years = re.findall(r'\b(20\d{2}|19\d{2})\b', input.question)

        # Check if this is a "change in average" question
        is_change_in_average = "average" in input.question.lower() and "change" in input.question.lower()

        if is_change_in_average:
            return f'''You are computing an ABSOLUTE CHANGE between averages.

Question: {input.question}

CRITICAL: This question asks for ABSOLUTE CHANGE (subtraction), NOT percentage change.
Do NOT compute (new-old)/old * 100. Instead compute: new_average - old_average

The previous answer "{input.original_answer}" appears to be a PERCENTAGE.
That is WRONG - we need the actual numeric DIFFERENCE.

Years mentioned: {years}

Steps:
1. Identify the metric being asked about
2. Find values for the relevant years
3. Compute the average for each period (if needed)
4. Compute the ABSOLUTE difference: later_value - earlier_value

Evidence (tables):
{tables_str}

Evidence (text):
{input.evidence_text[:2500]}

Return ONLY valid JSON:
{{
  "values": [
    {{"label": "metric year1", "value": numeric_value}},
    {{"label": "metric year2", "value": numeric_value}},
    ...
  ],
  "average_1": {{"period": "description", "value": numeric_value}},
  "average_2": {{"period": "description", "value": numeric_value}},
  "calculation": "show: avg2 - avg1 = difference",
  "answer": final_numeric_difference
}}
'''
        else:
            return f'''You are computing an ABSOLUTE CHANGE (difference).

Question: {input.question}

CRITICAL: This question asks for ABSOLUTE CHANGE (subtraction), NOT percentage change.
Do NOT compute (new-old)/old * 100. Instead compute: new_value - old_value

The previous answer "{input.original_answer}" appears to be wrong.
We need the actual numeric DIFFERENCE.

Years mentioned: {years}

Steps:
1. Identify what values to compare
2. Find the values for each period
3. Compute the ABSOLUTE difference: later_value - earlier_value

Evidence (tables):
{tables_str}

Evidence (text):
{input.evidence_text[:2500]}

Return ONLY valid JSON:
{{
  "values": [
    {{"label": "old_value", "value": numeric_value}},
    {{"label": "new_value", "value": numeric_value}}
  ],
  "calculation": "new - old = difference",
  "answer": final_numeric_difference
}}
'''

    def _build_focused_prompt(self, input: Layer2Input) -> str:
        """Build prompt for focused value extraction."""
        formula_desc = self._get_formula_description(input.formula_type)

        # Format tables
        tables_str = self._format_tables(input.evidence_tables)

        return f'''You are extracting specific values to answer a financial question.

Question: {input.question}

Formula type detected: {input.formula_type or "unknown"}
{formula_desc}

The previous extraction got: {input.original_answer}
This appears to be WRONG. Please re-extract the correct values.

Evidence (text):
{input.evidence_text[:3000]}

Evidence (tables):
{tables_str}

Extract the exact values needed and compute the answer.

Return ONLY valid JSON:
{{
  "values": [
    {{"label": "description of value", "value": numeric_value, "source": "where found"}},
    ...
  ],
  "calculation": "show step by step calculation",
  "answer": final_numeric_answer
}}
'''

    def _build_table_sum_prompt(self, input: Layer2Input) -> str:
        """Build prompt for table sum extraction."""
        tables_str = self._format_tables(input.evidence_tables)

        return f'''You are computing a SUM or TOTAL from a financial table.

Question: {input.question}

IMPORTANT: You must identify ALL rows that should be included in the sum.

The previous answer was: {input.original_answer}
This appears to be WRONG - likely missing some values.

Tables:
{tables_str}

Text context:
{input.evidence_text[:2000]}

Instructions:
1. Identify which column contains the values to sum
2. List EVERY row that should be included
3. Show each value explicitly
4. Compute the sum

Return ONLY valid JSON:
{{
  "rows_included": ["row label 1", "row label 2", ...],
  "values": [value1, value2, ...],
  "sum": computed_sum,
  "answer": final_answer
}}
'''

    def _build_formula_guided_prompt(self, input: Layer2Input) -> str:
        """Build prompt for formula-guided extraction."""
        # Parse years from question if present
        years = re.findall(r'\b(20\d{2}|19\d{2})\b', input.question)

        tables_str = self._format_tables(input.evidence_tables)

        if "average" in input.question.lower() and "change" in input.question.lower():
            # Change between averages
            return f'''You are computing a CHANGE BETWEEN AVERAGES.

Question: {input.question}

This requires:
1. Computing the average for one period (e.g., avg of 2019 = (2019 + 2018) / 2)
2. Computing the average for another period
3. Finding the DIFFERENCE between these averages

Years mentioned: {years}

The previous answer was: {input.original_answer}
This appears to be WRONG.

Tables:
{tables_str}

Text:
{input.evidence_text[:2000]}

Extract ALL values needed (typically 4 values for 2 averages):

Return ONLY valid JSON:
{{
  "values": [
    {{"label": "metric year1", "value": ...}},
    {{"label": "metric year2", "value": ...}},
    ...
  ],
  "average_1": {{"years": [...], "value": ...}},
  "average_2": {{"years": [...], "value": ...}},
  "calculation": "step by step",
  "answer": final_difference
}}
'''

        # Generic formula-guided
        return f'''You are extracting values for a financial calculation.

Question: {input.question}
Formula type: {input.formula_type}

The previous answer was: {input.original_answer}
This appears to be WRONG.

Tables:
{tables_str}

Text:
{input.evidence_text[:2000]}

Extract the correct values and compute the answer.

Return ONLY valid JSON:
{{
  "values": [{{"label": "...", "value": ...}}, ...],
  "calculation": "show work",
  "answer": final_answer
}}
'''

    def _get_formula_description(self, formula_type: Optional[str]) -> str:
        """Get description of the formula type."""
        descriptions = {
            "percentage_change": "Formula: (new - old) / old * 100",
            "absolute_change": "Formula: new - old (NOT percentage)",
            "average": "Formula: sum(values) / count(values)",
            "total": "Formula: sum(all relevant values)",
            "ratio": "Formula: numerator / denominator",
            "proportion": "Formula: part / whole (result 0-1)",
            "change_of_averages": "Formula: avg_period2 - avg_period1 (each avg = sum/count)",
        }
        return descriptions.get(formula_type, "")

    def _format_tables(self, tables: List[List[List[str]]]) -> str:
        """Format tables for prompt."""
        if not tables:
            return "No tables provided"

        result = []
        for i, table in enumerate(tables):
            if not table:
                continue
            result.append(f"Table {i+1}:")
            for row in table[:20]:  # Limit rows
                result.append(" | ".join(str(cell) for cell in row))
            result.append("")

        return "\n".join(result) if result else "No tables provided"

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a precise financial data extractor. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        return response.choices[0].message.content or ""

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response."""
        # Try to extract JSON from response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON object in response
            match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass

        return None


def run_layer2(input: Layer2Input) -> Layer2Result:
    """Convenience function to run Layer 2 correction."""
    corrector = Layer2Corrector()
    return corrector.run(input)


def should_trigger_layer2(
    layer1_issues: List[str],
    formula_type: Optional[str],
    confidence: str
) -> bool:
    """Check if Layer 2 should be triggered."""
    corrector = Layer2Corrector()
    return corrector.should_trigger(layer1_issues, formula_type, confidence)
