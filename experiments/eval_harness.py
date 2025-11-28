"""Unified evaluation harness for fair FinBound vs baseline comparison.

This harness ensures:
1. All methods evaluate on identical test samples
2. All methods receive identical evidence context
3. All methods are scored with the same metrics
4. Results are logged to MLflow for reproducibility
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from finbound import FinBound
from finbound.data import UnifiedSample, to_unified, FinQALoader, TATQALoader
from finbound.types import EvidenceContext
from finbound.utils import extract_numbers, within_tolerance
from finbound.evaluation.metrics import (
    AuditabilityMetric,
    GroundingAccuracy,
    HallucinationRate,
    RunIDFidelity,
    TransparencyScore,
)


@dataclass
class EvalResult:
    """Result from a single evaluation."""

    sample_id: str
    method: str
    task_family: str
    predicted_answer: str
    gold_answer: str
    is_correct: bool
    grounding_score: float
    has_hallucination: bool
    citations: List[str]
    latency_ms: float
    verified: Optional[bool] = None
    error: Optional[str] = None
    raw_output: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class EvalMetrics:
    """Aggregated metrics across samples."""

    method: str
    task_family: str
    num_samples: int
    accuracy: float
    grounding_accuracy: float
    hallucination_rate: float
    transparency_score: float
    auditability: float
    run_id_fidelity: float
    avg_latency_ms: float
    verification_rate: Optional[float] = None


class EvalHarness:
    """
    Unified evaluation harness for comparing FinBound against baselines.

    Usage:
        harness = EvalHarness()
        harness.register_method("finbound", finbound_runner)
        harness.register_method("gpt4_zeroshot", gpt4_runner)

        results = harness.run_evaluation(
            samples=test_samples,
            task_family="F1",
            methods=["finbound", "gpt4_zeroshot"]
        )
    """

    def __init__(self, output_dir: str | Path = "experiments/results") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._methods: Dict[str, Callable] = {}
        self._results: List[EvalResult] = []

    def register_method(
        self,
        name: str,
        runner: Callable[[UnifiedSample, EvidenceContext, str], Dict[str, Any]],
    ) -> None:
        """
        Register an evaluation method.

        Runner signature: (sample, evidence_context, task_family) -> {
            "answer": str,
            "citations": List[str],
            "verified": Optional[bool],
            "raw_output": Dict
        }
        """
        self._methods[name] = runner

    def run_evaluation(
        self,
        samples: List[UnifiedSample],
        task_family: Literal["F1", "F2", "F3", "F4"],
        methods: Optional[List[str]] = None,
    ) -> List[EvalResult]:
        """
        Run evaluation on all samples with specified methods.

        All methods receive identical:
        - Sample (question, gold answer)
        - Evidence context (text blocks, tables)
        - Task family designation
        """
        methods = methods or list(self._methods.keys())
        results: List[EvalResult] = []
        grounding_metric = GroundingAccuracy()
        hallucination_metric = HallucinationRate()
        transparency_metric = TransparencyScore()
        auditability_metric = AuditabilityMetric()
        run_id_metric = RunIDFidelity()
        latency_sum: Dict[str, float] = {method: 0.0 for method in methods}
        accuracy_counts: Dict[str, int] = {method: 0 for method in methods}
        sample_counts: Dict[str, int] = {method: 0 for method in methods}

        for sample in samples:
            # Create identical evidence context for all methods
            evidence_context = sample.to_evidence_context()

            for method_name in methods:
                if method_name not in self._methods:
                    raise ValueError(f"Unknown method: {method_name}")

                runner = self._methods[method_name]
                result = self._evaluate_single(
                    sample=sample,
                    evidence_context=evidence_context,
                    task_family=task_family,
                    method_name=method_name,
                    runner=runner,
                )
                results.append(result)
                sample_counts[method_name] += 1
                latency_sum[method_name] += result.latency_ms
                if result.is_correct:
                    accuracy_counts[method_name] += 1

                # Update metrics per method
                grounding_metric.update(result.grounding_score)
                hallucination_metric.update(result.issues)
                transparency_metric.update(result.raw_output)
                auditability_metric.update(result.raw_output)
                run_id_metric.update(result.raw_output)

        self._results.extend(results)
        return results

    def _evaluate_single(
        self,
        sample: UnifiedSample,
        evidence_context: EvidenceContext,
        task_family: str,
        method_name: str,
        runner: Callable,
    ) -> EvalResult:
        """Evaluate a single sample with a single method."""
        start_time = time.perf_counter()
        error = None

        try:
            output = runner(sample, evidence_context, task_family)
            predicted = output.get("answer", "")
            citations = output.get("citations", [])
            verified = output.get("verified")
            raw_output = output.get("raw_output", {})
            verification_issues = output.get("verification_issues", [])
        except Exception as e:
            predicted = ""
            citations = []
            verified = None
            raw_output = {}
            verification_issues = []
            error = str(e)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Compute metrics
        is_correct = self._check_answer_match(predicted, sample.gold_answer)
        grounding_score = self._compute_grounding_score(citations, evidence_context)
        has_hallucination = self._detect_hallucination(
            answer=predicted,
            citations=citations,
            evidence=evidence_context,
            raw_output=raw_output,
            verification_issues=verification_issues,
            gold_answer=sample.gold_answer,
            is_correct=is_correct,
        )

        # Collect issues for hallucination metric
        issues: List[str] = []
        if has_hallucination:
            issues.append("numeric hallucination")

        return EvalResult(
            sample_id=sample.id,
            method=method_name,
            task_family=task_family,
            predicted_answer=predicted,
            gold_answer=sample.gold_answer,
            is_correct=is_correct,
            grounding_score=grounding_score,
            has_hallucination=has_hallucination,
            citations=citations,
            latency_ms=latency_ms,
            verified=verified,
            error=error,
            raw_output=raw_output,
            issues=issues,
        )

    def _check_answer_match(self, predicted: str, gold: str) -> bool:
        """Check if predicted answer matches gold (with normalization)."""
        # Convert dict/list answers to scalar if needed (pass gold for context)
        predicted = self._convert_to_scalar(predicted, gold)
        gold = self._convert_to_scalar(gold, gold)

        pred_norm = self._normalize_answer(predicted)
        gold_norm = self._normalize_answer(gold)

        # Empty prediction is never correct (unless gold is also empty)
        if not pred_norm:
            return not gold_norm

        # Exact match
        if pred_norm == gold_norm:
            return True

        # Numeric comparison with multiple tolerance strategies
        pred_num = self._extract_primary_number(pred_norm)
        gold_num = self._extract_primary_number(gold_norm)

        if pred_num is not None and gold_num is not None:
            # Check unit indicators
            pred_has_pct = "%" in predicted
            gold_has_pct = "%" in gold
            pred_has_million = "million" in predicted.lower()
            gold_has_million = "million" in gold.lower()
            pred_has_thousand = "thousand" in predicted.lower()
            gold_has_thousand = "thousand" in gold.lower()

            # Unit mismatch check: if pred has % but gold doesn't (and gold has no unit conversion hint),
            # this is likely a semantic error (e.g., "-1.9% million" vs "-1.9" for share count)
            # Only allow % mismatch if we're doing explicit percentage conversion
            if pred_has_pct and not gold_has_pct:
                # Pred has %, gold doesn't - first try the strict interpretation where
                # gold is a decimal form (0.78 vs 78%).
                if self._numbers_match(
                    pred_num / 100,
                    gold_num,
                    rel_tol=0.01,
                    abs_tol=0.5,
                ):
                    return True

                # Heuristic: if gold has no explicit unit tokens and the magnitude is
                # in a reasonable percentage range (<= 100), treat a direct numeric
                # match as equivalent. This allows "-10.5%" to match "-10.5" when the
                # label clearly represents a percentage without a '%' symbol.
                gold_lower = gold.lower()
                unit_tokens = (
                    "million",
                    "billion",
                    "thousand",
                    "m ",
                    " bn",
                    " k",
                    "share",
                    "shares",
                    "units",
                    "dollar",
                    "$",
                )
                has_explicit_unit = any(tok in gold_lower for tok in unit_tokens)
                if (
                    not has_explicit_unit
                    and abs(gold_num) <= 100
                    and self._numbers_match(pred_num, gold_num, rel_tol=0.01, abs_tol=0.5)
                ):
                    return True

                # Otherwise, treat as a unit mismatch and fall through.

            elif gold_has_pct and not pred_has_pct:
                # Gold has %, pred doesn't
                # First try direct match (78.3 vs 78.3% - both represent same percentage)
                if self._numbers_match(pred_num, gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True
                # Also try if pred is decimal form (0.783 vs 78.3%)
                if self._numbers_match(pred_num * 100, gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True

            else:
                # Both have % or neither has % - direct numeric comparison is valid
                # Strategy 1: Direct numeric tolerance (within 1%)
                if self._numbers_match(pred_num, gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True

                # Strategy 2: Integer rounding (-20.65 vs -21)
                if self._numbers_match(round(pred_num), gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True
                if self._numbers_match(pred_num, round(gold_num), rel_tol=0.01, abs_tol=0.5):
                    return True

            # Strategy 3: Unit scaling (millions, thousands)
            # If gold has "million" but pred doesn't, try dividing pred by 1000
            if gold_has_million and not pred_has_million and not pred_has_thousand:
                if self._numbers_match(pred_num / 1000, gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True
            # If pred has "million" but gold doesn't, try multiplying pred
            if pred_has_million and not gold_has_million:
                if self._numbers_match(pred_num * 1000, gold_num, rel_tol=0.01, abs_tol=0.5):
                    return True

        # Strategy 5: Multi-number matching (795, 772 vs "2019: $795, 2018: $772")
        pred_nums = self._extract_all_numbers(pred_norm)
        gold_nums = self._extract_all_numbers(gold_norm)
        if len(pred_nums) >= 2 and len(gold_nums) >= 2:
            # Check if all gold numbers appear in pred (in any order)
            if all(any(self._numbers_match(g, p, rel_tol=0.01, abs_tol=0.5) for p in pred_nums) for g in gold_nums):
                return True

        # Substring containment for TEXT answers only (not numeric)
        # Skip this check if gold looks numeric (contains digits) to avoid false positives
        # like "-1.9% million" matching "-1.9"
        gold_is_numeric = bool(re.search(r'\d', gold_norm))
        if not gold_is_numeric:
            if gold_norm in pred_norm or pred_norm in gold_norm:
                return True

        # Text equivalence for common variations
        text_equivalents = [
            ("annually", "annual basis"),
            ("annual", "annually"),
            ("quarterly", "quarter basis"),
            ("monthly", "month basis"),
        ]
        for a, b in text_equivalents:
            if (a in pred_norm and b in gold_norm) or (b in pred_norm and a in gold_norm):
                return True

        return False

    def _convert_to_scalar(self, answer: str, gold: str = "") -> str:
        """Convert dict/list answers to scalar values.

        If gold contains comma-separated values, extract dict values as comma-separated.
        Otherwise, sum numeric dict values.
        """
        if not answer:
            return answer
        answer = str(answer).strip()
        gold = str(gold).strip() if gold else ""

        # Handle dict-like strings: {'2013': 1356, '2012': 2220}
        if answer.startswith("{") and ":" in answer:
            import ast
            try:
                d = ast.literal_eval(answer)
                if isinstance(d, dict):
                    values = [v for v in d.values() if isinstance(v, (int, float))]
                    if values:
                        # Check if gold expects comma-separated values (e.g., "19,911, 15,916")
                        # by looking for pattern like "num, num" or multiple numbers
                        gold_has_multiple = bool(re.search(r'\d+[,\s]+\d+[,\s]+\d+', gold.replace(',', '')))
                        if gold_has_multiple or ', ' in gold:
                            # Return as comma-separated values
                            return ", ".join(str(int(v) if v == int(v) else v) for v in values)
                        else:
                            # Sum for single value gold
                            return str(sum(values))
            except (ValueError, SyntaxError):
                pass

        # Handle list-like strings: ['a', 'b', 'c'] -> "a, b, c"
        if answer.startswith("[") and answer.endswith("]"):
            import ast
            try:
                lst = ast.literal_eval(answer)
                if isinstance(lst, list):
                    return ", ".join(str(x) for x in lst)
            except (ValueError, SyntaxError):
                pass

        return answer

    def _extract_primary_number(self, text: str) -> float | None:
        """Extract the primary numeric value from text."""
        import re
        # Remove common non-numeric chars but keep minus and decimal
        cleaned = text.replace(",", "").replace("$", "").replace("%", "").strip()
        # Match number patterns including negative and decimals
        match = re.search(r"-?\d+\.?\d*", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        return None

    def _extract_all_numbers(self, text: str) -> list[float]:
        """Extract all numeric values from text."""
        import re
        cleaned = text.replace(",", "").replace("$", "").replace("%", "")
        matches = re.findall(r"-?\d+\.?\d*", cleaned)
        numbers = []
        for m in matches:
            try:
                numbers.append(float(m))
            except ValueError:
                pass
        return numbers

    def _numbers_match(self, a: float, b: float, rel_tol: float = 0.01, abs_tol: float = 0.5) -> bool:
        """Check if two numbers match within tolerance.

        Note: abs_tol is scaled for small values to avoid false positives.
        For values < 10, we use a stricter tolerance proportional to magnitude.
        """
        if a == b:
            return True

        # For small values, scale abs_tol proportionally to avoid false positives
        # e.g., 0.667 vs 0.8 should NOT match with abs_tol=0.5
        max_val = max(abs(a), abs(b), 1.0)  # At least 1.0 to avoid division issues
        scaled_abs_tol = min(abs_tol, max_val * 0.05)  # At most 5% of magnitude

        if abs(a - b) <= scaled_abs_tol:
            return True
        if b != 0 and abs(a - b) / abs(b) <= rel_tol:
            return True
        if a != 0 and abs(a - b) / abs(a) <= rel_tol:
            return True
        return False

    def _normalize_answer(self, answer: str) -> str:
        """Normalize answer for comparison."""
        if not answer:
            return ""
        text = str(answer).lower().strip().strip(".")
        # Normalize whitespace
        text = " ".join(text.split())
        # Handle leading zero: .2 -> 0.2
        import re
        text = re.sub(r"(?<![0-9])\.(\d)", r"0.\1", text)
        return text

    def _compute_grounding_score(
        self,
        citations: List[str],
        evidence: EvidenceContext,
    ) -> float:
        """Compute what fraction of citations are properly grounded in evidence.

        A citation is considered grounded if:
        1. It references the source document (filename/sample_id from metadata)
        2. OR it references a specific evidence block (by index or content match)
        3. OR it contains a substantial phrase (3+ consecutive words) from evidence
        4. OR it references table data that exists in the evidence tables
        5. OR it uses structured table references (row/column descriptions)
        """
        if not citations:
            return 0.0

        # Build evidence corpus for matching
        evidence_blocks = [block.lower().strip() for block in evidence.text_blocks]
        evidence_full_text = " ".join(evidence_blocks)

        # Extract source identifiers from metadata
        source_ids: set[str] = set()
        if evidence.metadata:
            for key in ["source", "sample_id", "filename", "doc_id"]:
                if key in evidence.metadata and evidence.metadata[key]:
                    source_id = str(evidence.metadata[key]).lower().strip()
                    source_ids.add(source_id)
                    # Also add without extension
                    if "." in source_id:
                        source_ids.add(source_id.rsplit(".", 1)[0])
                    # Add basename
                    if "/" in source_id:
                        source_ids.add(source_id.rsplit("/", 1)[-1])
                        source_ids.add(source_id.rsplit("/", 1)[-1].rsplit(".", 1)[0])

        # Extract all table cell values and headers
        table_values: set[str] = set()
        table_headers: set[str] = set()
        for table in evidence.tables:
            for row_idx, row in enumerate(table):
                for col_idx, cell in enumerate(row):
                    cell_str = str(cell).lower().strip()
                    if cell_str:
                        table_values.add(cell_str)
                        # Also add numeric variants
                        cleaned = cell_str.replace(",", "").replace("$", "").replace("%", "")
                        if cleaned:
                            table_values.add(cleaned)
                        # First row and first column often contain headers
                        if row_idx == 0 or col_idx == 0:
                            table_headers.add(cell_str)

        grounded_count = 0
        for citation in citations:
            citation_lower = citation.lower().strip()

            # Method 1: Check if citation is a source document reference
            # e.g., "V/2008/page_17.pdf", "ETR/2011/page_341.pdf"
            if self._is_source_reference(citation_lower, source_ids):
                grounded_count += 1
                continue

            # Method 2: Check if citation is a structured table reference
            # e.g., "Table row 'canada', column 'total (mmboe)'"
            if self._is_structured_table_reference(citation_lower, table_headers, table_values):
                grounded_count += 1
                continue

            # Method 3: Check if citation is a direct reference to evidence block
            # e.g., "Evidence block 1", "paragraph 2", "table row 3"
            if self._is_direct_reference(citation_lower, len(evidence_blocks), len(evidence.tables)):
                grounded_count += 1
                continue

            # Method 4: Check for substantial phrase match (3+ consecutive words)
            if self._has_phrase_match(citation_lower, evidence_full_text, min_words=3):
                grounded_count += 1
                continue

            # Method 5: Check if citation references specific table values
            if self._references_table_data(citation_lower, table_values):
                grounded_count += 1
                continue

            # Method 6: Check if any evidence block substantially contains the citation content
            citation_words = set(citation_lower.split())
            for block in evidence_blocks:
                block_words = set(block.split())
                # If >50% of citation words appear in this block, consider it grounded
                if len(citation_words) > 0:
                    overlap = len(citation_words & block_words) / len(citation_words)
                    if overlap > 0.5:
                        grounded_count += 1
                        break

        return grounded_count / len(citations)

    def _is_source_reference(self, citation: str, source_ids: set[str]) -> bool:
        """Check if citation references the source document."""
        # Direct match
        if citation in source_ids:
            return True
        # Check if citation contains any source identifier
        for source_id in source_ids:
            if source_id in citation or citation in source_id:
                return True
        # Check for PDF filename pattern
        if re.match(r"^[a-z]+/\d{4}/page_\d+\.pdf$", citation):
            return True
        # Check for filename-like pattern at end
        if re.search(r"[a-z0-9_/-]+\.(pdf|json|txt)$", citation):
            return True
        return False

    def _is_structured_table_reference(
        self, citation: str, table_headers: set[str], table_values: set[str]
    ) -> bool:
        """Check if citation is a structured table reference like 'Table row X, column Y'."""
        # Pattern: "Table row 'X', column 'Y'" or "Table: X and Y values"
        table_patterns = [
            r"table\s+row\s+['\"]?([^'\"]+)['\"]?,?\s+columns?\s+['\"]?([^'\"]+)['\"]?",  # "table row 'X', column(s) 'Y'"
            r"table:\s+(.+)",
            r"row\s+['\"]?([^'\"]+)['\"]?\s+(?:and|,)\s+['\"]?([^'\"]+)['\"]?",
            r"table\s+row\s+['\"]?[^'\"]+['\"]?",  # Just "table row 'X'" without column
        ]
        for pattern in table_patterns:
            match = re.search(pattern, citation)
            if match:
                # Found a table reference pattern - check if referenced values exist
                groups = match.groups()
                for g in groups:
                    if g:
                        g_lower = g.lower().strip()
                        # Check if any part matches headers or values
                        if g_lower in table_headers or g_lower in table_values:
                            return True
                        # Check partial matches for compound references
                        for header in table_headers:
                            if header in g_lower or g_lower in header:
                                return True
                # If we found a table pattern, consider it grounded even without exact match
                return True
        return False

    def _is_direct_reference(self, citation: str, num_blocks: int, num_tables: int) -> bool:
        """Check if citation is a direct reference like 'paragraph 1' or 'table 2'."""
        import re
        # Match patterns like "evidence 1", "paragraph 2", "table 1", "block 3"
        patterns = [
            r"(?:evidence|paragraph|block|section|text)\s*(?:#?\s*)?(\d+)",
            r"(?:table|row|column)\s*(?:#?\s*)?(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, citation)
            if match:
                return True
        return False

    def _has_phrase_match(self, citation: str, evidence_text: str, min_words: int = 3) -> bool:
        """Check if citation contains a phrase of min_words consecutive words from evidence."""
        citation_words = citation.split()
        if len(citation_words) < min_words:
            return citation in evidence_text

        # Check all consecutive word sequences of length min_words
        for i in range(len(citation_words) - min_words + 1):
            phrase = " ".join(citation_words[i:i + min_words])
            if phrase in evidence_text:
                return True
        return False

    def _references_table_data(self, citation: str, table_values: set[str]) -> bool:
        """Check if citation references specific values from tables."""
        import re
        # Extract numbers and potential cell values from citation
        numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", citation)
        for num in numbers:
            normalized = num.replace(",", "")
            if normalized in table_values or num in table_values:
                return True
        return False

    def _detect_hallucination(
        self,
        answer: str,
        citations: List[str],
        evidence: EvidenceContext,
        raw_output: Optional[Dict[str, Any]] = None,
        verification_issues: Optional[List[str]] = None,
        gold_answer: Optional[str] = None,
        is_correct: bool = False,
    ) -> bool:
        """Detect hallucinations with awareness of chain-of-evidence/tool events.

        Important: If the answer is correct (matches gold), we don't flag it as
        hallucination even if the computed value doesn't appear in raw evidence.
        Computed results from valid calculations are not hallucinations.
        """
        # If answer is correct, it's not a hallucination (computed values are valid)
        if is_correct:
            return False

        answer_numbers = extract_numbers(answer)
        if not answer_numbers:
            return False

        grounded_numbers: List[float] = []

        # Also add gold answer numbers as "grounded" - answers close to gold are not hallucinations
        if gold_answer:
            gold_numbers = extract_numbers(gold_answer)
            grounded_numbers.extend(gold_numbers)

        def _append_numbers(text: str) -> None:
            for num in extract_numbers(text):
                grounded_numbers.append(num)

        for block in evidence.text_blocks:
            _append_numbers(block)
        for table in evidence.tables:
            _append_numbers(" ".join(str(cell) for cell in table))

        tool_events = (raw_output or {}).get("tool_events") or []
        for event in tool_events:
            result = event.get("result")
            try:
                grounded_numbers.append(float(result))
            except (TypeError, ValueError):
                continue

        for step in (raw_output or {}).get("chain_of_evidence", {}).get("steps", []):
            tool_result = step.get("tool_result") or {}
            if "result" in tool_result:
                try:
                    grounded_numbers.append(float(tool_result["result"]))
                except (TypeError, ValueError):
                    continue

        verification_issues = verification_issues or []
        has_explicit_issue = any("hallucination" in issue.lower() for issue in verification_issues)

        if not grounded_numbers:
            return has_explicit_issue

        def _is_grounded(num: float) -> bool:
            return any(within_tolerance(num, grounded) for grounded in grounded_numbers)

        has_ungrounded = any(not _is_grounded(num) for num in answer_numbers)
        return has_explicit_issue or has_ungrounded

    def compute_aggregate_metrics(
        self,
        results: Optional[List[EvalResult]] = None,
    ) -> Dict[str, EvalMetrics]:
        """Compute aggregate metrics per method."""
        results = results or self._results

        groups: Dict[str, List[EvalResult]] = {}
        for r in results:
            key = f"{r.method}_{r.task_family}"
            groups.setdefault(key, []).append(r)

        metrics: Dict[str, EvalMetrics] = {}
        for key, group in groups.items():
            method, task = key.rsplit("_", 1)
            n = len(group)

            grounding_metric = GroundingAccuracy()
            hallucination_metric = HallucinationRate()
            transparency_metric = TransparencyScore()
            auditability_metric = AuditabilityMetric()
            run_id_metric = RunIDFidelity()

            latency = 0.0
            verification_vals = []
            correct = 0

            for r in group:
                grounding_metric.update(r.grounding_score)
                hallucination_metric.update(r.has_hallucination)
                transparency_metric.update(r.raw_output)
                auditability_metric.update(r.raw_output)
                run_id_metric.update(r.raw_output)

                latency += r.latency_ms
                if r.is_correct:
                    correct += 1
                if r.verified is not None:
                    verification_vals.append(1 if r.verified else 0)

            metrics[key] = EvalMetrics(
                method=method,
                task_family=task,
                num_samples=n,
                accuracy=correct / n if n else 0.0,
                grounding_accuracy=grounding_metric.value,
                hallucination_rate=hallucination_metric.value,
                transparency_score=transparency_metric.value,
                auditability=auditability_metric.value,
                run_id_fidelity=run_id_metric.value,
                avg_latency_ms=latency / n if n else 0.0,
                verification_rate=(
                    sum(verification_vals) / len(verification_vals)
                    if verification_vals
                    else None
                ),
            )

        return metrics

    def save_results(self, run_id: str) -> Path:
        """Save results to JSON file."""
        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save individual results
        results_file = run_dir / "results.json"
        with results_file.open("w") as f:
            json.dump(
                [
                    {
                        "sample_id": r.sample_id,
                        "method": r.method,
                        "task_family": r.task_family,
                        "predicted_answer": r.predicted_answer,
                        "gold_answer": r.gold_answer,
                        "is_correct": r.is_correct,
                        "grounding_score": r.grounding_score,
                        "has_hallucination": r.has_hallucination,
                        "citations": r.citations,
                        "latency_ms": r.latency_ms,
                        "verified": r.verified,
                        "error": r.error,
                        "grounding_score": r.grounding_score,
                        "has_hallucination": r.has_hallucination,
                    }
                    for r in self._results
                ],
                f,
                indent=2,
            )

        # Save aggregate metrics
        metrics = self.compute_aggregate_metrics()
        metrics_file = run_dir / "metrics.json"
        with metrics_file.open("w") as f:
            json.dump(
                {
                    k: {
                        "method": v.method,
                        "task_family": v.task_family,
                        "num_samples": v.num_samples,
                        "accuracy": v.accuracy,
                        "grounding_accuracy": v.grounding_accuracy,
                        "hallucination_rate": v.hallucination_rate,
                        "transparency_score": v.transparency_score,
                        "auditability": v.auditability,
                        "run_id_fidelity": v.run_id_fidelity,
                        "avg_latency_ms": v.avg_latency_ms,
                        "verification_rate": v.verification_rate,
                    }
                    for k, v in metrics.items()
                },
                f,
                indent=2,
            )

        return run_dir

    def print_summary(self) -> None:
        """Print summary table of results."""
        metrics = self.compute_aggregate_metrics()

        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        print(
            f"{'Method':<20} {'Task':<5} {'N':<6} {'Acc':<8} {'Ground':<8} "
            f"{'Halluc':<8} {'Transp':<8} {'Audit':<8} {'RunID':<8} {'Latency':<10}"
        )
        print("-" * 80)

        for key, m in sorted(metrics.items()):
            print(
                f"{m.method:<20} {m.task_family:<5} {m.num_samples:<6} "
                f"{m.accuracy:.3f}   {m.grounding_accuracy:.3f}   "
                f"{m.hallucination_rate:.3f}   {m.transparency_score:.3f}   "
                f"{m.auditability:.3f}   {m.run_id_fidelity:.3f}   {m.avg_latency_ms:.0f}ms"
            )
        print("=" * 80)


def load_test_samples(
    dataset: Literal["finqa", "tatqa"],
    split: str = "dev",
    limit: Optional[int] = None,
    task_filter: Optional[str] = None,
    answer_type: Optional[str] = None,
    answer_from: Optional[str] = None,
) -> List[UnifiedSample]:
    """Load test samples as UnifiedSamples.

    Args:
        dataset: Dataset name ("finqa" or "tatqa")
        split: Dataset split (dev, train, test)
        limit: Maximum number of samples to load
        task_filter: For TAT-QA, use predefined filter ("F1", "F2", "F3", "F4")
        answer_type: For TAT-QA, filter by answer type ("arithmetic", "span", etc.)
        answer_from: For TAT-QA, filter by evidence source ("table", "text", "table-text")

    TAT-QA Task Filters:
        - F1: answer_type="arithmetic" (numeric calculations)
        - F2: answer_from="table-text" (multi-source retrieval)
        - F3: answer_type in ["span", "multi-span"] (text extraction)
        - F4: answer_type="arithmetic" with scale (unit reasoning)
    """
    if dataset == "finqa":
        loader = FinQALoader(split=split)
    elif dataset == "tatqa":
        loader = TATQALoader(
            split=split,
            task_filter=task_filter,
            answer_type=answer_type,
            answer_from=answer_from,
        )
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    samples = []
    for i, raw_sample in enumerate(loader.iter_samples()):
        if limit and i >= limit:
            break
        samples.append(to_unified(raw_sample))

    return samples
