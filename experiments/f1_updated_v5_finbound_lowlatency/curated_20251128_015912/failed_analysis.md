# Failed Questions Analysis - FinBound v5 Low-Latency Mode

**Dataset:** 50 FinQA + 50 TAT-QA = 100 curated samples
**Run Date:** 2024-11-28
**Experiment:** f1_updated_v5_finbound_lowlatency
**Model:** GPT-4o (Low-Latency Mode)

## Summary

**Overall Results:**
- **Accuracy:** 78/100 (78%)
- **Failed:** 22 samples
- **Grounding Accuracy:** 89%
- **Hallucination Rate:** 10%
- **Avg Latency:** ~10,911 ms

**Comparison:**
- FinBound v5 Low-Latency: 78/100 (78%)
- GPT-4 Zero-shot: 70/100 (70%)
- **FinBound is +8% more accurate than GPT-4**

---

## Failed Samples (22 total)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | HOLX/2007/page_129.pdf-1 | 46.3 | 106500 | Wrong interpretation |
| 2 | PNC/2013/page_62.pdf-2 | 3576 | 1356, 2220 (list) | Sum vs list |
| 3 | ABMD/2006/page_75.pdf-1 | 25% | 78.52 | Wrong calculation |
| 4 | AMAT/2013/page_18.pdf-2 | 7.22 | 7.86 | Close but wrong |
| 5 | FRT/2005/page_117.pdf-1 | 92% | 21.18 | Wrong interpretation |
| 6 | ALXN/2007/page_104.pdf-1 | 4441 | 3441.4 | Off by ~1000 |
| 7 | ETFC/2014/page_26.pdf-4 | -67.33 | 67.33 | Sign error |
| 8 | TSCO/2017/page_31.pdf-2 | 73.4% | 74.46 | Close but wrong |
| 9 | a983501d (TAT-QA) | 3728 | 2349 | Wrong formula |
| 10 | b382a11b (TAT-QA) | 0.11 | 24.91 | Wrong calculation |
| 11 | a9ecc9dd (TAT-QA) | 58.43 | 26.75 | Wrong formula |
| 12 | 191c3926 (TAT-QA) | 64509 | 19373 | Wrong values |
| 13 | af49c57c (TAT-QA) | 12.47 | 2200 million | Wrong interpretation |
| 14 | d7bcc322 (TAT-QA) | -1903 | 1903 | Sign error |
| 15 | 9f7000b0 (TAT-QA) | 0.78 | 78.3 | Scale error (100x) |
| 16 | 3502f875 (TAT-QA) | -168630 | 1138341 | Wrong calculation |
| 17 | e302a7ec (TAT-QA) | 12 | 11 | Off by 1 |
| 18 | 16e717d5 (TAT-QA) | 467 | 467% | Format error |
| 19 | 8cb754f8 (TAT-QA) | 0.5 | 31.25 | Percentage vs points |
| 20 | 22e20f25 (TAT-QA) | 547.5 | 383.5 | Wrong formula (change in avg) |
| 21 | a360cee9 (TAT-QA) | 3 | -3 | Sign error |
| 22 | 407d43ea (TAT-QA) | 198.5 | -198.5 | Sign error |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Wrong calculation/formula | 6 | 27.3% |
| Sign error | 4 | 18.2% |
| Wrong interpretation | 3 | 13.6% |
| Close but wrong | 2 | 9.1% |
| Wrong values | 2 | 9.1% |
| Scale error | 1 | 4.5% |
| Sum vs list | 1 | 4.5% |
| Format error | 1 | 4.5% |
| Percentage vs points | 1 | 4.5% |
| Off by N | 1 | 4.5% |

---

## FinQA vs TAT-QA Breakdown

| Dataset | Correct | Failed | Accuracy |
|---------|---------|--------|----------|
| FinQA (50) | 42 | 8 | 84% |
| TAT-QA (50) | 36 | 14 | 72% |
| **Total** | **78** | **22** | **78%** |

**Key Insight:** FinBound performs better on FinQA (84%) than TAT-QA (72%). TAT-QA questions with complex temporal averages and multi-step calculations remain challenging.

---

## Improvements from Previous Versions

### Questions Fixed in v5:
- ABMD/2009/page_56.pdf-1: 40294 (was incorrect, now correct)
- SLB/2012/page_44.pdf-2: 25.9% (was incorrect, now correct)
- FBHS/2017/page_23.pdf-1: 1320.8 (was incorrect, now correct)
- FRT/2005/page_117.pdf-2: 11.49% (was incorrect, now correct)
- 1238d807 (TAT-QA): -19411 (sign now correct)
- Multiple temporal average questions now correct

### Persistent Issues:
1. **Sign errors** - 4 samples still have sign issues
2. **Sum vs list ambiguity** - PNC/2013 still fails
3. **Complex multi-step calculations** - Some TAT-QA formulas still incorrect

---

## Hallucination Analysis

10 samples (10%) had hallucinations flagged:
- ABMD/2006/page_75.pdf-1
- ETFC/2014/page_26.pdf-4
- TSCO/2017/page_31.pdf-2
- af49c57c (TAT-QA)
- d7bcc322 (TAT-QA)
- 9f7000b0 (TAT-QA)
- 3502f875 (TAT-QA)
- 22e20f25 (TAT-QA)
- a360cee9 (TAT-QA)
- 407d43ea (TAT-QA)

Most hallucinations are due to wrong value extraction or sign misinterpretation, not fabricated values.

---

## Recommendations

1. **Sign handling**: Add explicit sign detection for change/difference questions
2. **Sum vs list**: Better detection of "total X for Y and Z" patterns
3. **Percentage vs points**: Distinguish "change by X%" vs "X percentage points"
4. **Scale validation**: Cross-check magnitude against expected ranges
5. **TAT-QA formulas**: Improve temporal average and multi-step calculation handling
