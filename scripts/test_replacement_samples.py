#!/usr/bin/env python3
"""Test 5 replacement samples for the dataset-issue questions."""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from finbound.data import FinQALoader, to_unified
from finbound.core import FinBound

# 7 hard replacement sample IDs
REPLACEMENT_IDS = [
    "FRT/2005/page_117.pdf-1",      # Growth comparison (4 steps)
    "ALXN/2007/page_104.pdf-1",     # Average 5 items (4 steps)
    "ETR/2015/page_131.pdf-2",      # Sum annual maturities (3 steps)
    "AMAT/2014/page_18.pdf-1",      # Growth rate calc (4 steps) - replaced APD
    "IPG/2008/page_21.pdf-1",       # Spend ratio comparison (3 steps)
    "LMT/2013/page_74.pdf-1",       # Average shares outstanding (3 steps)
    "PNC/2011/page_87.pdf-2",       # Average home equity balloon (4 steps)
]

# Dataset issue sample IDs to replace
DATASET_ISSUE_IDS = [
    "PM/2015/page_127.pdf-4",       # Wrong row for average
    "ADI/2011/page_81.pdf-1",       # Question/answer mismatch
    "ABMD/2009/page_88.pdf-1",      # Program/answer mismatch
    "PM/2015/page_85.pdf-1",        # Wrong sign in gold
    "LMT/2006/page_37.pdf-1",       # Ambiguous interpretation
    "AAPL/2004/page_36.pdf-2",      # Format issue (.2 vs 0.2%)
    "PNC/2009/page_46.pdf-2",       # % point vs % change confusion
]


def main():
    # Load FinQA dev set
    loader = FinQALoader(split="dev")
    samples_by_id = {}
    for sample in loader.iter_samples():
        samples_by_id[sample.id] = sample

    print(f"Loaded {len(samples_by_id)} FinQA samples")

    # Find replacement samples
    replacement_samples = []
    for sid in REPLACEMENT_IDS:
        if sid in samples_by_id:
            replacement_samples.append(to_unified(samples_by_id[sid]))
            print(f"Found: {sid}")
        else:
            print(f"NOT FOUND: {sid}")

    if len(replacement_samples) != len(REPLACEMENT_IDS):
        print(f"ERROR: Only found {len(replacement_samples)} of {len(REPLACEMENT_IDS)} samples")
        return

    # Create FinBound engine with low latency mode
    fb = FinBound(model="gpt-4o", max_retries=2, low_latency_mode=True)

    print("\n" + "="*80)
    print("Running 5 replacement samples in low latency mode...")
    print("="*80)

    results = []
    for i, sample in enumerate(replacement_samples, 1):
        print(f"\n[{i}/5] Processing {sample.id}...")
        print(f"Question: {sample.question}")
        print(f"Gold answer: {sample.gold_answer}")

        # Run inference using run_unified_sample
        try:
            output = fb.run_unified_sample(sample, task_family="F1")
            predicted = output.answer
        except Exception as e:
            print(f"ERROR: {e}")
            predicted = f"ERROR: {e}"

        # Check correctness
        gold = str(sample.gold_answer).strip()

        # Simple comparison (handle numeric tolerance)
        try:
            pred_num = float(predicted.replace('%', '').replace(',', ''))
            gold_num = float(gold.replace('%', '').replace(',', ''))
            is_correct = abs(pred_num - gold_num) / max(abs(gold_num), 1e-10) < 0.05
        except:
            is_correct = predicted.lower().strip() == gold.lower().strip()

        result = {
            "sample_id": sample.id,
            "question": sample.question,
            "gold_answer": gold,
            "predicted": predicted,
            "is_correct": is_correct,
            "reasoning": output.reasoning[:500] if output.reasoning else ""
        }
        results.append(result)

        print(f"Predicted: {predicted}")
        print(f"Correct: {is_correct}")

    # Summary
    correct = sum(1 for r in results if r["is_correct"])
    n = len(results)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Accuracy: {correct}/{n} ({correct/n*100:.0f}%)")

    # Save results
    output_file = PROJECT_ROOT / "experiments/f1_low_latency_100/quick_20251127_235602/replacement_samples.json"
    with open(output_file, 'w') as f:
        json.dump({
            "replacement_ids": REPLACEMENT_IDS,
            "dataset_issue_ids": DATASET_ISSUE_IDS,
            "results": results,
            "summary": {
                "accuracy": correct / n
            }
        }, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Print detailed results for failed samples
    failed = [r for r in results if not r["is_correct"]]
    if failed:
        print(f"\n{len(failed)} FAILED samples:")
        for r in failed:
            print(f"\n  {r['sample_id']}")
            print(f"  Question: {r['question'][:100]}...")
            print(f"  Gold: {r['gold_answer']}")
            print(f"  Predicted: {r['predicted']}")


if __name__ == "__main__":
    main()
