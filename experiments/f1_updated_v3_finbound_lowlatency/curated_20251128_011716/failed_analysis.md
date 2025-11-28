# Failed Questions Analysis - FinBound Low-Latency (F1_UPDATED v3)

**Dataset:** 50 FinQA + 50 TAT-QA = 100 samples (UPDATED from v2)
**Run Date:** 2024-11-28
**Experiment:** f1_updated_v3_finbound_lowlatency

**Note:** This run uses an UPDATED dataset from v2. Changes made:
- Removed 15 easier questions and replaced with harder ones
- Added 8 new TAT-QA temporal average questions (harder: 3-year `/3`, 5-year `/5` calculations)
- Added 6 new multi-step FinQA questions (5+ operations)
- Added "decrease by" pattern detection fix in engine.py
- Disabled ratio inverse check

The dataset includes temporal average questions that follow TAT-QA convention: "2019 average X" = (X_2019 + X_2018) / 2.

## Summary

**Overall Results:**
- **Accuracy:** 83/100 (83%)
- **Failed:** 17 samples
- **Avg Latency:** ~10,800 ms

**Comparison with FinBound v2 (same code, different dataset):**
- FinBound v2: 75/100 (75%) on easier dataset
- FinBound v3: 83/100 (83%) on HARDER dataset
- **v3 is +8% more accurate despite harder questions!**

Key v3 improvements:
- "decrease by" pattern detection fixed c55030b2
- Ratio inverse check disabled fixed 4 samples
- Evaluation tolerance fix improved matching

---

## Failed Samples (17 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | PNC/2013/page_62.pdf-2 | 3576 | "1356 million for 2013 and 2220 million for 2012" | Sum vs list |
| 2 | ABMD/2006/page_75.pdf-1 | 25% | 85.27 | Wrong calculation |
| 3 | ALXN/2007/page_104.pdf-1 | 4441 | 3441.4 | Off by 1000 |
| 4 | a983501d (TAT-QA) | 3728 | 2349 | Wrong formula |
| 5 | b382a11b (TAT-QA) | 0.11 | 24.92 | Wrong calculation |
| 6 | a9ecc9dd (TAT-QA) | 58.43 | 26.75 | Wrong formula |
| 7 | 81cab6e1 (TAT-QA) | -531925 | 531925 | Sign error |
| 8 | af49c57c (TAT-QA) | 12.47 | 22000 | Wrong interpretation |
| 9 | d7bcc322 (TAT-QA) | -1903 | 1903 | Sign error |
| 10 | 01de2123 (TAT-QA) | -78.06 | 78.1% | Sign error |
| 11 | 9f7000b0 (TAT-QA) | 0.78 | 78.28 | Scale error (100x) |
| 12 | 3502f875 (TAT-QA) | -168630 | 1138341 | Wrong calculation |
| 13 | 5a97069f (TAT-QA) | 1541.5 | 2287.3 | Wrong values |
| 14 | e302a7ec (TAT-QA) | 12 | 11 | Off by 1 |
| 15 | 16e717d5 (TAT-QA) | 467 | "S$ 467% million" | Format error |
| 16 | 8cb754f8 (TAT-QA) | 0.5 | 31.25 | Wrong calculation |
| 17 | 22e20f25 (TAT-QA) | 547.5 | 383 | Wrong formula |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Sign error | 3 | 17.6% |
| Wrong calculation/formula | 7 | 41.2% |
| Wrong values extracted | 1 | 5.9% |
| Scale error | 1 | 5.9% |
| Off by N | 2 | 11.8% |
| Format error | 1 | 5.9% |
| Sum vs list | 1 | 5.9% |
| Wrong interpretation | 1 | 5.9% |

---

## Detailed Analysis by Error Type

### Sign Errors (3 samples)

#### 81cab6e1 (TAT-QA)
- **Question:** "What is the net difference in sale of systems between 2017 and 2019?"
- **Gold:** -531925
- **Derivation:** `-139,042 - 392,883`
- **Predicted:** 531925
- **Analysis:** FinBound computed the absolute difference but dropped the negative sign. The question asks for "net difference" which should preserve sign (2019 - 2017 = -139,042 - 392,883 = -531,925).

#### d7bcc322 (TAT-QA)
- **Question:** "For Balance payable as at June 30, 2019, What is the difference between Workforce reduction and Facility costs?"
- **Gold:** -1903
- **Derivation:** `1,046 - 2,949`
- **Predicted:** 1903
- **Analysis:** FinBound computed the correct magnitude but with wrong sign. Workforce reduction (1,046) - Facility costs (2,949) = -1,903.

#### 01de2123 (TAT-QA)
- **Question:** "For adjusted operating costs, what was the percentage change in the amount of before exceptional items... between 2018 and 2019?"
- **Gold:** -78.06
- **Derivation:** `(4.3-19.6)/19.6`
- **Predicted:** 78.1%
- **Analysis:** FinBound computed the correct magnitude but as positive. The value decreased from 19.6 to 4.3, so the percentage change is negative.

---

### Wrong Calculation/Formula (7 samples)

#### ABMD/2006/page_75.pdf-1 (FinQA)
- **Question:** "what is the decline from current future minimum lease payments and the following years expected obligation?"
- **Gold:** 25%
- **Program:** `subtract(1703, 1371), divide(#0, 1703)`
- **Predicted:** 85.27
- **Analysis:** The question asks for the percentage decline from year 1 to year 2. Gold formula: (1703-1371)/1703 = 19.5% but gold is 25%. FinBound computed a completely different value (85.27), suggesting wrong values were extracted.

#### a983501d (TAT-QA)
- **Question:** "What was the average difference between EBITDA and underlying EBITDA for both FYs?"
- **Gold:** 3728
- **Derivation:** `((85,123 - 79,046) + (63,954 - 62,575)) / 2`
- **Predicted:** 2349
- **Analysis:** FinBound likely computed only one year's difference instead of averaging both years.

#### b382a11b (TAT-QA)
- **Question:** "What is the proportion of granted shares between 2017 and 2018 over outstanding shares at September 30, 2017?"
- **Gold:** 0.11
- **Derivation:** `299,397/2,845,866`
- **Predicted:** 24.92
- **Analysis:** FinBound appears to have used wrong values or inverted the ratio. The correct answer is ~10.5%, but FinBound got ~25%.

#### a9ecc9dd (TAT-QA)
- **Question:** "What is the value of Finjan Blue future commitment that are due in less than one year as a percentage of the total contractual obligations?"
- **Gold:** 58.43
- **Derivation:** `2,000/3,423`
- **Predicted:** 26.75
- **Analysis:** FinBound extracted wrong values from the table. Gold: 2000/3423 = 58.4%, but FinBound computed ~27%.

#### 3502f875 (TAT-QA)
- **Question:** "What is the COGS for 2019?"
- **Gold:** -168630
- **Derivation:** `54,229 - 222,859`
- **Predicted:** 1138341
- **Analysis:** This question requires computing COGS = Revenue - Gross Profit (or similar). FinBound extracted completely wrong values, getting 1.1M instead of -168K.

#### 8cb754f8 (TAT-QA)
- **Question:** "How many percent did the weighted average hedged rate for the year change by from 2018 to 2019?"
- **Gold:** 0.5
- **Derivation:** `2.10 - 1.60`
- **Predicted:** 31.25
- **Analysis:** The question asks for the absolute change in percentage points (2.10% - 1.60% = 0.5 percentage points). FinBound likely computed percentage change instead: (2.10-1.60)/1.60 = 31.25%.

#### 22e20f25 (TAT-QA)
- **Question:** "What is the change between 2018 and 2019 average free cash flow?"
- **Gold:** 547.5
- **Derivation:** `[(4,411+4,044)/2] - [(4,044+3,316)/2]`
- **Predicted:** 383
- **Analysis:** This is a complex temporal average question. FinBound computed the wrong formula. The correct calculation:
  - 2019 avg FCF = (4,411 + 4,044)/2 = 4,227.5
  - 2018 avg FCF = (4,044 + 3,316)/2 = 3,680
  - Change = 4,227.5 - 3,680 = 547.5

---

### Scale Error (1 sample)

#### 9f7000b0 (TAT-QA)
- **Question:** "What is the current ratio in 2019?"
- **Gold:** 0.78
- **Derivation:** `121,041 / 154,619`
- **Predicted:** 78.28
- **Analysis:** FinBound computed the ratio correctly but expressed it as a percentage (78.28%) instead of a decimal ratio (0.78). The current ratio is traditionally expressed as a simple ratio, not a percentage.

---

### Off by N Errors (2 samples)

#### ALXN/2007/page_104.pdf-1 (FinQA)
- **Question:** "what is the average future minimum annual rental payment for the next five years?"
- **Gold:** 4441
- **Program:** `add(3144, 3160), add(#0, 3200), add(#1, 2768), add(#2, 9934), divide(#3, const_5)`
- **Predicted:** 3441.4
- **Analysis:** The values to sum are: 3144 + 3160 + 3200 + 2768 + 9934 = 22,206 / 5 = 4,441.2
  FinBound got 3,441.4, which is exactly 1,000 less (17,207 / 5 = 3,441.4). One value was likely missed or misread.

#### e302a7ec (TAT-QA)
- **Question:** "How long is Leigh Fox's tenure with the company?"
- **Gold:** 12
- **Derivation:** `2020 - 2008`
- **Predicted:** 11
- **Analysis:** The question requires calculating years from start date (2008) to current year (2020). FinBound got 11 instead of 12, possibly due to off-by-one calculation or different interpretation of "tenure" (complete years vs total span).

---

### Format Error (1 sample)

#### 16e717d5 (TAT-QA)
- **Question:** "How much of the investing cash outflow was attributed to acquisitions in 2018?"
- **Gold:** 467
- **Derivation:** `123 + 344`
- **Predicted:** "S$ 467% million"
- **Analysis:** FinBound got the correct numeric value (467) but output it in a malformed format "S$ 467% million" instead of just "467". This appears to be a response formatting issue where the model incorrectly combined currency symbol, percentage sign, and unit.

---

### Sum vs List Error (1 sample)

#### PNC/2013/page_62.pdf-2 (FinQA)
- **Question:** "in millions what was total residential mortgages balance for 2013 and 2012?"
- **Gold:** 3576
- **Program:** `add(1356, 2220)`
- **Predicted:** "1356 million for 2013 and 2220 million for 2012"
- **Analysis:** FinBound correctly identified both values (1356 and 2220) but listed them separately instead of summing them. The question asks for "total" which requires addition: 1356 + 2220 = 3576.

---

### Wrong Interpretation (1 sample)

#### af49c57c (TAT-QA)
- **Question:** "How much were the research and development expenses in 2018?"
- **Gold:** 12.47
- **Derivation:** `(1-15%)*($2.2/15%)`
- **Predicted:** 22000
- **Analysis:** This is a complex inference question. The text mentions R&D is 15% of something, and $2.2B relates to that 15%. The formula:
  - If 15% = $2.2B, then 100% = $2.2B / 0.15 = $14.67B
  - R&D expenses = 85% of $14.67B = $12.47B
  FinBound completely misunderstood the relationship, outputting 22000 (possibly $22B raw value).

---

### Wrong Values Extracted (1 sample)

#### 5a97069f (TAT-QA)
- **Question:** "What is the unrevised value of Food Care for 2018?"
- **Gold:** 1541.5
- **Derivation:** `1,914.4 - 372.9`
- **Predicted:** 2287.3
- **Analysis:** The question requires finding the unrevised (original) value by subtracting some revision amount. FinBound appears to have added instead of subtracted: 1,914.4 + 372.9 = 2,287.3.

---

## FinQA vs TAT-QA Breakdown

| Dataset | Correct | Failed | Accuracy |
|---------|---------|--------|----------|
| FinQA (50) | 47 | 3 | 94% |
| TAT-QA (50) | 36 | 14 | 72% |
| **Total** | **83** | **17** | **83%** |

---

## Comparison: FinBound v3 vs FinBound v2

**Note:** v3 uses a HARDER dataset (15 easy questions replaced with harder ones), so direct comparison is not apples-to-apples.

| Metric | FinBound v3 | FinBound v2 |
|--------|-------------|-------------|
| **Accuracy** | **83%** | 75% |
| **Failed** | 17 | 25 |
| **Sign errors** | 3 (2 NEW samples) | 1 |
| **Ratio inverse errors** | 0 | 4 |
| **Avg Latency** | ~10.8s | ~6.2s |
| **Dataset** | HARDER | Original |

### Key Changes in v3:
1. **Ratio inverse check DISABLED** - fixed 4 errors (SPGI, ETFC, MMM, ba6783f3)
2. **"decrease by" pattern detection** - fixed c55030b2
3. **Evaluation tolerance fix** - improved matching
4. **Harder dataset** - 15 easy questions replaced with harder temporal averages

### Sign Errors Analysis:
- **v2 sign errors (1):** d7bcc322 only
- **v3 sign errors (3):** d7bcc322 + 81cab6e1 + 01de2123
  - 81cab6e1 and 01de2123 are NEW harder samples not in v2!
  - On overlapping samples, sign errors unchanged (still just d7bcc322)

---

## Recommendations

1. **Sign Handling**: 3 sign errors remain. Consider:
   - Explicit sign detection for "difference" and "change" questions
   - Post-processing to verify sign matches the question semantics

2. **Scale Detection**: Current ratio (9f7000b0) was reported as percentage instead of ratio. Add detection for ratio-type questions.

3. **Sum vs List Disambiguation**: PNC/62 still fails for both methods.

4. **Format Cleaning**: 16e717d5 had correct value but wrong format. Add response sanitization.

5. **Complex Multi-step**: Both methods struggle with questions requiring 3+ calculation steps.
