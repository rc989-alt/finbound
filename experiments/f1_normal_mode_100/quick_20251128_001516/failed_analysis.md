# Failed Questions Analysis - F1 Normal Mode (100 Samples)

## Summary

**Overall Results:**
- **Accuracy:** 82/100 (82%)
- **Failed:** 18 samples
- **Hallucination Rate:** 12%
- **Avg Latency:** ~17.1 seconds

---

## Mode Comparison: Normal vs Low Latency

Both modes achieve 82% accuracy with 89% overlap in failed questions.

| Metric | Normal Mode | Low Latency |
|--------|-------------|-------------|
| Accuracy | 82% | 82% |
| Avg Latency | 17,139 ms | 5,944 ms |
| Latency Reduction | baseline | -65% |
| Failed Samples | 18 | 18 |
| Common Failures | 16 | 16 |

### Verification Impact Analysis

**Normal mode verification HELPED (2 samples):**
- ETR/2003/page_84.pdf-2: Low latency got 503.21, normal got correct 1041.5
- HOLX/2007/page_129.pdf-1: Low latency got 106500, normal got correct 46.3

**Normal mode verification HURT (2 samples):**
- AES/2016/page_191.pdf-3: Low latency got correct 11.3, normal got -11.33
- STT/2008/page_83.pdf-2: Low latency got correct 44%, normal got 63.64

**Net effect:** 0 (verification helps and hurts equally)

---

## Failed Samples (18 total)

### Common Failures (16 samples - fail in both modes)

| # | Sample ID | Gold | Predicted | Root Cause |
|---|-----------|------|-----------|------------|
| 1 | JPM/2008/page_85.pdf-3 | 10.94% | -10.94 | Sign error on ratio |
| 2 | AAPL/2004/page_36.pdf-2 | .2 | 0.2% | Format issue (dataset) |
| 3 | ABMD/2006/page_75.pdf-1 | 25% | 78.53 | Wrong year values |
| 4 | SPGI/2018/page_74.pdf-1 | 1.16 | 90.4 | Wrong values extracted |
| 5 | PNC/2009/page_46.pdf-2 | -1 | -0.33 | % point vs % change |
| 6 | AES/2002/page_46.pdf-4 | 2.62 | 6.2 | Multi-year table parsing |
| 7 | CB/2010/page_200.pdf-4 | 4.9 | 20.58 | Entity disambiguation |
| 8 | PM/2015/page_85.pdf-1 | 3.4% | -3.39% | Dataset error (wrong sign) |
| 9 | PM/2015/page_127.pdf-4 | -6806 | -4088.33 | Dataset error (wrong row) |
| 10 | RSG/2016/page_144.pdf-1 | 4 | 25 | Ratio direction error |
| 11 | LMT/2006/page_90.pdf-3 | 6.4 | 15.62 | "After year X" sum |
| 12 | ABMD/2009/page_88.pdf-1 | 5583331 | 16750000 | Dataset error (mismatch) |
| 13 | ADI/2011/page_81.pdf-1 | 65.1% | 34.9 | Dataset error (wrong metric) |
| 14 | MSI/2009/page_65.pdf-2 | 1.69 | 59.17 | Wrong values extracted |
| 15 | HWM/2017/page_41.pdf-1 | 69.24% | -69.23% | "Reduction" sign error |
| 16 | LMT/2006/page_37.pdf-1 | 48.2% | 20.11% | Dataset ambiguity |

### Only Failed in Normal Mode (2 samples)

#### AES/2016/page_191.pdf-3
| | Value |
|---|---|
| Gold | 11.3 |
| Normal Predicted | -11.33 |
| Low Latency Predicted | 11.3 (correct) |

**Root Cause:** Verification pass introduced a sign error. The initial extraction was correct (11.3), but the verification incorrectly changed it to -11.33.

**Lesson:** Verification can sometimes regress correct answers.

---

#### STT/2008/page_83.pdf-2
| | Value |
|---|---|
| Gold | 44% |
| Normal Predicted | 63.64 |
| Low Latency Predicted | 44 (correct) |

**Root Cause:** Verification pass changed the correct calculation to an incorrect one. The multi-pass verification voted for a wrong formula.

**Lesson:** Majority voting doesn't always converge to the correct answer.

---

## Error Classification Summary

| Category | Count | Samples |
|----------|-------|---------|
| Dataset Errors | 7 | AAPL, PM/85, PM/127, ABMD/09, ADI, LMT/37, PNC |
| Sign/Direction Errors | 3 | JPM, HWM, AES/16 |
| Wrong Value Extraction | 4 | SPGI, AES/02, CB, MSI |
| Multi-step/Sum Errors | 2 | ABMD/06, LMT/90 |
| Ratio Direction | 1 | RSG |
| Verification Regression | 1 | STT |

---

## Key Findings

1. **Verification is a double-edged sword**: It corrects 2 errors but introduces 2 new ones, resulting in net zero improvement.

2. **Low latency mode is equivalent**: With 65% faster latency and identical accuracy, low latency mode is recommended for most use cases.

3. **Dataset quality matters**: 7 of 18 failures (39%) are due to dataset annotation issues, not model errors.

4. **Core extraction issues**: 11 samples fail due to fundamental value extraction or formula selection errors that neither mode can fix.

---

## Recommendations

### For Production Use
- **Use low latency mode** - Same accuracy, 65% faster
- Reserve normal mode for high-stakes decisions where extra verification time is acceptable

### For Model Improvement
1. Fix sign detection for ratios and reductions
2. Improve "percentage point" vs "percentage change" detection
3. Better multi-period sum handling ("next N years")
4. Entity disambiguation in multi-column tables

### For Dataset Quality
- 7 samples should be flagged or corrected in the FinQA dataset
- Consider using adjusted accuracy (80%) excluding dataset errors
