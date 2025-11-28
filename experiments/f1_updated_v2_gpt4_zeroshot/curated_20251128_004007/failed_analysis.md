# Failed Questions Analysis - GPT-4 Zero-shot (F1_UPDATED v2 - Corrected Dataset)

**Dataset:** 50 FinQA + 50 TAT-QA = 100 samples (proper F1 benchmark)

## Summary

**Overall Results:**
- **Accuracy:** 72/100 (72%)
- **Failed:** 28 samples
- **Avg Latency:** ~2,100 ms

---

## Failed Samples (28 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | ABMD/2009/page_56.pdf-1 | 40294 | 20.147 | Scale/unit error |
| 2 | SLB/2012/page_44.pdf-2 | 25.9% | 16.67 | Wrong calculation |
| 3 | FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.658 | Wrong calculation |
| 4 | FRT/2005/page_117.pdf-2 | 11.49% | $68,412,000 | Wrong formula |
| 5 | PNC/2013/page_62.pdf-2 | 3576 | "2013: 1356, 2012: 2220" | Sum vs list |
| 6 | ABMD/2006/page_75.pdf-1 | 25% | uncertain | Extraction failure |
| 7 | AMAT/2013/page_18.pdf-2 | 7.22 | uncertain | Extraction failure |
| 8 | ALXN/2007/page_104.pdf-1 | 4441 | 3441 | Off by 1000 |
| 9 | 94ef7822 (TAT-QA) | 56 | 44 | Wrong calculation |
| 10 | a983501d (TAT-QA) | 3728 | 2820 | Wrong formula |
| 11 | 1238d807 (TAT-QA) | -19411 | "$19,411 decrease" | Format/sign |
| 12 | a9ecc9dd (TAT-QA) | 58.43 | 26.75% | Wrong formula |
| 13 | 889488f7 (TAT-QA) | 2053.5 | "2025, 2082" | Average vs list |
| 14 | 191c3926 (TAT-QA) | 64509 | uncertain | Extraction failure |
| 15 | ecf25a96 (TAT-QA) | 232328.5 | 243424 | Average vs single |
| 16 | af49c57c (TAT-QA) | 12.47 | uncertain | Extraction failure |
| 17 | 34144864 (TAT-QA) | -3 | "decrease" | Format error |
| 18 | d7bcc322 (TAT-QA) | -1903 | "$1,903" | Sign error |
| 19 | 3502f875 (TAT-QA) | -168630 | uncertain | Extraction failure |
| 20 | e151e953 (TAT-QA) | 18.34 | 0.1834 | Scale error (100x) |
| 21 | df12359b (TAT-QA) | 13182 | 13026 | Wrong calculation |
| 22 | e302a7ec (TAT-QA) | 12 | 15 years | Wrong value |
| 23 | a0414f81 (TAT-QA) | 172 | 166 | Average vs single |
| 24 | bf7abd62 (TAT-QA) | 50.5 | 57 | Average vs single |
| 25 | 4d259081 (TAT-QA) | 121.5 | list | Average vs list |
| 26 | dc5e217a (TAT-QA) | 4227.5 | 4411 | Average vs single |
| 27 | 7cd3aedf (TAT-QA) | 3680 | 4044 | Average vs single |
| 28 | 22e20f25 (TAT-QA) | 547.5 | 367 | Average change wrong |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Temporal average errors | 7 | 25% |
| Wrong formula/calculation | 6 | 21% |
| Extraction failure (uncertain) | 5 | 18% |
| Format/list vs value | 4 | 14% |
| Scale/unit error | 2 | 7% |
| Off by N | 2 | 7% |
| Sign error | 1 | 4% |
| Wrong value | 1 | 4% |

---

## Detailed Analysis

### Temporal Average Errors (7 samples) - TAT-QA Convention

These failures are due to TAT-QA's specific convention: **"2019 average X" = (X_2019 + X_2018) / 2**

GPT-4 doesn't know this convention and returns single year values instead of averaging.

#### dc5e217a - 2019 average free cash flow
- **Gold:** 4227.5 = (4411 + 4044) / 2
- **Predicted:** 4411 (only 2019 value)
- **Root Cause:** Missing TAT-QA temporal average convention

#### 7cd3aedf - 2018 average free cash flow
- **Gold:** 3680 = (4044 + 3316) / 2
- **Predicted:** 4044 (only 2018 value)
- **Root Cause:** Missing TAT-QA temporal average convention

#### 22e20f25 - Change in average free cash flow 2018 to 2019
- **Gold:** 547.5 = 4227.5 - 3680
- **Predicted:** 367 = 4411 - 4044 (change in single values)
- **Root Cause:** Change of averages requires 4 values

#### ecf25a96 - 2019 average amounts falling due
- **Gold:** 232328.5 = (243424 + 221233) / 2
- **Predicted:** 243424 (only 2019)
- **Root Cause:** Missing temporal average

#### a0414f81 - Average defined contribution expense
- **Gold:** 172 = (166 + 178) / 2
- **Predicted:** 166 (only 2019)
- **Root Cause:** Missing temporal average

#### bf7abd62 - Average defined benefit expense
- **Gold:** 50.5 = (57 + 44) / 2
- **Predicted:** 57 (only 2019)
- **Root Cause:** Missing temporal average

#### 4d259081 - Average of difference
- **Gold:** 121.5
- **Predicted:** Listed values instead of computing
- **Root Cause:** Multi-step average calculation

---

### Extraction Failures (5 samples)

#### ABMD/2006/page_75.pdf-1
- **Gold:** 25%
- **Predicted:** uncertain
- **Root Cause:** Could not locate values in evidence

#### AMAT/2013/page_18.pdf-2
- **Gold:** 7.22
- **Predicted:** uncertain
- **Root Cause:** Could not locate values in evidence

#### 191c3926 (TAT-QA)
- **Gold:** 64509
- **Predicted:** uncertain
- **Root Cause:** Complex table navigation

#### af49c57c (TAT-QA)
- **Gold:** 12.47
- **Predicted:** uncertain
- **Root Cause:** Complex calculation requirement

#### 3502f875 (TAT-QA)
- **Gold:** -168630
- **Predicted:** uncertain
- **Root Cause:** Could not extract required values

---

### Wrong Formula/Calculation (6 samples)

#### SLB/2012/page_44.pdf-2
- **Gold:** 25.9%
- **Predicted:** 16.67
- **Analysis:** Used wrong values or formula for percentage change

#### FBHS/2017/page_23.pdf-1
- **Gold:** 1320.8
- **Predicted:** 1373.658
- **Analysis:** Used 26% instead of 25% for international sales calculation

#### FRT/2005/page_117.pdf-2
- **Gold:** 11.49%
- **Predicted:** $68,412,000
- **Analysis:** Returned absolute value instead of percentage

#### 94ef7822 (TAT-QA)
- **Gold:** 56
- **Predicted:** 44
- **Analysis:** Wrong values from table

#### a983501d (TAT-QA)
- **Gold:** 3728
- **Predicted:** 2820
- **Analysis:** Wrong formula for EBITDA difference calculation

#### df12359b (TAT-QA)
- **Gold:** 13182
- **Predicted:** 13026
- **Analysis:** Close but wrong calculation

---

### Format/List vs Value (4 samples)

#### PNC/2013/page_62.pdf-2
- **Gold:** 3576 (sum)
- **Predicted:** "2013: 1356 million, 2012: 2220 million"
- **Root Cause:** Listed values instead of summing

#### 889488f7 (TAT-QA)
- **Gold:** 2053.5 (average)
- **Predicted:** "2025 in 2018, 2082 in 2019"
- **Root Cause:** Listed values instead of averaging

#### 1238d807 (TAT-QA)
- **Gold:** -19411
- **Predicted:** "$19,411 decrease"
- **Root Cause:** Text format instead of numeric

#### 34144864 (TAT-QA)
- **Gold:** -3
- **Predicted:** "decrease"
- **Root Cause:** Qualitative instead of quantitative answer

---

### Sign Errors (1 sample)

#### d7bcc322 (TAT-QA)
- **Gold:** -1903
- **Predicted:** "$1,903"
- **Root Cause:** Lost negative sign in output

---

### Scale/Unit Errors (2 samples)

#### ABMD/2009/page_56.pdf-1
- **Gold:** 40294
- **Predicted:** 20.147
- **Root Cause:** Sum vs single value, also scale error

#### e151e953 (TAT-QA)
- **Gold:** 18.34
- **Predicted:** 0.1834
- **Root Cause:** Missing 100x multiplier for percentage

---

### Off by N (2 samples)

#### ALXN/2007/page_104.pdf-1
- **Gold:** 4441 (5-year average)
- **Predicted:** 3441
- **Analysis:** Off by ~1000, likely missed one value in average

#### a9ecc9dd (TAT-QA)
- **Gold:** 58.43
- **Predicted:** 26.75%
- **Analysis:** Completely wrong formula

---

## Key Findings

1. **TAT-QA temporal average convention is the #1 issue** - 7/28 failures (25%) are due to GPT-4 not knowing that "2019 average X" means (X_2019 + X_2018)/2

2. **FinQA vs TAT-QA breakdown:**
   - FinQA failures: 8/50 (84% accuracy on FinQA)
   - TAT-QA failures: 20/50 (60% accuracy on TAT-QA)

3. **Only 1 sign error** - GPT-4 handles signs naturally without explicit guidance

4. **5 "uncertain" responses** - GPT-4 admits when it can't extract values rather than hallucinating

---

## Comparison: FinQA-only vs Full F1

| Metric | FinQA-only (prev run) | Full F1 (this run) |
|--------|----------------------|-------------------|
| Total samples | 100 FinQA | 50 FinQA + 50 TAT-QA |
| Accuracy | 87% | 72% |
| FinQA accuracy | 87% | 84% |
| TAT-QA accuracy | N/A | 60% |

**TAT-QA is significantly harder** due to:
- Temporal average convention
- More complex multi-step calculations
- Different table structures

---

## Recommendations

1. **Teach TAT-QA temporal average convention** - Add explicit instruction: "For TAT-QA questions, '2019 average X' = (X_2019 + X_2018) / 2"

2. **Sum vs list disambiguation** - Clarify when to sum vs list values

3. **Format guidance** - Ensure numeric output format

4. **Scale verification** - Add sanity checks for percentage scale
