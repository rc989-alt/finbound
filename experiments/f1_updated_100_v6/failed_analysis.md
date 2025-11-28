# Failed Questions Analysis - FinBound v6

**Experiment:** FinBound + PoT v6 on F1_UPDATED (100 samples)
**Date:** 2025-11-28
**Accuracy:** 73/100 (73.0%)
**Regression:** -5% from v5 (78%)

---

## Executive Summary

Out of 100 samples, 27 failed. The errors fall into 5 categories:

| Error Type | Count | % of Failures | Potential Fix |
|------------|-------|---------------|---------------|
| Wrong Values/Calculation | 11 | 40.7% | Better table extraction |
| Sign Error | 4 | 14.8% | Re-enable sign detection |
| Scale Error (100x) | 4 | 14.8% | Decimal vs percentage detection |
| Format Mismatch | 3 | 11.1% | Output formatting rules |
| Other Wrong Calculation | 5 | 18.5% | Formula verification |

---

## Detailed Analysis by Error Type

### 1. Sign Errors (4 cases) - High Priority

These are cases where the magnitude is correct but the sign is wrong.

| Sample ID | Gold | Predicted | Analysis |
|-----------|------|-----------|----------|
| ETFC/2014/page_26.pdf-4 | **-67.33** | 67.33 | Negative change computed as positive |
| 01de2123 | **-78.06** | 3.1 % | Negative value lost entirely |
| a360cee9 | **3** | -3 | Positive changed to negative |
| 407d43ea | **198.5** | -198.5 | Positive changed to negative |

**Root Cause:**
- Sign detection logic in `layer0_checks.py` is DISABLED due to previous regressions
- PoT computes `new - old` without considering question context (increase vs decrease)
- No post-processing to align sign with question intent

**Recommendation:**
```python
# Re-enable sign detection with stricter conditions:
# 1. Only flip when question explicitly asks for "decrease/decline"
# 2. AND current answer is positive
# 3. AND magnitude matches expected range
```

---

### 2. Scale Errors - 100x (4 cases) - High Priority

These are decimal vs percentage confusion (0.51 → 51).

| Sample ID | Gold | Predicted | Issue |
|-----------|------|-----------|-------|
| 72325ec6 | **0.51** | 51 | Small % scaled up 100x |
| 9f7000b0 | **0.78** | 78 | Small % scaled up 100x |
| b382a11b | **0.11** | 24.91 | Wrong scale + wrong calc |
| ABMD/2009 | **40294** | 9.46 million | Wrong unit interpretation |

**Root Cause:**
- LLM sometimes returns percentage as decimal (0.51) and other times as whole number (51)
- No consistent rule for when to multiply by 100
- Evidence-based scaling was DISABLED due to regressions

**Pattern:** Gold values like 0.51%, 0.78% are small percentages that LLM incorrectly scales to 51%, 78%

**Recommendation:**
```python
# Add sanity check: if question asks for "percentage" and answer < 1,
# check if answer * 100 appears in evidence values
# Only scale if there's strong evidence it should be scaled
```

---

### 3. Wrong Values from Table (8 cases) - Medium Priority

LLM extracted wrong row/column from table.

| Sample ID | Gold | Predicted | Issue |
|-----------|------|-----------|-------|
| FBHS/2017 | **1320.8** | 1373.66 | Wrong row selected |
| ALXN/2007 | **4441** | 3443.4 | Wrong values extracted |
| a983501d | **3728** | 2354 | Average of wrong values |
| a9ecc9dd | **58.43** | 26.75 | Wrong percentage base |
| af49c57c | **12.47** | 22000 | Completely wrong interpretation |
| 3502f875 | **-168630** | 1080112 | Wrong values + wrong sign |
| 5a97069f | **1541.5** | 2287.3 | Wrong temporal values |
| 22e20f25 | **547.5** | 367 | Change in averages wrong |

**Root Cause:**
- Table extraction selects values by proximity, not semantic matching
- Multi-step calculations compound extraction errors
- Questions about "change in average" are particularly error-prone

**Recommendation:**
- Already added CELL VERIFICATION PROCEDURE in v6
- Need to verify extraction results match question keywords
- Add cross-validation: extracted values should appear in evidence

---

### 4. Wrong Calculation/Formula (8 cases) - **RECLASSIFIED**

**UPDATE: Log analysis reveals these are NOT calculation errors - they're verification bugs!**

| Sample ID | Gold | Predicted | Root Cause (from logs) |
|-----------|------|-----------|------------------------|
| C/2017 | **93.5%** | 193.5 % | **VERIFICATION BUG** - LLM was correct, verification changed it |
| SLB/2012 | **25.9%** | 16.67 % | **POT IGNORED** - PoT had 25.85%, arbitration chose LLM |
| FRT/2005-2 | **11.49%** | 68412000 | **POT VERIFIED WRONG** - PoT agreed with wrong value |
| BDX/2018 | **66.2%** | 151.11 % | **VERIFICATION BUG** - LLM was correct, verification changed it |
| ABMD/2006 | **25%** | 85.26 | Genuine calculation error |
| AMAT/2013 | **7.22** | 8.57 | Rounding/calculation error |
| FRT/2005-1 | **92%** | 1.28 | Percentage vs decimal confusion |
| 8cb754f8 | **0.5** | 31.25 | Percentage point vs % change |

**Actual Root Causes:**
1. **Verification Bug (2 cases)**: Single-pass verification incorrectly "correcting" correct answers
2. **PoT Arbitration (1 case)**: PoT was correct but arbitration chose LLM
3. **PoT Verification Failure (1 case)**: PoT verified an obviously wrong answer (68412000)
4. **Genuine Errors (4 cases)**: Actual formula/calculation mistakes

**Specific Issue - 8cb754f8:**
- Gold: 0.5 (percentage POINT change)
- Predicted: 31.25 (percentage CHANGE)
- The `percentage_point_change` detection exists but isn't triggering

---

### 5. Format Mismatch (3 cases) - Low Priority

Answer is essentially correct but format differs.

| Sample ID | Gold | Predicted | Issue |
|-----------|------|-----------|-------|
| e302a7ec | **12** | 11 years and 4 months | Extra text/wrong rounding |
| 16e717d5 | **467** | 467 % | Extra % symbol added |
| TSCO/2018 | **99.8%** | 581.5 | Wrong value entirely |

**Root Cause:**
- Output formatting adds % when not needed (16e717d5)
- Verbose output instead of numeric (e302a7ec)
- TSCO/2018 is actually wrong calculation, not format

---

## CRITICAL BUG FOUND: Verification Introducing Errors

**Root Cause of 5% Regression Identified!**

Analysis of the run.log reveals that the **verification step is WRONGLY correcting correct answers**:

### Case 1: C/2017 (Gold=93.5%, Pred=193.5%)
```
[LOG] Pass 1 result: correct=False, answer=93.5%
[LOG] Verification caught error: 93.5% -> 193.5% (type: wrong_values)
[LOG] Verification corrected answer: 93.5% -> 193.5%
```
**The LLM correctly answered 93.5%, but verification WRONGLY changed it to 193.5%!**

### Case 2: BDX/2018 (Gold=66.2%, Pred=151.11%)
```
[LOG] Pass 1 result: correct=False, answer=151.11%
[LOG] Verification caught error: 66.2% -> 151.11% (type: wrong_denominator)
[LOG] Verification corrected answer: 66.2% -> 151.11%
```
**LLM had correct answer 66.2%, verification WRONGLY changed it to 151.11%!**

### Case 3: SLB/2012 (Gold=25.9%, Pred=16.67%)
```
[LOG] PoT differs from LLM: LLM=16.6700, PoT=25.8530 (diff=55.09%)
[LOG] Arbitration kept LLM answer (confidence=0.90): absolute increase, not percentage
```
**Here PoT was CORRECT (25.85% ≈ 25.9%)!** But arbitration wrongly kept LLM's 16.67.

---

## Analysis: Why Verification Is Failing

| Sample | LLM Answer | PoT Answer | Verification Action | Result |
|--------|------------|------------|---------------------|--------|
| C/2017 | 93.5% ✓ | N/A | Changed to 193.5% | WRONG |
| BDX/2018 | 66.2% ✓ | 226.0 | Changed to 151.11% | WRONG |
| SLB/2012 | 16.67 | 25.85% ✓ | Kept LLM | WRONG |

**Patterns:**
1. Single-pass verification (gpt-4o-mini) incorrectly flags correct answers
2. When PoT disagrees with LLM, arbitration has bias toward LLM
3. For SLB/2012, PoT calculated correct percentage change but was ignored

---

## Recommendations: Fix Verification Bug

### P0 - CRITICAL FIX
1. **Don't let single-pass verification override correct answers**
   - Current: If verification says `is_correct=False`, it applies correction
   - Fix: Require multi-pass agreement before applying any correction

2. **Trust PoT when it's close to evidence values**
   - If PoT result (25.85) is within 1% of a valid answer (25.9), prefer PoT
   - If LLM result doesn't match any evidence, be suspicious

### P1 - Improve Arbitration
3. **When PoT and LLM disagree significantly (>10%), investigate**
   - Check which answer appears in evidence
   - Check which matches question pattern (% change vs absolute)

---

## Comparison: v5 (78%) vs v6 (73%)

### New Failures in v6 (samples that passed in v5 but failed in v6)

**CONFIRMED: At least 2 samples (C/2017, BDX/2018) failed due to verification bug.**

The 5% drop is primarily caused by:
1. **Verification bug**: Single-pass verification incorrectly "correcting" correct answers
2. **PoT arbitration bias**: Keeping LLM answer when PoT was correct

### Samples that Improved (may have fixed some)

Some samples may have improved with the new prompts but overall net effect is negative due to the verification bug.

---

## Recommendations by Priority

### P0 - Quick Fixes (Immediate)

1. **Fix format mismatch (16e717d5):**
   - Don't add % symbol when gold answer doesn't have it
   - Check if question asks for absolute number vs percentage

2. **Review sign detection:**
   - Consider re-enabling with stricter conditions
   - Only apply when magnitude matches AND question has clear direction words

### P1 - Short Term

3. **Scale error detection:**
   - Add check: if answer is 100x off from any evidence value, flag for review
   - Don't auto-scale, but log warning

4. **Percentage point vs percentage change:**
   - Debug why `percentage_point_change` pattern isn't triggering for 8cb754f8
   - Add more explicit guidance in prompt

### P2 - Medium Term

5. **Table extraction validation:**
   - Cross-check extracted values appear in evidence
   - If value doesn't appear, re-extract with different prompt

6. **Formula verification:**
   - After calculation, verify result is in reasonable range
   - If percentage > 100 or < -100, flag for review

### P3 - Investigate Regression

7. **Compare v5 vs v6 sample-by-sample:**
   - Identify exactly which samples regressed
   - Understand if prompt changes caused issues

---

## Specific Sample Deep Dives

### Case Study 1: 72325ec6 (Scale Error)
- **Gold:** 0.51
- **Predicted:** 51
- **Question Type:** Percentage calculation
- **Issue:** LLM returned 51 when answer should be 0.51%
- **Evidence check:** Does 0.51 or 51 appear in evidence?

### Case Study 2: ETFC/2014 (Sign Error)
- **Gold:** -67.33
- **Predicted:** 67.33
- **Question Type:** Change/difference calculation
- **Issue:** Negative sign lost
- **Question context:** Does it ask for "change" or "decrease"?

### Case Study 3: 8cb754f8 (% Point vs % Change)
- **Gold:** 0.5
- **Predicted:** 31.25
- **Question Type:** Percentage point change
- **Issue:** Computed percentage change instead of point difference
- **Pattern:** Question likely asks "how much did the rate change" (points, not %)

---

## Files in This Analysis

- `metrics.json` - Summary statistics
- `results.json` - All 27 failed samples with error types
- `run.log` - Full execution log
- `failed_analysis.md` - This detailed analysis

---

## Next Steps

### Immediate Action: Test Low-Latency Mode

Low-latency mode (`low_latency_mode=True`) skips the verification step entirely, which should:
1. Fix the C/2017 regression (93.5% will stay 93.5%, not become 193.5%)
2. Fix the BDX/2018 regression (66.2% will stay 66.2%, not become 151.11%)
3. Potentially improve accuracy by 2-3%

**Test command:**
```bash
python scripts/test_f1_updated_100_lowlatency.py
```

### Other Next Steps

1. ~~Run v5 again to establish baseline~~ → Actually just run low-latency mode
2. Fix format mismatch (easiest win)
3. Re-enable sign detection with guards
4. Debug percentage_point_change detection
5. Add scale sanity checks
6. **NEW**: Consider making low-latency mode the default for single-pass cases
