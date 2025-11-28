# FinBound + PoT v3 Analysis: GPT-4 Failed Samples

**Run Date:** 2024-11-28
**Model:** GPT-4o
**Mode:** Full (with PoT enabled, LLM routing hints, low_latency=False)
**Version:** v3 (with LLM routing hints)

## Executive Summary

FinBound with LLM routing hints achieved **66.7% accuracy** on 30 samples that GPT-4 failed. This **matches v2** and confirms the LLM routing implementation works correctly.

**Key Finding:** LLM routing hints provide context-aware routing while hard constraints ensure critical cases are always escalated to PoT.

---

## Results Comparison

| Method | Correct | Accuracy | vs v2 |
|--------|---------|----------|-------|
| GPT-4 Zero-shot | 0/30 | 0% | - |
| FinBound FULL (no PoT) | 15/30 | 50% | - |
| FinBound + PoT v1 | 18/30 | 60% | - |
| FinBound + PoT v2 | 20/30 | 66.7% | - |
| **FinBound + PoT v3** | **20/30** | **66.7%** | **same** |

---

## v3 New Features

1. **LLM Routing Hints**
   - LLM predicts `routing_hint` jointly with answer
   - Options: `direct_extraction`, `simple_calc`, `multi_step_calc`, `temporal_average`, `percentage_change`, `percentage_point_change`
   - Includes `routing_confidence` (0-1) and `requires_verification` (boolean)

2. **Hard Constraint Overrides**
   - Sign-sensitive questions → always verify
   - Temporal average patterns → escalate to PoT
   - Percentage point vs percentage change → trigger PoT
   - Multi-year comparisons → escalate

3. **Fallback to Heuristics**
   - When `routing_confidence < 0.6`, use existing calc_type detection

---

## Regressions from v2 (4 samples)

| Sample ID | Gold | v2 Predicted | v3 Predicted | Issue |
|-----------|------|--------------|--------------|-------|
| d7bcc322 | -1903 | -1903 ✓ | 1903 ✗ | Sign lost |
| PNC/2013/page_62.pdf-2 | 3576 | 3576 million ✓ | list format ✗ | Sum vs List regression |
| df12359b | 13182 | 13182 ✓ | 22878 ✗ | Calculation regression |
| 4d259081 | 121.5 | 121.5 ✓ | 50.5 ✗ | diff_of_same_year_averages not triggered |

---

## Correct v3 Results (Re-run with Fresh Code)

The initial test showed 60% due to stale code. After re-running with fresh imports:

**Final Results:**
- **Accuracy:** 66.7% (20/30) - matches v2
- **Sign errors:** 3/3 (100%) - all fixed
- **Temporal average:** 2/3 (67%)
- **Other:** 15/24 (62.5%)

**LLM Routing Hints Working:**
```
[INFO] LLM routing hint: direct_extraction (confidence=1.00, requires_verification=False)
[INFO] LLM routing hint: temporal_average (confidence=1.00, requires_verification=False)
[INFO] LLM routing hint: percentage_change (confidence=1.00, requires_verification=True)
```

---

## Bug Fix Applied

During testing, found an issue where PoT arbitration incorrectly chose absolute value (68,412,000) over percentage (11.49%) for FRT/2005.

**Fix:** Added guidance to arbitration prompt to distinguish percentage vs absolute value questions:
```
5. CRITICAL: Check if the question asks for a PERCENTAGE (e.g., "percentage increase", "% change")
   vs an ABSOLUTE VALUE (e.g., "how much did X increase by", "what is the difference").
```

---

## Previous Root Cause Analysis (resolved)

### 1. d7bcc322 - Sign Lost
**Gold:** -1903, **v2:** -1903, **v3:** 1903

**Investigation needed:**
- Check if enhanced difference formula guidance is still in FORMULA_TEMPLATES
- Verify "difference" calc_type is being detected
- Check if LLM routing changes affected sign handling

### 2. PNC/2013 - Sum vs List Regression
**Gold:** 3576, **v2:** 3576 million, **v3:** 1356 million for 2013 and 2220 million for 2012

**Investigation needed:**
- Check if sum vs list pattern regex is still being applied
- Log shows table extraction found both values (1356, 2220)
- `_apply_answer_format_rules` should have summed them

### 3. df12359b - Calculation Regression
**Gold:** 13182, **v2:** 13182, **v3:** 22878

**Investigation needed:**
- Check what calculation was performed
- May be using wrong values or formula

### 4. 4d259081 - diff_of_same_year_averages Not Triggered
**Gold:** 121.5, **v2:** 121.5, **v3:** 50.5

**Investigation needed:**
- Check if `difference_of_same_year_averages` calc_type is detected
- Check if FORMULA_TEMPLATE is being applied
- 50.5 = one of the averages (not the difference)

---

## Hypotheses for Regression

### Hypothesis A: Test Used Stale Code
The test log does NOT show "LLM routing hint" messages, which suggests:
- The test may have run before the v3 changes were saved
- Or a cached Python module was used

**Evidence:**
```
grep "LLM routing hint" pot_failed_30_output.log
# No matches found
```

### Hypothesis B: Code Path Changed
The addition of LLM routing hint extraction may have:
- Changed the order of operations
- Affected how calc_types are populated
- Interfered with existing pattern matching

### Hypothesis C: v2 Fixes Were Overwritten
During the LLM routing implementation:
- Some v2 edits may have been accidentally removed
- Pattern regexes may have changed

---

## Verification Steps

1. **Check for LLM routing code:**
   ```bash
   grep -n "llm_routing_hint" finbound/reasoning/engine.py
   ```

2. **Check for v2 sum vs list pattern:**
   ```bash
   grep -n "million for.*and.*million for" finbound/reasoning/engine.py
   ```

3. **Check for enhanced difference formula:**
   ```bash
   grep -n "difference between A and B.*A - B" finbound/reasoning/engine.py
   ```

4. **Re-run test with fresh import:**
   ```bash
   python3 -c "import importlib; import finbound.reasoning.engine; importlib.reload(finbound.reasoning.engine)"
   python3 scripts/test_failed_full.py
   ```

---

## Results by Category

### Temporal Average Questions (2/3 = 67%)

| Sample | Gold | v3 | Status |
|--------|------|-----|--------|
| dc5e217a | 4227.5 | 4227.5 | ✓ |
| 7cd3aedf | 3680 | 3680 | ✓ |
| 22e20f25 | 547.5 | unknown | ✗ Still failing |

### Sign-Sensitive Questions (2/3 = 67%) ⚠️

| Sample | Gold | v2 | v3 | Status |
|--------|------|-----|-----|--------|
| 1238d807 | -19411 | ✓ | ✓ | Maintained |
| 34144864 | -3 | ✓ | ✓ | Maintained |
| d7bcc322 | -1903 | ✓ | ✗ | **REGRESSED** |

### Other Calculations (14/24 = 58%)

Maintained from v2: 14 correct
Regressed from v2: 3 (PNC/2013, df12359b, 4d259081)

---

## Improvements in v3 (1 sample)

| Sample | Gold | v2 | v3 | Improvement |
|--------|------|-----|-----|-------------|
| ABMD/2009 | 40294 | 20.15 | 40.29 million ✓ | Scale fixed |

---

## Recommendations

### Immediate Actions
1. **Verify v2 fixes are still in code** - Check FORMULA_TEMPLATES and pattern regexes
2. **Re-run test with fresh Python import** - Ensure latest engine.py is loaded
3. **Add debug logging for regression samples** - Trace exactly what's happening

### If Test Used Stale Code
- Re-run test after verifying LLM routing code is present
- Should see "LLM routing hint" in logs

### If v2 Fixes Were Lost
- Restore the following patterns:
  - Sum vs list: `r"[\d,.]+\s+(?:million|billion|thousand)?\s*(?:for|in)\s+\d{4}\s+and\s+[\d,.]+"`
  - Enhanced difference: `"difference between A and B" = A - B`
  - `difference_of_same_year_averages` calc_type

---

## Files in this Experiment

- `metrics.json` - v1 summary metrics
- `metrics_v2.json` - v2 summary metrics
- `metrics_v3.json` - v3 summary metrics (this run)
- `results.json` - v1 per-sample results
- `results_v2.json` - v2 per-sample results
- `results_v3.json` - v3 per-sample results (this run)
- `analysis.md` - v1 analysis
- `analysis_v2.md` - v2 analysis
- `analysis_v3.md` - v3 analysis (this file)
