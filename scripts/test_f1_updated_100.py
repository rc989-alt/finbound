#!/usr/bin/env python3
"""
Test FinBound with PoT on all 100 samples from F1_UPDATED dataset.

Usage:
    python scripts/test_f1_updated_100.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

# Enable PoT
os.environ["FINBOUND_ENABLE_POT"] = "1"

from experiments.eval_harness import EvalHarness
from experiments.run_experiments import load_curated_samples
from experiments.baselines.finbound_runner import create_runner as finbound_runner


def main():
    print("=" * 70)
    print("FinBound + PoT Test on ALL 100 F1_UPDATED Samples")
    print("=" * 70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"PoT enabled: {os.environ.get('FINBOUND_ENABLE_POT', '0')}")
    print()

    # Create eval harness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "experiments" / f"f1_updated_100_{timestamp}"
    harness = EvalHarness(output_dir=str(output_dir))

    # Register FinBound method with PoT (FULL mode - with verification)
    harness.register_method("finbound_pot", finbound_runner(low_latency_mode=False))

    # Load ALL curated samples from F1_UPDATED (should be 100)
    samples = load_curated_samples("F1_UPDATED", limit=None)
    print(f"Loaded {len(samples)} samples from F1_UPDATED")

    # Count by source
    finqa_count = sum(1 for s in samples if "finqa" in s.id.lower() or "/" in s.id)
    tatqa_count = len(samples) - finqa_count
    print(f"  FinQA: {finqa_count}")
    print(f"  TAT-QA: {tatqa_count}")

    if len(samples) == 0:
        print("No samples found!")
        return

    # Run evaluation
    print(f"\nRunning FinBound + PoT on {len(samples)} samples...")
    print("(This may take 30-60 minutes)")
    print()

    results = harness.run_evaluation(
        samples=samples,
        task_family="F1_UPDATED",
        methods=["finbound_pot"],
    )

    # Calculate results
    correct = sum(1 for r in results if r.is_correct)
    total = len(results)

    # Separate by source
    finqa_results = [r for r in results if "/" in r.sample_id]
    tatqa_results = [r for r in results if "/" not in r.sample_id]

    finqa_correct = sum(1 for r in finqa_results if r.is_correct)
    tatqa_correct = sum(1 for r in tatqa_results if r.is_correct)

    # Print summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"  FinQA: {finqa_correct}/{len(finqa_results)} ({100*finqa_correct/len(finqa_results):.1f}%)" if finqa_results else "  FinQA: N/A")
    print(f"  TAT-QA: {tatqa_correct}/{len(tatqa_results)} ({100*tatqa_correct/len(tatqa_results):.1f}%)" if tatqa_results else "  TAT-QA: N/A")
    print()

    # Print incorrect samples
    incorrect = [r for r in results if not r.is_correct]
    if incorrect:
        print(f"\nIncorrect samples ({len(incorrect)}):")
        for r in incorrect:
            print(f"  - {r.sample_id}")
            print(f"      Gold: {r.gold_answer}")
            print(f"      Pred: {r.predicted_answer}")

    print(f"\nEnd time: {datetime.now().isoformat()}")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
