# F1_EXTRA Failed Samples Analysis

**Date**: 2025-11-27
**Rerun Timestamp**: 20251127_001940
**Original F1_EXTRA Accuracy**: 68% (68/100 samples)
**Failed Samples**: 32
**Rerun Recovery**: 16/32 (50%)
**Persistent Failures**: 16

## Summary

After rerunning the 32 failed F1_EXTRA samples with FinBound, 16 were recovered, leaving 16 samples as persistent failures. This analysis examines the remaining error patterns.

## Rerun Results by Dataset

| Dataset | Failed | Recovered | Still Failed | Recovery Rate |
|---------|--------|-----------|--------------|---------------|
| FinQA   | 18     | 8         | 10           | 44.4%         |
| TAT-QA  | 14     | 8         | 6            | 57.1%         |
| **Total** | **32** | **16**   | **16**       | **50%**       |

## Persistent Failure Analysis (16 samples)

### Error Type Distribution

| Error Type | Count | Percentage |
|------------|-------|------------|
| Calculation Error | 8 | 50.0% |
| Sign Error | 4 | 25.0% |
| Question Interpretation | 3 | 18.75% |
| System Error | 1 | 6.25% |

---

## Detailed Failure Analysis

### 1. Calculation Errors (8 samples)

**STT/2008/page_83.pdf-1** (FinQA)
- Question: "what is the average variance of the value at risk of each 2008 section?"
- Gold: `3.85`, Predicted: `1.45`
- Issue: Wrong values identified or incorrect averaging formula

**AAP/2011/page_28.pdf-3** (FinQA)
- Question: "compared to the lowest stock price, how much did advanced auto parts outperform the overall market?"
- Gold: `71.8%`, Predicted: `31.56`
- Issue: Wrong comparison points used; likely compared wrong data points

**LMT/2015/page_56.pdf-3** (FinQA)
- Question: "what was the average backlog at year-end from 2013 to 2015"
- Gold: `197000`, Predicted: `19700`
- Issue: **Scale error** - off by factor of 10 (likely missed "millions" scale)

**IPG/2008/page_21.pdf-1** (FinQA)
- Question: "how much more, in percent, was spent on october shares than november shares?"
- Gold: `1229%`, Predicted: `565.12`
- Issue: Wrong values extracted from table or calculation error

**AMAT/2014/page_18.pdf-1** (FinQA)
- Question: "what is the growth rate in sales from 2013 to 2014?"
- Gold: `22.2%`, Predicted: `22.97`
- Issue: Minor calculation variance (within ~0.8% tolerance but exceeds threshold)

**10e936a6-8d76-4bbe-b058-86f12091b447** (TAT-QA)
- Question: "What is the difference between the average investment income and average financing costs?"
- Gold: `2140`, Predicted: `2521`
- Issue: Incorrect values extracted for averaging

**aa4b7a98-1ec7-4bd8-a258-e928e92c9f75** (TAT-QA)
- Question: "What is the average of Net revenues by geographical region of shipment?"
- Gold: `9189`, Predicted: `3185.33`
- Issue: Model averaged wrong number of items (divided by 3 instead of summing correctly)

**abe51f5c-86e3-43cd-8e55-fd387d978321** (TAT-QA)
- Question: "What is the average Cost of sales?"
- Gold: `5579.33`, Predicted: `-5579.33`
- Issue: **Sign error** - Cost of sales should be positive, model added negative sign

---

### 2. Sign Errors (4 samples)

**CDNS/2006/page_30.pdf-4** (FinQA)
- Question: "what was the difference in percentage cumulative 5-year total return..."
- Gold: `55.07%`, Predicted: `-55.07`
- Issue: Reversed subtraction order (A-B instead of B-A)

**HIG/2011/page_188.pdf-2** (FinQA)
- Question: "in 2010 what was the percentage change in the deferred policy acquisition costs..."
- Gold: `-7.8%`, Predicted: `-7.19%`
- Issue: Calculation variance; close but not exact

**AES/2016/page_191.pdf-1** (FinQA)
- Question: "what was the percentage change in the unrecognized tax benefits from 2014 to 2015?"
- Gold: `-5%`, Predicted: `-5.33%`
- Issue: Minor variance beyond tolerance threshold

**ADBE/2018/page_86.pdf-3** (FinQA)
- Question: "what is the percentage change in total gross amount of unrecognized tax benefits from 2016 to 2017?"
- Gold: `-3.1%`, Predicted: `3.16%`
- Issue: **Sign flip** - model calculated increase instead of decrease

---

### 3. Question Interpretation Errors (3 samples)

**163f08ab-cfae-426a-9c03-4f84feba3bb6** (TAT-QA)
- Question: "What was the average Net cash used in financing activities between fiscal years 2017-2019?"
- Gold: `615`, Predicted: `-615`
- Issue: "Cash used" is typically negative in cash flow statements, but gold answer expects positive absolute value

**22e20f25-669a-46b9-8779-2768ba391955** (TAT-QA)
- Question: "What is the change between 2018 and 2019 average free cash flow?"
- Gold: `547.5`, Predicted: `383%`
- Issue: Model calculated **percentage change** instead of **absolute change**

**94ef7822-a201-493e-b557-a640f4ea4d83** (TAT-QA)
- Question: "What is the change in the average total current tax expense between 2017-2018, and 2018-2019?"
- Gold: `56`, Predicted: `2.1%`
- Issue: Model calculated **percentage change** instead of **absolute change**

---

### 4. System Errors (1 sample)

**MRO/2007/page_149.pdf-2** (FinQA)
- Gold: `2057`, Predicted: `null`
- Error: "Request rejected by Approval Gate: Domain: forecasting operations require a defined time horizon."
- Issue: System-level rejection, possibly due to question phrasing triggering safety filter

---

## Root Cause Analysis

### Primary Issues

1. **Absolute vs Percentage Change Confusion** (18.75% of failures)
   - Questions with "change" are interpreted as percentage change
   - Need explicit detection of "absolute change" vs "percentage change"
   - Keywords like "What is the change" should default to absolute value

2. **Sign Handling** (25% of failures)
   - Inconsistent handling of negative values
   - "Cash used" should be positive when asking for "how much"
   - Subtraction order matters: (new - old) vs (old - new)

3. **Scale/Unit Errors** (6.25% of failures)
   - Missing scale factors (millions, thousands)
   - Need better extraction of unit context from tables

4. **Value Extraction** (50% of failures)
   - Wrong row/column selection from tables
   - Averaging wrong number of items
   - Missing data points in summation

### Comparison with F1 Failures

| Issue Category | F1 Rate | F1_EXTRA Rate |
|----------------|---------|---------------|
| Calculation Error | 58.8% | 50.0% |
| Question Interpretation | 23.5% | 18.75% |
| Sign Error | - | 25.0% |
| System Error | - | 6.25% |

F1_EXTRA shows higher sign error rates, suggesting these samples have more ambiguous directionality in questions.

---

## Recommendations for Improvement

### 1. Question Classification Enhancement
- **Detect "change" vs "percentage change"** explicitly
  - "What is the change" -> absolute difference
  - "What is the percentage change" -> relative change
  - "How much did X change" -> absolute difference
- Add semantic parsing to identify expected output type

### 2. Sign Normalization
- When question asks "how much was used/spent", return positive value
- Explicitly track whether context implies increase or decrease
- Add verification step for sign consistency

### 3. Scale Detection
- Extract scale indicators from table headers and context
- Cross-validate magnitude against reasonable ranges
- Flag results that differ by powers of 10 from typical values

### 4. Enhanced Table Extraction
- Implement row/column disambiguation for multi-year tables
- Add confidence scoring for cell selection
- Cross-reference multiple cells to verify consistency

### 5. Verification Pipeline Improvements
- Add sanity checks:
  - Percentage changes should typically be -100% to +1000%
  - Average of N items should be between min and max values
  - Signs should be consistent with question semantics
- Implement retry with explicit step-by-step calculation

---

## Conclusion

The 16 persistent failures (16% of total F1_EXTRA) represent:
- **50% calculation errors** - wrong values extracted or computed
- **25% sign errors** - direction/polarity issues
- **18.75% interpretation errors** - absolute vs percentage confusion
- **6.25% system errors** - pipeline rejections

The 50% recovery rate on rerun suggests these samples are at the boundary of model capability. Key improvements should focus on:
1. Question type classification (absolute vs percentage)
2. Sign/polarity handling
3. Table cell extraction accuracy

These issues require targeted improvements to the FinBound pipeline, particularly in the question understanding and arithmetic verification stages.
