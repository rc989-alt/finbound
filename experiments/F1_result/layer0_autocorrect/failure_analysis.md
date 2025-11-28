# FinBound F1 Failure Analysis

**Date:** 2025-11-27
**Dataset:** TAT-QA (100 samples)
**Accuracy:** 86% (86/100 correct)

## Results Summary

| Metric | FinBound | GPT-4 Zero-shot | Delta |
|--------|----------|-----------------|-------|
| **Accuracy** | **86%** | 67% | +19% |
| Hallucination Rate | 5% | ~15% | -10% |
| Avg Latency | 26,520ms | 2,398ms | +24s |

---

## Failed Questions (14)

### 1. SCALE ERROR - Ratio question
- **Question:** What is the ratio of IMFT's total assets to total liabilities in 2019?
- **Predicted:** 0.03
- **Gold:** 2.93
- **Analysis:** Model returned decimal (0.03) instead of ratio value (2.93). Likely inverted the ratio or misread values.

### 2. SCALE ERROR - Change in assets
- **Question:** What is the change of IMFT's total assets from 2018 to 2019?
- **Predicted:** -3.61
- **Gold:** -361
- **Analysis:** Off by factor of 100. Model may have divided by 100 thinking it was a percentage.

### 3. SIGN ERROR - Net profit difference
- **Question:** What was the difference in net profit between both FYs?
- **Predicted:** 16458
- **Gold:** -16458
- **Analysis:** Correct magnitude, wrong sign. "Difference between X and Y" vs "X - Y" ambiguity.

### 4. SCALE ERROR - Ratio question
- **Question:** What is the ratio of Data Center Group to Mobileye goodwill amount in 2019?
- **Predicted:** 69.5
- **Gold:** 0.7
- **Analysis:** Inverted ratio. Model computed Mobileye/DCG instead of DCG/Mobileye.

### 5. WRONG VALUE - Total expenses
- **Question:** What was the total expenses for Oracle in 2018?
- **Predicted:** 26119
- **Gold:** 35796
- **Analysis:** Extracted wrong row or missed some expense categories. Complex table with multiple expense lines.

### 6. SIGN ERROR - Average tax rate
- **Question:** What was the average State and local income tax rate, net of federal tax benefits between 2017-2019?
- **Predicted:** -3
- **Gold:** 3
- **Analysis:** Sign flip. Tax benefits may have been interpreted as negative.

### 7. WRONG VALUE - Change in averages
- **Question:** What is the change in the average total current tax expense between 2017-2018, and 2018-2019?
- **Predicted:** 5.69
- **Gold:** 56
- **Analysis:** Complex multi-step: needs (avg_2018-2019) - (avg_2017-2018). Model likely computed wrong intermediate values.

### 8. ROUNDING - Percentage change
- **Question:** What was the percentage change in the Domestic manufacturers deduction from 2017 to 2018?
- **Predicted:** -162.11%
- **Gold:** -162.15
- **Analysis:** Minor rounding difference (0.04%). Could be marked correct with tolerance.

### 9. SCALE ERROR - Net debt change
- **Question:** What was the change in net debt from 2018 to 2019?
- **Predicted:** 0.59
- **Gold:** 59.4
- **Analysis:** Off by factor of 100. Returned proportion instead of absolute change.

### 10. SCALE ERROR - Percentage change
- **Question:** What was the percentage change in net debt from 2018 to 2019?
- **Predicted:** 0.25
- **Gold:** 25.19
- **Analysis:** Off by factor of 100. Returned decimal (0.25) instead of percentage (25.19%).

### 11. SIGN ERROR - Average allowance
- **Question:** What is the average Specific allowance for credit losses?
- **Predicted:** -198.5
- **Gold:** 198.5
- **Analysis:** Sign flip. "Allowance for losses" is positive, but table may show as negative.

### 12. WRONG VALUE - Share price total
- **Question:** What is the total price of shares that were exercised or canceled between 2016 and 2017?
- **Predicted:** 2184414.7
- **Gold:** 981341.34
- **Analysis:** Incorrect aggregation. May have summed wrong columns or included extra rows.

### 13. MAGNITUDE ERROR - Outstanding shares
- **Question:** What is the price of outstanding shares on September 30, 2019?
- **Predicted:** 7
- **Gold:** 11808314
- **Analysis:** Model returned share count (7) instead of total price. Misunderstood question.

### 14. SIGN ERROR - Rights difference
- **Question:** What is the difference in the number of rights 'granted during the period' between 2018 and 2019?
- **Predicted:** -1226114
- **Gold:** 1226114
- **Analysis:** Correct magnitude, wrong sign. Computed 2018-2019 instead of 2019-2018.

---

## Error Type Distribution

| Error Type | Count | % of Failures |
|------------|-------|---------------|
| **SCALE ERROR (100x)** | 5 | 36% |
| **SIGN ERROR** | 4 | 29% |
| **WRONG VALUE EXTRACTION** | 4 | 29% |
| **MAGNITUDE ERROR** | 1 | 7% |

---

## Root Cause Analysis

### 1. Scale Errors (5 failures, 36%)
**Pattern:** Model returns decimal when integer expected or vice versa
- Ratio questions: 0.03 vs 2.93, 69.5 vs 0.7
- Change questions: 0.59 vs 59.4, 0.25 vs 25.19

**Root Causes:**
- Confusion between proportion (0-1) and percentage (0-100)
- Ratio inversion (A/B vs B/A)
- Missing scale indicator in question

**Fix:** Enhance Layer 0 scale detection for ratio questions

### 2. Sign Errors (4 failures, 29%)
**Pattern:** Correct magnitude but wrong direction

**Root Causes:**
- "difference between X and Y" ambiguity (X-Y vs Y-X)
- Negative values in tables interpreted inconsistently
- "Allowance for losses" sign confusion

**Fix:**
- Detect "difference between" pattern and clarify direction
- Check sign against table context (are values already negative?)

### 3. Wrong Value Extraction (4 failures, 29%)
**Pattern:** Completely incorrect values from table

**Root Causes:**
- Complex multi-step calculations (change in averages)
- Tables with similar-named rows
- Wrong column selection

**Fix:** Layer 2 focused extraction with explicit value verification

### 4. Magnitude Errors (1 failure, 7%)
**Pattern:** Off by many orders of magnitude

**Root Causes:**
- Question misinterpretation ("price of shares" vs "number of shares")

**Fix:** Better question parsing for "price" vs "count" vs "total"

---

## Recommendations for Layer 2

1. **Ratio Detection:** Add explicit ratio direction checking (A/B vs B/A)
2. **Sign Verification:** For "difference" questions, verify which direction was computed
3. **Scale Sanity:** Compare answer magnitude to evidence values
4. **Multi-step Verification:** For complex calculations, verify intermediate steps
5. **Question Clarification:** For ambiguous questions, extract key terms (numerator vs denominator)

---

## Questions to Investigate

The following questions need focused extraction in Layer 2:
- Ratio questions with potential inversion
- "Difference between" questions (sign ambiguity)
- "Change in average" questions (multi-step)
- Questions about "total price" vs "count"
