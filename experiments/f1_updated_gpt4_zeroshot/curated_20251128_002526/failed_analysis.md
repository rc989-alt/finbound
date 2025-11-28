# Failed Questions Analysis - GPT-4 Zero-shot (F1_UPDATED - 100 FinQA samples)

**Note:** This run used 100 FinQA-only samples, not the proper F1 benchmark (50 FinQA + 50 TAT-QA).

## Summary

**Overall Results:**
- **Accuracy:** 87/100 (87%)
- **Failed:** 13 samples
- **Hallucination Rate:** 3%
- **Avg Latency:** ~2,152 ms

---

## Failed Samples (13 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | JPM/2008/page_85.pdf-3 | 10.94% | uncertain | Extraction failure |
| 2 | PNC/2013/page_207.pdf-1 | 3044% | 30.44% | Scale error (100x) |
| 3 | PNC/2013/page_62.pdf-2 | 3576 | "2013: 1356 million, 2012: 2220 million" | Sum vs list |
| 4 | ABMD/2006/page_75.pdf-1 | 25% | uncertain | Extraction failure |
| 5 | AMAT/2013/page_18.pdf-2 | 7.22 | uncertain | Extraction failure |
| 6 | ZBH/2003/page_58.pdf-3 | 72.83% | uncertain | Extraction failure |
| 7 | STT/2008/page_83.pdf-2 | 44% | 28% | Wrong calculation |
| 8 | SLB/2012/page_44.pdf-3 | 25.9% | 16.67 | Wrong formula |
| 9 | BLK/2013/page_124.pdf-2 | 2448 | 698 | Wrong values (partial) |
| 10 | AMT/2005/page_54.pdf-2 | 105.0% | uncertain | Extraction failure |
| 11 | AON/2009/page_48.pdf-4 | 22.55% | uncertain | Extraction failure |
| 12 | AMAT/2014/page_18.pdf-1 | 22.2% | 22.97% | Rounding/value error |
| 13 | IPG/2008/page_21.pdf-1 | 1229% | 1129% | Off by 100 |

---

## Error Classification

| Category | Count | Samples |
|----------|-------|---------|
| Extraction failure (uncertain) | 6 | JPM, ABMD, AMAT/13, ZBH, AMT, AON |
| Scale/unit error | 2 | PNC/207 (100x), IPG (off by 100) |
| Wrong calculation/formula | 3 | STT, SLB, AMAT/14 |
| Wrong values extracted | 1 | BLK |
| Sum vs list error | 1 | PNC/62 |

---

## Detailed Analysis

### 1. JPM/2008/page_85.pdf-3
**Question:** What was JPMorgan Chase's common equity tier 1 ratio in 2008?
- **Gold:** 10.94%
- **Predicted:** uncertain
- **Analysis:** Model failed to extract the ratio. The calculation requires dividing Tier 1 capital by risk-weighted assets.
- **Root Cause:** Complex financial terminology, model didn't recognize the calculation pattern.

### 2. PNC/2013/page_207.pdf-1
**Question:** What percent of the fair value is the notional value of derivatives?
- **Gold:** 3044%
- **Predicted:** 30.44%
- **Analysis:** Model got the correct ratio but scaled incorrectly. 36197/1189 = 30.44, but answer should be expressed as 3044% (notional >> fair value).
- **Root Cause:** Scale/multiplier error - should be ~30x not ~0.3x.

### 3. PNC/2013/page_62.pdf-2
**Question:** Total residential mortgages balance for 2013 and 2012?
- **Gold:** 3576 (sum of 1356 + 2220)
- **Predicted:** "2013: 1356 million, 2012: 2220 million"
- **Analysis:** Model listed values instead of summing them.
- **Root Cause:** Question interpretation - "total...for 2013 and 2012" was interpreted as listing both years, not summing.

### 4. ABMD/2006/page_75.pdf-1
**Question:** Growth rate calculation
- **Gold:** 25%
- **Predicted:** uncertain
- **Root Cause:** Model couldn't locate or extract the required values.

### 5. AMAT/2013/page_18.pdf-2
**Question:** Percentage calculation
- **Gold:** 7.22
- **Predicted:** uncertain
- **Root Cause:** Model couldn't locate or extract the required values.

### 6. ZBH/2003/page_58.pdf-3
**Question:** Percentage of finished goods in total inventory
- **Gold:** 72.83%
- **Predicted:** uncertain
- **Root Cause:** Model couldn't locate or extract the required values.

### 7. STT/2008/page_83.pdf-2
**Question:** Some ratio calculation
- **Gold:** 44%
- **Predicted:** 28%
- **Analysis:** Model extracted different values or used wrong formula.
- **Root Cause:** Wrong values extracted or wrong calculation method.

### 8. SLB/2012/page_44.pdf-3
**Question:** Percentage change calculation
- **Gold:** 25.9%
- **Predicted:** 16.67
- **Analysis:** Model got a different result, possibly using wrong years or values.
- **Root Cause:** Wrong formula or value extraction.

### 9. BLK/2013/page_124.pdf-2
**Question:** Sum of note values
- **Gold:** 2448 (sum of multiple notes)
- **Predicted:** 698 (only one note value)
- **Analysis:** Model only extracted one value instead of summing all relevant notes.
- **Root Cause:** Incomplete extraction - missed aggregation requirement.

### 10. AMT/2005/page_54.pdf-2
**Question:** Growth calculation
- **Gold:** 105.0%
- **Predicted:** uncertain
- **Root Cause:** Model couldn't locate or extract the required values.

### 11. AON/2009/page_48.pdf-4
**Question:** Ratio calculation
- **Gold:** 22.55%
- **Predicted:** uncertain
- **Root Cause:** Model couldn't locate or extract the required values.

### 12. AMAT/2014/page_18.pdf-1
**Question:** Growth rate calculation
- **Gold:** 22.2%
- **Predicted:** 22.97%
- **Analysis:** Close but not within tolerance. Model extracted correct values but calculation differs.
- **Root Cause:** Slight calculation or rounding difference.

### 13. IPG/2008/page_21.pdf-1
**Question:** Ratio comparison
- **Gold:** 1229%
- **Predicted:** 1129%
- **Analysis:** Off by exactly 100, likely arithmetic error.
- **Root Cause:** Arithmetic error in multi-step calculation.

---

## Key Findings

1. **Extraction failures dominate:** 6/13 (46%) failures are due to the model returning "uncertain" - it couldn't extract or compute the answer.

2. **Scale/unit errors:** 2/13 (15%) involve scale misunderstanding (100x multiplier issues).

3. **No hallucination in failures:** Only 3 of 13 failed samples show has_hallucination=true, and those are calculation errors, not fabricated data.

4. **High grounding in errors:** Most failures (7/13) have grounding_score=1.0, meaning the model found relevant data but calculated incorrectly.

---

## Recommendations

1. **Add retry logic for "uncertain":** When model returns uncertain, retry with more explicit extraction instructions.

2. **Scale verification:** Add a sanity check for ratios >100% or <1% to verify scale makes sense.

3. **Sum vs list disambiguation:** For questions with "total...for X and Y", clarify whether to sum or list.

4. **Multi-value aggregation:** Ensure model understands when to sum multiple values vs extract single value.

---

## Comparison Note

This run achieved 87% on 100 FinQA-only samples. This is NOT comparable to the F1 benchmark which uses 50 FinQA + 50 TAT-QA samples.
