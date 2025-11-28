# Failed Questions Investigation

**Experiment:** PoT v3 Analysis on 100 Sample Run (Partial - 57 samples)
**Date:** 2024-11-28

## Executive Summary

Out of 57 samples processed:
- **49 triggered PoT** (86%)
- **33 cases where PoT differed from LLM**
- **Arbitration kept LLM in all 33 cases** (100% correct decisions)
- **PoT was wrong in every disagreement**

This analysis investigates why PoT failed in these 33 cases.

---

## Issue Breakdown

| Issue Type | Count | % of Failures |
|------------|-------|---------------|
| Large Discrepancy | 9 | 27.3% |
| Sign Inversion | 8 | 24.2% |
| Moderate Difference | 6 | 18.2% |
| Extreme Error | 5 | 15.2% |
| Order Of Magnitude | 5 | 15.2% |
| **Total** | **33** | **100%** |

---

## Detailed Analysis by Issue Type

### Large Discrepancy (9 cases)

| Case | LLM Value | PoT Value | Diff | Arbitration Rationale |
|------|-----------|-----------|------|----------------------|
| 1 | 127.40 | 642.00 | 403.9% | The question asks for the average payment volume per transaction for American Ex... |
| 3 | 688.00 | -6.36 | 100.9% | The question asks for the change in millions of operating income from 2016 to 20... |
| 7 | 0.20 | 0.73 | 263.6% | The question asks for the gross margin decline in fiscal 2004 from 2003, which i... |
| 9 | 114.00 | 492.00 | 331.6% | The question asks for the amount of tax related to the unrealized losses reclass... |
| 14 | 1.11 | -9.60 | 968.3% | The question asks for the ratio of the pension trust assets for 2017 to 2018, wh... |
| ... | *4 more cases* | | | |

### Sign Inversion (8 cases)

**Root Cause:** PoT computed correct magnitude but wrong sign direction.

**Pattern:** `diff ≈ 200%` indicates sign flip (e.g., LLM=18.6, PoT=-18.6)

**Why it happens:**
- `create_pot_program_for_sign_sensitive()` always computes `new - old`
- Doesn't consider question context (increase vs decrease phrasing)
- LLM correctly interprets the question, PoT applies blind formula

| Case | LLM Value | PoT Value | Diff | Arbitration Rationale |
|------|-----------|-----------|------|----------------------|
| 2 | 18.60 | -18.60 | 200.0% | The question asks for the net change in net revenue in millions, which is an abs... |
| 8 | -1.90 | 1.90 | 200.0% | The question asks for the change in the weighted average common shares outstandi... |
| 16 | 2.58 | -2.58 | 200.1% | The question asks for the percentage increase in interest expense. The PoT compu... |
| 17 | -3.00 | 3.02 | 200.8% | The question asks for the expected growth rate in amortization expense from 2016... |
| 20 | 6.20 | -6.20 | 200.0% | The question asks for the absolute difference in dollars between the high and lo... |
| ... | *3 more cases* | | | |

### Moderate Difference (6 cases)

| Case | LLM Value | PoT Value | Diff | Arbitration Rationale |
|------|-----------|-----------|------|----------------------|
| 6 | 2013.00 | 864.00 | 57.1% | The question asks for the total residential mortgages balance for 2013 and 2012,... |
| 10 | 2057.00 | 403.00 | 80.4% | The question asks for the total development costs in 2008 if they increased by t... |
| 19 | 778000.00 | 389000.00 | 50.0% | The question asks for the total square footage with a lease expiration date in 2... |
| 28 | -4088.33 | -3922.00 | 4.1% | The question asks for the average currency translation adjustments from 2013 to ... |
| 31 | 44.00 | 1.52 | 96.5% | The question asks for the percentage difference between the average VAR for fore... |
| ... | *1 more cases* | | | |

### Extreme Error (5 cases)

**Root Cause:** PoT used completely wrong values or formula.

**Pattern:** `diff > 10000%` indicates PoT is computing something unrelated

**Why it happens:**
- `_build_generic_pot_program()` selects values by position, not semantics
- Question asks for percentage, PoT computes absolute value (or vice versa)
- Values extracted for different purposes (e.g., total vs ratio)

| Case | LLM Value | PoT Value | Diff | Arbitration Rationale |
|------|-----------|-----------|------|----------------------|
| 4 | 10.94 | 1380763.00 | 12621134.0% | The question asks for a percentage (CET1 ratio), and the original reasoning prov... |
| 18 | 86.80 | 6446489.00 | 7426730.7% | The question asks for a percentage of total future principal payments of corpora... |
| 21 | 4.86 | 14228.00 | 292657.2% | The question asks for the ratio of statutory capital and surplus to statutory ne... |
| 29 | 4.00 | -9000000.00 | 225000100.0% | The question asks for the ratio of gallons hedged in 2017 to 2018, which is a st... |
| 30 | 21.65 | 19104.00 | 88140.2% | The question asks for the percentage of the total purchase price represented by ... |

### Order Of Magnitude (5 cases)

**Root Cause:** PoT used wrong formula type or wrong denominator.

**Pattern:** `diff > 1000%` indicates formula mismatch

**Why it happens:**
- Question asks for ratio, PoT computes sum
- Question asks for percentage of X, PoT uses wrong base
- Temporal ordering incorrect (old/new swapped)

| Case | LLM Value | PoT Value | Diff | Arbitration Rationale |
|------|-----------|-----------|------|----------------------|
| 5 | 3044.00 | 37386.00 | 1128.2% | The question asks for a percentage, specifically what percent the notional value... |
| 11 | 34.00 | 698.60 | 1954.7% | The question asks for the percentage of total aggregate contractual obligations ... |
| 12 | -52.50 | 1217.00 | 2418.1% | The question asks for the percentage change of the carrying amount of loan recei... |
| 13 | 78.53 | 5854.00 | 7354.5% | The question asks for the decline in percentage from the current future minimum ... |
| 15 | -1.00 | -33.33 | 3233.3% | The question asks for the change in percentage points, which is an absolute diff... |

---

## Recommendations

### 1. Sign Inversion Fix (Implemented)
```python
# Align PoT sign to LLM when magnitude matches
if 0.95 <= magnitude_ratio <= 1.05 and sign_diff > 1.9:
    pot_value = abs(pot_value) if proposed_numeric > 0 else -abs(pot_value)
```

### 2. Sanity Check (Implemented)
```python
# Reject PoT if orders of magnitude off
if magnitude_ratio > 100 or magnitude_ratio < 0.01:
    return result, None  # Skip PoT
```

### 3. Reduced Hard Constraints (Implemented)
- Removed `sign_sensitive` as a hard trigger (was causing 86% trigger rate)
- Only trigger on specific patterns: `temporal_average`, `percentage_point_change`, `change_in_averages`

### 4. Semantic Value Selection (Implemented)
- Use label patterns to identify numerator/denominator
- Use temporal ordering from year labels for old/new values

---

## Conclusion

PoT v3 failed because:
1. **Over-triggering** - 86% trigger rate with 0% accuracy when disagreeing
2. **Sign blindness** - Formula doesn't consider question context
3. **Value confusion** - Selects values by position, not semantics
4. **Formula mismatch** - Applies percentage when absolute needed (or vice versa)

The arbitration layer correctly rejected all wrong PoT answers, but PoT added latency without helping accuracy.

**Fixes applied in v4** should reduce triggers to ~10-20% and improve PoT accuracy when triggered.

---

## Part 2: V5 Error Analysis (22 Incorrect out of 100)

The v5 experiment achieved **78% accuracy** (78/100). Below is the analysis of the 22 incorrect samples and how existing solutions apply.

### Error Categories from V5

| Category | Count | Potential Improvement | Status |
|----------|-------|----------------------|--------|
| Calculation/Wrong Values | 11 | +11% | Needs investigation |
| Scale Error | 5 | +5% | Existing solutions partially apply |
| Format Mismatch | 4 | +4% | Existing solutions apply |
| Sign Error | 2 | +2% | Disabled due to regressions |
| Sum vs List | 1 | +1% | Existing solution applies |

---

### 1. Sign Errors (2 cases)

**Failed Samples:**
- `ETFC/2014`: Gold=-67.33, Pred=67.33
- `d7bcc322`: Gold=-1903, Pred=1903

**Existing Solution in Engine:**
```python
# layer0_checks.py - Lines 58-76
POSITIVE_WORDS = ("increase", "growth", "gain", "rose", "higher", "up by", "grew")
NEGATIVE_WORDS = ("decrease", "decline", "loss", "fell", "lower", "down by", "reduction")
```

**Why It's Not Working:**
The sign detection in Layer 0 was **disabled** because it caused regressions:
```python
# layer0_checks.py - Lines 116-126
# NOTE: Previously auto-scaled decimal answers (0.25 → 25) for percentage questions
# but this caused significant regressions. For example:
# - Gold 0.51% (a small percentage change) was wrongly scaled to 51%
# - Gold 0.18% was wrongly scaled to 18%
# Disabled auto-scaling to avoid these false positives.
```

**Recommendation:**
Sign detection could be re-enabled with **stricter conditions**:
- Only apply when question explicitly contains "decrease/decline" AND answer is positive
- Only apply when LLM computed `new - old` but question asks for `old - new` direction
- Add confidence threshold before flipping sign

---

### 2. Scale Errors (5 cases)

**Failed Samples:**
- `HOLX/2007`: Gold=46.3, Pred=106500 (2300x off)
- `b382a11b`: Gold=0.11, Pred=24.91 (226x off)
- `9f7000b0`: Gold=0.78, Pred=78.3 (100x off - likely % vs decimal)
- `af49c57c`: Gold=12.47, Pred=2200 million (wrong unit)

**Existing Solution in Engine:**
```python
# layer0_checks.py - Lines 138-144 (DISABLED)
# NOTE: Previously had evidence-based scaling logic here but it caused
# significant regressions by incorrectly scaling correct answers. Examples:
# - Gold 172 → 1.72 (wrongly scaled down)
# - Gold -864 → -8.64 (wrongly scaled down)
# - Gold 0.51 → 51 (wrongly scaled up)
# The logic was too speculative - using evidence magnitudes to guess answer scale
# is unreliable. Removed in favor of more precise type-based corrections only.
```

**Why It's Not Working:**
Scale correction was removed because it was too aggressive. The 100x scale errors (0.78 vs 78.3) are percentage vs decimal confusion, but auto-correction caused more harm than good.

**Recommendation:**
Instead of auto-correcting, add **verification pass** that flags suspicious scales:
- If answer is >100 and question asks for "percentage", flag for review
- Cross-check with evidence values - if answer doesn't appear in evidence and is 100x off from evidence values, flag it

---

### 3. Sum vs List (1 case)

**Failed Sample:**
- `PNC/2013`: Gold=3576, Pred="1356 million for 2013 and 2220 million for 2012"

**Existing Solution in Engine:**
```python
# engine.py - Lines 2046-2100
def _should_summarize_total(self, answer, question_lower, calc_types):
    """Only trigger summarization when answer contains multiple values
    AND question asks for combined total."""

    has_multi_value_answer = bool(
        # "1356 million for 2013 and 2220 million for 2012" format
        re.search(r"[\d,.]+\s+(?:million|billion|thousand)?\s*(?:for|in)\s+\d{4}\s+and\s+[\d,.]+",
                  answer, re.IGNORECASE)
    )

def _summarize_total_answer(self, answer, question_lower, values_used):
    """Sum up values when model returned separate values but question wants total."""
    numeric_values = [...]
    total = sum(numeric_values)
```

**Why It's Not Working:**
The regex pattern exists but may not be catching all cases. The pattern `[\d,.]+\s+(?:million|billion|thousand)?\s*(?:for|in)\s+\d{4}\s+and\s+[\d,.]+` should match "1356 million for 2013 and 2220 million for 2012".

**Investigation Needed:**
1. Check if `_should_summarize_total` is being called
2. Check if the question contains "total" to trigger summarization
3. Verify values_used contains both 1356 and 2220 for summing

---

### 4. Format Mismatch (4 cases)

**Failed Samples:**
- `AMAT/2013`: Gold=7.22, Pred=7.86 (rounding/calculation)
- `TSCO/2017`: Gold=73.4%, Pred=74.46 (% symbol missing + slight diff)
- `e302a7ec`: Gold=12, Pred=11 (rounding)
- `16e717d5`: Gold=467, Pred=467% (extra % symbol)

**Existing Solution in Engine:**
```python
# engine.py - Lines 1881-1895
def _format_percentage_answer(self, answer, question_lower):
    """Add % symbol if needed for percentage questions."""

# layer0_checks.py - Lines 127-136
elif expected_type in {"absolute", "currency"} and answer_format == "percentage":
    # AUTO-FIX: Strip % symbol for absolute questions
    corrected, corr_type = _strip_percentage_symbol(answer_text, answer_value)
```

**Why It's Not Working:**
- `16e717d5` (467 vs 467%): The answer has an extra % symbol. The stripping logic should handle this but may not be triggered if question type detection fails.
- `TSCO/2017` (73.4% vs 74.46): This is a calculation error (0.8% off), not just format.

---

### 5. Wrong Values / Calculation Errors (11 cases)

**Failed Samples:**
- `a983501d`: Gold=3728, Pred=2349 (wrong values from table)
- `191c3926`: Gold=64509, Pred=19373 (wrong row/column)
- `ABMD/2006`: Gold=25%, Pred=78.52 (wrong calculation)
- `FRT/2005`: Gold=92%, Pred=21.18 (wrong formula)
- And 7 more...

**Existing Solution in Engine:**
```python
# Multi-pass table extraction (engine.py)
# - 3 extraction passes with voting
# - Semantic labels for numerator/denominator

# Verification passes (engine.py)
# - Multi-pass verification for HARD questions
# - Cross-check calculated result
```

**Why It's Not Working:**
These are fundamental LLM errors in:
1. Selecting wrong row/column from table
2. Applying wrong formula (percentage vs absolute)
3. Using wrong time period values

**Recommendation:**
- Improve table extraction prompts with more explicit row/column matching
- Add formula verification step that checks if formula matches question pattern
- Cross-validate extracted values against question keywords

---

## Summary of Existing Solutions and Gaps

| Issue | Existing Solution | Status | Gap |
|-------|------------------|--------|-----|
| Sign Error | `POSITIVE_WORDS/NEGATIVE_WORDS` detection | **Disabled** | Caused regressions on small percentages |
| Scale Error | Evidence-based scaling | **Disabled** | Caused regressions (172→1.72) |
| Sum vs List | `_should_summarize_total()` | **Active** | May need regex tuning |
| Format Mismatch | `_format_percentage_answer()` | **Active** | Working for most cases |
| Wrong Values | Multi-pass extraction | **Active** | LLM limitation, needs better prompts |

## Next Steps

1. **Re-enable sign detection with stricter conditions** - Only flip sign when:
   - Question contains explicit "decrease/decline" AND answer is positive
   - Magnitude matches but sign is wrong
   - High confidence threshold (>0.9)

2. **Debug sum vs list for PNC/2013** - Check why existing solution didn't trigger

3. **Improve table extraction prompts** - Add explicit row/column matching guidance

4. **Accept diminishing returns** - Some errors are LLM limitations that require more fundamental changes (better models, fine-tuning, etc.)
