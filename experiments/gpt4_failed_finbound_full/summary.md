# FinBound FULL Mode on GPT-4 Failed Samples

**Run Date:** 2024-11-28
**Model:** GPT-4o
**Mode:** Full (with verification, low_latency=False)

## Results Summary

| Metric | Value |
|--------|-------|
| Total Samples | 30 |
| Correct | 15 |
| Accuracy | **50.0%** |

**Note:** GPT-4 got 0/30 (0%) on these samples, FinBound FULL mode recovered 15/30 (50%).

---

## Detailed Results

### Correct (15 samples)

| # | Sample ID | Gold | Predicted |
|---|-----------|------|-----------|
| 1 | AMAT/2013/page_18.pdf-2 | 7.22 | 7.22 |
| 2 | 94ef7822 (TAT-QA) | 56 | 56 |
| 3 | 889488f7 (TAT-QA) | 2053.5 | 2053.5 |
| 4 | 191c3926 (TAT-QA) | 64509 | 64609 |
| 5 | ecf25a96 (TAT-QA) | 232328.5 | 232328.5 |
| 6 | 34144864 (TAT-QA) | -3 | -3 |
| 7 | 73693527 (TAT-QA) | 0.95 | 0.95 |
| 8 | e151e953 (TAT-QA) | 18.34 | 18.35 |
| 9 | df12359b (TAT-QA) | 13182 | 13182 |
| 10 | a0414f81 (TAT-QA) | 172 | 172 |
| 11 | bf7abd62 (TAT-QA) | 50.5 | 50.5 |
| 12 | 4d259081 (TAT-QA) | 121.5 | 121.5 |
| 13 | dc5e217a (TAT-QA) | 4227.5 | 4227.5 |
| 14 | 7cd3aedf (TAT-QA) | 3680 | 3680 |
| 15 | 2067daa1 (TAT-QA) | 88.45 | 88.45 |

### Failed (15 samples)

| # | Sample ID | Gold | Predicted | Error Type |
|---|-----------|------|-----------|------------|
| 1 | ABMD/2009/page_56.pdf-1 | 40294 | 9.46 million | Scale error |
| 2 | SLB/2012/page_44.pdf-2 | 25.9% | 16.67% | Wrong calculation |
| 3 | FBHS/2017/page_23.pdf-1 | 1320.8 | 1373.66 | Wrong calculation |
| 4 | FRT/2005/page_117.pdf-2 | 11.49% | 68412000 | Wrong interpretation |
| 5 | PNC/2013/page_62.pdf-2 | 3576 | list (1356, 2220) | Sum vs list |
| 6 | ABMD/2006/page_75.pdf-1 | 25% | 78.52 | Wrong calculation |
| 7 | a983501d (TAT-QA) | 3728 | 2349 | Wrong formula |
| 8 | 1238d807 (TAT-QA) | -19411 | 19411 | Sign error |
| 9 | a9ecc9dd (TAT-QA) | 58.43 | 26.75 | Wrong formula |
| 10 | af49c57c (TAT-QA) | 12.47 | 3900 | Wrong interpretation |
| 11 | d7bcc322 (TAT-QA) | -1903 | 1903 | Sign error |
| 12 | 3502f875 (TAT-QA) | -168630 | 1138341 | Wrong calculation |
| 13 | e302a7ec (TAT-QA) | 12 | 2 | Wrong calculation |
| 14 | 8cb754f8 (TAT-QA) | 0.5 | 31.25 | Percentage vs points |
| 15 | 22e20f25 (TAT-QA) | 547.5 | 70 | Wrong formula |

---

## Error Classification

| Category | Count | % of Failures |
|----------|-------|---------------|
| Wrong calculation | 5 | 33.3% |
| Wrong formula | 3 | 20.0% |
| Sign error | 2 | 13.3% |
| Wrong interpretation | 2 | 13.3% |
| Sum vs list | 1 | 6.7% |
| Scale error | 1 | 6.7% |
| Percentage vs points | 1 | 6.7% |

---

## Key Insights

1. **FinBound FULL mode recovered 50% of GPT-4's failures** - demonstrating value of verification and multi-pass extraction

2. **Temporal average handling improved significantly:**
   - dc5e217a: Gold 4227.5, Predicted 4227.5 (correct temporal avg)
   - 7cd3aedf: Gold 3680, Predicted 3680 (correct temporal avg)
   - 889488f7: Gold 2053.5, Predicted 2053.5 (correct avg)

3. **Sign errors persist** - Both 1238d807 and d7bcc322 still have sign issues (predicted absolute value instead of negative)

4. **Complex multi-step calculations remain challenging:**
   - a983501d (EBITDA avg difference): Gold 3728, Predicted 2349
   - 22e20f25 (change in averages): Gold 547.5, Predicted 70

5. **FinQA samples remain harder** - Only 1/7 FinQA failures recovered vs 14/23 TAT-QA failures

---

## Comparison with Overall Results

| Method | Full Dataset (100) | GPT-4 Failures (30) | Avg Latency |
|--------|-------------------|---------------------|-------------|
| GPT-4 Zero-shot | 70% | 0% | ~2,152 ms |
| FinBound Low-latency v5 | **78%** | ~43%* | ~10,911 ms |
| FinBound FULL | ~80%* | **50%** | ~15,000 ms* |

*Estimated based on overlapping samples

---

## Updated Metrics (from v5 experiments)

**FinBound Low-Latency v5 on Full Dataset:**
- Accuracy: 78/100 (78%)
- Grounding Accuracy: 89%
- Hallucination Rate: 10%
- Transparency Score: 100%
- Avg Latency: 10,911 ms

**FinBound vs GPT-4:**
- FinBound Low-latency: 78% (+8% over GPT-4)
- GPT-4 Zero-shot: 70%
