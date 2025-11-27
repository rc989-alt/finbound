# Layer 2: LLM-Guided Re-extraction Design

## Overview

Layer 2 handles cases where Layer 0/1 detection indicates a problem but cannot auto-correct because:
1. **Wrong values extracted** from tables/text
2. **Missing operands** for the formula
3. **Formula type confusion** (e.g., percentage vs absolute)

Layer 2 uses targeted LLM prompts to re-extract values with explicit guidance.

---

## Failure Pattern Analysis

From the F1 benchmark failures, Layer 2 targets these patterns:

| Pattern | Example | Root Cause | Layer 2 Solution |
|---------|---------|------------|------------------|
| **Missing sum component** | 40294 vs 29504 | Didn't sum all rows | Table-aware sum extraction |
| **Wrong formula type** | 56 vs 5.7% | Computed % instead of absolute | Formula-guided extraction |
| **Wrong values extracted** | 547.5 vs 383.5 | Picked wrong cells | Focused re-extraction |
| **Wrong row/column** | 12.47 vs 19.13 | Read adjacent cell | Column-aware extraction |
| **Sign confusion** | -168630 vs 1138341 | Wrong value entirely | Full re-extraction |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Layer 2                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Trigger    │────▶│  Extraction  │────▶│  Validation  │    │
│  │   Detection  │     │   Strategy   │     │   & Merge    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  • recompute_mismatch  • Focused prompt    • Compare with       │
│  • missing_operands    • Table isolation     original          │
│  • low confidence      • Multi-pass vote   • Select best       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Trigger Conditions

Layer 2 activates when Layer 1 reports:

```python
LAYER2_TRIGGERS = [
    "recompute_mismatch",      # Answer doesn't match formula recomputation
    "missing_operands",        # Not enough values for detected formula
    "operand_order_mismatch",  # After auto-correct still wrong (rare)
]

# Also trigger on low confidence + specific formula types
CONFIDENCE_TRIGGERS = {
    "low": ["average", "total", "percentage_change"],
    "medium": ["change_of_averages", "difference_of_averages"],
}
```

---

## Extraction Strategies

### Strategy 1: Focused Value Extraction

For questions where we know the formula but extracted wrong values:

```python
FOCUSED_EXTRACTION_PROMPT = '''
The question asks: "{question}"

This requires computing: {formula_type}
Formula: {formula_template}

From the evidence below, extract ONLY the specific values needed:
- {operand_1_description}
- {operand_2_description}

Evidence:
{evidence}

Return JSON:
{{
  "values": [
    {{"label": "...", "value": ..., "source": "table row X" or "text"}},
    ...
  ],
  "calculation": "show your work",
  "answer": ...
}}
'''
```

### Strategy 2: Table-Aware Extraction

For table sum/average questions where cells were missed:

```python
TABLE_SUM_PROMPT = '''
Question: "{question}"

This asks for a SUM or TOTAL. You must:
1. Identify ALL rows that should be included
2. List each value with its row label
3. Sum them explicitly

Table:
{formatted_table}

Return JSON:
{{
  "rows_included": ["row1 label", "row2 label", ...],
  "values": [value1, value2, ...],
  "sum": ...,
  "answer": ...
}}
'''
```

### Strategy 3: Formula-Guided Extraction

For "change between averages" type questions:

```python
CHANGE_OF_AVERAGES_PROMPT = '''
Question: "{question}"

This asks for: CHANGE BETWEEN {year1} AND {year2} AVERAGE {metric}

Step-by-step:
1. Find {metric} for {year2} and {year2-1} → compute {year2} average
2. Find {metric} for {year1} and {year1-1} → compute {year1} average
3. Result = {year2} average - {year1} average

Extract these 4 values from the evidence:
- {metric} for {year2}: ___
- {metric} for {year2-1}: ___
- {metric} for {year1}: ___
- {metric} for {year1-1}: ___

Evidence:
{evidence}

Return JSON with all 4 values and final calculation.
'''
```

---

## Multi-Pass Voting

For high-stakes corrections, run 3 extraction passes and vote:

```python
def layer2_extract_with_voting(question, evidence, formula_type, n_passes=3):
    """Run multiple extraction passes and vote on operands."""
    extractions = []

    for i in range(n_passes):
        result = run_focused_extraction(
            question, evidence, formula_type,
            temperature=0.3 + (i * 0.1)  # Vary temperature
        )
        extractions.append(result)

    # Vote on each operand value
    final_values = vote_on_values(extractions)

    # Recompute with consensus values
    answer = recompute(formula_type, final_values)

    return answer, final_values, confidence_score(extractions)
```

---

## Integration with Verification Gate

```python
# In verification_gate/gate.py

def verify(self, ...):
    # ... existing Layer 0/1 checks ...

    # Layer 2: LLM-guided re-extraction
    if self._should_trigger_layer2(layer1_result, issues):
        layer2_result = self._run_layer2(
            question=structured_request.raw_text,
            evidence=evidence_context,
            formula_type=layer1_result.formula_type,
            original_answer=reasoning_result.answer,
            layer1_issues=layer1_result.issues,
        )

        if layer2_result.confidence > 0.8:
            # Apply Layer 2 correction
            reasoning_result.answer = layer2_result.answer
            reasoning_result.raw_model_output["layer2_correction"] = layer2_result.to_dict()
```

---

## Layer2Input / Layer2Result Types

```python
@dataclass
class Layer2Input:
    question: str
    evidence_text: str
    evidence_tables: List[List[List[str]]]  # Structured tables
    formula_type: str
    original_answer: str
    original_operands: List[dict]  # From Layer 1
    layer1_issues: List[str]

@dataclass
class Layer2Result:
    corrected_answer: str
    extracted_values: List[dict]  # {"label": ..., "value": ..., "source": ...}
    calculation_trace: str
    confidence: float  # 0-1 based on voting agreement
    correction_applied: bool
    strategy_used: str  # "focused", "table_sum", "formula_guided"
```

---

## Latency Considerations

| Strategy | Expected Latency | When to Use |
|----------|------------------|-------------|
| Focused extraction | ~2-3s | Single missing value |
| Table-aware sum | ~3-4s | Sum/total questions |
| Formula-guided | ~4-5s | Complex multi-step |
| Multi-pass voting | ~8-12s | High-stakes, low confidence |

**Optimization**: Only run Layer 2 on ~10-20% of samples (those with Layer 1 issues).

---

## Success Metrics

Target improvements from Layer 2:

| Failure Type | Current Count | Target Fix Rate | Expected Gain |
|--------------|---------------|-----------------|---------------|
| Wrong values extracted | 5 | 60% | +3 correct |
| Missing sum component | 2 | 80% | +1.6 correct |
| Formula confusion | 2 | 70% | +1.4 correct |
| **Total** | **9** | | **+6 correct (+6%)** |

---

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create `finbound/correction/layer2.py` with types and base logic
2. Add trigger detection in verification gate
3. Implement focused extraction strategy

### Phase 2: Strategy Expansion
4. Add table-aware sum extraction
5. Add formula-guided extraction for complex types
6. Implement multi-pass voting

### Phase 3: Optimization
7. Add caching for repeated patterns
8. Tune confidence thresholds
9. A/B test on F1 benchmark

---

## File Structure

```
finbound/
├── correction/
│   ├── __init__.py
│   ├── layer0_autofix.py      # Existing
│   └── layer2.py              # NEW
├── routing/
│   ├── layer0_checks.py       # Existing
│   └── layer1.py              # Existing
└── verification_gate/
    └── gate.py                 # Update to call Layer 2
```
