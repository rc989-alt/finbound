# Failed Questions Analysis - GPT-4 Zero-Shot (F1_UPDATED v5)

**Dataset:** 50 FinQA + 50 TAT-QA = 100 samples
**Run Date:** 2024-11-28
**Experiment:** f1_updated_v5_gpt4_zeroshot
**Model:** GPT-4o

## Summary

**Overall Results:**
- **Accuracy:** 70/100 (70%)
- **Failed:** 30 samples
- **Avg Latency:** ~2,152 ms

**Comparison:**
- GPT-4 v5: 70/100 (70%) - this run
- FinBound v3: 83/100 (83%) - low-latency mode
- **FinBound is +13% more accurate than GPT-4**

---

## Failed Samples (30 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | ABMD/2009/page_56.pdf-1 | 40294 | 20.147 | Scale error (1000x) |
| 2 | SLB/2012/page_44.pdf-2 | 25.9% | 16.67 | Wrong calculation |
| 3 | FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.658 | Wrong calculation |
| 4 | FRT/2005/page_117.pdf-2 | 11.49% | 68312000 | Wrong interpretation |
| 5 | PNC/2013/page_62.pdf-2 | 3576 | "2013: 1356, 2012: 2220" | Sum vs list |
| 6 | ABMD/2006/page_75.pdf-1 | 25% | uncertain | No answer |
| 7 | AMAT/2013/page_18.pdf-2 | 7.22 | uncertain | No answer |
| 8 | 94ef7822 (TAT-QA) | 56 | 44 | Wrong calculation |
| 9 | a983501d (TAT-QA) | 3728 | 2820 | Wrong formula (multi-step) |
| 10 | 1238d807 (TAT-QA) | -19411 | "decrease of 19411" | Sign error |
| 11 | a9ecc9dd (TAT-QA) | 58.43 | 26.74% | Wrong formula |
| 12 | 889488f7 (TAT-QA) | 2053.5 | "2025/2082" | List vs average |
| 13 | 191c3926 (TAT-QA) | 64509 | uncertain | No answer |
| 14 | ecf25a96 (TAT-QA) | 232328.5 | 243424 | Wrong formula (average) |
| 15 | af49c57c (TAT-QA) | 12.47 | Uncertain | Wrong interpretation |
| 16 | 34144864 (TAT-QA) | -3 | "decrease" | Qualitative vs quantitative |
| 17 | d7bcc322 (TAT-QA) | -1903 | $1,903 | Sign error |
| 18 | 73693527 (TAT-QA) | 0.95 | uncertain | No answer |
| 19 | e151e953 (TAT-QA) | 18.34 | 0.1834 | Scale error (100x) |
| 20 | 3502f875 (TAT-QA) | -168630 | uncertain | No answer |
| 21 | df12359b (TAT-QA) | 13182 | 13026 | Wrong calculation |
| 22 | e302a7ec (TAT-QA) | 12 | 15 years | Off by N / wrong interpretation |
| 23 | 8cb754f8 (TAT-QA) | 0.5 | 31.25% | Percentage vs points |
| 24 | a0414f81 (TAT-QA) | 172 | 166 | Wrong values (average) |
| 25 | bf7abd62 (TAT-QA) | 50.5 | 57 | Wrong values (average) |
| 26 | 4d259081 (TAT-QA) | 121.5 | "166/57" | List vs difference |
| 27 | dc5e217a (TAT-QA) | 4227.5 | 4411 | Wrong formula (temporal avg) |
| 28 | 7cd3aedf (TAT-QA) | 3680 | 4044 | Wrong formula (temporal avg) |
| 29 | 22e20f25 (TAT-QA) | 547.5 | 367 | Wrong formula (temporal avg) |
| 30 | 2067daa1 (TAT-QA) | 88.45 | "88.45" but parsed incorrectly | Format issue |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Wrong calculation/formula | 10 | 33.3% |
| No answer (uncertain) | 5 | 16.7% |
| Temporal average errors | 3 | 10.0% |
| Sign errors | 2 | 6.7% |
| Scale errors | 2 | 6.7% |
| List vs aggregate | 3 | 10.0% |
| Wrong interpretation | 3 | 10.0% |
| Format/parsing issues | 2 | 6.7% |

---

## Detailed Analysis by Error Type

### No Answer / Uncertain (5 samples)

GPT-4 returned "uncertain" for questions it couldn't confidently answer:

#### ABMD/2006/page_75.pdf-1 (FinQA)
- **Question:** "what is the decline from current future minimum lease payments and the following years expected obligation?"
- **Gold:** 25%
- **Predicted:** "uncertain"
- **Analysis:** GPT-4 couldn't determine the calculation needed.

#### AMAT/2013/page_18.pdf-2 (FinQA)
- **Question:** Complex multi-step calculation
- **Gold:** 7.22
- **Predicted:** "uncertain"

#### 191c3926 (TAT-QA)
- **Gold:** 64509
- **Predicted:** "uncertain"

#### 73693527 (TAT-QA)
- **Gold:** 0.95
- **Predicted:** "uncertain"

#### 3502f875 (TAT-QA)
- **Question:** "What is the COGS for 2019?"
- **Gold:** -168630
- **Predicted:** "uncertain"
- **Analysis:** Required computing COGS from other values, GPT-4 couldn't derive it.

---

### Sign Errors (2 samples)

#### 1238d807 (TAT-QA)
- **Question:** Change in statutory federal income tax from 2018 to 2019
- **Gold:** -19411
- **Predicted:** "The decrease... was $19,411"
- **Analysis:** Identified the magnitude correctly but expressed it qualitatively with no sign.

#### d7bcc322 (TAT-QA)
- **Question:** "What is the difference between Workforce reduction and Facility costs?"
- **Gold:** -1903
- **Derivation:** `1,046 - 2,949 = -1,903`
- **Predicted:** "$1,903"
- **Analysis:** Computed absolute difference, dropped sign.

---

### Temporal Average Errors (3 samples)

These questions follow TAT-QA convention where "2019 average X" = (X_2019 + X_2018) / 2.

#### dc5e217a (TAT-QA)
- **Question:** "What is the average free cash flow for 2019?"
- **Gold:** 4227.5 = (4,411 + 4,044) / 2
- **Predicted:** 4,411 (just 2019 value)
- **Analysis:** Didn't understand "2019 average" means (2019 + 2018) / 2

#### 7cd3aedf (TAT-QA)
- **Question:** "What is the average free cash flow for 2018?"
- **Gold:** 3680 = (4,044 + 3,316) / 2
- **Predicted:** 4,044 (just 2018 value)

#### 22e20f25 (TAT-QA)
- **Question:** "What is the change between 2018 and 2019 average free cash flow?"
- **Gold:** 547.5 = 4227.5 - 3680
- **Predicted:** 367 = 4,411 - 4,044 (simple year-to-year change)
- **Analysis:** Used simple change instead of change in temporal averages.

---

### Scale Errors (2 samples)

#### ABMD/2009/page_56.pdf-1 (FinQA)
- **Gold:** 40294 (in $000s)
- **Predicted:** 20.147 (in millions)
- **Analysis:** Read value as $20,147K but should have doubled/summed.

#### e151e953 (TAT-QA)
- **Gold:** 18.34 (percentage)
- **Predicted:** 0.1834 (decimal)
- **Analysis:** Correct calculation but wrong scale (should be * 100).

---

### Sum vs List / Aggregate Errors (3 samples)

#### PNC/2013/page_62.pdf-2 (FinQA)
- **Question:** "in millions what was total residential mortgages balance for 2013 and 2012?"
- **Gold:** 3576 = 1356 + 2220
- **Predicted:** "2013: 1356 million, 2012: 2220 million"
- **Analysis:** Listed both values instead of summing them. The word "total" should trigger addition.

#### 889488f7 (TAT-QA)
- **Question:** "What was the average interest expenses?"
- **Gold:** 2053.5 = (2025 + 2082) / 2
- **Predicted:** Listed both values
- **Analysis:** Didn't compute the average.

#### 4d259081 (TAT-QA)
- **Question:** What is the difference between defined contribution and defined benefit schemes?
- **Gold:** 121.5 = 166 - 57 (or similar)
- **Predicted:** Listed both values
- **Analysis:** Didn't compute the difference.

---

### Percentage vs Points Error (1 sample)

#### 8cb754f8 (TAT-QA)
- **Question:** "How many percent did the weighted average hedged rate change by from 2018 to 2019?"
- **Gold:** 0.5 (percentage points: 2.10% - 1.60% = 0.5 pp)
- **Predicted:** 31.25% (percentage change: (2.10 - 1.60) / 1.60)
- **Analysis:** Confused "change by" (absolute difference) with "percentage change" (relative).

---

### Wrong Calculation / Formula (10 samples)

Various calculation errors where GPT-4 used wrong values or formulas:

- **SLB/2012/page_44.pdf-2:** Expected temporal average percentage change
- **FBHS/2017/page_23.pdf-1:** Wrong percentage extraction
- **94ef7822:** Off by 12 (got 44, expected 56)
- **a983501d:** Multi-step average calculation error
- **a9ecc9dd:** Wrong denominator used
- **df12359b:** Close but wrong (13026 vs 13182)
- **a0414f81:** Got 166 instead of average 172
- **bf7abd62:** Got 57 instead of average 50.5

---

## FinQA vs TAT-QA Breakdown

| Dataset | Correct | Failed | Accuracy |
|---------|---------|--------|----------|
| FinQA (50) | 43 | 7 | 86% |
| TAT-QA (50) | 27 | 23 | 54% |
| **Total** | **70** | **30** | **70%** |

**Key Insight:** GPT-4 performs much better on FinQA (86%) than TAT-QA (54%). TAT-QA's temporal average convention is particularly challenging.

---

## Comparison: GPT-4 vs FinBound on Overlapping Failures

Questions that **both** GPT-4 and FinBound failed:
- PNC/2013/page_62.pdf-2 (sum vs list)
- ABMD/2006/page_75.pdf-1 (complex formula)
- a983501d (multi-step average)
- a9ecc9dd (wrong formula)
- af49c57c (wrong interpretation)
- d7bcc322 (sign error)
- 3502f875 (COGS calculation)
- 8cb754f8 (percentage vs points)
- 22e20f25 (temporal average change)

Questions **GPT-4 failed but FinBound got correct:**
- Many temporal average questions
- Scale/format handling
- Sign-sensitive calculations

Questions **FinBound failed but GPT-4 got correct:**
- Some lookup questions
- Simple calculations that FinBound over-complicated

---

## Recommendations

1. **Temporal Average Convention**: GPT-4 doesn't understand TAT-QA's "2019 average" = (2019 + 2018) / 2 convention. Need explicit few-shot examples or prompt engineering.

2. **Sum vs List Disambiguation**: Both GPT-4 and FinBound struggle with "total X for Y and Z" - unclear if sum or list is expected.

3. **Sign Handling**: GPT-4 often describes direction ("increase/decrease") instead of returning signed numbers.

4. **Percentage vs Points**: Need clearer distinction between "percentage change" and "change in percentage points."

5. **Scale Consistency**: Ensure consistent units in output (percentage as 25 vs 0.25, thousands vs millions).
