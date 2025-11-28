# PoT Analysis: 100 Sample Run (Partial - 57 samples)

**Date:** 2024-11-28
**Dataset:** FinQA (F1 task)
**Mode:** PoT v3 with LLM routing hints
**Status:** Killed after 57 samples

## Executive Summary

PoT v3 was triggered frequently but **never improved accuracy**. In all 33 cases where PoT differed from LLM, **arbitration correctly chose the LLM answer**.

This indicates:
1. PoT program generation has significant bugs
2. Arbitration is working correctly as a safety net
3. PoT is adding latency without benefit

---

## Statistics

| Metric | Value |
|--------|-------|
| Samples processed | 57 |
| PoT triggered | 49 (86% of samples) |
| PoT differed from LLM | 33 (67% of triggers) |
| Arbitration kept LLM | 33 (100%) |
| Arbitration chose PoT | 0 (0%) |

---

## Issue Breakdown

| Issue Type | Count | Description |
|------------|-------|-------------|
| Order of magnitude errors | 10 | PoT value off by 1000x+ (wrong values/formula) |
| Large discrepancy | 9 | PoT value off by 100-1000% |
| Sign inversion | 8 | PoT returns -X when LLM returns X (200% diff) |
| Calculation difference | 6 | Moderate differences (< 100%) |

---

## Root Cause Analysis

### 1. Sign Inversion (8 cases)

**Pattern:** `diff = 200%` (e.g., LLM=18.6, PoT=-18.6)

**Root Cause:** `create_pot_program_for_sign_sensitive()` always computes `new - old`, but:
- Doesn't consider question context (increase vs decrease)
- Doesn't match LLM's interpretation

**Examples:**
- LLM=18.6, PoT=-18.6
- LLM=6.2, PoT=-6.2
- LLM=2.58, PoT=-2.58
- LLM=3.2, PoT=-3.2
- LLM=1.42, PoT=-1.42
- LLM=57.0, PoT=-57.0

### 2. Order of Magnitude Errors (10 cases)

**Pattern:** `diff > 1000%` (e.g., LLM=10.94, PoT=1,380,763)

**Root Cause:** `_build_generic_pot_program()` selects wrong values:
- Uses raw table values instead of semantic matches
- Doesn't respect LLM's `values_used` ordering
- Applies wrong formula type (percentage vs absolute)

**Examples:**
- LLM=10.94 (CET1 ratio), PoT=1,380,763 (raw value sum?)
- LLM=86.8 (percentage), PoT=6,446,489 (absolute value)
- LLM=4.86 (ratio), PoT=14,228 (wrong calculation)
- LLM=4.0 (ratio), PoT=-9,000,000 (nonsensical)

### 3. Wrong Formula Application (9 cases)

**Pattern:** PoT uses sum when average needed, or percentage when difference needed

**Root Cause:** `calc_types` detection is correct, but PoT program uses wrong values:
- "percentage_of_total" uses wrong numerator/denominator
- "average" averages wrong set of values
- "difference" subtracts unrelated values

---

## Recommendations

### Immediate Fixes

1. **Disable PoT for now** - It's not helping and adds latency
   - Or set higher confidence threshold to reduce triggers

2. **Fix sign-sensitive logic:**
   ```python
   # Check if LLM answer is positive or negative
   # Match PoT sign to LLM's interpretation
   if proposed_numeric > 0 and pot_value < 0:
       pot_value = abs(pot_value)
   elif proposed_numeric < 0 and pot_value > 0:
       pot_value = -pot_value
   ```

3. **Improve value selection:**
   - Use LLM's `values_used` labels to select correct values
   - Match values by role (numerator/denominator, old/new)

### Long-term Fixes

4. **LLM-generated PoT programs:**
   - Instead of template-based programs, have LLM generate the program
   - Would handle novel calculation patterns

5. **Reduce PoT triggering:**
   - Only trigger when `routing_confidence < 0.7`
   - Skip PoT for `direct_extraction` and `simple_calc` hints

---

## Files

- `pot_analysis.json` - Structured analysis data
- `../pot_v3_full_100/run.log` - Full log file (57 samples)

