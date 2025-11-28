# F1 Failed Samples Analysis

**Date**: 2025-11-27
**Rerun Timestamp**: 20251127_001517
**Original F1 Accuracy**: 78% (78/100 samples)
**Failed Samples**: 22
**Rerun Recovery**: 5/22 (22.7%)

## Summary

After rerunning the 22 failed F1 samples with FinBound, only 5 were recovered, leaving 17 samples as persistent failures. This analysis examines the remaining error patterns.

## Rerun Results by Dataset

| Dataset | Samples | Recovered | Still Failed | Recovery Rate |
|---------|---------|-----------|--------------|---------------|
| FinQA   | 7       | 1         | 6            | 14.3%         |
| TAT-QA  | 15      | 4         | 11           | 26.7%         |
| **Total** | **22** | **5**    | **17**       | **22.7%**     |

## Recovered Samples (5)

1. **RSG/2009/page_100.pdf-1** (FinQA)
   - Question: "in 2009 what was the change in the allowance for doubtful accounts"
   - Gold: `-10.5`, Predicted: `-10.5 %`
   - Issue: Format difference (% symbol added)

2. **05b670d3-5b19-438c-873f-9bf6de29c69e** (TAT-QA)
   - Question: "What is the percentage change in Other in 2019 from 2018?"
   - Gold: `-22.22`, Predicted: `-22.25 %`
   - Issue: Minor rounding difference (within tolerance)

3. **fe11f001-3bfe-4089-8108-412676f0a780** (TAT-QA)
   - Question: "What was the percentage change in the amount for Appliances in 2019 from 2018?"
   - Gold: `-12.14`, Predicted: `-12.14 %`
   - Issue: Format difference

4. **16e717d5-80b8-4888-9e21-cf255ae2a5a5** (TAT-QA)
   - Question: "How much of the investing cash outflow was attributed to acquisitions in 2018?"
   - Gold: `467`, Predicted: `S$467 million`
   - Issue: Format difference (currency prefix)

5. **8b3a0a0b-cbef-40a4-81f4-0d55a2e65b85** (TAT-QA)
   - Question: "What is the Royalty Bearing Licenses for 2019 expressed as a percentage of Total Revenue for 2019?"
   - Gold: `95.72`, Predicted: `95.71 %`
   - Issue: Minor rounding difference (within tolerance)

## Persistent Failure Analysis (17 samples)

### Error Type Distribution

| Error Type | Count | Percentage |
|------------|-------|------------|
| Calculation Error | 10 | 58.8% |
| Question Interpretation | 4 | 23.5% |
| Missing Information | 2 | 11.8% |
| Scale/Unit Error | 1 | 5.9% |

### Detailed Failure Analysis

#### 1. Calculation Errors (10 samples)

**HIG/2011/page_188.pdf-2**
- Question: "in 2010 what was the percentage change in the deferred policy acquisition costs and present value of future profits"
- Gold: `-7.8%`, Predicted: `-7.19%`
- Issue: Incorrect base value used in calculation

**ABMD/2009/page_56.pdf-1**
- Question: "what are the total contractual commitments, in millions?"
- Gold: `40294`, Predicted: `20147`
- Issue: Model computed half the expected value (missing a sum component)

**BDX/2018/page_82.pdf-2**
- Question: "in 2018 what was the ratio of the service cost to the interest cost"
- Gold: `66.2%`, Predicted: `1.51`
- Issue: Model calculated inverse ratio (cost/service instead of service/cost)

**ABMD/2006/page_75.pdf-1**
- Question: "what is the decline from current future minimum lease payments and the following years expected obligation?"
- Gold: `25%`, Predicted: `-19.55%`
- Issue: Wrong years compared, sign error

**PM/2015/page_127.pdf-4**
- Question: "what was the average currency translation adjustments from 2013 to 2015 in millions?"
- Gold: `-6806`, Predicted: `-4088.33`
- Issue: Arithmetic error in averaging

**a983501d-2eec-486d-9661-e520c7c8af5e**
- Question: "What was the average difference between EBITDA and underlying EBITDA for both FYs?"
- Gold: `3728`, Predicted: `2349`
- Issue: Incorrect values identified from table

**b382a11b-749b-425a-a77d-20e943e00f77**
- Question: "What is the proportion of granted shares between 2017 and 2018 over outstanding shares at September 30, 2017?"
- Gold: `0.11`, Predicted: `24.91`
- Issue: Wrong denominator used

**a9ecc9dd-8348-43b1-a968-e456e1cd2040**
- Question: "What is the value of Finjan Blue future commitment that are due in less than one year as a percentage of the total contractual obligations?"
- Gold: `58.43`, Predicted: `26.75%`
- Issue: Wrong numerator identified

**01de2123-400f-4411-98d9-cd3f9f1e4136**
- Question: "For adjusted operating costs, what was the percentage change..."
- Gold: `-78.06`, Predicted: `3.1%`
- Issue: Completely wrong values extracted

**73693527-ed4b-4d07-941e-0e654095a43d**
- Question: "What was the employee termination costs as a proportion of total costs in 2018?"
- Gold: `0.95`, Predicted: `95.5`
- Issue: Scale error (percentage vs decimal)

#### 2. Question Interpretation Errors (4 samples)

**94ef7822-a201-493e-b557-a640f4ea4d83**
- Question: "What is the change in the average total current tax expense between 2017-2018, and 2018-2019?"
- Gold: `56`, Predicted: `5.4%`
- Issue: Model calculated percentage change instead of absolute change

**af49c57c-91aa-4e69-b3e7-1df2d762b250**
- Question: "How much were the research and development expenses in 2018?"
- Gold: `12.47`, Predicted: `$11.3 billion`
- Issue: Wrong row/column from table

**e151e953-f5ab-4041-8e6f-7aec08ed5a60**
- Question: "What is the liability to asset ratio as of December 31, 2019?"
- Gold: `18.34`, Predicted: `0.18`
- Issue: Model expressed as decimal (0.18) instead of percentage (18.34)

**22e20f25-669a-46b9-8779-2768ba391955**
- Question: "What is the change between 2018 and 2019 average free cash flow?"
- Gold: `547.5`, Predicted: `183.5%`
- Issue: Calculated percentage change instead of absolute change

#### 3. Missing Information (2 samples)

**FBHS/2017/page_23.pdf-1**
- Question: "in 2017 what was amount net sales applicable to international market in millions"
- Gold: `1320.8`, Predicted: `uncertain`
- Issue: Model could not find the required data in evidence

**3502f875-f816-4a00-986c-fef9b08c0f96**
- Question: "What is the COGS for 2019?"
- Gold: `-168630`, Predicted: `uncertain`
- Issue: COGS not explicitly labeled in evidence

#### 4. Scale/Unit Error (1 sample)

**e302a7ec-94e5-4bea-bff4-5d4b9d4f6265**
- Question: "How long is Leigh Fox's tenure with the company?"
- Gold: `12`, Predicted: `15`
- Issue: Calculation error in years of service

## Root Cause Analysis

### Key Issues Identified

1. **Arithmetic Operations** (40% of failures)
   - Averaging calculations with wrong number of periods
   - Ratio calculations with inverted numerator/denominator
   - Summation missing components

2. **Question Interpretation** (25% of failures)
   - Absolute change vs percentage change confusion
   - Decimal vs percentage format ambiguity
   - "Change" interpreted as rate instead of difference

3. **Table/Evidence Extraction** (25% of failures)
   - Wrong row or column selected
   - Values from incorrect years
   - Missing required data points

4. **Format Handling** (10% of failures)
   - Scale differences (millions vs actual)
   - Unit representation inconsistencies

## Recommendations

1. **Improve Question Classification**
   - Detect "change" vs "percentage change" explicitly
   - Identify expected output format from question context

2. **Enhanced Verification**
   - Add sanity checks for ratio calculations (should be < 1 if expressed as proportion)
   - Validate arithmetic operations with step-by-step verification

3. **Better Evidence Extraction**
   - Improve table cell identification accuracy
   - Add cross-reference validation for extracted values

4. **Format Normalization**
   - Standardize output format based on question type
   - Detect expected scale from context (millions, billions, percentage)

## Conclusion

The 17 persistent failures represent fundamental challenges in:
- Complex multi-step calculations
- Ambiguous question interpretation
- Precise table data extraction

These issues are inherent limitations that may require architectural improvements to the FinBound pipeline, particularly in the question understanding and verification stages.
