# FinBound + PoT Analysis: GPT-4 Failed Samples

**Run Date:** 2024-11-28
**Model:** GPT-4o
**Mode:** Full (with PoT enabled, low_latency=False)

## Executive Summary

FinBound with Program-of-Thoughts (PoT) integration achieved **60% accuracy** on 30 samples that GPT-4 failed, a **+10% improvement** over FinBound without PoT (50%).

---

## Results Comparison

| Method | Correct | Accuracy | Improvement |
|--------|---------|----------|-------------|
| GPT-4 Zero-shot | 0/30 | 0% | baseline |
| **FinBound FULL (no PoT)** | 15/30 | **50%** | +50% |
| **FinBound + PoT** | 18/30 | **60%** | +60% |

**PoT Contribution:** +3 samples (+10% accuracy)

---

## Detailed Comparison with FinBound FULL (no PoT)

### Samples Fixed by PoT (3 new)

| Sample ID | Gold | FinBound (no PoT) | FinBound + PoT | Why PoT Helped |
|-----------|------|-------------------|----------------|----------------|
| dc5e217a | 4227.5 | ❌ | ✅ 4227.5 | Temporal average computed correctly |
| 7cd3aedf | 3680 | ❌ | ✅ 3680 | Temporal average computed correctly |
| 1238d807 | -19411 | ❌ 19411 | ✅ -19411 | Sign preserved in calculation |

### Samples Still Correct (15 maintained)

Both FinBound versions got these correct:
- AMAT/2013/page_18.pdf-2 (7.22)
- 94ef7822 (56)
- 889488f7 (2053.5)
- 191c3926 (64509/64809)
- ecf25a96 (232328.5)
- 34144864 (-3)
- 73693527 (0.95)
- e151e953 (18.34/18.35)
- a0414f81 (172)
- bf7abd62 (50.5)
- 2067daa1 (88.45)
- ABMD/2009/page_56.pdf-1 (40294)
- SLB/2012/page_44.pdf-2 (25.9%)
- FRT/2005/page_117.pdf-2 (11.49%)
- e302a7ec (12)

### Regressions (FinBound no PoT got right, PoT got wrong) - 0

No regressions observed.

### Still Failing (12 samples)

| Sample ID | Gold | Predicted | Error Type |
|-----------|------|-----------|------------|
| 22e20f25 | 547.5 | 4228 | Wrong formula (change in averages) |
| d7bcc322 | -1903 | 1903 | Sign error |
| FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 | Wrong calculation |
| PNC/2013/page_62.pdf-2 | 3576 | list | Sum vs list |
| ABMD/2006/page_75.pdf-1 | 25% | 85.27 | Wrong calculation |
| a983501d | 3728 | 2349 | Wrong formula |
| a9ecc9dd | 58.43 | 26.75 | Wrong formula |
| af49c57c | 12.47 | 2.2B | Wrong interpretation |
| 3502f875 | -168630 | 1138341 | Wrong calculation |
| df12359b | 13182 | 22878 | Wrong calculation |
| 8cb754f8 | 0.5 | 31.25 | Percentage vs points |
| 4d259081 | 121.5 | 50.5 | Wrong calculation |

---

## PoT Impact by Category

### Temporal Average Questions (3 samples)

| Sample | Gold | No PoT | With PoT | Status |
|--------|------|--------|----------|--------|
| dc5e217a | 4227.5 | ❌ | ✅ | **Fixed** |
| 7cd3aedf | 3680 | ❌ | ✅ | **Fixed** |
| 22e20f25 | 547.5 | ❌ | ❌ | Still failing |

**Result:** 2/3 (67%) - PoT correctly computes simple temporal averages but failed on "change in averages"

### Sign-Sensitive Questions (3 samples)

| Sample | Gold | No PoT | With PoT | Status |
|--------|------|--------|----------|--------|
| 1238d807 | -19411 | ❌ | ✅ | **Fixed** |
| 34144864 | -3 | ✅ | ✅ | Maintained |
| d7bcc322 | -1903 | ❌ | ❌ | Still failing |

**Result:** 2/3 (67%) - PoT helps with sign preservation but not all cases

### Other Calculations (24 samples)

**Result:** 14/24 (58%) correct - Same as FinBound without PoT

---

## Key Insights

### 1. PoT Successfully Handles Temporal Averages
- `dc5e217a`: Correctly computed (4411 + 4044) / 2 = 4227.5
- `7cd3aedf`: Correctly computed (4044 + 3316) / 2 = 3680
- PoT interpreter executes deterministic calculations without LLM drift

### 2. Sign Preservation Improved
- `1238d807`: PoT preserved negative sign (-19411) where LLM returned positive
- Sign-sensitive operations benefit from explicit program execution

### 3. Remaining Challenges

**Change in Averages (22e20f25):**
- Expected: 547.5 = (4227.5 - 3680)
- Got: 4228 (just returned one average, not the difference)
- Root cause: PoT program generation didn't detect the "change between averages" pattern

**Persistent Sign Errors (d7bcc322):**
- Expected: -1903 (1046 - 2949)
- Got: 1903 (absolute value)
- Root cause: Question phrasing "difference between X and Y" - order ambiguity

**Sum vs List (PNC/2013):**
- Question asks for "total" but model returns list
- Root cause: Ambiguous question interpretation, not a PoT issue

---

## Projected Full Dataset Impact

| Scenario | Accuracy (100 samples) |
|----------|------------------------|
| GPT-4 Zero-shot | 70% |
| FinBound Low-latency v5 | 78% |
| FinBound FULL (no PoT) | ~80% |
| **FinBound + PoT** | **~82%** |

The +10% improvement on failed samples translates to +3% on the full dataset.

---

## Recommendations for Further Improvement

1. **Improve "change in averages" detection**
   - Pattern: "change between YEAR1 and YEAR2 average X"
   - Need to detect and build multi-step PoT program

2. **Better sign handling for "difference" questions**
   - "Difference between A and B" vs "Difference from A to B"
   - May need semantic analysis of operand order

3. **Sum vs List disambiguation**
   - Detect "total X for Y and Z" patterns
   - Force aggregation when "total" keyword present

4. **PoT program generation from LLM output**
   - Current: Pre-defined templates based on calc_types
   - Future: LLM generates PoT program as structured output

---

## Files in this Experiment

- `metrics.json` - Summary metrics
- `results.json` - Per-sample results
- `analysis.md` - This analysis
- `pot_failed_30_output.log` - Full execution log
