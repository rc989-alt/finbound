#!/usr/bin/env python3
"""Test the 4 sign error samples from F1_EXTRA analysis."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from finbound import FinBound
from finbound.data.unified import UnifiedSample

# Sign error sample IDs
SIGN_ERROR_IDS = [
    "CDNS/2006/page_30.pdf-4",   # Gold: 55.07%, Predicted: -55.07 (reversed subtraction)
    "HIG/2011/page_188.pdf-2",    # Gold: -7.8%, Predicted: -7.19% (close but not exact)
    "AES/2016/page_191.pdf-1",    # Gold: -5%, Predicted: -5.33% (minor variance)
    "ADBE/2018/page_86.pdf-3",    # Gold: -3.1%, Predicted: 3.16% (sign flip)
]


def load_samples():
    """Load the sign error samples from F1_EXTRA dataset."""
    samples = []

    # Load F1_EXTRA finqa samples
    finqa_path = "data/curated_samples/F1_EXTRA/finqa_samples.json"
    if os.path.exists(finqa_path):
        with open(finqa_path) as f:
            finqa_data = json.load(f)
            for item in finqa_data:
                sample_id = item.get("id") or item.get("sample_id")
                if sample_id in SIGN_ERROR_IDS:
                    samples.append(item)

    return samples


def run_sample(fb: FinBound, sample: dict) -> dict:
    """Run a single sample through FinBound."""
    start_time = time.time()

    try:
        # Convert to UnifiedSample
        unified = UnifiedSample(
            id=sample.get("id") or sample.get("sample_id"),
            question=sample["question"],
            gold_answer=sample.get("answer") or sample.get("gold_answer"),
            evidence_text=sample.get("evidence_text", ""),
            evidence_tables=sample.get("evidence_tables", []),
            dataset="finqa",
            metadata=sample.get("metadata", {}),
        )

        result = fb.run_unified_sample(unified, task_family="F1")
        elapsed_ms = (time.time() - start_time) * 1000

        gold = unified.gold_answer
        predicted = result.answer

        # Check correctness (with tolerance)
        is_correct = check_answer(predicted, gold)

        return {
            "sample_id": unified.id,
            "question": unified.question,
            "gold": gold,
            "predicted": predicted,
            "is_correct": is_correct,
            "latency_ms": elapsed_ms,
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "sample_id": sample.get("id") or sample.get("sample_id"),
            "question": sample.get("question", ""),
            "gold": sample.get("answer") or sample.get("gold_answer"),
            "error": str(e),
            "latency_ms": elapsed_ms,
        }


def check_answer(predicted: str, gold: str) -> bool:
    """Check if predicted answer matches gold (with tolerance)."""
    if not predicted or not gold:
        return False

    try:
        pred_str = str(predicted).replace("%", "").replace(",", "").strip()
        gold_str = str(gold).replace("%", "").replace(",", "").strip()

        pred_num = float(pred_str)
        gold_num = float(gold_str)

        # Exact match
        if abs(pred_num - gold_num) < 0.01:
            return True

        # 5% tolerance
        if gold_num != 0:
            ratio = abs(pred_num - gold_num) / abs(gold_num)
            return ratio < 0.05

        return abs(pred_num - gold_num) < 0.1
    except (ValueError, TypeError):
        return str(predicted).strip().lower() == str(gold).strip().lower()


def main():
    print("=" * 80)
    print("Testing Sign Error Samples from F1_EXTRA")
    print("=" * 80)

    samples = load_samples()

    if not samples:
        print("No samples found. Creating from known data...")
        # Fallback: use known sample data from analysis
        samples = [
            {
                "id": "CDNS/2006/page_30.pdf-4",
                "question": "what was the difference in percentage cumulative 5-year total return to shareholders of cadence design systems , inc . 2019s common stock and the s&p 500 for the period ended december 30 , 2006?",
                "answer": "55.07%",
            },
            {
                "id": "HIG/2011/page_188.pdf-2",
                "question": "in 2010 what was the percentage change in the deferred policy acquisition costs and present value of future profits",
                "answer": "-7.8%",
            },
            {
                "id": "AES/2016/page_191.pdf-1",
                "question": "what was the percentage change in the unrecognized tax benefits from 2014 to 2015?",
                "answer": "-5%",
            },
            {
                "id": "ADBE/2018/page_86.pdf-3",
                "question": "what is the percentage change in total gross amount of unrecognized tax benefits from 2016 to 2017?",
                "answer": "-3.1%",
            },
        ]

    print(f"\nFound {len(samples)} sign error samples")

    fb = FinBound()
    results = []

    for i, sample in enumerate(samples):
        sample_id = sample.get("id") or sample.get("sample_id")
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(samples)}] {sample_id}")
        print(f"Question: {sample.get('question', 'N/A')[:80]}...")
        print(f"Gold Answer: {sample.get('answer') or sample.get('gold_answer')}")
        print("-" * 60)

        result = run_sample(fb, sample)
        results.append(result)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            status = "CORRECT" if result["is_correct"] else "WRONG"
            print(f"Predicted: {result['predicted']}")
            print(f"Status: {status}")
            print(f"Latency: {result['latency_ms']:.0f}ms")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    correct = sum(1 for r in results if r.get("is_correct"))
    total = len(results)

    print(f"\nAccuracy: {correct}/{total} ({correct/total*100:.1f}%)")

    print("\nDetailed Results:")
    for r in results:
        status = "CORRECT" if r.get("is_correct") else "WRONG"
        print(f"  {r['sample_id']}: {status}")
        print(f"    Gold: {r.get('gold')}, Predicted: {r.get('predicted', r.get('error', 'N/A'))}")

    # Save results
    output_path = "experiments/F1_result/sign_error_retest_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
