from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional

from ..chain_of_evidence import ChainOfEvidence
from ...tools.calculator import Calculator
from ...utils.numeric_matcher import within_tolerance, extract_numbers

IMPORTANT_TERMS = {
    "revenue",
    "sales",
    "income",
    "debt",
    "cash",
    "assets",
    "liability",
    "liabilities",
    "expense",
    "expenses",
    "defined",
    "contribution",
    "benefit",
    "margin",
    "profit",
    "operating",
    "total",
    "average",
    "free",
    "flow",
}


@dataclass
class Layer1Issue:
    message: str
    step_index: int


class Layer1Guardrails:
    """
    Lightweight per-step checks that run during reasoning.
    """

    def __init__(self) -> None:
        self._issues: List[Layer1Issue] = []
        self._calculator = Calculator()
        self._evidence_index: Dict[str, str] = {}

    @property
    def issues(self) -> List[Layer1Issue]:
        return self._issues

    def reset(self) -> None:
        self._issues.clear()
        self._evidence_index.clear()

    def update_evidence(self, context_text_blocks: List[str]) -> None:
        self._evidence_index = {
            snippet: snippet for snippet in context_text_blocks
        }

    def run_checks(self, chain: ChainOfEvidence) -> None:
        self._issues.clear()
        for step in chain.steps:
            self._check_citations(step, chain)
            self._check_numeric(tool_result=step.tool_result, index=step.index)

    def _check_citations(self, step, chain: ChainOfEvidence) -> None:
        if not step.citations:
            self._issues.append(
                Layer1Issue(
                    message="Each reasoning step must include at least one citation.",
                    step_index=step.index,
                )
            )
            return

        for citation in step.citations:
            if citation not in self._evidence_index:
                self._issues.append(
                    Layer1Issue(
                        message="Citation not found in evidence context.",
                        step_index=step.index,
                    )
                )
            else:
                snippet = self._evidence_index[citation].lower()
                if "interest" in step.statement.lower() and "interest" not in snippet:
                    self._issues.append(
                        Layer1Issue(
                            message="Interest-related citation does not mention interest.",
                            step_index=step.index,
                        )
                    )
                if self._contains_numeric_claim(step.statement) and not self._numeric_in_snippet(
                    step.statement, snippet
                ):
                    self._issues.append(
                        Layer1Issue(
                            message="Numeric claim not backed by cited snippet.",
                            step_index=step.index,
                        )
                    )
                self._check_year_alignment(step.statement, snippet, step.index)
                self._check_metric_keywords(step.statement, snippet, step.index)

    def _check_numeric(self, tool_result: Optional[dict], index: int) -> None:
        if tool_result is None:
            return
        if "result" not in tool_result:
            self._issues.append(
                Layer1Issue(
                    message="Arithmetic tool result missing 'result' key.",
                    step_index=index,
                )
            )
            return

        numeric_statement = tool_result.get("statement", "")
        if numeric_statement:
            statement_numbers = self._extract_numbers(numeric_statement)
            if statement_numbers and isinstance(tool_result["result"], (int, float)):
                if not any(
                    self._calculator.near(tool_result["result"], num)
                    for num in statement_numbers
                ):
                    self._issues.append(
                        Layer1Issue(
                            message="Tool result does not match numeric claim in statement.",
                            step_index=index,
                        )
                    )

    def _extract_numbers(self, text: str) -> List[float]:
        matches = re.findall(r"-?\d+(?:\.\d+)?", text)
        return [float(m) for m in matches]

    def _contains_numeric_claim(self, statement: str) -> bool:
        return bool(re.search(r"-?\d+(?:\.\d+)?", statement))

    def _numeric_in_snippet(self, statement: str, snippet: str) -> bool:
        statement_numbers = extract_numbers(statement)
        snippet_numbers = extract_numbers(snippet)
        if not statement_numbers or not snippet_numbers:
            return False
        for a in statement_numbers:
            for b in snippet_numbers:
                if within_tolerance(a, b):
                    return True
        return False

    def _check_year_alignment(self, statement: str, snippet: str, index: int) -> None:
        years = re.findall(r"\b(?:19|20)\d{2}\b", statement)
        if not years:
            return
        missing = [year for year in years if year not in snippet]
        if missing and len(missing) == len(years):
            self._issues.append(
                Layer1Issue(
                    message="Citation missing year tokens referenced in reasoning.",
                    step_index=index,
                )
            )

    def _check_metric_keywords(self, statement: str, snippet: str, index: int) -> None:
        words = {
            token.lower()
            for token in re.findall(r"\b[a-zA-Z]{4,}\b", statement)
            if token.lower() in IMPORTANT_TERMS
        }
        if not words:
            return
        snippet_lower = snippet.lower()
        if not any(word in snippet_lower for word in words):
            self._issues.append(
                Layer1Issue(
                    message="Citation missing metric keywords referenced in reasoning.",
                    step_index=index,
                )
            )
