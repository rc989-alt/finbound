# F1 Benchmark Analysis - Layers 0+1 with Ratio Fix

**Date**: 2025-11-27
**Run ID**: curated_20251127_023856
**Baseline Accuracy**: 78%
**New Accuracy**: 81% (+3%)

---

## Executive Summary

This benchmark run includes:
- Layer 0: Type/unit/sign/range checks (detection)
- Layer 1: Formula detection + recomputation (detection)
- Ratio scaling fix: Converts decimal ratios (0.18) to percentage-scale (18.0)

**Result**: 81/100 samples correct (+3 from baseline)

---

## Metrics Comparison

| Metric | Baseline (v1.0) | New (v2.0) | Change |
|--------|-----------------|------------|--------|
| **Accuracy** | 78% | **81%** | **+3%** |
| Grounding | 96% | 97% | +1% |
| Hallucination | 10% | 7% | -3% |
| Transparency | 99% | 99% | = |
| Auditability | 100% | 100% | = |
| Avg Latency | ~22s | ~23.5s | +1.5s |

---

## Latency Analysis

### Why is latency higher (+1.5s)?

The increased latency is due to:

1. **Layer 0/1 checks added**: Each answer now runs through additional validation:
   - Layer 0: Type detection, unit check, sign check, range sanity (~10-50ms)
   - Layer 1: Formula detection, operand extraction, recomputation (~100-500ms)

2. **More complex samples being processed**: The new checks identify issues that trigger additional processing.

3. **Incorrect samples take longer**: 
   - Average latency (correct): 22,594ms
   - Average latency (incorrect): 27,115ms (+4.5s)
   
   Failed samples often trigger retries and multi-pass verification.

### Latency Distribution

| Metric | Value |
|--------|-------|
| Average | 23,453ms (23.5s) |
| Minimum | 8,895ms (8.9s) |
| Maximum | 63,979ms (64.0s) |

### Slowest Samples

| Sample ID | Latency | Correct? |
|-----------|---------|----------|
| a983501d-2eec-486d-9661-e520c7c8af5e | 64.0s | No |
| 73693527-ed4b-4d07-941e-0e654095a43d | 45.9s | No |
| 72325ec6-41ad-4648-9798-b22a61122cb4 | 39.2s | Yes |
| ETR/2004/page_213.pdf-4 | 39.1s | Yes |
| AMAT/2013/page_18.pdf-2 | 36.8s | Yes |

---

## Failure Analysis (19 samples)

### By Category

| Category | Count | % of Failures | Fixable By |
|----------|-------|---------------|------------|
| Calculation Error | 14 | 74% | Layer 1/2 |
| Format Error (% symbol) | 2 | 11% | Layer 0 |
| Scale Error (100x) | 2 | 11% | Layer 0 |
| Sign Error | 1 | 5% | Layer 0/1 |

### Format Errors (2 samples)
Questions ask for absolute value but answer includes % symbol.

| Sample | Gold | Predicted | Issue |
|--------|------|-----------|-------|
| 16e717d5 | 467 | 467 % | Extra % symbol |
| 22e20f25 | 547.5 | 547.5 % | Extra % symbol |

**Fix**: Strip % symbol when question asks for absolute change (not percentage change).

### Scale Errors (2 samples)
Proportion questions (expect 0-1 range) got percentage-scale answers.

| Sample | Gold | Predicted | Issue |
|--------|------|-----------|-------|
| 73693527 | 0.95 | 95.5 | Should be proportion (0-1) |
| 9f7000b0 | 0.78 | 78 | Should be proportion (0-1) |

**Fix**: Detect "proportion" keyword and keep decimal scale (don't convert to percentage).

### Sign Error (1 sample)

| Sample | Gold | Predicted | Issue |
|--------|------|-----------|-------|
| PM/2015/page_85.pdf-1 | 3.4% | -3.4 % | Wrong sign |

**Fix**: Better sign detection from question context.

### Calculation Errors (14 samples)

| Sample | Gold | Predicted | Root Cause |
|--------|------|-----------|------------|
| HIG/2011/page_188.pdf-2 | -7.8% | -7.18 % | Wrong base value |
| ABMD/2009/page_56.pdf-1 | 40294 | 29.6 | Missing sum component |
| FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 | Wrong value extraction |
| BDX/2018/page_82.pdf-2 | 66.2% | 1.51 | Inverted ratio |
| ABMD/2006/page_75.pdf-1 | 25% | -19.49 % | Wrong years + sign |
| PM/2015/page_127.pdf-4 | -6806 | -4088.33 | Averaging error |
| 94ef7822 | 56 | 5.69 % | Absolute vs % confusion |
| a983501d | 3728 | 2349 | Wrong values from table |
| b382a11b | 0.11 | 24.92 | Wrong denominator |
| a9ecc9dd | 58.43 | 26.75 | Wrong numerator |
| 191c3926 | 64509 | 19373 | Partial sum |
| af49c57c | 12.47 | 2.2 billion | Wrong row/column |
| 3502f875 | -168630 | 1138341 | Completely wrong extraction |
| e302a7ec | 12 | 11 | Off-by-one |

---

## Samples Fixed vs Baseline

### Newly Correct (3 samples)

Based on the accuracy improvement from 78% to 81%, approximately 3 samples were fixed by the Layer 0/1 improvements and ratio scaling fix.

### Still Failing from Baseline (16 samples)

Most baseline failures remain unfixed because they require:
- Better operand extraction (Layer 2)
- LLM-guided re-extraction for complex tables
- Multi-pass consensus for ambiguous values

---

## Recommendations

### Quick Wins (Layer 0 fixes, +3-5% accuracy potential)

1. **Format stripping for absolute questions**
   - Detect "change in X" (not "percentage change")
   - Strip % symbol from answer
   - Target: `16e717d5`, `22e20f25`, `94ef7822`

2. **Proportion handling**
   - Detect "proportion" keyword
   - Keep answer in 0-1 scale (don't multiply by 100)
   - Target: `73693527`, `9f7000b0`

3. **Sign consistency from question**
   - Better detection of expected sign from question context
   - Target: `PM/2015/page_85.pdf-1`

### Medium Effort (Layer 1 improvements)

4. **Better formula type detection**
   - "change in average X" = absolute change, not percentage
   - Target: `94ef7822`, `22e20f25`

5. **Operand order validation**
   - For ratio questions, validate numerator/denominator order
   - Target: `BDX/2018/page_82.pdf-2`

### Higher Effort (Layer 2 needed)

6. **LLM-guided extraction**
   - For complex tables, use focused extraction prompts
   - Target: `ABMD/2009`, `a983501d`, `af49c57c`

7. **Multi-pass consensus**
   - Run 3 extraction attempts, vote on operands
   - Target: `3502f875`, `191c3926`

---

## Next Steps

1. **Implement Layer 0 auto-correction** for format/scale errors (+3-5%)
2. **Improve absolute vs percentage change detection** (+2-3%)
3. **Design Layer 2 LLM extraction** for remaining calculation errors
4. **Target**: 90%+ accuracy

---

## Appendix: Full Failure List

| # | Sample ID | Gold | Predicted | Category |
|---|-----------|------|-----------|----------|
| 1 | HIG/2011/page_188.pdf-2 | -7.8% | -7.18 % | Calculation |
| 2 | ABMD/2009/page_56.pdf-1 | 40294 | 29.6 | Calculation |
| 3 | FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 | Calculation |
| 4 | BDX/2018/page_82.pdf-2 | 66.2% | 1.51 | Calculation |
| 5 | ABMD/2006/page_75.pdf-1 | 25% | -19.49 % | Calculation |
| 6 | PM/2015/page_85.pdf-1 | 3.4% | -3.4 % | Sign |
| 7 | PM/2015/page_127.pdf-4 | -6806 | -4088.33 | Calculation |
| 8 | 94ef7822 | 56 | 5.69 % | Calculation |
| 9 | a983501d | 3728 | 2349 | Calculation |
| 10 | b382a11b | 0.11 | 24.92 | Calculation |
| 11 | a9ecc9dd | 58.43 | 26.75 | Calculation |
| 12 | 191c3926 | 64509 | 19373 | Calculation |
| 13 | af49c57c | 12.47 | 2.2 billion | Calculation |
| 14 | 73693527 | 0.95 | 95.5 | Scale |
| 15 | 9f7000b0 | 0.78 | 78 | Scale |
| 16 | 3502f875 | -168630 | 1138341 | Calculation |
| 17 | e302a7ec | 12 | 11 | Calculation |
| 18 | 16e717d5 | 467 | 467 % | Format |
| 19 | 22e20f25 | 547.5 | 547.5 % | Format |
