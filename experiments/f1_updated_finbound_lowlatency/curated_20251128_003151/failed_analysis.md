# Failed Questions Analysis - FinBound Low-Latency (F1_UPDATED - 100 FinQA samples)

**Note:** This run used 100 FinQA-only samples, not the proper F1 benchmark (50 FinQA + 50 TAT-QA).

## Summary

**Overall Results:**
- **Accuracy:** 83/100 (83%)
- **Failed:** 17 samples
- **Hallucination Rate:** 11%
- **Avg Latency:** ~5,997 ms
- **Transparency Score:** 1.0
- **Auditability:** 1.0

---

## Failed Samples (17 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | JPM/2008/page_85.pdf-3 | 10.94% | -10.94 | Sign error |
| 2 | PNC/2013/page_62.pdf-2 | 3576 | "1356...2220..." | Sum vs list |
| 3 | ABMD/2006/page_75.pdf-1 | 25% | 85.26 | Wrong values |
| 4 | SPGI/2018/page_74.pdf-1 | 1.16 | 90.09 | Wrong formula |
| 5 | AES/2016/page_191.pdf-3 | 11.3 | -11.3 | Sign error |
| 6 | CB/2010/page_200.pdf-4 | 4.9 | 20.58 | Wrong calculation |
| 7 | ETR/2003/page_84.pdf-2 | 1041.5 | 503.21 | Partial sum |
| 8 | RSG/2016/page_144.pdf-1 | 4 | 25 | Wrong interpretation |
| 9 | LMT/2006/page_90.pdf-3 | 6.4 | 15.62 | Wrong years/values |
| 10 | MSI/2009/page_65.pdf-2 | 1.69 | 59.17 | Wrong formula |
| 11 | PM/2015/page_38.pdf-1 | 8.9% | -8.9% | Sign error |
| 12 | HWM/2017/page_41.pdf-1 | 69.24% | -69.24% | Sign error (reduction) |
| 13 | HOLX/2007/page_129.pdf-1 | 46.3 | 106500 | Wrong value (shares not price) |
| 14 | FRT/2005/page_117.pdf-1 | 92% | 21.18 | Wrong formula |
| 15 | ALXN/2007/page_104.pdf-1 | 4441 | 3441.4 | Off by 1000 |
| 16 | AMAT/2014/page_18.pdf-1 | 22.2% | 22.98% | Rounding error |
| 17 | IPG/2008/page_21.pdf-1 | 1229% | 1129 | Off by 100 |

---

## Error Classification

| Category | Count | Samples |
|----------|-------|---------|
| Sign error | 4 | JPM, AES/191, PM/38, HWM |
| Wrong values extracted | 5 | ABMD, CB, LMT/90, MSI, HOLX |
| Wrong formula/interpretation | 4 | SPGI, RSG, FRT, AMAT |
| Sum vs list error | 1 | PNC/62 |
| Partial sum/off by N | 3 | ETR/03, ALXN, IPG |

---

## Detailed Analysis

### Sign Errors (4 samples)

#### 1. JPM/2008/page_85.pdf-3
- **Gold:** 10.94%
- **Predicted:** -10.94
- **Analysis:** Model correctly computed the ratio but added a negative sign. CET1 ratio should always be positive.
- **Root Cause:** Sign inference error in ratio calculation.

#### 5. AES/2016/page_191.pdf-3
- **Gold:** 11.3
- **Predicted:** -11.3
- **Analysis:** The average settlements value is negative in the table, but the question asks for the average, which should preserve sign correctly. However, the absolute change should be positive.
- **Root Cause:** Sign handling in aggregation.

#### 11. PM/2015/page_38.pdf-1
- **Gold:** 8.9%
- **Predicted:** -8.9%
- **Analysis:** Question asks about change in discount rate. Model got magnitude correct but wrong sign.
- **Root Cause:** "Increase" vs "decrease" sign interpretation.

#### 12. HWM/2017/page_41.pdf-1
- **Gold:** 69.24%
- **Predicted:** -69.24%
- **Analysis:** Question asks about "reduction" in shares due to reverse stock split. Model treated reduction as negative.
- **Root Cause:** "Reduction" interpreted as negative change, but question asks for reduction amount (positive).

---

### Wrong Values Extracted (5 samples)

#### 3. ABMD/2006/page_75.pdf-1
- **Gold:** 25%
- **Predicted:** 85.26
- **Analysis:** Model extracted completely wrong values, possibly from wrong table or wrong rows.
- **Root Cause:** Table parsing error.

#### 6. CB/2010/page_200.pdf-4
- **Gold:** 4.9
- **Predicted:** 20.58
- **Analysis:** Expected ratio is ~4.9x but model computed ~20x. Likely extracted wrong denominator or numerator.
- **Root Cause:** Entity disambiguation - multiple similar columns in table.

#### 9. LMT/2006/page_90.pdf-3
- **Gold:** 6.4
- **Predicted:** 15.62
- **Analysis:** Question asks about pension benefits sum for specific years. Model extracted wrong year values.
- **Root Cause:** Multi-year table parsing, "after year X" interpretation.

#### 10. MSI/2009/page_65.pdf-2
- **Gold:** 1.69
- **Predicted:** 59.17
- **Analysis:** Expected ratio of segment sales. Model got completely different result.
- **Root Cause:** Wrong values extracted from table.

#### 13. HOLX/2007/page_129.pdf-1
- **Gold:** 46.3 (price per share)
- **Predicted:** 106500 (total value of shares)
- **Analysis:** Model returned total value ($106,500k) instead of per-share price ($106,500k / 2,300 shares = $46.3).
- **Root Cause:** Misunderstood question - wanted per-share value, not total.

---

### Wrong Formula/Interpretation (4 samples)

#### 4. SPGI/2018/page_74.pdf-1
- **Gold:** 1.16
- **Predicted:** 90.09
- **Analysis:** Expected ratio of pension assets 2018/2017 (1572/1739 ≈ 0.90 or inverse ≈ 1.11). Got 90.09 which is scaled wrong.
- **Root Cause:** Scale error or inverse ratio computed as percentage.

#### 8. RSG/2016/page_144.pdf-1
- **Gold:** 4
- **Predicted:** 25
- **Analysis:** Question about ratio of gallons hedged between years. Model computed wrong ratio.
- **Root Cause:** Direction of ratio (12M/3M = 4, not 3M*something = 25).

#### 14. FRT/2005/page_117.pdf-1
- **Gold:** 92%
- **Predicted:** 21.18
- **Analysis:** Growth rate question. Expected answer is ~92% but got ~21%.
- **Root Cause:** Wrong base year or wrong formula application.

#### 16. AMAT/2014/page_18.pdf-1
- **Gold:** 22.2%
- **Predicted:** 22.98%
- **Analysis:** Close but outside tolerance. Different calculation approach.
- **Root Cause:** Rounding or different value extraction.

---

### Sum vs List Error (1 sample)

#### 2. PNC/2013/page_62.pdf-2
- **Gold:** 3576 (sum)
- **Predicted:** "1356 million for 2013 and 2220 million for 2012"
- **Analysis:** Same issue as GPT-4. Model listed values instead of summing.
- **Root Cause:** Question interpretation ambiguity.

---

### Partial Sum / Off by N (3 samples)

#### 7. ETR/2003/page_84.pdf-2
- **Gold:** 1041.5 (sum of 2004-2006)
- **Predicted:** 503.21 (only 2004 value)
- **Analysis:** Question asks for sum of first 3 years, model only returned first year.
- **Root Cause:** Multi-year sum not fully aggregated.

#### 15. ALXN/2007/page_104.pdf-1
- **Gold:** 4441 (average of 5 years)
- **Predicted:** 3441.4
- **Analysis:** Off by ~1000. Likely missed one year's value in average calculation.
- **Root Cause:** Incomplete extraction for average calculation.

#### 17. IPG/2008/page_21.pdf-1
- **Gold:** 1229%
- **Predicted:** 1129
- **Analysis:** Off by exactly 100. Arithmetic error in multi-step calculation.
- **Root Cause:** Calculation error.

---

## Comparison: FinBound vs GPT-4 Zero-shot

| Metric | FinBound Low-latency | GPT-4 Zero-shot |
|--------|---------------------|-----------------|
| Accuracy | 83% | 87% |
| Failed | 17 | 13 |
| Hallucination Rate | 11% | 3% |
| Latency | ~6,000ms | ~2,150ms |
| Sign Errors | 4 | 0 |
| Extraction Failures ("uncertain") | 0 | 6 |

### Key Differences:
1. **FinBound never says "uncertain"** - always produces an answer (but sometimes wrong)
2. **GPT-4 has fewer sign errors** - FinBound struggles with sign-sensitive questions
3. **GPT-4 is faster** - 2.8x faster than FinBound low-latency
4. **FinBound has higher hallucination rate** - 11% vs 3%

### Overlap Analysis:
- **Both failed:** PNC/62, AMAT/14, IPG/08 (3 samples)
- **Only FinBound failed:** 14 samples (mostly sign errors and wrong values)
- **Only GPT-4 failed:** 10 samples (mostly "uncertain" responses)

---

## Recommendations

1. **Sign detection improvement:** 4/17 failures are sign errors. Add explicit sign verification for:
   - Ratio calculations (should be positive)
   - "Reduction" questions (magnitude, not direction)
   - Year-over-year changes (preserve direction)

2. **Multi-year aggregation:** Better handling of "sum of next N years" and "average of years X to Y" patterns.

3. **Value vs per-unit disambiguation:** When question mentions "per share" or similar, ensure division by count.

4. **Scale sanity checks:** Results >100x or <0.01x should trigger verification.

---

## Note

This analysis is for 100 FinQA-only samples. The proper F1 benchmark should include 50 FinQA + 50 TAT-QA samples for valid comparison.
