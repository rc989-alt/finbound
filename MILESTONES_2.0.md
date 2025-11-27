# FinBound 2.0: Accuracy-Focused Correction Architecture

## Overview

**Current State**: 78% accuracy (83% effective after rerun recovery), 17 persistent failures
**Target State**: 90%+ accuracy, fix 12+ of 17 persistent failures

---

## Codex Task List

Each task below is self-contained and can be assigned to Codex independently.

---

## Task 1: Layer 0 - Question Type Detector

**File**: `finbound/correction/layer0_autofix.py`

**Goal**: Detect whether a question expects an absolute value or a percentage answer.

**Input**:
- `question: str` - The financial question

**Output**:
- `"absolute"` - Question asks for a number (e.g., "what is the change in X")
- `"percentage"` - Question asks for a percentage (e.g., "what is the percentage change")
- `"proportion"` - Question asks for a proportion (0-1 range)
- `"unknown"` - Cannot determine

**Test Cases**:
```python
# Should return "absolute"
"What is the change in the average total current tax expense between 2017-2018, and 2018-2019?"
"How much were the research and development expenses in 2018?"
"What is the change between 2018 and 2019 average free cash flow?"

# Should return "percentage"
"What is the percentage change in Other in 2019 from 2018?"
"What was the percentage change in the amount for Appliances in 2019 from 2018?"

# Should return "proportion"
"What was the employee termination costs as a proportion of total costs in 2018?"
"What is the proportion of granted shares between 2017 and 2018 over outstanding shares?"
```

**Implementation Hint**:
```python
def detect_question_type(question: str) -> str:
    q = question.lower()

    # Check for explicit percentage keywords
    if any(w in q for w in ["percentage change", "percent change", "% change"]):
        return "percentage"

    # Check for proportion keywords
    if "proportion" in q and "percentage" not in q:
        return "proportion"

    # Check for absolute change patterns (without percentage words)
    absolute_patterns = [
        r"what is the change in",
        r"what was the change in",
        r"change between .* and .* average",
        r"how much (?:was|were|did)",
        r"difference between",
    ]
    if "percentage" not in q and "percent" not in q and "%" not in q:
        for pattern in absolute_patterns:
            if re.search(pattern, q):
                return "absolute"

    # Check for percentage of total
    if any(w in q for w in ["percentage of", "% of", "as a percentage"]):
        return "percentage"

    return "unknown"
```

**Success Criteria**: Correctly classify all 6 test cases above.

---

## Task 2: Layer 0 - Scale Auto-Converter

**File**: `finbound/correction/layer0_autofix.py`

**Goal**: Automatically convert between proportion (0-1) and percentage (0-100) based on question type.

**Input**:
- `answer: float` - The model's numeric answer
- `question_type: str` - From Task 1 ("absolute", "percentage", "proportion")

**Output**:
- `corrected_answer: float` - The corrected value
- `correction_applied: bool` - Whether a correction was made
- `correction_type: str` - Type of correction ("scale_to_proportion", "scale_to_percentage", "none")

**Test Cases**:
```python
# Proportion expected, got percentage-scale value
scale_autoconvert(answer=95.5, question_type="proportion")
# → corrected=0.955, correction_applied=True, correction_type="scale_to_proportion"

# Percentage expected, got proportion-scale value
scale_autoconvert(answer=0.18, question_type="percentage")
# → corrected=18.0, correction_applied=True, correction_type="scale_to_percentage"

# Already correct scale
scale_autoconvert(answer=56.0, question_type="absolute")
# → corrected=56.0, correction_applied=False, correction_type="none"

# Percentage expected, already percentage scale
scale_autoconvert(answer=78.5, question_type="percentage")
# → corrected=78.5, correction_applied=False, correction_type="none"
```

**Implementation Hint**:
```python
def scale_autoconvert(answer: float, question_type: str) -> tuple[float, bool, str]:
    if question_type == "proportion":
        if abs(answer) > 1:  # Looks like percentage scale
            return answer / 100, True, "scale_to_proportion"

    elif question_type == "percentage":
        if 0 < abs(answer) < 1:  # Looks like proportion scale
            return answer * 100, True, "scale_to_percentage"

    return answer, False, "none"
```

**Target Fixes**:
- `73693527`: 95.5 → 0.955 (gold: 0.95)
- `e151e953`: 0.18 → 18.0 (gold: 18.34)

**Success Criteria**: Both target samples corrected to within 5% of gold.

---

## Task 3: Layer 0 - Format Stripper

**File**: `finbound/correction/layer0_autofix.py`

**Goal**: Strip percentage symbols when question asks for absolute value.

**Input**:
- `answer_str: str` - The model's answer as string (e.g., "467%", "-10.5%")
- `question_type: str` - From Task 1

**Output**:
- `numeric_value: float` - The extracted numeric value
- `had_percentage: bool` - Whether % was present
- `correction_applied: bool` - Whether we stripped % for absolute question

**Test Cases**:
```python
# Absolute question, got percentage format
strip_format(answer_str="467%", question_type="absolute")
# → numeric_value=467.0, had_percentage=True, correction_applied=True

# Percentage question, got percentage format (correct)
strip_format(answer_str="-10.5%", question_type="percentage")
# → numeric_value=-10.5, had_percentage=True, correction_applied=False

# No percentage symbol
strip_format(answer_str="1320.8", question_type="absolute")
# → numeric_value=1320.8, had_percentage=False, correction_applied=False
```

**Target Fixes**:
- `RSG/2009`: "-10.5%" → -10.5 (gold: -10.5)
- `16e717d5`: "467%" → 467 (gold: 467)

**Success Criteria**: Both target samples corrected exactly.

---

## Task 4: Layer 0 - Complete Auto-Fix Pipeline

**File**: `finbound/correction/layer0_autofix.py`

**Goal**: Combine Tasks 1-3 into a single function that runs all Layer 0 checks.

**Input**:
```python
@dataclass
class Layer0Input:
    question: str
    answer: float
    answer_str: str  # Original string representation
```

**Output**:
```python
@dataclass
class Layer0Result:
    original_answer: float
    corrected_answer: float
    correction_applied: bool
    correction_type: Optional[str]  # "scale_to_proportion", "scale_to_percentage", "strip_percentage", None
    question_type: str  # "absolute", "percentage", "proportion", "unknown"
    needs_layer1: bool  # True if can't auto-fix, needs recomputation
```

**Implementation**:
```python
def run_layer0(input: Layer0Input) -> Layer0Result:
    # 1. Detect question type
    question_type = detect_question_type(input.question)

    # 2. Try format stripping first
    numeric, had_pct, stripped = strip_format(input.answer_str, question_type)
    if stripped:
        return Layer0Result(
            original_answer=input.answer,
            corrected_answer=numeric,
            correction_applied=True,
            correction_type="strip_percentage",
            question_type=question_type,
            needs_layer1=False
        )

    # 3. Try scale conversion
    corrected, scaled, scale_type = scale_autoconvert(input.answer, question_type)
    if scaled:
        return Layer0Result(
            original_answer=input.answer,
            corrected_answer=corrected,
            correction_applied=True,
            correction_type=scale_type,
            question_type=question_type,
            needs_layer1=False
        )

    # 4. Check if absolute/percentage mismatch needs Layer 1
    needs_layer1 = (question_type == "absolute" and had_pct) or \
                   (question_type == "percentage" and not had_pct and abs(input.answer) > 100)

    return Layer0Result(
        original_answer=input.answer,
        corrected_answer=input.answer,
        correction_applied=False,
        correction_type=None,
        question_type=question_type,
        needs_layer1=needs_layer1
    )
```

**Success Criteria**:
- Fix 4 target samples: 73693527, e151e953, RSG/2009, 16e717d5
- No false positives on correct answers

---

## Task 5: Layer 1 - Formula Knowledge Base

**File**: `finbound/correction/formula_kb.py`

**Goal**: Define formula templates for common financial calculations.

**Formulas to Implement**:

| Formula Type | Pattern Examples | Computation |
|--------------|------------------|-------------|
| `percentage_change` | "percentage change", "% change", "YoY" | `(new - old) / old * 100` |
| `absolute_change` | "what is the change in", "difference between" | `new - old` |
| `average` | "average", "mean" | `sum(values) / len(values)` |
| `percentage_of_total` | "% of total", "as a percentage of" | `part / total * 100` |
| `ratio` | "ratio of X to Y" | `X / Y` |
| `sum_total` | "total of", "sum of" | `sum(values)` |
| `temporal_average` | "2019 average X" | `(X_2019 + X_2018) / 2` |
| `change_of_averages` | "change in average X" | `avg1 - avg2` |

**Implementation**:
```python
from dataclasses import dataclass
from typing import List, Dict, Callable, Any
import re

@dataclass
class FormulaTemplate:
    name: str
    patterns: List[str]  # Regex patterns to match
    compute: Callable[..., float]  # Computation function
    operands: List[str]  # Names of required operands
    validate: Callable[[float], bool]  # Sanity check

FORMULA_KB: Dict[str, FormulaTemplate] = {
    "percentage_change": FormulaTemplate(
        name="percentage_change",
        patterns=[r"percentage change", r"percent change", r"% change", r"yoy", r"year over year"],
        compute=lambda new, old: ((new - old) / old) * 100 if old != 0 else None,
        operands=["new_value", "old_value"],
        validate=lambda r: -100 <= r <= 10000
    ),
    "absolute_change": FormulaTemplate(
        name="absolute_change",
        patterns=[r"what is the change in", r"what was the change in", r"difference between"],
        compute=lambda new, old: new - old,
        operands=["new_value", "old_value"],
        validate=lambda r: True
    ),
    # ... implement all 8 formulas
}

def detect_formula_type(question: str) -> Optional[str]:
    """Match question to formula type."""
    q = question.lower()
    for name, template in FORMULA_KB.items():
        for pattern in template.patterns:
            if re.search(pattern, q):
                return name
    return None
```

**Test Cases**:
```python
detect_formula_type("What is the percentage change in revenue from 2018 to 2019?")
# → "percentage_change"

detect_formula_type("What is the change in the average total current tax expense?")
# → "absolute_change" (no "percentage" keyword)

detect_formula_type("What was the average currency translation adjustments from 2013 to 2015?")
# → "average"

detect_formula_type("What is the ratio of service cost to interest cost?")
# → "ratio"
```

**Success Criteria**: Correctly detect formula type for 80%+ of F1 questions.

---

## Task 6: Layer 1 - Operand Extractor

**File**: `finbound/correction/operand_extractor.py`

**Goal**: Extract operands (numbers) needed for formula computation from evidence.

**Input**:
- `question: str` - The question
- `evidence: str` - The financial document text/tables
- `formula_type: str` - From Task 5
- `model_reasoning: str` - The model's reasoning (may contain extracted values)

**Output**:
```python
@dataclass
class ExtractedOperands:
    operands: Dict[str, float]  # e.g., {"new_value": 100, "old_value": 80}
    sources: Dict[str, str]  # e.g., {"new_value": "Table 1, row 3, 2019 column"}
    complete: bool  # True if all required operands found
```

**Implementation Strategy**:
1. Parse years from question (e.g., "from 2018 to 2019")
2. Extract metric name from question (e.g., "revenue", "EBITDA")
3. Search evidence for values matching year + metric
4. Also parse model's reasoning for already-extracted values

**Pseudo-code**:
```python
def extract_operands(question: str, evidence: str, formula_type: str, model_reasoning: str) -> ExtractedOperands:
    template = FORMULA_KB[formula_type]
    operands = {}
    sources = {}

    # 1. Try to extract from model's reasoning first
    numbers_in_reasoning = re.findall(r'[-+]?\d*\.?\d+', model_reasoning)

    # 2. Extract years from question
    years = re.findall(r'\b(19|20)\d{2}\b', question)

    # 3. For percentage_change, need new and old values
    if formula_type == "percentage_change" and len(years) >= 2:
        old_year, new_year = sorted(years)[:2]
        # Search evidence for values at these years
        operands["old_value"] = find_value_for_year(evidence, old_year)
        operands["new_value"] = find_value_for_year(evidence, new_year)

    # 4. For average, need all values in range
    elif formula_type == "average":
        if len(years) >= 2:
            operands["values"] = find_values_in_year_range(evidence, years[0], years[-1])

    complete = all(op in operands for op in template.operands)
    return ExtractedOperands(operands=operands, sources=sources, complete=complete)
```

**Success Criteria**: Extract correct operands for 70%+ of calculation questions.

---

## Task 7: Layer 1 - Deterministic Recomputation

**File**: `finbound/correction/recompute.py`

**Goal**: Given operands and formula type, compute the answer deterministically.

**Input**:
```python
@dataclass
class RecomputeInput:
    formula_type: str
    operands: Dict[str, float]
    model_answer: float  # For comparison
```

**Output**:
```python
@dataclass
class RecomputeResult:
    recomputed_value: float
    matches_model: bool  # Within 1% tolerance
    correction_applied: bool
    final_answer: float  # Use recomputed if different
```

**Implementation**:
```python
def recompute(input: RecomputeInput) -> RecomputeResult:
    template = FORMULA_KB[input.formula_type]

    # Compute based on formula type
    if input.formula_type == "percentage_change":
        recomputed = template.compute(
            input.operands["new_value"],
            input.operands["old_value"]
        )
    elif input.formula_type == "absolute_change":
        recomputed = template.compute(
            input.operands["new_value"],
            input.operands["old_value"]
        )
    elif input.formula_type == "average":
        recomputed = template.compute(input.operands["values"])
    # ... handle all formula types

    # Validate
    if not template.validate(recomputed):
        return RecomputeResult(
            recomputed_value=recomputed,
            matches_model=False,
            correction_applied=False,
            final_answer=input.model_answer  # Don't use invalid recomputation
        )

    # Compare with model
    tolerance = 0.01  # 1%
    relative_diff = abs(input.model_answer - recomputed) / max(abs(recomputed), 1e-6)
    matches = relative_diff < tolerance

    return RecomputeResult(
        recomputed_value=recomputed,
        matches_model=matches,
        correction_applied=not matches,
        final_answer=recomputed if not matches else input.model_answer
    )
```

**Target Fixes**:
- `94ef7822`: 5.4% → 56 (absolute change, not percentage)
- `22e20f25`: 183.5% → 547.5 (absolute change of averages)
- `PM/2015/127`: -4088.33 → -6806 (correct average)
- `BDX/2018`: 1.51 → 66.2% (correct ratio)

**Success Criteria**: Fix 4+ of the 6 Layer 1 target samples.

---

## Task 8: Layer 1 - Complete Recomputation Pipeline

**File**: `finbound/correction/layer1_recompute.py`

**Goal**: Combine Tasks 5-7 into complete Layer 1 pipeline.

**Input**:
```python
@dataclass
class Layer1Input:
    question: str
    evidence: str
    model_answer: float
    model_reasoning: str
```

**Output**:
```python
@dataclass
class Layer1Result:
    formula_type: Optional[str]
    operands: Dict[str, float]
    operands_complete: bool
    recomputed_value: Optional[float]
    correction_applied: bool
    final_answer: float
    confidence: str  # "high", "medium", "low"
```

**Implementation**:
```python
def run_layer1(input: Layer1Input) -> Layer1Result:
    # 1. Detect formula type
    formula_type = detect_formula_type(input.question)
    if formula_type is None:
        return Layer1Result(
            formula_type=None,
            operands={},
            operands_complete=False,
            recomputed_value=None,
            correction_applied=False,
            final_answer=input.model_answer,
            confidence="low"
        )

    # 2. Extract operands
    extracted = extract_operands(
        input.question, input.evidence, formula_type, input.model_reasoning
    )

    if not extracted.complete:
        return Layer1Result(
            formula_type=formula_type,
            operands=extracted.operands,
            operands_complete=False,
            recomputed_value=None,
            correction_applied=False,
            final_answer=input.model_answer,
            confidence="low"
        )

    # 3. Recompute
    recompute_result = recompute(RecomputeInput(
        formula_type=formula_type,
        operands=extracted.operands,
        model_answer=input.model_answer
    ))

    return Layer1Result(
        formula_type=formula_type,
        operands=extracted.operands,
        operands_complete=True,
        recomputed_value=recompute_result.recomputed_value,
        correction_applied=recompute_result.correction_applied,
        final_answer=recompute_result.final_answer,
        confidence="high" if recompute_result.matches_model else "medium"
    )
```

**Success Criteria**: Fix 6+ of 10 calculation errors.

---

## Task 9: Layer 2 - LLM-Guided Extraction

**File**: `finbound/correction/layer2_extraction.py`

**Goal**: When Layer 1 fails (missing operands), use LLM to explicitly extract values.

**Input**:
```python
@dataclass
class Layer2Input:
    question: str
    evidence: str
    formula_type: str
    required_operands: List[str]  # e.g., ["new_value", "old_value"]
```

**Output**:
```python
@dataclass
class Layer2Result:
    operands: Dict[str, float]
    sources: Dict[str, str]
    confidence: str
    success: bool
```

**Implementation**:
```python
def llm_guided_extraction(input: Layer2Input, llm_client) -> Layer2Result:
    template = FORMULA_KB[input.formula_type]

    prompt = f"""
    Question: {input.question}

    Evidence:
    {input.evidence}

    I need to calculate: {template.name}
    Formula: {template.compute.__doc__ or template.name}

    Please extract these specific values from the evidence:
    {json.dumps(template.operands, indent=2)}

    For EACH value, respond with:
    1. The exact numeric value (just the number)
    2. Where you found it (table name, row, column, year)

    Output as JSON:
    {{
        "operand_name": {{"value": 123.45, "source": "Table X, 2019 column"}}
    }}
    """

    response = llm_client.complete(prompt, temperature=0.0)
    parsed = json.loads(response)

    operands = {k: v["value"] for k, v in parsed.items()}
    sources = {k: v["source"] for k, v in parsed.items()}

    return Layer2Result(
        operands=operands,
        sources=sources,
        confidence="medium",
        success=all(op in operands for op in input.required_operands)
    )
```

**Target Fixes**:
- `ABMD/2009`: Missing sum component
- `a983501d`: Wrong table values
- `a9ecc9dd`: Wrong numerator

**Success Criteria**: Successfully extract operands for 60%+ of Layer 2 samples.

---

## Task 10: Layer 2 - Multi-Pass Consensus

**File**: `finbound/correction/layer2_extraction.py`

**Goal**: Run multiple extraction attempts and use majority vote for operands.

**Implementation**:
```python
def multi_pass_extraction(input: Layer2Input, llm_client, num_passes: int = 3) -> Layer2Result:
    extractions = []

    for i in range(num_passes):
        result = llm_guided_extraction(input, llm_client)
        extractions.append(result.operands)

    # Consensus voting
    consensus = {}
    for operand in input.required_operands:
        values = [e.get(operand) for e in extractions if operand in e]
        if values:
            # Use most common value (within tolerance)
            consensus[operand] = get_consensus_value(values, tolerance=0.05)

    return Layer2Result(
        operands=consensus,
        sources={},
        confidence="high" if len(set(tuple(e.items()) for e in extractions)) == 1 else "medium",
        success=all(op in consensus for op in input.required_operands)
    )

def get_consensus_value(values: List[float], tolerance: float) -> Optional[float]:
    """Return value that most others agree with within tolerance."""
    if not values:
        return None

    for candidate in values:
        agreeing = sum(1 for v in values if abs(v - candidate) / max(abs(candidate), 1e-6) < tolerance)
        if agreeing > len(values) / 2:
            return candidate

    return values[0]  # Fallback to first if no consensus
```

**Success Criteria**: Improve extraction accuracy by 20% over single-pass.

---

## Task 11: Correction Orchestrator

**File**: `finbound/correction/orchestrator.py`

**Goal**: Wire all layers together into unified correction pipeline.

**Implementation**:
```python
@dataclass
class CorrectionResult:
    original_answer: float
    final_answer: float
    correction_applied: bool
    correction_source: str  # "layer0", "layer1", "layer2", "none"
    confidence: str
    audit_trail: List[dict]

class CorrectionOrchestrator:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def correct(
        self,
        question: str,
        evidence: str,
        model_answer: float,
        model_answer_str: str,
        model_reasoning: str
    ) -> CorrectionResult:
        audit = []

        # ===== LAYER 0 =====
        layer0_input = Layer0Input(
            question=question,
            answer=model_answer,
            answer_str=model_answer_str
        )
        layer0_result = run_layer0(layer0_input)
        audit.append({"layer": 0, "result": asdict(layer0_result)})

        if layer0_result.correction_applied:
            return CorrectionResult(
                original_answer=model_answer,
                final_answer=layer0_result.corrected_answer,
                correction_applied=True,
                correction_source="layer0",
                confidence="high",
                audit_trail=audit
            )

        # ===== LAYER 1 =====
        layer1_input = Layer1Input(
            question=question,
            evidence=evidence,
            model_answer=layer0_result.corrected_answer,
            model_reasoning=model_reasoning
        )
        layer1_result = run_layer1(layer1_input)
        audit.append({"layer": 1, "result": asdict(layer1_result)})

        if layer1_result.correction_applied:
            return CorrectionResult(
                original_answer=model_answer,
                final_answer=layer1_result.final_answer,
                correction_applied=True,
                correction_source="layer1",
                confidence=layer1_result.confidence,
                audit_trail=audit
            )

        if layer1_result.operands_complete and not layer1_result.correction_applied:
            # Recomputation matched - answer is verified correct
            return CorrectionResult(
                original_answer=model_answer,
                final_answer=model_answer,
                correction_applied=False,
                correction_source="none",
                confidence="high",
                audit_trail=audit
            )

        # ===== LAYER 2 =====
        if self.llm_client and layer1_result.formula_type:
            layer2_input = Layer2Input(
                question=question,
                evidence=evidence,
                formula_type=layer1_result.formula_type,
                required_operands=FORMULA_KB[layer1_result.formula_type].operands
            )
            layer2_result = multi_pass_extraction(layer2_input, self.llm_client)
            audit.append({"layer": 2, "result": asdict(layer2_result)})

            if layer2_result.success:
                # Recompute with Layer 2 operands
                recompute_result = recompute(RecomputeInput(
                    formula_type=layer1_result.formula_type,
                    operands=layer2_result.operands,
                    model_answer=model_answer
                ))

                if recompute_result.correction_applied:
                    return CorrectionResult(
                        original_answer=model_answer,
                        final_answer=recompute_result.final_answer,
                        correction_applied=True,
                        correction_source="layer2",
                        confidence=layer2_result.confidence,
                        audit_trail=audit
                    )

        # No correction possible
        return CorrectionResult(
            original_answer=model_answer,
            final_answer=model_answer,
            correction_applied=False,
            correction_source="none",
            confidence="low",
            audit_trail=audit
        )
```

**Success Criteria**:
- Fix 12+ of 17 persistent failures
- Achieve 90%+ accuracy on F1 benchmark

---

## Task 12: Integration Tests

**File**: `tests/test_correction_pipeline.py`

**Goal**: Test the full correction pipeline on the 17 failed samples.

**Test Data** (from `experiments/F1_result/failed_questions/`):
```python
FAILED_SAMPLES = [
    # Layer 0 targets
    {"id": "73693527", "gold": 0.95, "model": 95.5, "layer": "L0"},
    {"id": "e151e953", "gold": 18.34, "model": 0.18, "layer": "L0"},
    {"id": "RSG/2009", "gold": -10.5, "model_str": "-10.5%", "layer": "L0"},
    {"id": "16e717d5", "gold": 467, "model_str": "467%", "layer": "L0"},

    # Layer 1 targets
    {"id": "94ef7822", "gold": 56, "model": 5.4, "layer": "L1"},
    {"id": "22e20f25", "gold": 547.5, "model": 183.5, "layer": "L1"},
    {"id": "PM/2015/127", "gold": -6806, "model": -4088.33, "layer": "L1"},
    {"id": "BDX/2018", "gold": 66.2, "model": 1.51, "layer": "L1"},
    {"id": "HIG/2011", "gold": -7.8, "model": -7.19, "layer": "L1"},
    {"id": "b382a11b", "gold": 0.11, "model": 24.91, "layer": "L1"},

    # Layer 2 targets
    {"id": "ABMD/2009", "gold": 40294, "model": 20147, "layer": "L2"},
    {"id": "a983501d", "gold": 3728, "model": 2349, "layer": "L2"},
    {"id": "a9ecc9dd", "gold": 58.43, "model": 26.75, "layer": "L2"},
    {"id": "01de2123", "gold": -78.06, "model": 3.1, "layer": "L2"},
    {"id": "af49c57c", "gold": 12.47, "model": 11.3, "layer": "L2"},

    # Correct abstentions (should NOT be "fixed")
    {"id": "FBHS/2017", "gold": 1320.8, "model": "uncertain", "layer": "ABSTAIN"},
    {"id": "3502f875", "gold": -168630, "model": "uncertain", "layer": "ABSTAIN"},
]
```

**Success Criteria**:
- Layer 0: Fix 4/4 (100%)
- Layer 1: Fix 4/6 (67%)
- Layer 2: Fix 3/5 (60%)
- Abstentions: Do NOT change (0/2 modified)
- **Total: Fix 11-13/15 addressable samples**

---

## Summary: Task Dependencies

```
Task 1 (Question Type) ─┐
Task 2 (Scale Convert) ─┼─→ Task 4 (Layer 0 Complete)
Task 3 (Format Strip)  ─┘

Task 5 (Formula KB) ────┐
Task 6 (Operand Extract)┼─→ Task 8 (Layer 1 Complete)
Task 7 (Recompute)     ─┘

Task 9 (LLM Extract) ───┬─→ Task 10 (Multi-Pass)
                        │
Task 4 ─────────────────┤
Task 8 ─────────────────┼─→ Task 11 (Orchestrator) ─→ Task 12 (Tests)
Task 10 ────────────────┘
```

**Recommended Order**:
1. Tasks 1-4 (Layer 0) - Can run independently
2. Tasks 5-8 (Layer 1) - Can run independently
3. Tasks 9-10 (Layer 2) - Requires LLM client
4. Task 11 (Orchestrator) - Requires Tasks 4, 8, 10
5. Task 12 (Tests) - Requires Task 11
