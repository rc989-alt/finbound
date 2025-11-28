# Detailed Analysis - FinBound v7 Low Latency

**Experiment:** FinBound + PoT v7 Low Latency on F1_UPDATED (100 samples)
**Date:** 2025-11-28
**Accuracy:** 77/100 (77.0%)

---

## Performance Comparison

| Version | Accuracy | Avg Latency | Notes |
|---------|----------|-------------|-------|
| **Original low-latency** | **83%** | **~6s** | Baseline (no PoT) |
| v6 (full mode + PoT) | 73% | ~23s | PoT + buggy verification |
| v7 (low-latency + PoT) | 77% | ~13s | PoT, no verification |

### Key Finding: 6% Regression from Original

v7 low-latency (77%) is **6% worse** than the original low-latency (83%), despite both skipping verification. The regression is caused by changes introduced for PoT integration.

---

## Regression Analysis: What Changed?

### Changes from Original to v7:
1. PoT enabled (`FINBOUND_ENABLE_POT=1`)
2. Table extraction prompt changes (CELL VERIFICATION PROCEDURE)
3. VALUE EXTRACTION format requirement added
4. QuantLib integration

### Samples that Regressed (Passed in Original, Failed in v7)

| Sample ID | Original | v7 | Issue |
|-----------|----------|-----|-------|
| SLB/2012/page_44.pdf-2 | **25.9%** ✓ | 16.67% ✗ | PoT arbitration chose wrong answer |
| 94ef7822 | 56 ✓ | 2.2 ✗ | New failure - wrong extraction |
| a983501d | ? | 5320 ✗ | Gold=3728, completely wrong |
| 191c3926 | ? | 19373 ✗ | Gold=64509, wrong extraction |
| 22e20f25 | ? | 70 ✗ | Gold=547.5, very wrong |

### Deep Dive: SLB/2012/page_44.pdf-2

**Original (correct):**
```
predicted_answer: "25.9 %"
gold_answer: "25.9%"
is_correct: true
latency_ms: 5276
```

**v7 (wrong):**
```
predicted: "16.67 %"
gold: "25.9%"
is_correct: false
```

**Root Cause:**
- Original correctly calculated percentage change: (81.15 - 64.48) / 64.48 = 25.85% ≈ 25.9%
- v7 with PoT calculated absolute difference: 81.15 - 64.48 = 16.67
- PoT computed 25.85% correctly but arbitration chose LLM's 16.67

**Fix needed:** Trust PoT when it matches percentage change pattern

---

## Latency Analysis

| Version | Total Time | Per Sample | Change |
|---------|------------|------------|--------|
| Original | ~10 min | ~6s | - |
| v7 | ~22 min | ~13.2s | +120% |

**Latency increased 2x** even in low-latency mode due to:
1. PoT execution (additional calculation steps)
2. Multiple extraction passes
3. PoT arbitration logic

---

## Error Breakdown: v7 (23 errors)

| Error Type | Count | % |
|------------|-------|---|
| Wrong values/extraction | 10 | 43.5% |
| Sign error | 4 | 17.4% |
| Scale error (100x) | 2 | 8.7% |
| Wrong calculation | 3 | 13.0% |
| PoT arbitration wrong | 1 | 4.3% |
| Format mismatch | 1 | 4.3% |
| Rounding error | 1 | 4.3% |
| Percentage point vs change | 1 | 4.3% |

---

## Sample-by-Sample Comparison

### Samples that Failed in BOTH (Original and v7):

| Sample ID | Gold | Original Pred | v7 Pred | Notes |
|-----------|------|---------------|---------|-------|
| ABMD/2006 | 25% | 85.26 | 85.27 | Same error |
| FRT/2005-1 | 92% | 21.18 | 21.18 | Same error |
| ALXN/2007-1 | 4441 | 3441.4 | 3441.4 | Same error |
| ETFC/2014-4 | -67.33 | (sign err) | 67.33 | Sign error |

### Samples FIXED by v7:
None identified - v7 has more errors than original.

### Samples BROKEN by v7:

| Sample ID | Gold | Original | v7 | Regression Cause |
|-----------|------|----------|-----|------------------|
| SLB/2012-2 | 25.9% | 25.9% ✓ | 16.67% ✗ | PoT arbitration |
| 94ef7822 | 56 | 56 ✓ | 2.2 ✗ | Extraction error |
| a983501d | 3728 | ? | 5320 ✗ | Wrong values |
| 191c3926 | 64509 | ? | 19373 ✗ | Wrong extraction |
| 22e20f25 | 547.5 | ? | 70 ✗ | Completely wrong |

---

## Root Cause Analysis

### 1. PoT Arbitration Bug (SLB/2012)
When PoT and LLM disagree, the arbitration has bias toward LLM even when PoT is correct.

**Log evidence:**
```
PoT differs from LLM: LLM=16.6700, PoT=25.8530 (diff=55.09%)
Arbitration kept LLM answer (confidence=0.90): absolute increase, not percentage
```

PoT was **correct** (25.85% matches gold 25.9%), but arbitration kept LLM.

### 2. Table Extraction Prompt Changes
The new CELL VERIFICATION PROCEDURE may be:
- Adding complexity that confuses extraction
- Causing different values to be selected
- Changing the extraction behavior negatively

### 3. PoT Adds Latency Without Benefit
In low-latency mode:
- PoT still runs but results are often ignored
- Adds ~7s latency per sample
- Net accuracy is WORSE than without PoT

---

## Recommendations

### P0 - CRITICAL: Consider Disabling PoT for Low-Latency

Current data shows PoT is **hurting** accuracy:
- Original (no PoT): 83%
- v7 (with PoT): 77%
- Regression: -6%

**Option 1:** Disable PoT in low-latency mode completely
**Option 2:** Only use PoT for specific question types where it helps

### P1 - Fix PoT Arbitration

When PoT result matches a valid percentage pattern (like 25.85% ≈ 25.9%):
- Trust PoT over LLM
- Check if LLM answer is absolute difference vs percentage change
- Add pattern matching for question type

### P2 - Revert Table Extraction Prompts

The CELL VERIFICATION PROCEDURE changes may be causing regressions.
Consider reverting to original extraction prompts.

### P3 - Benchmark Each Change

Run A/B tests to measure impact of:
1. PoT alone (without prompt changes)
2. Prompt changes alone (without PoT)
3. Both together

---

## Files in This Analysis

- `metrics.json` - Summary statistics
- `results.json` - All 23 failed samples
- `run.log` - Full execution log
- `detailed_analysis.md` - This analysis

---

## Conclusion

**The PoT integration has caused a 6% regression** (83% → 77%) in low-latency mode. The main issues are:

1. **PoT arbitration bug**: Keeps LLM answer when PoT is correct
2. **Prompt changes**: May be negatively affecting extraction
3. **No accuracy benefit**: PoT is adding latency without improving results

**Recommendation:** Consider reverting PoT changes or making them opt-in only for complex calculations where they demonstrably help.
