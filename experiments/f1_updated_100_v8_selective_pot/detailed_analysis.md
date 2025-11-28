# Detailed Analysis - FinBound v8 Selective PoT

**Experiment:** FinBound v8 - Selective PoT (percentage_change only)
**Date:** 2025-11-28
**Accuracy:** 77/100 (77.0%)

---

## Configuration

v8 Changes from v7:
- PoT **only** triggers for `percentage_change` routing hint
- Disabled triggers:
  - `temporal_average`
  - `multi_step_calc`
  - `percentage_point_change`
  - `requires_verification=True`
  - Hard constraint triggers (temporal_average, change_in_averages patterns)
  - Fallback heuristics

---

## Performance Comparison

| Version | Accuracy | PoT Triggers | Latency | Notes |
|---------|----------|--------------|---------|-------|
| **Original (no PoT)** | **83%** | 0 | ~6s | Baseline |
| v6 (full mode + PoT) | 73% | ~40 | ~23s | PoT + buggy verification |
| v7 (low-latency + PoT) | 77% | ~30 | ~13s | All PoT triggers |
| **v8 (selective PoT)** | **77%** | **10** | ~10s | percentage_change only |

### Key Finding: Selective PoT Didn't Improve Accuracy

v8 (77%) achieves the **same accuracy as v7** despite triggering PoT only 10 times (vs ~30 in v7).

This confirms: **The 6% regression from 83% → 77% is NOT caused by PoT over-triggering.**

---

## PoT Trigger Analysis

### v8 PoT Triggers (10 total)

| # | Result | LLM Answer | PoT Answer | Outcome |
|---|--------|------------|------------|---------|
| 1 | Verified | 2.58% | 2.5814% | Correct |
| 2 | Verified | 5.5% | 5.5044% | Correct |
| 3 | Verified | 1.27% | 1.2658% | Correct |
| 4 | Verified | -7.8% | -7.7578% | Correct |
| 5 | Sanity Failed | 11.49% | 68412000 | PoT ignored (correct) |
| 6 | Differs | 85.27 | 5529 | PoT ignored |
| 7 | Verified | -12.14% | -12.1447% | Correct |
| 8 | Verified | 0.51% | 0.5084% | Correct |
| 9 | Verified | -27.4% | -27.3973% | Correct |
| 10 | Verified | - | - | Correct |

**Summary:**
- 8/10 (80%) PoT triggers verified LLM correctly
- 2/10 (20%) PoT sanity check failed (correctly ignored)
- **0 cases where PoT corrected a wrong LLM answer**

---

## Root Cause Analysis

### Why 77% instead of 83%?

The 6% regression is caused by **other system changes**, NOT PoT:

1. **Table Extraction Prompt Changes**
   - CELL VERIFICATION PROCEDURE added
   - VALUE EXTRACTION format requirements
   - May be causing different/wrong value extraction

2. **QuantLib Integration**
   - New calculation backend
   - May have edge cases

3. **Code Changes Since Original 83%**
   - Multiple prompt modifications
   - Extraction logic updates

### Evidence: Same 23 Errors in v7 and v8

Both versions have the same 23 incorrect samples, indicating:
- PoT is not the cause of these errors
- The errors existed before PoT was enabled
- Reducing PoT triggers doesn't fix them

---

## Error Breakdown (23 errors)

| Error Type | Count | % |
|------------|-------|---|
| Wrong values/extraction | 10 | 43.5% |
| Sign error | 3 | 13.0% |
| Scale error (100x) | 2 | 8.7% |
| Wrong calculation | 4 | 17.4% |
| Format mismatch | 1 | 4.3% |
| Rounding error | 1 | 4.3% |
| Percentage point vs change | 1 | 4.3% |
| Other | 1 | 4.3% |

---

## Conclusions

1. **Selective PoT works as intended** - Only triggers for percentage_change (10 vs 30 triggers)
2. **PoT is NOT causing the regression** - Same accuracy with fewer triggers
3. **Root cause is elsewhere** - Likely prompt/extraction changes
4. **PoT provides marginal value** - Verifies correct answers but rarely corrects wrong ones

---

## Recommendations

### Option A: Disable PoT Entirely
Since PoT isn't improving accuracy and the regression is from other changes:
1. Set `FINBOUND_ENABLE_POT=0`
2. Investigate prompt/extraction changes from original 83% version
3. Revert to original prompts if possible

### Option B: Keep Selective PoT
If you want to keep PoT for safety:
1. Keep v8 configuration (percentage_change only)
2. Focus investigation on extraction/prompt regressions
3. Accept ~10% overhead for verification

### Option C: Full Investigation
1. A/B test each change since original 83%:
   - Prompt changes
   - Extraction logic
   - QuantLib integration
2. Identify specific cause of 6% regression
3. Revert only the problematic changes

---

## Files in This Analysis

- `metrics.json` - Summary statistics
- `results.json` - All 23 failed samples with PoT trigger details
- `run.log` - Full execution log
- `detailed_analysis.md` - This analysis
