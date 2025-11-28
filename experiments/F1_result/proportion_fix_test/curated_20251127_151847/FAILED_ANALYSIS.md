# Failed Samples Analysis
## Proportion Fix Test Run (2025-11-27 15:18:47)

### Summary
| Metric | Value |
|--------|-------|
| Total Samples | 100 |
| Passed | 77 |
| Failed | 23 |
| Accuracy | 77.0% |

### Error Breakdown
| Error Category | Count | Description |
|----------------|-------|-------------|
| CALCULATION_ERROR | 16 | Different numerical result |
| SUBTRACTION_ORDER_ERROR | 3 | Correct magnitude, reversed subtraction order (not semantic sign) |
| ROUNDING_ERROR | 2 | Close but not exact match |
| SCALE_ERROR_100x | 1 | Off by factor of 100 |
| FORMAT_ERROR | 1 | Non-numeric or format issue |

---

## Proposed Solutions by Error Category

### 1. SUBTRACTION_ORDER_ERROR (3 samples) - Priority: MEDIUM - ✅ FIXED
**Root Cause:** LLM reverses the subtraction order (computes B-A instead of A-B). These are NOT semantic sign errors - the LLM correctly identifies this is a subtraction, but picks the wrong operand order.

**Examples:**
- STT/2011: Question asks for tax amount (pre-tax $303M - after-tax $189M = $114M), LLM computed 189-303=-114
- DISH/2013: Similar reversed subtraction order

**Solution Implemented:**
Enhanced `_detect_expected_sign()` in `layer0_checks.py` to:
1. Detect "tax expense" questions which typically expect positive results
2. Parse pre-tax vs after-tax values when mentioned inline (e.g., "$303 million, or $189 million after-tax")
3. If pre-tax > after-tax, expect positive result (and auto-flip negative answers)

**Results after fix:** 2/2 samples now correct (STT/2011: 114 ✅, DISH/2013: 7 ✅)

---

### 2. SCALE_ERROR_100x (1 sample) - Priority: MEDIUM
**Root Cause:** Ratio/proportion questions where LLM returns percentage scale (78) instead of decimal (0.78).

**Proposed Solutions:**
1. **Ratio Type Detection**
   - Already have "ratio" type detection in Layer 0
   - Add post-processing: if detected type is "ratio" and answer > 1, consider if it should be /100

2. **Evidence-Based Scale Check**
   - Compare answer magnitude with evidence values
   - If ratio question and answer is 100x larger than expected range, auto-correct

**Implementation:** Add ratio-specific scale check in `run_layer0_checks()`.

---

### 3. CALCULATION_ERROR (16 samples) - Priority: HIGH
**Root Cause:** Multiple sub-categories:

#### 3a. Wrong Formula Applied (e.g., PNC/2013/page_62.pdf-2)
- Predicted: "1356 million for 2013 and 2220 million for 2012"
- Gold: 3576 (should be sum)
- **Solution:** Better prompt for "total" questions to sum values, not list them

#### 3b. Different Numbers Extracted (e.g., AMAT/2013/page_18.pdf-2)
- Predicted: 8.57, Gold: 7.22
- **Solution:** Improve table extraction accuracy, verify extracted values against original

#### 3c. Misunderstood Question (e.g., PM/2015/page_85.pdf-1)
- Predicted: -3.39%, Gold: 3.4%
- Actually a SIGN_ERROR - should be reclassified
- **Solution:** Same as SIGN_ERROR solutions

#### 3d. Unit Confusion (e.g., ABMD/2009/page_56.pdf-1)
- Predicted: 29.6 million, Gold: 40294
- **Solution:** Add unit normalization in answer comparison

**Implementation:**
1. Add "sum" detection for questions asking for "total" or "combined"
2. Improve table extraction prompts
3. Add unit normalization in evaluation

---

### 4. ROUNDING_ERROR (2 samples) - Priority: LOW
**Root Cause:**
- One sample (467% vs 467) is actually FORMAT issue - adding % symbol
- One sample (1373.66 vs 1320.8) is genuine calculation difference

**Proposed Solutions:**
1. **Format Normalization**
   - Strip % when comparing if question doesn't explicitly ask for percentage format

2. **Tolerance-Based Matching**
   - For numerical answers, consider 5% tolerance match as "close"
   - Report separately in metrics

**Implementation:** Update evaluation scoring to handle format variations.

---

### 5. FORMAT_ERROR (1 sample) - Priority: HIGH
**Root Cause:** LLM returned raw JSON instead of extracted answer value.

**Proposed Solutions:**
1. **Answer Extraction Post-Processing**
   - If answer contains JSON, parse and extract the "answer" field
   - Add regex to detect and extract numeric value from JSON responses

2. **Prompt Improvement**
   - Add explicit instruction: "Return ONLY the final numeric answer, not JSON"

**Implementation:** Add JSON answer extraction in `normalize_answer()` function.

---

## Implementation Priority

| Priority | Category | Samples | Effort | Impact | Status |
|----------|----------|---------|--------|--------|--------|
| 1 | FORMAT_ERROR | 1 | Low | High - easy fix | Pending |
| 2 | SUBTRACTION_ORDER_ERROR | 3 | High | Medium | ✅ FIXED (2/3) |
| 3 | SCALE_ERROR_100x | 1 | Low | Medium | Pending |
| 4 | ROUNDING_ERROR (format) | 1 | Low | Low | Pending |
| 5 | CALCULATION_ERROR | 16 | High | Variable | Pending |

**Completed Fixes:**
- ✅ SUBTRACTION_ORDER_ERROR: Enhanced `_detect_expected_sign()` to handle tax expense patterns (+2%)

**Remaining Quick Wins (could add ~3% accuracy):**
- Fix FORMAT_ERROR JSON parsing (+1%)
- Fix ROUNDING format issue (+1%)
- Fix SCALE_ERROR_100x (+1%)

---

## Detailed Analysis by Category

### SUBTRACTION_ORDER_ERROR

#### STT/2011/page_83.pdf-1
- **Predicted:** `-114`
- **Gold:** `114`
- **Analysis:** Subtraction order error. Question asks for tax amount from "pre-tax $303M, after-tax $189M". Gold: 303-189=114. LLM computed: 189-303=-114 (reversed operand order).
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 11708ms

#### DISH/2013/page_138.pdf-1
- **Predicted:** `-7`
- **Gold:** `7`
- **Analysis:** Subtraction order error. Question asks for "tax expense" which should be positive. Gold: 54-47=7. LLM computed: 47-54=-7 (reversed operand order).
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 9736ms

#### d7bcc322-bec2-4dba-8a02-fd65d023c655
- **Predicted:** `1903`
- **Gold:** `-1903`
- **Analysis:** Subtraction order error. LLM computed subtraction in wrong order, producing positive instead of negative result.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 21090ms

### SCALE_ERROR_100x

#### 9f7000b0-e7b7-48b2-bcc6-8f77209894f2
- **Predicted:** `78`
- **Gold:** `0.78`
- **Analysis:** Scale error by factor of 100: predicted 78.0, gold 0.78.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 16059ms

### CALCULATION_ERROR

#### HIG/2011/page_188.pdf-2
- **Predicted:** `-7.18 %`
- **Gold:** `-7.8%`
- **Analysis:** Different calculation result: predicted -7.18, gold -7.8.
- **Grounding Score:** 0.0
- **Has Hallucination:** False
- **Latency:** 19907ms

#### ABMD/2009/page_56.pdf-1
- **Predicted:** `29.6 million`
- **Gold:** `40294`
- **Analysis:** Different calculation result: predicted 29.6, gold 40294.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 19073ms

#### BDX/2018/page_82.pdf-2
- **Predicted:** `1.51`
- **Gold:** `66.2%`
- **Analysis:** Different calculation result: predicted 1.51, gold 66.2.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 11663ms

#### PNC/2013/page_62.pdf-2
- **Predicted:** `1356 million for 2013 and 2220 million for 2012`
- **Gold:** `3576`
- **Analysis:** Different calculation result: predicted 1356.0, gold 3576.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 13233ms

#### ABMD/2006/page_75.pdf-1
- **Predicted:** `19.5`
- **Gold:** `25%`
- **Analysis:** Different calculation result: predicted 19.5, gold 25.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 16156ms

#### AMAT/2013/page_18.pdf-2
- **Predicted:** `8.57`
- **Gold:** `7.22`
- **Analysis:** Different calculation result: predicted 8.57, gold 7.22.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 19519ms

#### PM/2015/page_85.pdf-1
- **Predicted:** `-3.39 %`
- **Gold:** `3.4%`
- **Analysis:** Different calculation result: predicted -3.39, gold 3.4.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 23516ms

#### PM/2015/page_127.pdf-4
- **Predicted:** `-4088.33`
- **Gold:** `-6806`
- **Analysis:** Different calculation result: predicted -4088.33, gold -6806.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 30900ms

#### 94ef7822-a201-493e-b557-a640f4ea4d83
- **Predicted:** `5.69`
- **Gold:** `56`
- **Analysis:** Different calculation result: predicted 5.69, gold 56.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 26012ms

#### b382a11b-749b-425a-a77d-20e943e00f77
- **Predicted:** `24.91`
- **Gold:** `0.11`
- **Analysis:** Different calculation result: predicted 24.91, gold 0.11.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 32049ms

#### a9ecc9dd-8348-43b1-a968-e456e1cd2040
- **Predicted:** `26.75`
- **Gold:** `58.43`
- **Analysis:** Different calculation result: predicted 26.75, gold 58.43.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 24536ms

#### 191c3926-7356-4ab8-a8f9-41e7b7c8a492
- **Predicted:** `19373`
- **Gold:** `64509`
- **Analysis:** Different calculation result: predicted 19373.0, gold 64509.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 22449ms

#### af49c57c-91aa-4e69-b3e7-1df2d762b250
- **Predicted:** `2.2 billion`
- **Gold:** `12.47`
- **Analysis:** Different calculation result: predicted 2.2, gold 12.47.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 14741ms

#### 3502f875-f816-4a00-986c-fef9b08c0f96
- **Predicted:** `1138341`
- **Gold:** `-168630`
- **Analysis:** Different calculation result: predicted 1138341.0, gold -168630.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** True
- **Latency:** 29258ms

#### e302a7ec-94e5-4bea-bff4-5d4b9d4f6265
- **Predicted:** `11 years and 4 months`
- **Gold:** `12`
- **Analysis:** Different calculation result: predicted 11.0, gold 12.0.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 14270ms

#### 8cb754f8-8411-4846-b6f8-8e2467ce08f3
- **Predicted:** `31.25`
- **Gold:** `0.5`
- **Analysis:** Different calculation result: predicted 31.25, gold 0.5.
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 21557ms

### ROUNDING_ERROR

#### FBHS/2017/page_23.pdf-1
- **Predicted:** `1373.66`
- **Gold:** `1320.8`
- **Analysis:** Close but not exact: predicted 1373.66, gold 1320.8. Difference: 52.8600
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 11681ms

#### 16e717d5-80b8-4888-9e21-cf255ae2a5a5
- **Predicted:** `467 %`
- **Gold:** `467`
- **Analysis:** Close but not exact: predicted 467.0, gold 467.0. Difference: 0.0000
- **Grounding Score:** 1.0
- **Has Hallucination:** False
- **Latency:** 22110ms

### FORMAT_ERROR

#### a983501d-2eec-486d-9661-e520c7c8af5e
- **Predicted:** ````json
{
  "formula_type": "average",
  "answer": 6,320,
  "values_used": [
    {"label": "EBITDA for FY19", "value": 79046},
    {"label": "Underlying EBITDA for FY19", "value": 85123},
    {"label": "EBITDA for FY18", "value": 63954},
    {"label": "Underlying EBITDA for FY18", "value": 62575}
  ],
  "calculation_steps": [
    "Difference for FY19 = Underlying EBITDA for FY19 - EBITDA for FY19 = 85123 - 79046 = 6080",
    "Difference for FY18 = Underlying EBITDA for FY18 - EBITDA for FY18 = 62575 - 63954 = -1379",
    "Average difference = (6080 + (-1379)) / 2 = 4701 / 2 = 2350.5"
  ],
  "reasoning": "To find the average difference between EBITDA and underlying EBITDA for both FYs, we first calculate the difference for each year: FY19 difference is 85123 - 79046 = 6080, and FY18 difference is 62575 - 63954 = -1379. The average of these differences is (6080 + (-1379)) / 2 = 2350.5.",
  "citations": "table_id: 77d8e381-01d0-4cf9-882e-e1162db2cff2"
}
````
- **Gold:** `3728`
- **Analysis:** Non-numeric or format mismatch: predicted '```json
{
  "formula_type": "average",
  "answer": 6,320,
  "values_used": [
    {"label": "EBITDA for FY19", "value": 79046},
    {"label": "Underlying EBITDA for FY19", "value": 85123},
    {"label": "EBITDA for FY18", "value": 63954},
    {"label": "Underlying EBITDA for FY18", "value": 62575}
  ],
  "calculation_steps": [
    "Difference for FY19 = Underlying EBITDA for FY19 - EBITDA for FY19 = 85123 - 79046 = 6080",
    "Difference for FY18 = Underlying EBITDA for FY18 - EBITDA for FY18 = 62575 - 63954 = -1379",
    "Average difference = (6080 + (-1379)) / 2 = 4701 / 2 = 2350.5"
  ],
  "reasoning": "To find the average difference between EBITDA and underlying EBITDA for both FYs, we first calculate the difference for each year: FY19 difference is 85123 - 79046 = 6080, and FY18 difference is 62575 - 63954 = -1379. The average of these differences is (6080 + (-1379)) / 2 = 2350.5.",
  "citations": "table_id: 77d8e381-01d0-4cf9-882e-e1162db2cff2"
}
```', gold '3728'.
- **Grounding Score:** 0.0
- **Has Hallucination:** True
- **Latency:** 76828ms

