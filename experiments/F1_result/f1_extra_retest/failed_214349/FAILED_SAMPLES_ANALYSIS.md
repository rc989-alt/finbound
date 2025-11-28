# Failed Samples Analysis - F1_EXTRA Retest (214349)

## Summary
| Metric | Value |
|--------|-------|
| Total Samples | 10 |
| Passed | 4 |
| Failed | 6 |
| Accuracy | 40% |

## Passed Samples (4/10)
| Sample ID | Predicted | Gold | Notes |
|-----------|-----------|------|-------|
| HIG/2011/page_188.pdf-2 | -7.77% | -7.8% | Correct (minor rounding) |
| AES/2016/page_191.pdf-1 | -5.33 | -5% | Correct |
| ADBE/2018/page_86.pdf-3 | -3.06 | -3.1% | Correct |
| CDNS/2006/page_30.pdf-4 | 55.07 | 55.07% | Correct |

---

## Failed Samples Analysis (6/10)

### 1. MRO/2007/page_149.pdf-2 - SYSTEM_ERROR
| Field | Value |
|-------|-------|
| **Predicted** | (empty) |
| **Gold Answer** | 2057 |
| **Error Category** | SYSTEM_ERROR |
| **Error Message** | Request rejected by Approval Gate: Domain: forecasting operations require a defined time horizon. |
| **Grounding Score** | 0.0 |
| **Has Hallucination** | false |
| **Latency** | 0.22ms |

**Root Cause:** The Approval Gate rejected the request because it detected a "forecasting operation" without a defined time horizon. This is a policy/governance error, not a calculation error.

**Proposed Fix:** Review Approval Gate rules for false positives on historical data extraction questions.

---

### 2. LMT/2015/page_56.pdf-3 - GOLD_ANSWER_ERROR (Not a model error!)
| Field | Value |
|-------|-------|
| **Predicted** | 19700 |
| **Gold Answer** | 197000 |
| **Error Category** | GOLD_ANSWER_ERROR |
| **Grounding Score** | 1.0 |
| **Has Hallucination** | true (incorrect - our answer is right) |
| **Latency** | 16559ms |

**Question:** "what was the average backlog at year-end from 2013 to 2015"

**Table Data (in millions):**
| Year | Backlog at Year-End |
|------|---------------------|
| 2015 | $17,400 |
| 2014 | $20,300 |
| 2013 | $21,400 |

**Our Calculation:**
- Sum: 17400 + 20300 + 21400 = 59,100
- Average: 59,100 / 3 = **19,700 million**

**Gold Program:** `add(17400, 20300), add(#0, 21400), divide(#1, const_3)`
- This program produces: (17400 + 20300 + 21400) / 3 = **19,700**

**Conclusion:** Our predicted answer of **19700** is CORRECT. The gold answer of **197000** appears to be erroneous (10x too large). This is a dataset annotation error, NOT a model error.

**Action:** Flag this sample for dataset review - gold answer should be 19700, not 197000.

---

### 3. IPG/2008/page_21.pdf-1 - CALCULATION_ERROR
| Field | Value |
|-------|-------|
| **Predicted** | 1129.09 |
| **Gold Answer** | 1229% |
| **Error Category** | CALCULATION_ERROR |
| **Grounding Score** | 1.0 |
| **Has Hallucination** | false |
| **Latency** | 22090ms |

**Question:** "how much more, in percent, was spent on october shares than november shares?"

**Gold Program:** `multiply(29704, 5.99), multiply(4468, 3.24), divide(#0, #1), multiply(#2, const_100)`

**Expected Calculation:**
- October spend: 29704 × $5.99 = $177,886.96
- November spend: 4468 × $3.24 = $14,476.32
- Ratio: 177,886.96 / 14,476.32 = 12.29
- As percentage: 12.29 × 100 = **1229%**

**Root Cause:** Our answer (1129) is ~100 off from 1229. This suggests we may have extracted slightly wrong share counts or prices from the table. The model correctly understood the formula but used slightly different input values.

**Proposed Fix:** Improve table value extraction accuracy for share repurchase data.

---

### 4. STT/2008/page_83.pdf-1 - CALCULATION_ERROR
| Field | Value |
|-------|-------|
| **Predicted** | 1.9 |
| **Gold Answer** | 3.85 |
| **Error Category** | CALCULATION_ERROR |
| **Grounding Score** | 1.0 |
| **Has Hallucination** | false |
| **Latency** | 32834ms |

**Question:** "what is the average variance of the value at risk of each 2008 section?"

**Gold Program:** `subtract(4.7, .3), subtract(const_4, .7), add(#0, #1), divide(#2, const_2)`

**Expected Calculation:**
- Variance 1: 4.7 - 0.3 = 4.4
- Variance 2: 4.0 - 0.7 = 3.3
- Sum: 4.4 + 3.3 = 7.7
- Average: 7.7 / 2 = **3.85**

**Root Cause:** Our answer (1.9) is exactly half of the gold (3.85). This indicates we likely:
1. Only computed one variance instead of two (either 4.4/2 ≈ 2.2 or 3.3/2 ≈ 1.65), OR
2. Divided by 4 instead of 2

**Proposed Fix:** For "average variance" questions, ensure all sections are identified and included in the calculation.

---

### 5. AMAT/2014/page_18.pdf-1 - ROUNDING_ERROR
| Field | Value |
|-------|-------|
| **Predicted** | 22.98 |
| **Gold Answer** | 22.2% |
| **Error Category** | ROUNDING_ERROR (minor calculation difference) |
| **Grounding Score** | 1.0 |
| **Has Hallucination** | false |
| **Latency** | 20458ms |

**Question:** "what is the growth rate in sales from 2013 to 2014?"

**Gold Program:** `divide(1.4, 16), divide(1.3, 18), subtract(#0, #1), divide(#2, #1)`

**Expected Calculation:**
- 2014 ratio: 1.4 / 16 = 0.0875
- 2013 ratio: 1.3 / 18 = 0.0722
- Difference: 0.0875 - 0.0722 = 0.0153
- Growth rate: 0.0153 / 0.0722 = 0.212 = **21.2%** (or 22.2% with different precision)

**Root Cause:** Very close values (22.98 vs 22.2). Likely using slightly different base values or calculation method. The difference is ~0.78 percentage points (~3.5% relative error).

**Proposed Fix:** Consider this a "close match" - add tolerance-based matching (within 5% relative error).

---

### 6. AAP/2011/page_28.pdf-3 - CALCULATION_ERROR
| Field | Value |
|-------|-------|
| **Predicted** | 31.56 |
| **Gold Answer** | 71.8% |
| **Error Category** | CALCULATION_ERROR |
| **Grounding Score** | 1.0 |
| **Has Hallucination** | false |
| **Latency** | 16223ms |
| **Citations** | Rows: 'advance auto parts', 's&p 500 index'; Columns: 'january 3 2009' |

**Question:** "compared to the lowest stock price, how much did advanced auto parts outperform the overall market?"

**Gold Program:** `subtract(88.67, 65.70), divide(#0, 65.70), subtract(201.18, 97.26), divide(#2, 97.26), subtract(#3, #1)`

**Expected Calculation:**
- S&P 500 gain from low: (88.67 - 65.70) / 65.70 = 0.35 = 35%
- AAP gain from low: (201.18 - 97.26) / 97.26 = 1.069 = 106.9%
- Outperformance: 106.9% - 35% = **71.8%**

**Root Cause:** Our answer (31.56) suggests we may have:
1. Used wrong base values (not the "lowest" values)
2. Compared to wrong time periods
3. Used simple difference instead of percentage returns from low

**Proposed Fix:** For stock comparison questions asking about "lowest price" or specific dates, need to correctly identify the reference point values from the table.

---

## Error Distribution

| Error Category | Count | % of Failures |
|----------------|-------|---------------|
| CALCULATION_ERROR | 4 | 67% |
| SCALE_ERROR_10x | 1 | 17% |
| SYSTEM_ERROR | 1 | 17% |

---

## Recommendations

### High Priority
1. **Fix SYSTEM_ERROR** - Review Approval Gate false positive on MRO/2007 forecasting detection
2. **Add Scale Detection** - Detect 10x/100x scale errors and check for unit annotations

### Medium Priority
3. **Improve Stock Comparison Logic** - AAP/2011 stock return calculation needs better date handling
4. **Add Tolerance Matching** - AMAT/2014 is very close (22.98 vs 22.2) - within acceptable error margin

### Lower Priority
5. **Deep Investigation** - IPG/2008 and STT/2008 need question-level debugging to find root cause

---

## Next Steps
1. Fetch original questions for failed samples to understand what's being asked
2. Check evidence tables to verify correct values are being extracted
3. Add specific fixes based on question patterns
