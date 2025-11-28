# F1 All Methods Experiment Analysis

**Date:** 2025-11-26
**Dataset:** F1 (100 curated financial QA samples)
**Methods Compared:** FinBound, GPT-4 Zero-shot, GPT-4 Few-shot, RAG No Verify, Claude Zero-shot

---

## Executive Summary

FinBound achieves **78% accuracy** on the F1 benchmark, outperforming all baseline methods by **17-18 percentage points**. This represents a significant improvement over traditional LLM approaches for financial question answering.

| Method | Accuracy | Improvement vs Best Baseline |
|--------|----------|------------------------------|
| **FinBound** | **78%** | — |
| GPT-4 Zero-shot | 61% | +17 pp |
| Claude Zero-shot | 61% | +17 pp |
| GPT-4 Few-shot | 60% | +18 pp |
| RAG No Verify | 60% | +18 pp |

---

## Detailed Performance Comparison

### Accuracy & Quality Metrics

| Method | Accuracy | Grounding Accuracy | Hallucination Rate |
|--------|----------|-------------------|-------------------|
| **FinBound** | **78%** | **96%** | **10%** |
| GPT-4 Zero-shot | 61% | 89.2% | 14% |
| GPT-4 Few-shot | 60% | 91.7% | 16% |
| RAG No Verify | 60% | 93.5% | 14% |
| Claude Zero-shot | 61% | 89.5% | 15% |

### Trust & Auditability Metrics

| Method | Transparency Score | Auditability | Run ID Fidelity | Verification Rate |
|--------|-------------------|--------------|-----------------|-------------------|
| **FinBound** | **99%** | **100%** | **100%** | **100%** |
| GPT-4 Zero-shot | 0% | 0% | 0% | N/A |
| GPT-4 Few-shot | 0% | 0% | 0% | N/A |
| RAG No Verify | 0% | 0% | 0% | N/A |
| Claude Zero-shot | 0% | 0% | 0% | N/A |

### Latency Comparison

| Method | Avg Latency (ms) | Avg Latency (s) | Relative Speed |
|--------|-----------------|-----------------|----------------|
| GPT-4 Few-shot | 1,822 | ~1.8s | 1.0x (fastest) |
| GPT-4 Zero-shot | 1,883 | ~1.9s | 1.0x |
| RAG No Verify | 2,497 | ~2.5s | 1.4x |
| Claude Zero-shot | 4,525 | ~4.5s | 2.5x |
| **FinBound** | **21,828** | **~22s** | **12x** |

---

## Key Findings

### 1. FinBound Advantages

**Accuracy Leadership (+17 pp)**
- FinBound correctly answers 78/100 questions vs 60-61/100 for baselines
- The multi-pass verification and tool-based calculation approach yields substantial accuracy gains

**Superior Grounding (96% vs 89-94%)**
- FinBound's explicit evidence citation reduces hallucinations
- Grounding accuracy 2-7 percentage points higher than all baselines

**Lowest Hallucination Rate (10% vs 14-16%)**
- Structured reasoning with tool calls reduces fabricated information
- 4-6 percentage point improvement over baseline methods

**Full Auditability (100% vs 0%)**
- Complete transparency into reasoning process
- Run ID fidelity enables reproducibility
- Critical for financial applications requiring regulatory compliance

### 2. Baseline Comparison

**GPT-4 vs Claude**
- Nearly identical accuracy (61% vs 61%)
- Similar grounding accuracy (~89%)
- Claude has ~2.4x higher latency

**Zero-shot vs Few-shot**
- Few-shot examples did not improve GPT-4 accuracy (60% vs 61%)
- Few-shot slightly increased hallucination rate (16% vs 14%)
- Suggests financial QA benefits more from structured tools than examples

**RAG Without Verification**
- Same accuracy as few-shot GPT-4 (60%)
- Better grounding (93.5%) than zero-shot approaches
- Retrieval helps grounding but not final accuracy without verification

### 3. Trade-offs

**Latency vs Accuracy**
- FinBound is ~12x slower than fastest baseline
- 22 seconds per question vs 1.8-4.5 seconds
- The accuracy gain of +17 pp may justify latency for:
  - High-stakes financial decisions
  - Regulatory/compliance use cases
  - Research applications requiring accuracy

**Complexity vs Trust**
- Baseline methods: Simple, fast, but unverifiable
- FinBound: Complex pipeline, slower, but fully auditable
- 100% auditability crucial for financial applications

---

## Performance by Method Type

### Direct LLM Approaches (GPT-4/Claude Zero-shot)
- Accuracy: 61%
- Pros: Fast, simple
- Cons: No auditability, higher hallucination

### Enhanced LLM (GPT-4 Few-shot)
- Accuracy: 60%
- Pros: Slightly better grounding than zero-shot
- Cons: Higher hallucination rate, no accuracy improvement

### Retrieval-Augmented (RAG No Verify)
- Accuracy: 60%
- Pros: Best grounding among baselines (93.5%)
- Cons: Still no verification, same accuracy as few-shot

### Full Pipeline (FinBound)
- Accuracy: 78%
- Pros: Best accuracy, grounding, auditability
- Cons: Highest latency

---

## Recommendations

### For Production Use Cases

1. **High-Accuracy Required**: Use FinBound
   - Financial analysis, regulatory reporting, investment decisions
   - Accept 22s latency for 17 pp accuracy gain

2. **Speed Critical**: Use GPT-4 Zero-shot
   - Interactive applications, real-time queries
   - Accept lower accuracy for sub-2s response

3. **Balanced Approach**: Consider RAG + Selective Verification
   - Use RAG for initial answers
   - Apply FinBound verification only for uncertain cases

### For Pipeline Improvement

1. **Latency Reduction**
   - Investigate parallel verification passes
   - Cache common calculation patterns
   - Target: <10s per question

2. **Accuracy Improvement**
   - Address sign handling in percentage changes (known issue)
   - Improve table value extraction
   - Target: 85%+ accuracy

---

## Conclusion

FinBound demonstrates that structured reasoning with tool-based calculations and multi-pass verification significantly outperforms direct LLM approaches for financial QA. The 17 percentage point accuracy improvement over GPT-4/Claude baselines, combined with 100% auditability, makes FinBound well-suited for financial applications where accuracy and trust are paramount.

The primary trade-off is latency (22s vs 2-4s), which may be acceptable for:
- Batch processing of financial documents
- High-stakes decision support
- Compliance and audit requirements

For time-sensitive applications, the baseline methods remain viable but should be used with awareness of their lower accuracy and lack of auditability.

---

## Detailed Failure Analysis by Method

### Failure Summary

| Method | Total Failures | Failure Rate |
|--------|---------------|--------------|
| **FinBound** | **22** | **22%** |
| GPT-4 Zero-shot | 39 | 39% |
| GPT-4 Few-shot | 40 | 40% |
| RAG No Verify | 40 | 40% |
| Claude Zero-shot | 39 | 39% |

---

### Failure Categories by Method

#### FinBound (22 failures)

| Category | Count | Examples |
|----------|-------|----------|
| Calculation (moderate) | 5 | PM/2015/page_127.pdf-4: gold=-6806, pred=-4088.33 |
| Format (% vs absolute) | 4 | 16e717d5: gold=467, pred=467% |
| Other | 4 | b382a11b: gold=0.11, pred=15.72 |
| Sign error | 3 | HIG/2011: gold=-7.8%, pred=7.18% |
| Calculation (close) | 2 | FBHS/2017: gold=1320.8, pred=1373.66 |
| Scale (100x) | 2 | 73693527: gold=0.95, pred=95.5 |
| Scale (10x) | 1 | - |
| Format (missing %) | 1 | - |

**FinBound-specific issues:**
- 4 unique failures only FinBound got wrong
- Sign handling still problematic for some percentage change questions
- Format confusion between percentage and absolute values

#### GPT-4 Zero-shot (39 failures)

| Category | Count | Examples |
|----------|-------|----------|
| Format (% vs absolute) | 12 | 72325ec6: gold=0.51, pred=0.51% |
| Calculation (close) | 8 | SLB/2012: gold=25.9%, pred=16.67 |
| Calculation (moderate) | 5 | PM/2015/page_127.pdf-4: gold=-6806, pred=-4088.33 |
| Other | 5 | FRT/2005: gold=11.49%, pred=$68,412,000 |
| Uncertain | 4 | ABMD/2006: returns "uncertain" |
| Format (missing %) | 2 | - |
| Sign error | 2 | PM/2015/page_85.pdf-1: gold=3.4%, pred=-3.39% |
| Scale (100x) | 1 | - |

**GPT-4 Zero-shot issues:**
- High format confusion (12 cases adding/removing %)
- Returns "uncertain" for 4 questions it could not answer
- No unique failures (all its failures are shared with other methods)

#### GPT-4 Few-shot (40 failures)

| Category | Count | Examples |
|----------|-------|----------|
| Format (% vs absolute) | 14 | 593a3304: gold=92.27, pred=92.3% |
| Calculation (close) | 9 | ecf25a96: gold=232328.5, pred=243424 |
| Calculation (moderate) | 7 | a983501d: gold=3728, pred=5320.5 |
| Sign error | 5 | 81cab6e1: gold=-531925, pred=$531,925 decrease |
| Format (missing %) | 3 | - |
| Other | 2 | - |

**GPT-4 Few-shot issues:**
- Few-shot examples did not reduce format confusion (14 vs 12)
- Higher sign error rate than zero-shot (5 vs 2)
- 1 unique failure not shared with other methods

#### RAG No Verify (40 failures)

| Category | Count | Examples |
|----------|-------|----------|
| Format (% vs absolute) | 13 | 182dd9ea: gold=2.84, pred=2.84% |
| Other/verbose | 12 | Returns prose instead of numbers |
| Calculation (close) | 7 | - |
| Format (missing %) | 3 | - |
| Calculation (moderate) | 2 | - |
| Sign error | 2 | - |
| Scale (100x) | 1 | - |

**RAG No Verify issues:**
- Highest "other" category (12) - often returns descriptive text instead of numeric answers
- Format confusion similar to other baselines
- 1 unique failure

#### Claude Zero-shot (39 failures)

| Category | Count | Examples |
|----------|-------|----------|
| Other/verbose | 10 | Returns descriptive text |
| Format (% vs absolute) | 10 | 593a3304: gold=92.27, pred=92.26% |
| Uncertain | 5 | AMAT/2013: returns "uncertain" |
| Calculation (close) | 4 | - |
| Calculation (moderate) | 3 | - |
| Format (missing %) | 3 | - |
| Sign error | 3 | PM/2015/page_85.pdf-1: gold=3.4%, pred=-3.39% |
| Scale (100x) | 1 | - |

**Claude Zero-shot issues:**
- High "uncertain" rate (5 questions)
- Similar format confusion to GPT-4
- No unique failures

---

### Common Failures (All Methods Failed)

**12 samples failed by ALL 5 methods:**

| Sample ID | Gold Answer | Analysis |
|-----------|-------------|----------|
| ABMD/2009/page_56.pdf-1 | 40294 | Complex calculation, all methods off by ~2x |
| PM/2015/page_127.pdf-4 | -6806 | Multi-step calculation error |
| 05b670d3-5b19-438c-873f-9bf6de29c69e | -22.22 | Sign/format issues |
| fe11f001-3bfe-4089-8108-412676f0a780 | -12.14 | Sign/format issues |
| 94ef7822-a201-493e-b557-a640f4ea4d83 | 56 | Wrong value selection |
| a983501d-2eec-486d-9661-e520c7c8af5e | 3728 | Calculation error |
| a9ecc9dd-8348-43b1-a968-e456e1cd2040 | 58.43 | Value interpretation error |
| af49c57c-91aa-4e69-b3e7-1df2d762b250 | 12.47 | Scale/format confusion |
| e151e953-f5ab-4041-8e6f-7aec08ed5a60 | 18.34 | Scale error |
| 3502f875-f816-4a00-986c-fef9b08c0f96 | -168630 | Large negative value handling |
| 8b3a0a0b-cbef-40a4-81f4-0d55a2e65b85 | 95.72 | Format confusion |
| 22e20f25-669a-46b9-8779-2768ba391955 | 547.5 | Format confusion |

**Root causes for universal failures:**
- Complex multi-step calculations requiring precise intermediate values
- Sign handling for negative percentage changes
- Scale/format ambiguity in financial questions

---

### FinBound Wins (Correct when all baselines failed)

**19 samples where FinBound succeeded but ALL baselines failed:**

| Sample ID | Gold | FinBound Prediction |
|-----------|------|---------------------|
| 1238d807-aa57-48a3-93b6-591873788625 | -19411 | -19411 |
| 182dd9ea-dd5f-4ea0-bc30-bb42ef1f801c | 2.84 | 2.84 |
| 593a3304-3fbe-47d2-a004-f4459ef3d014 | 92.27 | 92.27 |
| 72325ec6-41ad-4648-9798-b22a61122cb4 | 0.51 | 0.51 |
| 7cd3aedf-1291-4fea-bc9d-a25c65727b7b | 3680 | 3680 |
| FRT/2005/page_117.pdf-2 | 11.49% | 11.49% |
| 08ec32ab-4f3e-4549-876c-f4e668439ad9 | 1.18 | 1.18 |
| 170c75fb-da08-4e9d-8c5a-7cbb94e4176e | 82.05 | 82.05 |
| 4d259081-6da6-44bd-8830-e4de0031744c | 121.5 | 121.5 |
| 9963bd65-093e-4801-8050-d2524ff06e7f | 73.68 | 73.68 |

**Why FinBound wins:**
- Tool-based calculations produce exact numeric results
- Multi-pass verification catches format issues
- Explicit citation tracking ensures correct value extraction

---

### Improvement Recommendations

#### High Priority (Based on Failure Analysis)

1. **Fix Format Detection (5+ FinBound failures)**
   - Detect if question expects percentage vs absolute value
   - Normalize output format before answer comparison
   - Add explicit format validation in verification

2. **Improve Sign Handling (3 FinBound failures)**
   - Better detection of "decrease", "decline", "reduction" semantics
   - Preserve calculated sign unless question explicitly asks for magnitude

3. **Scale Validation (3 FinBound failures)**
   - Add magnitude reasonableness checks
   - Flag answers that differ by 10x/100x from evidence values

#### Medium Priority

4. **Reduce Calculation Drift (5+ failures)**
   - Add intermediate result validation
   - Cross-check against alternative calculation paths

5. **Improve Complex Question Handling**
   - Better breakdown of multi-step questions
   - Explicit tracking of intermediate results

---

### Appendix: Complete Failure Lists by Method

#### FinBound Failures (22)

| Sample ID | Gold | Predicted |
|-----------|------|-----------|
| HIG/2011/page_188.pdf-2 | -7.8% | 7.18% |
| ABMD/2009/page_56.pdf-1 | 40294 | 29.6 |
| FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 |
| RSG/2009/page_100.pdf-1 | -10.5 | -10.5% |
| BDX/2018/page_82.pdf-2 | 66.2% | 1.51 |
| ABMD/2006/page_75.pdf-1 | 25% | 19.49% |
| PM/2015/page_127.pdf-4 | -6806 | -4088.33 |
| 05b670d3-5b19-438c-873f-9bf6de29c69e | -22.22 | 22.22 decrease |
| fe11f001-3bfe-4089-8108-412676f0a780 | -12.14 | 12.14 |
| 94ef7822-a201-493e-b557-a640f4ea4d83 | 56 | 5.69% |
| a983501d-2eec-486d-9661-e520c7c8af5e | 3728 | 2349 |
| b382a11b-749b-425a-a77d-20e943e00f77 | 0.11 | 15.72 |
| a9ecc9dd-8348-43b1-a968-e456e1cd2040 | 58.43 | 26.75 |
| af49c57c-91aa-4e69-b3e7-1df2d762b250 | 12.47 | 2200 million |
| 01de2123-400f-4411-98d9-cd3f9f1e4136 | -78.06 | 78.1% |
| 73693527-ed4b-4d07-941e-0e654095a43d | 0.95 | 95.5 |
| e151e953-f5ab-4041-8e6f-7aec08ed5a60 | 18.34 | 0.18 |
| 3502f875-f816-4a00-986c-fef9b08c0f96 | -168630 | 1138341 |
| e302a7ec-94e5-4bea-bff4-5d4b9d4f6265 | 12 | 11 |
| 16e717d5-80b8-4888-9e21-cf255ae2a5a5 | 467 | 467% |
| 22e20f25-669a-46b9-8779-2768ba391955 | 547.5 | (failed) |
| 8b3a0a0b-cbef-40a4-81f4-0d55a2e65b85 | 95.72 | (failed) |
