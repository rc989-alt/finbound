# Failed Questions Analysis - FinBound Low-Latency (F1_UPDATED v2 - Corrected Dataset)

**Dataset:** 50 FinQA + 50 TAT-QA = 100 samples (proper F1 benchmark)

**Note:** This run used the sign-detection-disabled version of FinBound.

## Summary

**Overall Results:**
- **Accuracy:** 75/100 (75%)
- **Failed:** 25 samples
- **Avg Latency:** ~6,200 ms

---

## Failed Samples (25 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | SPGI/2018/page_74.pdf-1 | 1.16 | 90.42 | Ratio inverse error |
| 2 | ETFC/2013/page_26.pdf-2 | 2.37 | 42.19% | Ratio inverse error |
| 3 | MMM/2005/page_95.pdf-1 | 18.6 | 5.39% | Ratio inverse error |
| 4 | FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 | Wrong calculation (26% not 25%) |
| 5 | PNC/2013/page_62.pdf-2 | 3576 | list | Sum vs list |
| 6 | ABMD/2006/page_75.pdf-1 | 25% | 85.26 | Wrong values |
| 7 | FRT/2005/page_117.pdf-1 | 92% | 21.18 | Wrong formula |
| 8 | ALXN/2007/page_104.pdf-1 | 4441 | 3441.4 | Off by 1000 |
| 9 | 94ef7822 (TAT-QA) | 56 | 2.1 | Wrong calculation |
| 10 | a983501d (TAT-QA) | 3728 | 2349 | Wrong formula |
| 11 | ba6783f3 (TAT-QA) | 2.93 | 34.13% | Ratio inverse error |
| 12 | b382a11b (TAT-QA) | 0.11 | 24.91 | Wrong calculation |
| 13 | 1238d807 (TAT-QA) | -19411 | -56.92 | Wrong values |
| 14 | a9ecc9dd (TAT-QA) | 58.43 | 26.75 | Wrong formula |
| 15 | a4308d65 (TAT-QA) | 4900 | 0.02% | Wrong calculation |
| 16 | af49c57c (TAT-QA) | 12.47 | 2200 million | Wrong interpretation |
| 17 | d7bcc322 (TAT-QA) | -1903 | 1903 | Sign error (1 only!) |
| 18 | 9f7000b0 (TAT-QA) | 0.78 | 78.3 | Scale error (100x) |
| 19 | 3502f875 (TAT-QA) | -168630 | 1138341 | Wrong values |
| 20 | c55030b2 (TAT-QA) | 1 | 23.26 | Wrong calculation |
| 21 | e302a7ec (TAT-QA) | 12 | 11 | Off by 1 |
| 22 | 16e717d5 (TAT-QA) | 467 | "S$ 467% million" | Format error |
| 23 | 8cb754f8 (TAT-QA) | 0.5 | 31.25 | Wrong calculation |
| 24 | 22e20f25 (TAT-QA) | 547.5 | 70 | Avg change wrong |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Ratio inverse error | 4 | 16% |
| Wrong calculation/formula | 10 | 40% |
| Wrong values extracted | 4 | 16% |
| Scale error | 1 | 4% |
| Sign error | 1 | 4% |
| Sum vs list | 1 | 4% |
| Off by N | 2 | 8% |
| Format error | 1 | 4% |
| Wrong interpretation | 1 | 4% |

---

## Key Finding: Sign Errors Reduced!

**Before sign detection removal:** 4 sign errors (from previous run)
**After sign detection removal:** 1 sign error

The single remaining sign error is:
- **d7bcc322**: Gold = -1903, Predicted = 1903

This is a significant improvement! Removing sign detection reduced sign errors from 4 to 1.

---

## Detailed Analysis

### Ratio Inverse Errors (4 samples)

These are cases where the `_apply_answer_format_rules` function incorrectly "fixed" the answer by taking the inverse.

#### SPGI/2018/page_74.pdf-1
- **Gold:** 1.16
- **Predicted:** 90.42 (incorrectly scaled inverse)
- **Root Cause:** Ratio inverse check triggered incorrectly

#### ETFC/2013/page_26.pdf-2
- **Gold:** 2.37
- **Predicted:** 42.19%
- **Root Cause:** Ratio inverse check triggered incorrectly

#### MMM/2005/page_95.pdf-1
- **Gold:** 18.6
- **Predicted:** 5.39%
- **Root Cause:** Ratio inverse check triggered incorrectly

#### ba6783f3 (TAT-QA)
- **Gold:** 2.93
- **Predicted:** 34.13%
- **Root Cause:** Ratio inverse check triggered incorrectly

---

### TAT-QA Temporal Average Success

Unlike GPT-4, FinBound correctly handles many temporal average questions:

- **dc5e217a:** 2019 avg FCF → 4227.5 ✓
- **7cd3aedf:** 2018 avg FCF → 3680 ✓
- **ecf25a96:** 2019 avg amounts due → 232328.5 ✓
- **a0414f81:** Avg defined contribution → 172 ✓
- **bf7abd62:** Avg defined benefit → 50.5 ✓
- **4d259081:** Avg difference → 121.5 ✓

This is a key advantage over GPT-4 zero-shot which failed 7 temporal average questions.

---

### Wrong Calculations (10 samples)

Most failures are due to extracting wrong values or using wrong formulas:

#### 94ef7822 (TAT-QA)
- **Gold:** 56
- **Predicted:** 2.1
- **Analysis:** Completely wrong calculation

#### a983501d (TAT-QA)
- **Gold:** 3728
- **Predicted:** 2349
- **Analysis:** Wrong formula for EBITDA difference

#### a4308d65 (TAT-QA)
- **Gold:** 4900
- **Predicted:** 0.02%
- **Analysis:** Computed percentage instead of sum

---

## Comparison: FinBound vs GPT-4 on F1_UPDATED v2

| Metric | FinBound Low-Latency | GPT-4 Zero-shot |
|--------|---------------------|-----------------|
| **Accuracy** | **75%** | 72% |
| **Failed** | 25 | 28 |
| **Sign errors** | **1** | 1 |
| **Temporal avg correct** | **~7** | ~0 |
| **"Uncertain" responses** | 0 | 5 |
| **Ratio inverse errors** | 4 | 0 |
| **Avg Latency** | ~6,200ms | ~2,100ms |

### Key Differences:

1. **FinBound is 3% more accurate** (75% vs 72%)
2. **FinBound handles TAT-QA temporal averages better** - correctly computes "2019 average X" = (X_2019 + X_2018)/2
3. **GPT-4 has fewer ratio errors** - FinBound's ratio inverse check causes false positives
4. **GPT-4 is 3x faster** - 2,100ms vs 6,200ms
5. **Sign errors now equal** - After removing sign detection, both have 1 sign error

---

## FinQA vs TAT-QA Breakdown

| Dataset | FinBound Correct | FinBound Accuracy |
|---------|------------------|-------------------|
| FinQA (50) | 42 | 84% |
| TAT-QA (50) | 33 | 66% |
| **Total** | **75** | **75%** |

| Dataset | GPT-4 Correct | GPT-4 Accuracy |
|---------|---------------|----------------|
| FinQA (50) | 42 | 84% |
| TAT-QA (50) | 30 | 60% |
| **Total** | **72** | **72%** |

FinBound outperforms GPT-4 on TAT-QA (66% vs 60%) primarily due to temporal average handling.

---

## Recommendations

1. **Fix ratio inverse check** - The `_apply_answer_format_rules` ratio inverse logic causes 4 false positives. Consider disabling or refining it.

2. **Keep sign detection disabled** - Reducing sign errors from 4 to 1 validates this change.

3. **Investigate remaining TAT-QA failures** - Many are complex multi-step calculations.

4. **Sum vs list disambiguation** - PNC/62 still fails (same as GPT-4).
