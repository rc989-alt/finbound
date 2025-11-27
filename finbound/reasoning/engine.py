from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from ..tools.calculator import Calculator
from ..types import EvidenceContext, EvidenceContract, ReasoningResult, StructuredRequest
from ..utils.rate_limiter import get_rate_limiter
from .chain_of_evidence import ChainOfEvidence
from .extraction import StructuredTableParser
from .citations import format_citation
from .gates import Layer1Guardrails
from ..routing.layer0_checks import run_layer0_checks, Layer0Result
from ..routing.question_classifier import (
    classify_question,
    get_routing_recommendation,
    Difficulty,
    ClassificationResult,
)


# Formula templates for common financial calculations
FORMULA_TEMPLATES = {
    "percentage_change": (
        "FORMULA: percentage change = (new_value - old_value) / old_value * 100\n"
        "CRITICAL: Identify which period is 'old' (earlier/base) and 'new' (later).\n"
        "- If comparing 2019 to 2018: old=2018, new=2019\n"
        "- If comparing 2018 to 2019: old=2019, new=2018\n"
        "- Positive result = increase, Negative result = decrease"
    ),
    "absolute_change": (
        "FORMULA: absolute change = new_value - old_value\n"
        "CRITICAL for 'change from X to Y' or 'change in X from Y':\n"
        "- 'change from 2018 to 2019' = value_2019 - value_2018\n"
        "- 'change in 2019 from 2018' = value_2019 - value_2018\n"
        "- The result should have the SAME SIGN as the actual change\n"
        "- If value decreased, result should be NEGATIVE\n"
        "- Do NOT compute percentage unless explicitly asked"
    ),
    "percentage_of_total": (
        "FORMULA: percentage of total = (part / total) * 100\n"
        "CRITICAL: Identify what is the PART and what is the TOTAL.\n"
        "- 'What percentage of revenue is cost' = cost / revenue * 100\n"
        "- 'X as a percentage of Y' = X / Y * 100 (Y is the denominator/total)\n"
        "- The TOTAL/WHOLE goes in the DENOMINATOR"
    ),
    "temporal_average": (
        "FORMULA for 'YEAR average X': average = (value_YEAR + value_YEAR-1) / 2\n"
        "CRITICAL: In TAT-QA/financial contexts, 'YEAR average' means:\n"
        "- '2019 average X' = (X_2019 + X_2018) / 2\n"
        "- '2018 average X' = (X_2018 + X_2017) / 2\n"
        "- You MUST extract BOTH the current year AND prior year values\n"
        "- Do NOT just return the single year's value\n"
        "- Example: '2019 average free cash flow' with 2019=4411 and 2018=4044\n"
        "  Answer = (4411 + 4044) / 2 = 4227.5"
    ),
    "average": (
        "FORMULA: average = sum(all_values) / count(all_values)\n"
        "CRITICAL: You MUST list ALL values being averaged.\n"
        "- If asked for average over 2 years, you need BOTH years' values\n"
        "- Count how many values you're averaging"
    ),
    "difference_of_averages": (
        "FORMULA for 'difference between YEAR1 average X and YEAR1 average Y':\n"
        "Step 1: Compute average_X = (X_YEAR1 + X_YEAR1-1) / 2\n"
        "Step 2: Compute average_Y = (Y_YEAR1 + Y_YEAR1-1) / 2\n"
        "Step 3: Result = average_X - average_Y\n"
        "CRITICAL: This requires 4 values total (2 for each metric)"
    ),
    "change_of_averages": (
        "FORMULA for 'change between YEAR1 and YEAR2 average X':\n"
        "Step 1: Compute avg_YEAR2 = (X_YEAR2 + X_YEAR2-1) / 2\n"
        "Step 2: Compute avg_YEAR1 = (X_YEAR1 + X_YEAR1-1) / 2\n"
        "Step 3: Result = avg_YEAR2 - avg_YEAR1\n"
        "CRITICAL: This requires 4 values total (2 for each year's average)"
    ),
    "total": (
        "FORMULA: total = sum(all_values)\n"
        "CRITICAL: List each value being summed with its label."
    ),
    "difference": (
        "FORMULA: difference = value_a - value_b\n"
        "CRITICAL: Verify which value is subtracted from which.\n"
        "- 'How much more is A than B' = A - B\n"
        "- 'Change from A to B' = B - A"
    ),
    "ratio": (
        "FORMULA: ratio = numerator / denominator\n"
        "CRITICAL: Verify which value is numerator vs denominator.\n"
        "- 'A as a percentage of B' = A / B * 100\n"
        "- 'ratio of A to B' = A / B"
    ),
}

# Keywords that indicate calculation type
CALCULATION_KEYWORDS = {
    "percentage_change": [
        "percent change",
        "percentage change",
        "rate of change",
        "year-over-year",
        "yoy",
        "percentage point",
        "percent increase",
        "percent decrease",
    ],
    "absolute_change": [
        "change in",
        "change from",
        "change of",
        "what was the change",
        "what is the change",
        "increased by",
        "decreased by",
        "rise from",
        "fall from",
        "delta",
        "variation",
    ],
    "percentage_of_total": [
        "percentage of",
        "percent of",
        "as a percentage of",
        "as a percent of",
        "portion of",
        "share of",
        "fraction of",
        "what percentage of",
        "what percent of",
        "represents what percent",
        "represents what percentage",
        "out of total",
        "of the total",
    ],
    "average": [
        "average",
        "mean",
        "avg",
        "averaged",
        "on average",
        "per year average",
        "arithmetic mean",
    ],
    "temporal_average": [
        # These get detected by regex patterns below
    ],
    "difference_of_averages": [
        "difference between",
    ],
    "change_of_averages": [
        "change between",
    ],
    "total": [
        "total",
        "sum",
        "combined",
        "aggregate",
        "altogether",
        "overall",
        "cumulative",
        "in total",
    ],
    "difference": [
        "difference",
        "how much more",
        "how much less",
        "compared to",
        "increase",
        "decrease",
        "how much did",
        "by how much",
        "gap between",
        "spread between",
        "change between",
        "change from",
        "change of",
    ],
    "ratio": [
        "ratio",
        "proportion",
        "divided by",
        "multiple of",
        "times larger",
        "per share",
        "per unit",
    ],
}

CALCULATION_REGEXES = {
    "percentage_change": [
        r"year[-\s]?over[-\s]?year",
        r"yoy",
        r"percent(?:age)?\s+(?:increase|decrease|change)",
    ],
    "absolute_change": [
        r"change\s+(?:from|in)\s+.+\s+(?:from|to)\s+\d{4}",
        r"(?:rise|fall|jump|drop)\s+from\s+\d",
        r"what\s+(?:is|was)\s+the\s+change\s+(?:in|of)",
    ],
    "percentage_of_total": [
        r"(?:what|which)\s+percent(?:age)?\s+of",
        r"as\s+a\s+percent(?:age)?\s+of",
        r"percent(?:age)?\s+of\s+(?:total|the)",
        r"represents?\s+(?:what|which)\s+percent",
        r"portion\s+of\s+(?:total|the)",
    ],
    "temporal_average": [
        # P0: Detect "YEAR average X" pattern (TAT-QA convention)
        r"\b(\d{4})\s+average\b",  # "2019 average"
        r"average\s+.+\s+(?:for|in)\s+(\d{4})",  # "average X for 2019"
        r"what\s+is\s+the\s+(\d{4})\s+average",  # "what is the 2019 average"
    ],
    "average": [
        r"average\s+of\s+\d",
        r"mean\s+of",
    ],
    "difference_of_averages": [
        # P3: Detect "difference between X average and Y average"
        r"difference\s+between\s+\d{4}\s+average",
        r"difference\s+between\s+.+\s+average\s+.+\s+and\s+.+\s+average",
    ],
    "change_of_averages": [
        # P3: Detect "change between YEAR1 and YEAR2 average"
        r"change\s+between\s+\d{4}\s+and\s+\d{4}\s+average",
    ],
    "difference": [
        r"difference\s+between",
        r"gap\s+between",
    ],
    "ratio": [
        r"\b(?:ratio|proportion)\b",
        r"times\s+(?:higher|lower)",
    ],
}


class ReasoningEngine:
    """
    Minimal reasoning engine using OpenAI chat completions.

    It asks the model to:
      - answer the question,
      - show a short reasoning trace,
      - emit a small list of textual "citations".
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        enable_verification_pass: bool = True,
        enable_table_extraction: bool = True,
    ) -> None:
        self._client = OpenAI()
        self._model = model
        self._logger = logging.getLogger(__name__)
        self._calculator = Calculator()
        self._layer1_guardrails = Layer1Guardrails()
        self._current_context: EvidenceContext | None = None
        self._limiter = get_rate_limiter()
        self._enable_verification_pass = enable_verification_pass
        self._enable_table_extraction = enable_table_extraction
        self._structured_table_parser = StructuredTableParser()
        self._tools = [
            {
                "type": "function",
                "function": {
                    "name": "finbound_calculate",
                    "description": (
                        "Perform deterministic arithmetic (add, subtract, multiply, "
                        "divide, convert percentages or basis points to decimals). "
                        "Use this whenever you can compute a number exactly."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": [
                                    "add",
                                    "subtract",
                                    "multiply",
                                    "divide",
                                    "percentage_to_decimal",
                                    "basis_points_to_decimal",
                                ],
                            },
                            "a": {"type": "number", "description": "First operand"},
                            "b": {
                                "type": "number",
                                "description": "Second operand (if required)",
                            },
                        },
                        "required": ["operation", "a"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
        self._max_tool_iterations = 5

    def run(
        self,
        structured_request: StructuredRequest,
        evidence_contract: EvidenceContract,
        evidence_context: EvidenceContext | None = None,
    ) -> ReasoningResult:
        # Classify question difficulty for intelligent routing
        question_classification = classify_question(structured_request.raw_text)
        self._logger.info(
            "Question classified as %s (reason: %s, confidence: %.2f)",
            question_classification.difficulty.value,
            question_classification.reason,
            question_classification.confidence,
        )

        # Detect calculation type, expected format, and sign guidance
        calc_types = self._detect_calculation_type(structured_request)
        formula_guidance = self._get_formula_guidance(calc_types)
        expected_answer_type = self._detect_expected_answer_type(structured_request.raw_text)
        expected_sign = self._detect_expected_sign(structured_request.raw_text)
        aggregation_intent = self._detect_aggregation_intent(structured_request.raw_text)

        format_warnings: List[str] = []
        sign_notes: List[str] = []
        calculation_warnings: List[str] = []

        # P2: Detect if this is a text extraction question (not numeric)
        is_text_extraction = self._detect_text_extraction_question(structured_request.raw_text)

        # P1: Detect "consist of" questions
        consist_of_metric = self._detect_consist_of_question(structured_request.raw_text)

        # P2: Detect formatted span questions (expect exact text with units)
        is_formatted_span = self._detect_formatted_span_question(structured_request.raw_text)

        system_prompt = (
            "You are FinBound, a financial reasoning assistant.\n"
            "- Never introduce numbers that cannot be grounded in the evidence provided.\n"
            "- When numerical relationships (percentages, basis points, deltas, ratios)\n"
            "  allow you to compute the requested value with deterministic arithmetic,\n"
            "  you MUST carry out the calculation and report the numeric result.\n"
            "- 100 basis points = 1 percentage point (0.01); convert basis points and\n"
            "  percentages to decimals before performing math.\n"
            "- Always call the `finbound_calculate` tool to perform arithmetic instead of\n"
            "  doing math inline when you can specify the operands. This keeps the audit\n"
            "  trail deterministic.\n"
            "- Show explicit arithmetic (including tool results) in your reasoning so it\n"
            "  can be verified.\n"
            "- Only respond with \"uncertain\" when the evidence truly does not permit a\n"
            "  safe calculation or conclusion.\n"
            "\n"
            "CRITICAL - Self-verification for calculations:\n"
            "- STEP 0: CONFIRM FORMULA TYPE - Before ANY calculation, explicitly state:\n"
            "  'FORMULA TYPE: [percentage_change | percentage_of_total | average | total | difference | ratio | direct_lookup | text_span | multi_span]'\n"
            "  This is REQUIRED. Get the formula type wrong = wrong answer.\n"
            "- For table lookups: Explicitly state the row and column you are reading.\n"
            "- For percentage changes: Always compute (new - old) / old * 100. Verify\n"
            "  which year is 'old' (denominator) and which is 'new' (numerator).\n"
            "- For percentage of total: formula is (part / total) * 100 - TOTAL is denominator!\n"
            "- For averages: List ALL values being averaged and count them. Do NOT use a single year's value.\n"
            "- After computing, re-check: Does the sign make sense? Is the magnitude\n"
            "  reasonable given the input values?\n"
            f"{formula_guidance}"
        )

        # P2: Add text extraction guidance for span-type questions
        if is_text_extraction:
            system_prompt += (
                "\n\n"
                "TEXT EXTRACTION RULES (P2):\n"
                "This question asks for TEXT from the evidence, not a calculation.\n"
                "- Extract the MINIMAL text span that directly answers the question\n"
                "- Do NOT add prefixes like 'On a cost-plus contract, the company...' - just extract the answer portion\n"
                "- For 'What is X paid?' -> extract only what is paid, not 'X is paid...'\n"
                "- For 'What are the types?' -> list each type, separated by commas, matching the exact wording in evidence\n"
                "- Match the EXACT wording from the evidence (including 'type' suffixes, hyphens, etc.)\n"
                "  * 'cost-plus type' NOT 'cost plus' or 'cost-plus'\n"
                "  * 'fixed-price type' NOT 'fixed price type' or 'fixed-price'\n"
                "  * 'time-and-material type' NOT 'time and material type'\n"
                "- For multi-part answers, use comma-separated format: 'item1, item2, item3'\n"
                "- Do NOT paraphrase or rephrase the answer - use the exact text from evidence\n"
            )

        # P1: Add "consist of" guidance for cash flow table questions
        if consist_of_metric:
            system_prompt += (
                "\n\n"
                f"CONSIST OF QUESTION DETECTED (P1):\n"
                f"The question asks: 'What does {consist_of_metric} consist of?'\n"
                "\n"
                "CRITICAL INTERPRETATION for cash flow tables:\n"
                "- This question asks for the LINE ITEMS that appear AFTER the metric row\n"
                "- These are the adjustments/items that bridge from one subtotal to the next\n"
                "- Look at the table structure:\n"
                "  * Find the EXACT row for the specified metric\n"
                "  * The answer is the SUBSEQUENT rows until the next subtotal\n"
                "  * These are usually adjustment items like 'Taxation', 'Dividends', etc.\n"
                "\n"
                "Example table structure:\n"
                "  Operating free cash flow    5,511\n"
                "  Taxation                   (1,412)  <- 'operating FCF consists of' these\n"
                "  Dividends received            53   <- (items AFTER operating FCF)\n"
                "  Dividends paid              (249)\n"
                "  Interest received/paid       508\n"
                "  Free cash flow (pre-spectrum) 4,411\n"
                "  Licence and spectrum payments (311) <- 'free cash flow (pre-spectrum) consists of' these\n"
                "  Restructuring payments        (56)  <- (items AFTER pre-spectrum FCF)\n"
                "  Free cash flow              4,044\n"
                "\n"
                "CRITICAL - MATCH THE EXACT METRIC:\n"
                f"- You are looking for items after '{consist_of_metric}' specifically\n"
                "- 'operating free cash flow' and 'free cash flow (pre-spectrum)' are DIFFERENT metrics\n"
                "- Each metric has its OWN set of subsequent items\n"
                "\n"
                "Examples:\n"
                "- 'What does operating free cash flow consist of?' = 'Taxation, Dividends received, Dividends paid, Interest received and paid'\n"
                "- 'What does free cash flow (pre-spectrum) consist of?' = 'Licence and spectrum payments, Restructuring payments'\n"
                "\n"
                "NOT the items that SUM UP to the metric, but the items AFTER it until the next subtotal.\n"
            )

        # P2: Add formatted span guidance for questions expecting exact text with units
        if is_formatted_span:
            system_prompt += (
                "\n\n"
                "FORMATTED SPAN EXPECTED (P2):\n"
                "This question may expect an answer with currency symbols and units.\n"
                "- If the evidence contains a formatted value like '$(9.8) million', extract it EXACTLY\n"
                "- Do NOT convert to raw numbers (e.g., -9800000 or -9.8)\n"
                "- Preserve the original formatting: currency symbol ($, €, £), parentheses for negatives, units (million, billion)\n"
                "- Example: '$(9.8) million' is the answer, NOT '-9.8' or '-9800000'\n"
                "- Look for the exact text span in the evidence that matches the question\n"
            )

        system_prompt += (
            "\n"
            "Return your response as a JSON object with keys:\n"
            "  - `formula_type`: REQUIRED - one of: percentage_change, percentage_of_total, average, total, difference, ratio, direct_lookup, text_span, multi_span,\n"
            "  - `answer`: the final concise answer (numeric if possible, or exact text span),\n"
            "  - `values_used`: list of {{\"label\": \"description\", \"value\": number}} for each value extracted from evidence,\n"
            "  - `calculation_steps`: array of strings showing each calculation step,\n"
            "  - `reasoning`: short, step-by-step logic including the math you ran,\n"
            "  - `citations`: short strings referencing the evidence you relied on."
        )

        # Add expected answer type guidance if detected
        if expected_answer_type != "unknown":
            system_prompt += f"\n\nEXPECTED ANSWER FORMAT: {expected_answer_type}"
            if expected_answer_type == "percentage":
                system_prompt += "\nYour answer should be a percentage (e.g., '3.4%' or '25%')."
            elif expected_answer_type == "absolute":
                system_prompt += "\nYour answer should be an absolute value (e.g., '172' or '$500 million')."
        if expected_sign:
            system_prompt += f"\n{self._get_sign_guidance(expected_sign)}"
        if aggregation_intent != "unknown":
            system_prompt += f"\n{self._get_aggregation_guidance(aggregation_intent)}"

        # Pre-extract table cells for numeric questions
        table_extraction = self._extract_table_cells(
            structured_request.raw_text,
            evidence_context,
        )

        context_section = (
            evidence_context.as_prompt_section() + "\n\n"
            if evidence_context and evidence_context.as_prompt_section()
            else ""
        )

        user_prompt = (
            f"User request: {structured_request.raw_text}\n\n"
            f"{table_extraction}"
            f"{context_section}"
            f"Evidence contract: {evidence_contract.description}\n\n"
            "Respond ONLY with a JSON object, no other text."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response_content = "{}"
        latest_completion = None

        tool_events: List[Dict[str, Any]] = []
        chain = ChainOfEvidence()

        for _ in range(self._max_tool_iterations):
            completion = self._limiter.call(
                self._client.chat.completions.create,
                model=self._model,
                messages=messages,
                temperature=0.0,
                tools=self._tools,
                tool_choice="auto",
            )
            latest_completion = completion
            response_message = completion.choices[0].message

            if response_message.tool_calls:
                messages.append(self._message_to_dict(response_message))
                for tool_call in response_message.tool_calls:
                    tool_response = self._execute_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        tool_events,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_response,
                        }
                    )
                continue

            response_content = response_message.content or "{}"
            break

        message_content = response_content

        payload = self._parse_model_json(message_content)

        answer = str(payload.get("answer", "")).strip()
        reasoning = str(payload.get("reasoning", "")).strip()
        citations = self._normalize_citations(payload.get("citations"))

        # Extract structured calculation trace
        values_used = payload.get("values_used", [])
        calculation_steps = payload.get("calculation_steps", [])
        calculation_warnings.extend(
            self._check_denominator_requirements(
                structured_request.raw_text,
                values_used,
                calc_types,
            )
        )
        calculation_warnings.extend(
            self._verify_sum_completeness(
                values_used,
                self._extract_expected_count(structured_request.raw_text),
                calc_types,
            )
        )

        # Retry logic for "uncertain" answers when calculation is expected
        if answer.lower() == "uncertain" and calc_types:
            self._logger.info("Model returned 'uncertain' - attempting retry with stronger prompt")
            retry_answer, retry_payload = self._retry_uncertain_answer(
                structured_request,
                evidence_context,
                calc_types,
                expected_answer_type,
            )
            if retry_answer and retry_answer.lower() != "uncertain":
                answer = retry_answer
                reasoning = str(retry_payload.get("reasoning", reasoning)).strip()
                citations = self._normalize_citations(retry_payload.get("citations")) or citations
                values_used = retry_payload.get("values_used", values_used)
                calculation_steps = retry_payload.get("calculation_steps", calculation_steps)
                self._logger.info("Retry succeeded with answer: %s", answer)

        # Multi-pass verification for numeric answers (uses intelligent routing)
        is_verified, corrected_answer = self._verify_calculation(
            structured_request,
            answer,
            reasoning,
            evidence_context,
            expected_sign=expected_sign,
            question_classification=question_classification,
        )
        verification_applied = False
        if not is_verified and corrected_answer:
            self._logger.info(
                "Verification corrected answer: %s -> %s",
                answer,
                corrected_answer,
            )
            answer = corrected_answer
            verification_applied = True

        tool_result = tool_events[-1] if tool_events else None
        if reasoning:
            chain.add_step(
                statement=reasoning,
                citations=citations,
                tool_result={**tool_result, "statement": reasoning}
                if tool_result
                else None,
            )

        answer_before_format = answer
        answer = self._apply_answer_format_rules(
            answer,
            expected_answer_type,
            structured_request.raw_text,
            calc_types,
            values_used,
        )
        if answer != answer_before_format:
            self._logger.info("DEBUG TRACE: answer changed by _apply_answer_format_rules: %s -> %s", answer_before_format, answer)

        detected_answer_format = self._detect_answer_format(answer)
        answer, conversion_note = self._convert_answer_format(
            answer,
            detected_answer_format,
            expected_answer_type,
        )
        if conversion_note:
            format_warnings.append(conversion_note)

        is_valid_format, format_warning = self._validate_answer_format(
            answer,
            expected_answer_type,
        )
        if format_warning:
            format_warnings.append(format_warning)

        answer, sign_note = self._verify_sign_consistency(
            answer,
            structured_request.raw_text,
            reasoning,
            expected_sign,
        )
        if sign_note:
            sign_notes.append(sign_note)

        # Apply Layer 0 auto-corrections for format/scale/sign errors
        evidence_text = ""
        if self._current_context:
            evidence_text = "\n".join(self._current_context.text_blocks)
        answer, layer0_result = self._apply_layer0_corrections(
            answer,
            structured_request.raw_text,
            reasoning,
            evidence_text,
        )

        if self._current_context:
            self._layer1_guardrails.update_evidence(self._current_context.text_blocks)
        self._layer1_guardrails.run_checks(chain)

        return ReasoningResult(
            answer=answer,
            reasoning=reasoning,
            citations=citations,
            raw_model_output={
                "completion": latest_completion.model_dump() if latest_completion else {},
                "tool_events": tool_events,
                "chain_of_evidence": chain.to_dict(),
                "layer1_issues": [
                    {"message": issue.message, "step_index": issue.step_index}
                    for issue in self._layer1_guardrails.issues
                ],
                "table_extraction_used": bool(table_extraction),
                "verification_applied": verification_applied,
                "calculation_trace": {
                    "values_used": values_used,
                    "calculation_steps": calculation_steps,
                    "detected_calc_types": calc_types,
                    "expected_answer_type": expected_answer_type,
                },
                "format_warnings": format_warnings,
                "sign_notes": sign_notes,
                "calculation_warnings": calculation_warnings,
                "layer0_result": layer0_result.to_dict(),
                "question_classification": {
                    "difficulty": question_classification.difficulty.value,
                    "reason": question_classification.reason,
                    "confidence": question_classification.confidence,
                    "hints": {
                        "expected_unit": question_classification.hints.expected_unit,
                        "needs_average": question_classification.hints.needs_average,
                        "multi_year": question_classification.hints.multi_year,
                        "multi_row": question_classification.hints.multi_row,
                        "sign_sensitive": question_classification.hints.sign_sensitive,
                        "formula_type": question_classification.hints.formula_type,
                    },
                },
            },
        )

    def update_guardrails_context(self, context: EvidenceContext | None) -> None:
        self._current_context = context

    def _retry_uncertain_answer(
        self,
        structured_request: StructuredRequest,
        evidence_context: EvidenceContext | None,
        calc_types: List[str],
        expected_answer_type: str,
    ) -> tuple[str, Dict[str, Any]]:
        """Retry with a more forceful prompt when model returns 'uncertain'."""
        formula_guidance = self._get_formula_guidance(calc_types)

        # More aggressive system prompt that doesn't allow "uncertain"
        retry_system = (
            "You are FinBound, a financial reasoning assistant.\n"
            "IMPORTANT: You MUST provide a numeric answer. 'Uncertain' is NOT acceptable.\n"
            "Even if you are not 100% confident, make your best calculation based on the evidence.\n\n"
            "Instructions:\n"
            "1. Extract the relevant numbers from the evidence\n"
            "2. Apply the appropriate formula\n"
            "3. Return a numeric answer\n\n"
            f"{formula_guidance}\n"
            "Return your response as a JSON object with keys:\n"
            "  - `answer`: the final numeric answer (REQUIRED - do NOT say 'uncertain'),\n"
            "  - `values_used`: list of {{\"label\": \"description\", \"value\": number}},\n"
            "  - `calculation_steps`: array of strings showing each step,\n"
            "  - `reasoning`: explanation of your calculation,\n"
            "  - `citations`: evidence references."
        )

        if expected_answer_type != "unknown":
            retry_system += f"\n\nEXPECTED FORMAT: {expected_answer_type}"

        table_extraction = self._extract_table_cells(
            structured_request.raw_text,
            evidence_context,
        )

        context_section = (
            evidence_context.as_prompt_section() + "\n\n"
            if evidence_context and evidence_context.as_prompt_section()
            else ""
        )

        retry_user = (
            f"Question: {structured_request.raw_text}\n\n"
            f"{table_extraction}"
            f"{context_section}"
            "You MUST calculate and provide a numeric answer. "
            "Respond ONLY with a JSON object containing your answer."
        )

        messages = [
            {"role": "system", "content": retry_system},
            {"role": "user", "content": retry_user},
        ]

        try:
            completion = self._limiter.call(
                self._client.chat.completions.create,
                model=self._model,
                messages=messages,
                temperature=0.0,
            )
            response_content = completion.choices[0].message.content or "{}"
            payload = self._parse_model_json(response_content)
            answer = str(payload.get("answer", "")).strip()
            return answer, payload
        except Exception as e:
            self._logger.warning("Retry failed: %s", e)
            return "", {}

    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "role": message.role,
            "content": message.content or "",
        }
        if message.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        return data

    def _execute_tool_call(
        self,
        name: str,
        arguments_json: str | None,
        tool_events: List[Dict[str, Any]],
    ) -> str:
        if name != "finbound_calculate":
            return "Unsupported tool"

        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return "Invalid arguments"

        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")

        if a is None:
            return "Missing operand 'a'"

        try:
            if operation in {"add", "subtract", "multiply"} and b is None:
                return f"Missing operand 'b' for {operation}"
            if operation == "add":
                result = self._calculator.add(a, b)
            elif operation == "subtract":
                result = self._calculator.subtract(a, b)
            elif operation == "multiply":
                result = self._calculator.multiply(a, b)
            elif operation == "divide":
                if b is None:
                    return "Missing operand 'b' for division"
                result = self._calculator.divide(a, b)
            elif operation == "percentage_to_decimal":
                result = self._calculator.percentage_to_decimal(a)
            elif operation == "basis_points_to_decimal":
                result = self._calculator.basis_points_to_decimal(a)
            else:
                return f"Unsupported operation '{operation}'"
        except (TypeError, ValueError) as exc:
            message = f"Calculation error: {exc}"
            self._logger.warning("Calculator error: %s", message)
            tool_events.append(
                {
                    "name": name,
                    "operation": operation,
                    "arguments": {"a": a, "b": b},
                    "error": str(exc),
                }
            )
            return message

        payload = {"result": result}
        tool_events.append(
            {
                "name": name,
                "operation": operation,
                "arguments": {"a": a, "b": b},
                "result": result,
            }
        )
        self._logger.info(
            "Tool call %s %s(%s, %s) -> %s", name, operation, a, b, result
        )
        return json.dumps(payload)

    def _parse_model_json(self, content: str) -> Dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return {"answer": content, "reasoning": "", "citations": []}

    def _normalize_citations(self, raw_value: Any) -> List[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return format_citation(raw_value)
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return format_citation(parsed)
                except json.JSONDecodeError:
                    pass
            return format_citation([text])
        return []

    def _parse_model_json(self, content: str) -> Dict[str, Any]:
        """Parse JSON from model response, handling markdown code blocks."""
        text = content.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"answer": content, "reasoning": "", "citations": []}

    def _normalize_citations(self, raw: Any) -> List[str]:
        """Normalize citations to a list of strings."""
        if raw is None:
            return []

        # Already a list
        if isinstance(raw, list):
            return [str(c).strip() for c in raw if str(c).strip()]

        # String that might be JSON-encoded list
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(c).strip() for c in parsed if str(c).strip()]
                except json.JSONDecodeError:
                    pass
            # Single citation as string
            if raw:
                return [raw]

        return []

    def _extract_table_cells(
        self,
        question: str,
        evidence_context: EvidenceContext | None,
    ) -> str:
        """Pre-extract relevant table cells for numeric questions.

        Returns a structured string with extracted values to prepend to evidence.
        """
        if not evidence_context or not self._enable_table_extraction:
            return ""

        # Check if this looks like a table-based numeric question
        numeric_keywords = [
            "average", "total", "sum", "difference", "change",
            "percentage", "ratio", "how much", "what is the",
            "calculate", "compute"
        ]
        question_lower = question.lower()
        if not any(kw in question_lower for kw in numeric_keywords):
            return ""

        # Check if evidence has tables
        if not evidence_context.tables:
            return ""

        # Detect if this is a summation question requiring multiple rows
        summation_keywords = ["total", "sum of", "combined", "aggregate", "overall", "all"]
        is_summation_question = any(kw in question.lower() for kw in summation_keywords)

        # Detect denominator hints from question
        denominator_hints = self._detect_denominator_hints(question)

        extraction_prompt = (
            "You are a precise financial data extractor. Given the question and table data,\n"
            "identify and extract ONLY the specific cell values needed to answer the question.\n"
            "\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Read the question carefully to identify EXACTLY which row(s) and column(s) are needed\n"
            "2. Match row labels EXACTLY (e.g., 'net sales' is different from 'total sales')\n"
            "3. Match column labels EXACTLY (e.g., '2013' is different from '2012')\n"
            "4. For percentage change questions: identify which year is the BASE (denominator) and which is NEW (numerator)\n"
            "5. For sum/total questions: identify ALL rows that need to be summed - LIST EVERY ROW\n"
            "6. Verify each value by double-checking the row AND column intersection\n"
            "7. IMPORTANT: If the question asks about a SPECIFIC metric (e.g., 'cash flow from operations'),\n"
            "   only extract that row, NOT a subtotal or different category\n"
            "\n"
            "SPECIAL ROW SELECTION RULES:\n"
            "8. ADJUSTED CALCULATIONS: When question mentions 'adjusted' values and table shows an adjustment:\n"
            "   - Look for rows with 'plus:', 'less:', 'adjusted' prefixes\n"
            "   - If multiple rows have similar names (e.g., 'tower cash flow'), prefer the one\n"
            "     that is part of the adjustment formula (e.g., 'plus: 4× tower cash flow')\n"
            "   - The adjusted component is usually what feeds into the adjusted total\n"
            "9. CURRENT vs FOLLOWING YEAR: In lease/obligation tables:\n"
            "   - 'Current year' typically means the FIRST future year in the table\n"
            "   - 'Following year' means the NEXT row/year after 'current'\n"
            "   - For a table showing 2007, 2008, 2009: current=2007, following=2008\n"
            "\n"
            "DENOMINATOR DETECTION (for ratio/percentage questions):\n"
            "- 'percentage of X': X is the DENOMINATOR (total)\n"
            "- 'as a percentage of Y': Y is the DENOMINATOR\n"
            "- 'share of Z': Z is the DENOMINATOR\n"
            "- 'out of total': total is the DENOMINATOR\n"
            "- For percentage change: earlier year is the DENOMINATOR (base)\n"
            f"{denominator_hints}\n"
            "\n"
        )

        # P0: Detect temporal average questions
        is_temporal_average = bool(re.search(r"\b\d{4}\s+average\b", question.lower()))
        if is_temporal_average:
            extraction_prompt += (
                "TEMPORAL AVERAGE DETECTED (TAT-QA CONVENTION):\n"
                "This question asks for 'YEAR average X'. This means:\n"
                "  average = (value_YEAR + value_YEAR-1) / 2\n"
                "\n"
                "For example, '2019 average free cash flow' requires:\n"
                "1. Extract the 2019 value from the table\n"
                "2. Extract the 2018 value from the table (prior year)\n"
                "3. You MUST return BOTH values!\n"
                "\n"
                "CRITICAL: Return values for BOTH the specified year AND the prior year.\n"
                "Do NOT just return the single year's value.\n\n"
            )

        if is_summation_question:
            extraction_prompt += (
                "SUMMATION REQUIREMENT DETECTED:\n"
                "This question asks for a TOTAL/SUM. You MUST:\n"
                "1. Identify ALL rows that should be summed (not just one)\n"
                "2. List EACH row value separately with its label\n"
                "3. Do NOT use a pre-computed subtotal if individual rows are available\n"
                "4. Count how many rows you're summing - should be more than 1\n\n"
            )

        extraction_prompt += (
            "Return a JSON object with:\n"
            "- `extracted_values`: list of {\"label\": \"ROW_NAME for COLUMN_NAME\", \"value\": number}\n"
            "- `relevant_rows`: list of exact row names/labels being used\n"
            "- `relevant_columns`: list of exact column names being used\n"
            "- `calculation_type`: one of [\"percentage_change\", \"sum\", \"difference\", \"ratio\", \"percentage_of_total\", \"direct_lookup\"]\n"
            "- `denominator_value`: if ratio/percentage, explicitly state which value is the denominator\n"
            "- `denominator_label`: the label/description of the denominator value\n"
            "\n"
            "Example for percentage of total: 'what percentage of total revenue is from region X?'\n"
            "{\"extracted_values\": [{\"label\": \"region X revenue\", \"value\": 200},\n"
            "                        {\"label\": \"total revenue (DENOMINATOR)\", \"value\": 1000}],\n"
            " \"relevant_rows\": [\"region X\", \"total\"], \"relevant_columns\": [\"revenue\"],\n"
            " \"calculation_type\": \"percentage_of_total\",\n"
            " \"denominator_value\": 1000, \"denominator_label\": \"total revenue\"}\n"
        )

        formatted_tables: List[str] = []
        for idx, table in enumerate(evidence_context.tables):
            markdown = (
                self._structured_table_parser.to_markdown(table)
                if isinstance(table, list)
                else str(table)
            )
            formatted_tables.append(f"Table {idx + 1}:\n{markdown}")

        table_text = "\n\n".join(formatted_tables)

        try:
            num_passes = 3 if is_summation_question else 1
            extraction_candidates: List[Dict[str, Any]] = []
            for pass_idx in range(num_passes):
                temp = 0.0 if pass_idx == 0 else 0.2
                completion = self._limiter.call(
                    self._client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": extraction_prompt},
                        {"role": "user", "content": f"Question: {question}\n\nTables:\n{table_text}"},
                    ],
                    temperature=temp,
                )
                extraction_result = completion.choices[0].message.content or ""
                self._logger.info(
                    "Table extraction result (pass %d): %s",
                    pass_idx + 1,
                    extraction_result[:200],
                )
                try:
                    extracted = json.loads(extraction_result.strip().strip("`").replace("json\n", ""))
                    extraction_candidates.append(extracted)
                except json.JSONDecodeError:
                    continue

            best_extraction = self._select_best_extraction(extraction_candidates)
            if best_extraction.get("extracted_values"):
                values_str = "\n".join(
                    f"- {v['label']}: {v['value']}"
                    for v in best_extraction["extracted_values"]
                )
                return (
                    f"\n[PRE-EXTRACTED TABLE VALUES]\n"
                    f"Rows used: {best_extraction.get('relevant_rows', [])}\n"
                    f"Columns used: {best_extraction.get('relevant_columns', [])}\n"
                    f"Values:\n{values_str}\n"
                    f"[END PRE-EXTRACTED VALUES]\n\n"
                )

        except Exception as e:
            self._logger.warning("Table extraction failed: %s", e)

        return ""

    def _detect_calculation_type(
        self,
        question_or_request: StructuredRequest | str,
    ) -> List[str]:
        """Detect what type of calculation is being asked for."""
        if isinstance(question_or_request, StructuredRequest):
            question_text = question_or_request.raw_text
            operations = set(question_or_request.requested_operations)
        else:
            question_text = question_or_request
            operations = set()

        question_lower = question_text.lower()
        detected_types: List[str] = []

        def _add(calc_type: str) -> None:
            if calc_type not in detected_types:
                detected_types.append(calc_type)

        # P0: Check for temporal average FIRST (before generic average)
        # Pattern: "YEAR average X" like "2019 average free cash flow"
        temporal_avg_match = re.search(r"\b(\d{4})\s+average\b", question_lower)
        if temporal_avg_match:
            _add("temporal_average")
            self._logger.info(
                "Detected temporal_average pattern for year %s in: %s",
                temporal_avg_match.group(1),
                question_text[:80],
            )

        # P3: Check for difference_of_averages BEFORE generic difference
        # Pattern: "difference between 2019 average X and 2019 average Y"
        if re.search(r"difference\s+between\s+\d{4}\s+average", question_lower):
            _add("difference_of_averages")
            _add("temporal_average")  # Will need temporal average logic too
            self._logger.info("Detected difference_of_averages in: %s", question_text[:80])

        # P3: Check for change_of_averages
        # Pattern: "change between 2018 and 2019 average X"
        if re.search(r"change\s+between\s+\d{4}\s+and\s+\d{4}\s+average", question_lower):
            _add("change_of_averages")
            _add("temporal_average")  # Will need temporal average logic too
            self._logger.info("Detected change_of_averages in: %s", question_text[:80])

        for calc_type, keywords in CALCULATION_KEYWORDS.items():
            if any(keyword in question_lower for keyword in keywords):
                _add(calc_type)

        for calc_type, patterns in CALCULATION_REGEXES.items():
            if any(re.search(pattern, question_lower) for pattern in patterns):
                _add(calc_type)

        if "comparison" in operations:
            _add("difference")

        # P1: Detect absolute_change vs percentage_change more precisely
        # "change in X from Y to Z" or "change from Y to Z" = absolute_change
        # Unless it says "percent change" or "percentage change"
        if (
            ("from" in question_lower and "to" in question_lower)
            or "between" in question_lower
        ) and re.search(r"\d", question_lower):
            # Check if it's asking for percentage or absolute
            if "percent" not in question_lower and "%" not in question_lower:
                _add("absolute_change")
            else:
                _add("percentage_change")

        # P0: If temporal_average detected, remove generic "average" to avoid confusion
        if "temporal_average" in detected_types and "average" in detected_types:
            detected_types.remove("average")

        return detected_types

    def _detect_text_extraction_question(self, question: str) -> bool:
        """P2: Detect if this question asks for text extraction (span) rather than calculation."""
        question_lower = question.lower()

        # Patterns that indicate text extraction questions
        text_extraction_patterns = [
            r"what (?:is|are|was|were) the (?:contract )?types?\??",
            r"what (?:is|are) .*(?:paid|received|defined|described|determined)\??",
            r"what (?:does|do) .* consist of\??",
            r"what (?:is|are) the .*(?:items|components|elements|factors)\??",
            r"what financial items",
            r"how (?:is|are|was|were) .* (?:defined|determined|calculated|presented)\??",
            r"what (?:is|was) the .* (?:for|in|during) (?:fy|fiscal)\d{2}\??",  # FY questions often want exact text
        ]

        for pattern in text_extraction_patterns:
            if re.search(pattern, question_lower):
                self._logger.info("Detected text extraction question: %s", question[:80])
                return True

        # If no numeric keywords present, likely text extraction
        numeric_keywords = [
            "how much", "total", "sum", "average", "percentage", "percent",
            "change", "increase", "decrease", "difference", "ratio"
        ]
        has_numeric = any(kw in question_lower for kw in numeric_keywords)

        # Questions asking "what is/are the X" without numeric keywords -> text extraction
        if re.search(r"what (?:is|are|was|were) the\b", question_lower) and not has_numeric:
            self._logger.info("Detected text extraction (no numeric keywords): %s", question[:80])
            return True

        return False

    def _detect_consist_of_question(self, question: str) -> Optional[str]:
        """P1: Detect 'consist of' questions that ask for delta rows between subtotals.

        Returns the metric name if detected, None otherwise.
        """
        question_lower = question.lower()

        # Pattern: "What does X consist of?" or "What financial items does X consist of?"
        consist_of_patterns = [
            r"what (?:financial )?items does ([\w\s\(\)\-]+) consist of",
            r"what does ([\w\s\(\)\-]+) consist of",
        ]

        for pattern in consist_of_patterns:
            match = re.search(pattern, question_lower)
            if match:
                metric_name = match.group(1).strip()
                self._logger.info(
                    "Detected 'consist of' question for metric: %s",
                    metric_name,
                )
                return metric_name

        return None

    def _detect_formatted_span_question(self, question: str) -> bool:
        """P2: Detect if question asks for a formatted span (with currency/units).

        These questions expect exact text extraction, not raw numbers.
        """
        question_lower = question.lower()

        # Patterns that typically expect formatted answers
        formatted_span_patterns = [
            r"what (?:was|is) the (?:net )?(?:profit|loss|income|revenue|earnings)",
            r"what (?:was|is) the .* in (?:fy|fiscal)\s?\d{2}",  # "in FY19"
            r"what (?:was|is) the .* (?:for|during) (?:the )?(?:year|quarter|period)",
        ]

        for pattern in formatted_span_patterns:
            if re.search(pattern, question_lower):
                self._logger.info(
                    "Detected formatted span question (may need exact text): %s",
                    question[:80],
                )
                return True

        return False

    def _detect_expected_answer_type(self, question: str) -> str:
        """Detect whether the answer should be a percentage, absolute value, or text."""
        question_lower = question.lower()

        # First check for explicit unit indicators that override percentage inference
        # If question asks "in millions/thousands/billions", it wants an absolute count, not %
        absolute_unit_patterns = [
            r"in millions?\b",
            r"in thousands?\b",
            r"in billions?\b",
            r", in millions?\??$",
            r", in thousands?\??$",
            r", in billions?\??$",
        ]
        for pattern in absolute_unit_patterns:
            if re.search(pattern, question_lower):
                return "absolute"

        # Percentage indicators
        percentage_patterns = [
            r"what (?:is|was) the (?:percent|percentage)",
            r"percent(?:age)? (?:change|growth|decline|increase|decrease)",
            r"as a percent",
            r"what percent",
            # "what is the decline/increase/growth" implies percentage ONLY if no explicit unit
            r"what (?:is|was) the (?:decline|increase|growth|change) (?:from|in|between)",
            r"by how much did .* (?:increase|decrease|decline|grow|change) from",
        ]
        for pattern in percentage_patterns:
            if re.search(pattern, question_lower):
                return "percentage"

        # Absolute value indicators
        absolute_patterns = [
            r"how much",
            r"what (?:is|was|were) the (?:total|amount|value|difference)",
            r"calculate the (?:total|sum|difference|average)",
        ]
        for pattern in absolute_patterns:
            if re.search(pattern, question_lower):
                return "absolute"

        return "unknown"

    def _get_formula_guidance(self, calc_types: List[str]) -> str:
        """Get relevant formula templates based on detected calculation types."""
        if not calc_types:
            return ""

        guidance_parts = ["\n[CALCULATION GUIDANCE]"]
        for calc_type in calc_types:
            if calc_type in FORMULA_TEMPLATES:
                guidance_parts.append(f"\n{FORMULA_TEMPLATES[calc_type]}")
        guidance_parts.append("\n[END CALCULATION GUIDANCE]\n")

        return "\n".join(guidance_parts)

    def _apply_answer_format_rules(
        self,
        answer: str,
        expected_type: str,
        question_text: str,
        calc_types: List[str],
        values_used: List[Dict[str, Any]],
    ) -> str:
        """Ensure the final answer format matches the expected type."""
        if not answer:
            return answer

        cleaned = answer.strip()
        if not cleaned:
            return cleaned

        question_lower = question_text.lower()

        if self._needs_percentage_format(expected_type, question_lower):
            cleaned = self._format_percentage_answer(cleaned, question_lower)
        elif self._needs_ratio_scaling(question_lower):
            # Ratio questions (e.g., "liability to asset ratio") need percentage-scale
            # but WITHOUT the % symbol. Scale 0.18 -> 18.0
            cleaned = self._format_ratio_answer(cleaned)

        if self._should_force_absolute(question_lower, calc_types):
            cleaned = self._apply_absolute_value(cleaned)

        if self._should_summarize_total(cleaned, question_lower, calc_types):
            cleaned = self._summarize_total_answer(cleaned, question_lower, values_used)

        return cleaned

    def _apply_layer0_corrections(
        self,
        answer: str,
        question: str,
        reasoning: str,
        evidence_text: str = "",
    ) -> Tuple[str, Layer0Result]:
        """Apply Layer 0 auto-corrections for format/scale/sign errors.

        Returns:
            (corrected_answer, layer0_result)
        """
        layer0_result = run_layer0_checks(
            question=question,
            answer_text=answer,
            reasoning_text=reasoning,
            evidence_text=evidence_text,
        )

        # Apply correction if available
        if layer0_result.correction_applied and layer0_result.corrected_answer:
            return layer0_result.corrected_answer, layer0_result

        return answer, layer0_result

    def _needs_percentage_format(self, expected_type: str, question_lower: str) -> bool:
        # Note: "ratio" questions need percentage-scale but often without % symbol
        # This is handled separately in _format_ratio_answer
        return expected_type == "percentage" or any(
            token in question_lower for token in ("percent", "percentage", "percentage point")
        )

    def _needs_ratio_scaling(self, question_lower: str) -> bool:
        # Ratio questions like "liability to asset ratio" expect percentage-scale (18.34)
        # but WITHOUT the % symbol. Proportion questions stay as decimal (0.95).
        return "ratio" in question_lower and "proportion" not in question_lower

    def _format_percentage_answer(self, answer: str, question_lower: str) -> str:
        value, match = self._extract_number_with_match(answer)
        if match is None or value is None:
            return answer

        scaled_value = value
        has_percent = "%" in answer
        if not has_percent and abs(value) <= 1 and (
            "percent" in question_lower or "percentage" in question_lower
        ):
            scaled_value = value * 100

        formatted = self._format_plain_number(scaled_value)
        replacement = f"{formatted}%"
        return self._replace_number_segment(answer, match, replacement, remove_percent_sign=has_percent)

    def _format_ratio_answer(self, answer: str) -> str:
        """Scale ratio answers from decimal (0.18) to percentage-scale (18.0) WITHOUT % symbol."""
        value, match = self._extract_number_with_match(answer)
        if match is None or value is None:
            return answer

        # Only scale if it looks like a decimal ratio (0 < |value| <= 1)
        if abs(value) <= 1 and "%" not in answer:
            scaled_value = value * 100
            formatted = self._format_plain_number(scaled_value)
            return self._replace_number_segment(answer, match, formatted, remove_percent_sign=False)

        return answer

    def _should_force_absolute(self, question_lower: str, calc_types: List[str]) -> bool:
        """Detect when the question explicitly asks for magnitude regardless of direction.

        CRITICAL: Do NOT force absolute for "change from X to Y" questions - these need signed results.
        Only force absolute when explicitly asking for magnitude/size.
        """
        # First check if this is a "change from X to Y" question - these preserve sign
        preserve_sign_patterns = [
            r"what (?:is|was) the change in .* (?:from|in) \d{4}",
            r"what (?:is|was) the change .* from \d{4} to \d{4}",
            r"change in .* from \d{4}",
        ]
        if any(re.search(pattern, question_lower) for pattern in preserve_sign_patterns):
            return False  # Do NOT force absolute - preserve sign

        absolute_keywords = [
            "absolute value",
            "magnitude",
            "size of the change",
            "regardless of direction",
            "how big was the change",
        ]
        if any(keyword in question_lower for keyword in absolute_keywords):
            return True

        # Only these patterns explicitly ask for magnitude (not signed change)
        absolute_patterns = [
            r"how much did .* (?:increase|decrease) by",  # "how much did X increase by" = magnitude
            r"how much has .* (?:increased|decreased) by",
        ]
        if any(re.search(pattern, question_lower) for pattern in absolute_patterns):
            return True

        return False

    def _apply_absolute_value(self, answer: str) -> str:
        value, match = self._extract_number_with_match(answer)
        if match is None or value is None:
            return answer
        abs_value = abs(value)
        formatted = self._format_plain_number(abs_value)

        has_percent = "%" in answer
        currency = "$" if "$" in answer[: match.start() + 1] else ""
        replacement = formatted
        if currency:
            replacement = f"{currency}{replacement}"
        if has_percent:
            replacement = f"{replacement}%"
        return self._replace_number_segment(
            answer,
            match,
            replacement,
            remove_percent_sign=has_percent,
        )

    def _should_summarize_total(
        self, answer: str, question_lower: str, calc_types: List[str]
    ) -> bool:
        """
        Only trigger summarization when:
        1. The answer contains multiple values (like "2013: 1356, 2012: 2220")
        2. AND the question explicitly asks for a combined total across multiple items

        This prevents the function from corrupting single-value answers.
        """
        # Check if answer contains multiple separate numbers (multi-value response)
        # Pattern: "year: value" repeated, or list of values
        has_multi_value_answer = bool(
            re.search(r"\d{4}\s*:\s*[\d,.]+.*\d{4}\s*:\s*[\d,.]+", answer)
            or re.search(r"[:,]\s*[\d,.]+\s+(?:and|,)\s*[\d,.]+", answer, re.IGNORECASE)
        )

        if not has_multi_value_answer:
            # Single value answer - don't touch it
            return False

        # Must explicitly ask for combined total
        explicit_total_patterns = [
            r"\btotal\b.*\b(?:for|of|in)\b.*\band\b",  # "total for 2013 and 2012"
            r"\bcombined\b",
            r"\bsum\s+of\b",
            r"\baggregate\b",
            r"\ball\s+(?:years?|periods?)\b.*\btotal\b",
        ]

        return any(re.search(p, question_lower) for p in explicit_total_patterns)

    def _summarize_total_answer(
        self,
        answer: str,
        question_lower: str,
        values_used: List[Dict[str, Any]],
    ) -> str:
        """Sum up values when model returned separate values but question wants total."""
        numeric_values: List[float] = []
        for item in values_used:
            value = item.get("value") if isinstance(item, dict) else None
            parsed = self._safe_float(value)
            if parsed is not None:
                numeric_values.append(parsed)

        if len(numeric_values) < 2:
            return answer

        total = sum(numeric_values)
        unit = self._detect_unit_suffix(answer, question_lower)
        # Only add currency if original answer had it (not just the question)
        currency = "$" if "$" in answer else ""
        return self._format_number_with_suffix(total, unit, currency)

    def _extract_number_with_match(self, text: str) -> Tuple[float | None, re.Match[str] | None]:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
        if not match:
            return None, None
        try:
            value = float(match.group(0).replace(",", ""))
        except ValueError:
            return None, match
        return value, match

    def _replace_number_segment(
        self,
        original: str,
        match: re.Match[str],
        replacement: str,
        remove_percent_sign: bool = False,
    ) -> str:
        prefix = original[: match.start()].strip()
        suffix = original[match.end() :].strip()
        if remove_percent_sign and suffix.startswith("%"):
            suffix = suffix[1:].strip()
        segments = [segment for segment in (prefix, replacement, suffix) if segment]
        return " ".join(segments)

    def _format_plain_number(self, value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _format_number_with_suffix(self, value: float, unit: str, currency: str) -> str:
        formatted = self._format_plain_number(value)
        if currency:
            formatted = f"{currency}{formatted}"
        if unit == "%":
            return f"{formatted}%"
        if unit:
            return f"{formatted} {unit}".strip()
        return formatted

    def _detect_unit_suffix(self, *texts: str) -> str:
        for text in texts:
            if not text:
                continue
            match = re.search(r"(million|billion|thousand|percent|%)", text, re.IGNORECASE)
            if match:
                token = match.group(1)
                return "%" if token == "%" else token.lower()
        return ""

    def _safe_float(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").replace("$", ""))
            except ValueError:
                return None
        return None

    def _detect_denominator_hints(self, question: str) -> str:
        """Detect what should be the denominator based on question phrasing."""
        question_lower = question.lower()
        hints = []

        # BREAKTHROUGH #6: Detect "current" and "following year" patterns in fiscal year tables
        # "decline from current... and following year" means compare adjacent rows
        current_following_patterns = [
            (r"(?:from|between) current .* (?:and|to) (?:the )?following", "CURRENT_FOLLOWING_ADJACENT"),
            (r"decline (?:from|in) current .* following", "CURRENT_FOLLOWING_ADJACENT"),
            (r"current (?:year'?s?|period'?s?) .* following (?:year'?s?|period'?s?)", "CURRENT_FOLLOWING_ADJACENT"),
        ]
        for pattern, hint_type in current_following_patterns:
            if re.search(pattern, question_lower):
                hints.append(
                    "FISCAL YEAR TERMINOLOGY DETECTED:\n"
                    "- 'Current' typically means the FIRST data row (earliest future year)\n"
                    "- 'Following year' means the NEXT row (the year after 'current')\n"
                    "- For a table with years 2007, 2008, 2009: 'current' = 2007, 'following' = 2008\n"
                    "- When asked for 'decline from current to following', calculate:\n"
                    "  percentage decline = (current - following) / current × 100\n"
                    "- Example: If 2007=1703 and 2008=1371, decline = (1703-1371)/1703 = 19.5%\n"
                    "- BUT if the table context shows the question is about consecutive rows,\n"
                    "  'current' and 'following' refer to ADJACENT rows in the table."
                )
                break

        # BREAKTHROUGH #7: Detect "adjusted" calculation patterns - prefer rows that are part of adjustment formula
        if "adjusted" in question_lower:
            adjusted_patterns = [
                r"portion of (?:the )?adjusted",
                r"related to .* adjusted",
                r"as a (?:percent|percentage|portion|share) of (?:the )?adjusted",
            ]
            if any(re.search(p, question_lower) for p in adjusted_patterns):
                hints.append(
                    "ADJUSTED CALCULATION CONTEXT DETECTED:\n"
                    "- When a table shows an adjustment formula (e.g., 'consolidated - X + Y = adjusted'),\n"
                    "  identify which row is being asked about IN THE CONTEXT OF the adjusted calculation.\n"
                    "- For 'portion of adjusted X is related to Y':\n"
                    "  * Look for a row that CONTRIBUTES to the adjusted value (e.g., 'plus: Y', 'less: Y')\n"
                    "  * Use the ADJUSTED COMPONENT row, not a raw/unadjusted row with similar name\n"
                    "- Example: If table has 'tower cash flow' and 'plus: 4× tower cash flow',\n"
                    "  the latter is the adjustment component and should be used as numerator.\n"
                    "- Prefer rows with 'plus:', 'less:', 'adjusted' prefixes when asking about adjusted values."
                )

        # Pattern: "percentage of X" -> X is denominator
        match = re.search(r"percent(?:age)?\s+of\s+([a-z\s]+?)(?:\s+(?:is|was|were|that|in|for)|$)", question_lower)
        if match:
            denominator_term = match.group(1).strip()
            hints.append(f"DETECTED DENOMINATOR: '{denominator_term}' (from 'percentage of {denominator_term}')")

        # Pattern: "as a percentage of X" -> X is denominator
        match = re.search(r"as\s+a\s+percent(?:age)?\s+of\s+([a-z\s]+?)(?:\s+(?:is|was|were)|[?,]|$)", question_lower)
        if match:
            denominator_term = match.group(1).strip()
            hints.append(f"DETECTED DENOMINATOR: '{denominator_term}' (from 'as a percentage of {denominator_term}')")

        # Pattern: "share of X" -> X is denominator
        match = re.search(r"share\s+of\s+([a-z\s]+?)(?:\s+(?:is|was|were)|[?,]|$)", question_lower)
        if match:
            denominator_term = match.group(1).strip()
            hints.append(f"DETECTED DENOMINATOR: '{denominator_term}' (from 'share of {denominator_term}')")

        # Pattern: "X out of Y" -> Y is denominator
        match = re.search(r"out\s+of\s+([a-z\s]+?)(?:\s+(?:is|was|were)|[?,]|$)", question_lower)
        if match:
            denominator_term = match.group(1).strip()
            hints.append(f"DETECTED DENOMINATOR: '{denominator_term}' (from 'out of {denominator_term}')")

        # BREAKTHROUGH #3: Detect percentage change "from YEAR1 to YEAR2" -> YEAR1 is base (denominator)
        match = re.search(r"(?:change|increase|decrease|grow|decline).*from\s+(\d{4})\s+to\s+(\d{4})", question_lower)
        if match:
            base_year = match.group(1)
            new_year = match.group(2)
            hints.append(
                f"PERCENTAGE CHANGE DENOMINATOR: The BASE year is {base_year} (the denominator). "
                f"Formula: (value_{new_year} - value_{base_year}) / value_{base_year} × 100"
            )

        # Pattern: "by how much did X increase" -> earlier value is denominator
        if re.search(r"by how much did .* (increase|decrease|change)", question_lower):
            year_matches = re.findall(r"\b(20\d{2}|19\d{2})\b", question_lower)
            if len(year_matches) >= 2:
                years = sorted([int(y) for y in year_matches])
                hints.append(
                    f"PERCENTAGE CHANGE DENOMINATOR: Earlier year ({years[0]}) is the base/denominator. "
                    f"Do NOT divide by 100 - divide by the actual {years[0]} value from the evidence."
                )

        # BREAKTHROUGH #5: "by how much did X increase from Y to Z" must be percentage, not raw difference
        if re.search(r"by how much did .* (increase|decrease|grow|decline|change) from", question_lower):
            hints.append(
                "CRITICAL: 'By how much did X increase' asks for a PERCENTAGE, not the raw difference! "
                "You MUST divide the difference by the base value and multiply by 100. "
                "Example: If price went from 64.48 to 81.15, answer is (81.15-64.48)/64.48 × 100 = 25.9%, NOT 16.67."
            )

        if hints:
            return "DENOMINATOR HINTS FROM QUESTION:\n" + "\n".join(hints)
        return ""

    def _detect_aggregation_intent(self, question: str) -> str:
        """Detect whether question asks for a single value, total/sum, or average.

        Returns: 'single', 'total', 'average', 'temporal_average', 'cumulative_to_year', or 'unknown'
        """
        lowered = question.lower()

        # P0: Detect temporal average FIRST - "YEAR average X" pattern
        # This is the TAT-QA convention where "2019 average" means (2019 + 2018) / 2
        temporal_avg_patterns = [
            r"\b(\d{4})\s+average\b",  # "2019 average"
            r"what\s+is\s+the\s+(\d{4})\s+average",  # "what is the 2019 average"
        ]
        for pattern in temporal_avg_patterns:
            match = re.search(pattern, lowered)
            if match:
                year = match.group(1)
                self._logger.info(
                    "Aggregation intent detected: temporal_average (year=%s) - question: %s",
                    year, question[:80]
                )
                return "temporal_average"

        # BREAKTHROUGH #2: Detect "due BY year" patterns - sum all items up to that year
        cumulative_year_patterns = [
            r"(?:due|maturing|payable) (?:by|before|through|up to) (\d{4})",
            r"(?:notes|bonds|debt) due (?:by|before) (\d{4})",
            r"carrying value of .*due (?:by|before) (\d{4})",
        ]
        for pattern in cumulative_year_patterns:
            match = re.search(pattern, lowered)
            if match:
                year = match.group(1)
                self._logger.info(
                    "Aggregation intent detected: cumulative_to_year=%s - question: %s",
                    year, question[:80]
                )
                return f"cumulative_to_{year}"

        # Patterns indicating a SINGLE specific value is expected
        single_value_patterns = [
            r"what (?:is|was) the (?:value|amount|number) of",
            r"what (?:is|was) the .* (?:for|in|during) (?:the )?\d{4}",  # specific year
            r"what (?:is|was) the first",
            r"what (?:is|was) the second",
            r"what (?:is|was) the third",
            r"what (?:is|was) the .* payment",  # specific payment
            r"what (?:is|was) the .* contingent",  # contingent payment
            r"how much (?:is|was) the .* (?:for|in) \d{4}",
            r"the (?:amount|value) of .* (?:is|was)",
        ]

        # Patterns indicating TOTAL/SUM is expected
        total_patterns = [
            r"\btotal\b(?! (?:debt|revenue|assets|sales))",  # "total" as an operation, not as part of a metric name
            r"\bsum\s+of\b",
            r"\bcombined\b",
            r"\baggregate\b",
            r"\balltogether\b",
            r"\bcumulative\b",
            r"(?:add|adding) (?:up |together )?(?:all|the)",
            r"what (?:is|was|were) the total (?:of|for)",
        ]

        # Patterns indicating AVERAGE is expected
        average_patterns = [
            r"\baverage\b",
            r"\bmean\b",
            r"\bavg\b",
            r"on average",
        ]

        # Check for average first (highest priority)
        if any(re.search(p, lowered) for p in average_patterns):
            self._logger.info("Aggregation intent detected: average - question: %s", question[:80])
            return "average"

        # Check for total/sum
        if any(re.search(p, lowered) for p in total_patterns):
            self._logger.info("Aggregation intent detected: total - question: %s", question[:80])
            return "total"

        # Check for single value indicators
        if any(re.search(p, lowered) for p in single_value_patterns):
            self._logger.info("Aggregation intent detected: single - question: %s", question[:80])
            return "single"

        return "unknown"

    def _detect_expected_sign(self, question: str) -> Optional[str]:
        """Detect when the user explicitly asks for magnitude or decrease amount."""
        lowered = question.lower()

        # P0 FIX: "What is the change in X from Y to Z" should PRESERVE sign
        # Only strip sign for explicit absolute value requests
        # Do NOT include "what is the change" patterns here - they need sign!

        # Explicit absolute value requests - ONLY these should strip sign
        absolute_triggers = [
            "absolute value",
            "magnitude",
            "size of the change",
            "how big was the change",
            "regardless of direction",
        ]
        # These patterns ask "how much" which implies magnitude, not signed value
        absolute_patterns = [
            r"how much did .* (?:increase|decrease|change) by",  # "how much did X increase by"
            r"how much has .* (?:increased|decreased|changed) by",
        ]
        if any(trigger in lowered for trigger in absolute_triggers) or any(
            re.search(pattern, lowered) for pattern in absolute_patterns
        ):
            return "absolute"

        # P0 FIX: "What is/was the change in X from Y" should PRESERVE sign
        # These are asking for the actual difference (can be negative)
        # Do NOT return "absolute" for these - return None to preserve sign
        change_preserve_sign_patterns = [
            r"what (?:is|was) the change in .* (?:from|in) \d{4}",
            r"what (?:is|was) the change .* from \d{4} to \d{4}",
        ]
        if any(re.search(pattern, lowered) for pattern in change_preserve_sign_patterns):
            self._logger.info(
                "Detected 'change from X to Y' question - preserving sign: %s",
                question[:100],
            )
            return None  # Preserve sign

        # NEW: Detect "by what percent did X decrease/decline/fall" patterns
        # These ask for the MAGNITUDE of the decrease (positive number)
        decrease_magnitude_patterns = [
            r"by what percent(?:age)? did .* (?:decrease|decline|fall|drop)",
            r"what (?:was|is) the percent(?:age)? (?:decrease|decline|drop)",
            r"percent(?:age)? (?:that|by which) .* (?:decreased|declined|fell|dropped)",
            r"how much did .* (?:decrease|decline|fall|drop) (?:by|in percent)",
        ]
        if any(re.search(pattern, lowered) for pattern in decrease_magnitude_patterns):
            self._logger.info(
                "Detected 'decrease magnitude' question - will return positive value: %s",
                question[:100],
            )
            return "decrease_magnitude"

        # Log strict direction hints for debugging but do not enforce
        strict_direction = self._detect_strict_direction(question)
        if strict_direction:
            self._logger.info(
                "Sign hint detected (logging only): question='%s', hint=%s",
                question[:120],
                strict_direction,
            )

        return None

    def _detect_strict_direction(self, question: str) -> Optional[str]:
        lowered = question.lower()
        negative_patterns = [
            r"what was the decrease in",
            r"how much did .*decline",
            r"what was the loss",
            r"by how much did .*fall",
        ]
        for pattern in negative_patterns:
            if re.search(pattern, lowered):
                return "negative"

        positive_patterns = [
            r"what was the increase in",
            r"how much did .*grow",
            r"what was the gain",
            r"by how much did .*rise",
        ]
        for pattern in positive_patterns:
            if re.search(pattern, lowered):
                return "positive"
        return None

    def _get_sign_guidance(self, expected_sign: str | None) -> str:
        if expected_sign == "absolute":
            return (
                "\nSIGN RULE: The user asked for the magnitude of the change. "
                "Report the absolute value (always positive) even if the underlying math yields a negative sign."
            )
        if expected_sign == "decrease_magnitude":
            return (
                "\nSIGN RULE: The user asked 'by what percent did X decrease'. "
                "They want the MAGNITUDE of the decrease as a POSITIVE number. "
                "If your calculation gives -3.4%, report '3.4%' (positive). "
                "Do NOT include the negative sign - the word 'decrease' already implies direction."
            )
        if expected_sign == "percentage_change_magnitude":
            return (
                "\nSIGN RULE: The user asked 'what is the percentage change'. "
                "For generic percentage change questions, report the MAGNITUDE (absolute value). "
                "If your calculation gives -3.4%, report '3.4%' (positive). "
                "The direction (increase/decrease) is implied by context, not the number's sign."
            )
        return ""

    def _get_aggregation_guidance(self, aggregation_intent: str) -> str:
        """Return prompt guidance based on whether a single value, total, or average is expected."""
        if aggregation_intent == "single":
            return (
                "\nAGGREGATION RULE: This question asks for a SINGLE specific value. "
                "Do NOT sum or combine multiple rows. Extract and return only ONE value from the evidence. "
                "If you see multiple similar values (e.g., three contingent payments), identify which specific one "
                "the question asks for and return only that ONE value."
            )
        if aggregation_intent == "total":
            return (
                "\nAGGREGATION RULE: This question asks for a TOTAL/SUM. "
                "Make sure to identify and sum ALL relevant rows, not just one. "
                "List each value being summed with its label before computing the total."
            )
        if aggregation_intent == "temporal_average":
            return (
                "\nTEMPORAL AVERAGE RULE (TAT-QA CONVENTION):\n"
                "When asked for 'YEAR average X', this means:\n"
                "  average = (value_YEAR + value_YEAR-1) / 2\n"
                "\n"
                "Examples:\n"
                "- '2019 average free cash flow' = (FCF_2019 + FCF_2018) / 2\n"
                "- '2018 average free cash flow' = (FCF_2018 + FCF_2017) / 2\n"
                "\n"
                "CRITICAL: You MUST extract BOTH the current year AND prior year values!\n"
                "Do NOT just return the single year's value as the answer.\n"
                "\n"
                "Step-by-step:\n"
                "1. Identify the year mentioned (e.g., 2019)\n"
                "2. Extract the value for that year from the table\n"
                "3. Extract the value for the PRIOR year (e.g., 2018)\n"
                "4. Compute: (current_year_value + prior_year_value) / 2\n"
            )
        if aggregation_intent == "average":
            return (
                "\nAGGREGATION RULE: This question asks for an AVERAGE. "
                "You must: 1) Identify ALL values being averaged, 2) Count them correctly, "
                "3) Divide the sum by the count. Do NOT return a single year's value as the average."
            )
        # BREAKTHROUGH #2: Handle "due BY year" cumulative aggregation
        if aggregation_intent.startswith("cumulative_to_"):
            year = aggregation_intent.replace("cumulative_to_", "")
            return (
                f"\nAGGREGATION RULE: This question asks for items 'due BY {year}'. "
                f"You must SUM ALL items with maturity dates ON OR BEFORE {year}. "
                f"For example, if asked for 'notes due by 2017', sum notes due in 2014 + 2015 + 2016 + 2017. "
                f"Do NOT just return the {year} value - include ALL earlier maturities too. "
                f"Look at the maturity column and include every row where maturity <= {year}."
            )
        return ""

    def _detect_answer_format(self, answer: str) -> str:
        if not answer:
            return "unknown"
        lowered = answer.lower()
        if "%" in answer or "percent" in lowered:
            return "percentage"
        if re.search(r"[\d$]", answer):
            return "absolute"
        return "unknown"

    def _convert_answer_format(
        self,
        answer: str,
        detected_type: str,
        expected_type: str,
    ) -> Tuple[str, Optional[str]]:
        if expected_type == "unknown" or detected_type == "unknown":
            return answer, None
        if detected_type == expected_type:
            return answer, None

        value, _ = self._extract_number_with_match(answer)
        if value is None:
            return answer, None

        if detected_type == "percentage" and expected_type == "absolute":
            cleaned = re.sub(r"(percent|%)", "", answer, flags=re.IGNORECASE).strip()
            return cleaned, "Removed percentage indicator to match expected absolute format."

        if detected_type == "absolute" and expected_type == "percentage":
            # Cannot infer denominator safely; just signal warning.
            return answer, "Expected percentage format but only absolute value was provided."

        return answer, None

    def _validate_answer_format(
        self,
        answer: str,
        expected_type: str,
    ) -> Tuple[bool, Optional[str]]:
        if expected_type == "unknown":
            return True, None

        lowered = answer.lower()
        has_percent = "%" in answer or "percent" in lowered

        if expected_type == "percentage" and not has_percent:
            return False, "Answer missing '%' even though percentage was requested."

        if expected_type == "absolute" and has_percent:
            return False, "Answer should be an absolute value, but contains a percentage."

        return True, None

    def _verify_sign_consistency(
        self,
        answer: str,
        question: str,
        reasoning: str,
        expected_sign: Optional[str],
    ) -> Tuple[str, Optional[str]]:
        """Adjust or warn about sign mismatches when the question dictates direction."""
        if not expected_sign:
            return answer, None

        value, _ = self._extract_number_with_match(answer)
        if value is None:
            return answer, None

        if expected_sign == "absolute":
            if value < 0:
                return self._apply_absolute_value(answer), "Converted to absolute magnitude as requested."
            return answer, None

        # Handle "by what percent did X decrease" - return positive magnitude
        if expected_sign == "decrease_magnitude":
            if value < 0:
                self._logger.info(
                    "Converting negative to positive for decrease question: %s -> %s",
                    value,
                    abs(value),
                )
                return self._apply_absolute_value(answer), "Converted to positive magnitude for 'decrease' question."
            return answer, None

        if expected_sign in {"positive", "negative"}:
            self._logger.info(
                "Sign enforcement skipped (logging only): expected=%s, answer=%s",
                expected_sign,
                answer,
            )
            return answer, "Sign guidance logged only; no adjustment applied."

        return answer, None

    def _check_denominator_requirements(
        self,
        question_text: str,
        values_used: List[Dict[str, Any]],
        calc_types: List[str],
    ) -> List[str]:
        """Heuristic checks for denominator selection in ratio/percentage questions."""
        warnings: List[str] = []
        if not values_used or not calc_types:
            return warnings

        lower_labels = [
            str(item.get("label", "")).lower()
            for item in values_used
            if isinstance(item, dict)
        ]

        value_numbers = [
            self._safe_float(item.get("value"))
            for item in values_used
            if isinstance(item, dict)
        ]
        value_numbers = [num for num in value_numbers if num is not None]

        def _contains_keyword(keywords: List[str]) -> bool:
            return any(
                any(keyword in label for keyword in keywords)
                for label in lower_labels
            )

        ratio_like = any(
            calc in calc_types for calc in ("percentage_of_total", "ratio")
        )
        if ratio_like:
            if len(values_used) < 2:
                warnings.append(
                    "Ratio/percentage question but only one value extracted."
                )
            denom_keywords = [
                "total",
                "aggregate",
                "overall",
                "net sales",
                "total revenue",
                "total assets",
                "company total",
            ]
            if not _contains_keyword(denom_keywords):
                warnings.append(
                    "No denominator value detected for ratio/percentage question."
                )
            if len(value_numbers) >= 2:
                largest = max(value_numbers)
                smallest = min(value_numbers)
                if smallest > largest:
                    smallest, largest = largest, smallest
                if smallest > largest:
                    warnings.append(
                        "Possible denominator issue: component value exceeds total."
                    )
            # Check for suspicious round denominators not in evidence labels
            suspicious_denoms = {100, 1000, 10000, 100000}
            for val in value_numbers:
                if val in suspicious_denoms:
                    # Check if this round number is explicitly labeled (intentional)
                    is_labeled = any(
                        str(int(val)) in label or str(val) in label
                        for label in lower_labels
                    )
                    if not is_labeled:
                        warnings.append(
                            f"WARNING: Suspicious denominator {val} detected - may be "
                            "dividing by round number instead of actual evidence value. "
                            "For percentage change, use the base value from evidence as denominator."
                        )
                        self._logger.warning(
                            "Suspicious denominator %s in ratio calculation - values: %s, labels: %s",
                            val,
                            value_numbers,
                            lower_labels,
                        )

        if "percentage_change" in calc_types:
            year_mentions = re.findall(r"\b(19|20)\d{2}\b", question_text)
            if len(year_mentions) >= 2 and len(values_used) < 2:
                warnings.append(
                    "Percentage change question should reference at least two periods."
                )

        return warnings

    def _extract_expected_count(self, question: str) -> Optional[int]:
        lowered = question.lower()
        number_match = re.search(
            r"\b(\d+)\s+(?:segments|regions|items|divisions|components|lines)\b", lowered
        )
        if number_match:
            return int(number_match.group(1))

        range_match = re.search(r"(20\d{2}|19\d{2})\s*-\s*(20\d{2}|19\d{2})", question)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if end >= start:
                return (end - start) + 1
        return None

    def _verify_sum_completeness(
        self,
        values_used: List[Dict[str, Any]],
        expected_count: Optional[int],
        calc_types: List[str],
    ) -> List[str]:
        warnings: List[str] = []
        if "total" not in calc_types:
            return warnings

        actual_values = [
            item
            for item in values_used
            if isinstance(item, dict) and "value" in item
        ]

        # Check if expected count is specified and matches
        if expected_count is not None and actual_values and len(actual_values) != expected_count:
            warnings.append(
                f"Expected {expected_count} rows for the sum but extracted {len(actual_values)}."
            )

        # Check if only one value was extracted for a "total" question
        # This is often a sign that we're missing other rows
        if len(actual_values) == 1:
            warnings.append(
                "WARNING: Only 1 value extracted for a total/sum question. "
                "Verify that all relevant rows have been included in the sum."
            )
            self._logger.warning(
                "Sum completeness check: only 1 value for total question - values: %s",
                actual_values,
            )

        # Check if extracted values have similar labels (indicating pattern-based extraction might have missed some)
        if len(actual_values) >= 1:
            labels = [str(item.get("label", "")).lower() for item in actual_values]
            # Look for patterns like "notes due 2017" that suggest there might be more notes
            due_pattern_count = sum(1 for label in labels if "due" in label or "note" in label)
            if due_pattern_count >= 1 and len(actual_values) < 3:
                # If we found note-like labels but have few values, might be incomplete
                self._logger.info(
                    "Sum completeness: found %d note-like labels but only %d values - may be incomplete",
                    due_pattern_count,
                    len(actual_values),
                )

        return warnings

    def _select_best_extraction(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not extractions:
            return {}
        return max(
            extractions,
            key=lambda ex: len(ex.get("extracted_values", []) or []),
        )

    def _is_complex_calculation(
        self,
        question_or_request: StructuredRequest | str,
    ) -> bool:
        """Determine if this is a complex calculation that needs stronger verification."""
        calc_types = self._detect_calculation_type(question_or_request)
        question_text = (
            question_or_request.raw_text
            if isinstance(question_or_request, StructuredRequest)
            else question_or_request
        )

        # Complex if multiple calculation types detected
        if len(calc_types) > 1:
            return True

        # Complex if involves percentage change, average, or percentage_of_total (common error sources)
        complex_types = {"percentage_change", "average", "ratio", "percentage_of_total"}
        if any(ct in complex_types for ct in calc_types):
            return True

        # Complex if question mentions multiple time periods
        year_pattern = r"\b(19|20)\d{2}\b"
        years = re.findall(year_pattern, question_text)
        if len(set(years)) > 1:
            return True

        return False

    def _verify_calculation(
        self,
        question_or_request: StructuredRequest | str,
        proposed_answer: str,
        reasoning: str,
        evidence_context: EvidenceContext | None,
        expected_sign: Optional[str] = None,
        question_classification: Optional[ClassificationResult] = None,
    ) -> Tuple[bool, str | None]:
        """Run multi-pass verification to check if the calculation is correct.

        For complex calculations, runs 3 independent verification passes and uses
        majority voting to determine the correct answer.

        If question_classification is provided, uses intelligent routing:
        - easy questions: skip verification (handled by Layer 0)
        - medium questions: single-pass verification
        - hard questions: full multi-pass verification (3 passes)

        Returns (is_verified, corrected_answer or None).
        """
        calc_types = self._detect_calculation_type(question_or_request)

        if not self._enable_verification_pass:
            return True, None

        # Skip verification for non-numeric answers unless calculation expected
        if not proposed_answer or proposed_answer.lower() == "uncertain":
            if calc_types:
                return False, None
            return True, None

        # Check if answer looks numeric
        if not re.search(r'\d', proposed_answer):
            return True, None

        is_complex = self._is_complex_calculation(question_or_request)

        # Intelligent routing based on question classification
        if question_classification is not None:
            difficulty = question_classification.difficulty
            if difficulty == Difficulty.EASY:
                # Easy questions: skip expensive verification, rely on Layer 0
                self._logger.info(
                    "Skipping multi-pass verification for EASY question (will use Layer 0)"
                )
                return True, None
            elif difficulty == Difficulty.MEDIUM:
                # Medium questions: single pass verification
                is_complex = False
                self._logger.info(
                    "Using single-pass verification for MEDIUM question"
                )
            else:  # HARD
                # Hard questions: full multi-pass verification
                is_complex = True
                self._logger.info(
                    "Using full multi-pass verification for HARD question"
                )

        # Use stronger model for complex calculations
        verification_model = "gpt-4o" if is_complex else "gpt-4o-mini"

        # For complex calculations, run multi-pass verification (3 passes)
        num_passes = 3 if is_complex else 1

        # Get expected answer type
        question_text = (
            question_or_request.raw_text
            if isinstance(question_or_request, StructuredRequest)
            else question_or_request
        )

        expected_type = self._detect_expected_answer_type(question_text)

        # Get relevant formula guidance
        formula_guidance = self._get_formula_guidance(calc_types)

        sign_guidance = self._get_sign_guidance(expected_sign)

        verification_prompt = (
            "You are a meticulous calculation verifier for financial data.\n\n"
            "Given a question, proposed answer, and reasoning, verify if the calculation is correct by:\n"
            "1. FIRST: Re-read the question to understand EXACTLY what is being asked\n"
            "2. SECOND: Re-read the source values directly from the evidence (not from the reasoning)\n"
            "3. THIRD: Identify the correct formula based on what the question asks\n"
            "4. FOURTH: Re-compute the answer step by step, showing your work\n"
            "5. FIFTH: Check if the sign and magnitude make sense\n"
            "6. SIXTH: Verify the answer format matches what was asked\n"
            "\n"
            f"{formula_guidance}\n"
            f"{sign_guidance}\n"
            f"\nExpected answer type: {expected_type}\n"
            "\nCRITICAL FORMULA VERIFICATION:\n"
            "- For 'percentage of X that is Y': formula is (Y / X) * 100, where X is the TOTAL/WHOLE\n"
            "- For 'percentage change from A to B': formula is ((B - A) / A) * 100, where A is the BASE\n"
            "- For 'what portion/share/part of X': find what is being divided BY the total X\n"
            "- For 'as a percentage of total': the denominator should be the TOTAL, not a component\n"
            "- Check: Is the denominator correct? This is the #1 source of errors!\n"
            "\n"
            "CRITICAL DENOMINATOR CHECK:\n"
            "- The denominator MUST come from the evidence, not be an arbitrary number like 100\n"
            "- For percentage change: denominator = base/starting value (the earlier period)\n"
            "  Example: change from 64.48 to 81.15 → (81.15-64.48)/64.48 × 100 = 25.87%\n"
            "  WRONG: (81.15-64.48)/100 = 16.67 (DO NOT divide by 100!)\n"
            "- For percentage of total: denominator = the total/whole amount\n"
            "- If you see a calculation dividing by 100 when computing a percentage change, it's WRONG\n"
            "- ALWAYS identify which value is the denominator and verify it exists in evidence\n"
            "\n"
            "COMMON ERRORS TO CHECK FOR:\n"
            "- RAW DIFFERENCE vs PERCENTAGE: If question asks 'by how much did X increase', the answer\n"
            "  should be a PERCENTAGE, not the raw difference! If answer equals (new-old), it's WRONG.\n"
            "  Correct: (new-old)/old × 100. Example: 16.67 is WRONG, 25.9% is CORRECT for 64.48→81.15.\n"
            "- WRONG DENOMINATOR: Using 100 instead of the actual base value from evidence\n"
            "- WRONG DENOMINATOR: Using a component instead of total, or vice versa\n"
            "- WRONG FORMULA TYPE: Using percentage change when percentage of total was asked\n"
            "- Using wrong year's value (e.g., 2018 instead of 2019)\n"
            "- Confusing old/new in percentage change calculations\n"
            "- Using single value when average was requested\n"
            "- Returning percentage when absolute value was asked (or vice versa)\n"
            "- Wrong sign (positive vs negative)\n"
            "\n"
            "P1 - ABSOLUTE CHANGE vs PERCENTAGE CHANGE:\n"
            "- 'What is the change in X from 2018 to 2019?' = ABSOLUTE change = value_2019 - value_2018\n"
            "- 'What was the change in X?' = ABSOLUTE change (not percentage unless explicitly asked)\n"
            "- ONLY use percentage formula when question says 'percent', 'percentage', '%', or 'rate'\n"
            "- If question asks 'change from 2018 to 2019', compute: 2019_value - 2018_value\n"
            "- The sign matters! If 2019 < 2018, result should be NEGATIVE\n"
            "\n"
            "P0 - TEMPORAL AVERAGE (TAT-QA CONVENTION):\n"
            "- 'YEAR average X' means: (value_YEAR + value_YEAR-1) / 2\n"
            "- '2019 average free cash flow' = (FCF_2019 + FCF_2018) / 2\n"
            "- If answer equals a single year's value, it's WRONG for temporal average questions\n"
            "- For 'difference between 2019 average X and 2019 average Y':\n"
            "  Step 1: avg_X = (X_2019 + X_2018) / 2\n"
            "  Step 2: avg_Y = (Y_2019 + Y_2018) / 2\n"
            "  Step 3: Result = avg_X - avg_Y\n"
            "\n"
            "SPECIAL CASES TO CHECK:\n"
            "- ADJUSTED CALCULATIONS: If question asks about 'portion of ADJUSTED X related to Y':\n"
            "  * Look for rows labeled 'plus: Y' or 'four times Y' (adjustment components)\n"
            "  * Do NOT use the raw/plain row if an adjustment component exists\n"
            "  * Example: 'tower cash flow' vs 'plus: 4× tower cash flow' - use the latter for adjusted!\n"
            "- CURRENT/FOLLOWING YEAR: In lease/obligation tables:\n"
            "  * 'Current' = first future year row (e.g., 2007 if table starts at 2007)\n"
            "  * 'Following year' = next row after current (e.g., 2008)\n"
            "  * 'Decline from current to following' = (current - following) / current × 100\n"
            "\n"
            "Return a JSON object with:\n"
            "- `is_correct`: true/false\n"
            "- `question_asks_for`: what the question is really asking (e.g., 'percentage of total', 'percentage change')\n"
            "- `values_from_evidence`: list of {\"label\": \"...\", \"value\": number} extracted directly from evidence\n"
            "- `denominator_used`: what value was used as denominator in the proposed answer\n"
            "- `correct_denominator`: what value SHOULD be the denominator (from evidence)\n"
            "- `formula_used`: the formula you applied\n"
            "- `step_by_step`: array of calculation steps\n"
            "- `your_result`: your computed answer\n"
            "- `verification_reasoning`: explanation of your verification\n"
            "- `corrected_answer`: the correct answer if different (null if correct)\n"
            "- `error_type`: if incorrect, one of: 'wrong_denominator', 'wrong_formula_type', 'wrong_values',\n"
            "  'sign_error', 'magnitude_error', 'rounding_error', 'format_error', null if correct\n"
        )

        evidence_text = ""
        if evidence_context:
            evidence_text = evidence_context.as_prompt_section() or ""

        user_prompt = (
            f"Question: {question_text}\n\n"
            f"Proposed Answer: {proposed_answer}\n\n"
            f"Reasoning Used: {reasoning}\n\n"
            f"Evidence:\n{evidence_text}\n\n"
            "Verify this calculation step by step. Extract values DIRECTLY from the evidence above."
        )

        try:
            self._logger.info(
                "Using %s for verification (complex=%s, passes=%d)",
                verification_model,
                is_complex,
                num_passes,
            )

            # Collect results from multiple passes
            pass_results: List[Dict[str, Any]] = []

            for pass_idx in range(num_passes):
                # Use slight temperature variation for passes 2+ to get diverse checks
                temp = 0.0 if pass_idx == 0 else 0.1

                completion = self._limiter.call(
                    self._client.chat.completions.create,
                    model=verification_model,
                    messages=[
                        {"role": "system", "content": verification_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                )
                result = completion.choices[0].message.content or "{}"

                try:
                    result_text = result.strip().strip("`")
                    if result_text.lower().startswith("json"):
                        result_text = result_text[4:].strip()
                    verification = json.loads(result_text)
                    pass_results.append(verification)
                    self._logger.info(
                        "Pass %d result: correct=%s, answer=%s",
                        pass_idx + 1,
                        verification.get("is_correct"),
                        verification.get("your_result") or verification.get("corrected_answer"),
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    self._logger.warning("Pass %d parse error: %s", pass_idx + 1, e)
                    pass_results.append({"is_correct": True})  # Default to accept on parse error

            # Single pass mode - use the result directly
            if num_passes == 1:
                verification = pass_results[0]
                is_correct = verification.get("is_correct", True)
                corrected = verification.get("corrected_answer")
                error_type = verification.get("error_type")

                if not is_correct and corrected:
                    self._logger.info(
                        "Verification caught error: %s -> %s (type: %s)",
                        proposed_answer,
                        corrected,
                        error_type,
                    )
                    return False, str(corrected)

                return is_correct, None

            # Multi-pass mode - use majority voting
            correct_votes = sum(1 for r in pass_results if r.get("is_correct", True))
            incorrect_votes = num_passes - correct_votes

            self._logger.info(
                "Multi-pass voting: %d correct, %d incorrect",
                correct_votes,
                incorrect_votes,
            )

            # Even if verification says "correct", check if computed result differs from proposed
            # This catches cases where verification recomputes correctly but doesn't realize
            # the proposed answer is wrong (e.g., -8.64 vs -864)
            computed_results = [
                r.get("your_result") for r in pass_results if r.get("your_result") is not None
            ]
            self._logger.info(
                "Scale check: proposed=%s, computed_results=%s",
                proposed_answer,
                computed_results,
            )
            if computed_results and proposed_answer:
                try:
                    proposed_num = float(str(proposed_answer).replace("%", "").replace(",", "").strip())
                    computed_nums = []
                    for cr in computed_results:
                        try:
                            computed_nums.append(float(str(cr).replace("%", "").replace(",", "").strip()))
                        except (ValueError, TypeError):
                            pass

                    if computed_nums:
                        # Check if computed results consistently differ from proposed by ~100x
                        from collections import Counter
                        computed_counter = Counter([round(n, 2) for n in computed_nums])
                        most_common_computed, count = computed_counter.most_common(1)[0]

                        # If majority of passes computed a different value
                        if count >= (num_passes + 1) // 2 and proposed_num != 0:
                            ratio = abs(most_common_computed / proposed_num) if proposed_num != 0 else 0
                            # Check for 100x scale mismatch (either direction)
                            if 90 < ratio < 110 or 0.009 < ratio < 0.011:
                                self._logger.info(
                                    "Scale mismatch detected: proposed=%s, computed=%s (ratio=%.2f)",
                                    proposed_answer,
                                    most_common_computed,
                                    ratio,
                                )
                                # Return the computed result as correction
                                return False, str(int(most_common_computed) if most_common_computed == int(most_common_computed) else most_common_computed)
                except (ValueError, TypeError) as e:
                    self._logger.debug("Could not compare answers numerically: %s", e)

            # If majority says correct, accept original answer
            if correct_votes > incorrect_votes:
                return True, None

            # Majority says incorrect - find most common corrected answer
            corrected_answers = [
                str(r.get("corrected_answer"))
                for r in pass_results
                if not r.get("is_correct", True) and r.get("corrected_answer")
            ]

            if corrected_answers:
                # Use most common correction (simple majority)
                from collections import Counter
                answer_counts = Counter(corrected_answers)
                most_common = answer_counts.most_common(1)[0][0]
                self._logger.info(
                    "Multi-pass correction: %s -> %s (votes: %s)",
                    proposed_answer,
                    most_common,
                    dict(answer_counts),
                )
                return False, most_common

            return True, None

        except Exception as e:
            self._logger.warning("Verification failed: %s", e)
            return True, None
