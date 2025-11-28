#!/usr/bin/env python3
"""A/B test for parallel vs sequential verification on specific failed samples."""

import json
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from finbound import FinBound
from finbound.types import EvidenceContext

# Selected test samples from F1_EXTRA failures
TEST_SAMPLES = [
    {
        "id": "LMT/2015/page_56.pdf-3",
        "question": "what was the average backlog at year-end from 2013 to 2015",
        "gold": "197000",
        "error_type": "scale_error",
        "evidence": """
Backlog (in millions):
| Year | Backlog |
|------|---------|
| 2013 | 194,000 |
| 2014 | 197,000 |
| 2015 | 200,000 |
"""
    },
    {
        "id": "ADBE/2018/page_86.pdf-3",
        "question": "what is the percentage change in total gross amount of unrecognized tax benefits from 2016 to 2017?",
        "gold": "-3.1%",
        "error_type": "sign_flip",
        "evidence": """
Gross Unrecognized Tax Benefits (in millions):
| Year | Amount |
|------|--------|
| 2016 | 321    |
| 2017 | 311    |
| 2018 | 350    |
"""
    },
    {
        "id": "22e20f25-669a-46b9-8779-2768ba391955",
        "question": "What is the change between 2018 and 2019 average free cash flow?",
        "gold": "547.5",
        "error_type": "percent_vs_absolute",
        "evidence": """
Free Cash Flow (in millions):
| Year | Free Cash Flow |
|------|----------------|
| 2017 | 143            |
| 2018 | 286            |
| 2019 | 1119           |

Note: "2018 average" = (2017 + 2018) / 2 = 214.5
      "2019 average" = (2018 + 2019) / 2 = 702.5
      Change = 702.5 - 214.5 = 488 (or they may use different values)
"""
    },
]


def run_test(sample: dict, parallel: bool) -> dict:
    """Run a single test with or without parallel verification."""
    # Set environment variable
    os.environ["FINBOUND_PARALLEL_VERIFICATION"] = "1" if parallel else "0"

    # Initialize FinBound
    fb = FinBound()

    start_time = time.time()

    try:
        # Create evidence context
        evidence_context = EvidenceContext(
            text_blocks=[sample["evidence"]],
            tables=[],
            metadata={},
        )

        # Build user request
        user_request = f"Task: F1 - Financial Ground-Truth Reasoning\nUse tables and text to compute numeric answers with citations.\n\nQuestion: {sample['question']}"

        result = fb.run(
            user_request=user_request,
            evidence_context=evidence_context,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "sample_id": sample["id"],
            "parallel": parallel,
            "predicted": result.answer,
            "gold": sample["gold"],
            "is_correct": _check_answer(result.answer, sample["gold"]),
            "latency_ms": elapsed_ms,
            "verified": result.verified,
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "sample_id": sample["id"],
            "parallel": parallel,
            "error": str(e),
            "latency_ms": elapsed_ms,
        }


def _check_answer(predicted: str, gold: str) -> bool:
    """Check if predicted answer matches gold (with tolerance)."""
    try:
        # Extract numeric values
        pred_num = float(str(predicted).replace("%", "").replace(",", "").strip())
        gold_num = float(str(gold).replace("%", "").replace(",", "").strip())

        # Check for exact or close match
        if pred_num == gold_num:
            return True

        # Allow 5% tolerance
        if gold_num != 0:
            ratio = abs(pred_num - gold_num) / abs(gold_num)
            return ratio < 0.05

        return abs(pred_num - gold_num) < 0.1
    except (ValueError, TypeError):
        return str(predicted).strip().lower() == str(gold).strip().lower()


def main():
    print("=" * 80)
    print("A/B Test: Parallel vs Sequential Verification")
    print("=" * 80)

    results = []

    for sample in TEST_SAMPLES:
        print(f"\n{'='*60}")
        print(f"Sample: {sample['id']}")
        print(f"Question: {sample['question']}")
        print(f"Gold Answer: {sample['gold']}")
        print(f"Error Type: {sample['error_type']}")
        print("-" * 60)

        # Run sequential first
        print("\nRunning SEQUENTIAL verification...")
        seq_result = run_test(sample, parallel=False)
        print(f"  Predicted: {seq_result.get('predicted', seq_result.get('error'))}")
        print(f"  Correct: {seq_result.get('is_correct', 'N/A')}")
        print(f"  Latency: {seq_result.get('latency_ms', 0):.0f}ms")
        results.append(seq_result)

        # Run parallel
        print("\nRunning PARALLEL verification...")
        par_result = run_test(sample, parallel=True)
        print(f"  Predicted: {par_result.get('predicted', par_result.get('error'))}")
        print(f"  Correct: {par_result.get('is_correct', 'N/A')}")
        print(f"  Latency: {par_result.get('latency_ms', 0):.0f}ms")
        results.append(par_result)

        # Compare
        if 'latency_ms' in seq_result and 'latency_ms' in par_result:
            speedup = seq_result['latency_ms'] - par_result['latency_ms']
            print(f"\n  Speedup: {speedup:.0f}ms ({speedup/seq_result['latency_ms']*100:.1f}%)")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    seq_results = [r for r in results if not r.get('parallel')]
    par_results = [r for r in results if r.get('parallel')]

    seq_latency = sum(r.get('latency_ms', 0) for r in seq_results)
    par_latency = sum(r.get('latency_ms', 0) for r in par_results)

    seq_correct = sum(1 for r in seq_results if r.get('is_correct'))
    par_correct = sum(1 for r in par_results if r.get('is_correct'))

    print(f"\nSequential: {seq_correct}/{len(seq_results)} correct, {seq_latency:.0f}ms total")
    print(f"Parallel:   {par_correct}/{len(par_results)} correct, {par_latency:.0f}ms total")
    print(f"Speedup:    {seq_latency - par_latency:.0f}ms ({(seq_latency - par_latency)/seq_latency*100:.1f}%)")

    # Save results
    output_path = "experiments/F1_result/ab_test_parallel_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
