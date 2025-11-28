#!/usr/bin/env python3
"""
Test FinBound with PoT enabled on 30 failed samples from GPT-4 zeroshot.

This script tests the PoT (Program-of-Thoughts) integration on samples that
GPT-4 failed in the zeroshot experiment.

Usage:
    python scripts/test_failed_full.py
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

# Failed sample IDs from GPT-4 zeroshot (f1_updated_v5_gpt4_zeroshot)
# These are the 30 samples GPT-4 got wrong
SHORT_IDS = [
    # FinQA (7 failed)
    "ABMD/2009/page_56.pdf-1",     # Gold: 40294, scale error
    "SLB/2012/page_44.pdf-2",      # Gold: 25.9%, wrong calculation
    "FBHS/2017/page_23.pdf-1",     # Gold: 1320.8, wrong calculation
    "FRT/2005/page_117.pdf-2",     # Gold: 11.49%, wrong interpretation
    "PNC/2013/page_62.pdf-2",      # Gold: 3576, sum vs list
    "ABMD/2006/page_75.pdf-1",     # Gold: 25%, no answer
    "AMAT/2013/page_18.pdf-2",     # Gold: 7.22, no answer

    # TAT-QA (23 failed)
    "94ef7822",   # Gold: 56, wrong calculation
    "a983501d",   # Gold: 3728, wrong formula (multi-step)
    "1238d807",   # Gold: -19411, sign error
    "a9ecc9dd",   # Gold: 58.43, wrong formula
    "889488f7",   # Gold: 2053.5, list vs average
    "191c3926",   # Gold: 64509, no answer
    "ecf25a96",   # Gold: 232328.5, wrong formula (average)
    "af49c57c",   # Gold: 12.47, wrong interpretation
    "34144864",   # Gold: -3, qualitative vs quantitative
    "d7bcc322",   # Gold: -1903, sign error
    "73693527",   # Gold: 0.95, no answer
    "e151e953",   # Gold: 18.34, scale error
    "3502f875",   # Gold: -168630, no answer
    "df12359b",   # Gold: 13182, wrong calculation
    "e302a7ec",   # Gold: 12, off by N
    "8cb754f8",   # Gold: 0.5, percentage vs points
    "a0414f81",   # Gold: 172, wrong values (average)
    "bf7abd62",   # Gold: 50.5, wrong values (average)
    "4d259081",   # Gold: 121.5, list vs difference
    "dc5e217a",   # Gold: 4227.5, temporal average - PoT target
    "7cd3aedf",   # Gold: 3680, temporal average - PoT target
    "22e20f25",   # Gold: 547.5, temporal average change - PoT target
    "2067daa1",   # Gold: 88.45, format issue
]


def main():
    print("=" * 70)
    print("FinBound + PoT Test on 30 GPT-4 Failed Samples")
    print("=" * 70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"PoT enabled: {os.environ.get('FINBOUND_ENABLE_POT', '0')}")
    print()

    # Create eval harness
    output_dir = PROJECT_ROOT / "experiments" / "pot_failed_30"
    harness = EvalHarness(output_dir=str(output_dir))

    # Register FinBound method with PoT (FULL mode - with verification)
    harness.register_method("finbound_pot", finbound_runner(low_latency_mode=False))

    # Load curated samples from F1_UPDATED
    samples = load_curated_samples("F1_UPDATED", limit=None)
    print(f"Loaded {len(samples)} total samples from F1_UPDATED")

    # Filter to only failed samples (using prefix matching)
    filtered_samples = []
    for s in samples:
        for short_id in SHORT_IDS:
            if s.id.startswith(short_id) or short_id in s.id:
                filtered_samples.append(s)
                break

    print(f"Found {len(filtered_samples)} failed samples to test with PoT")

    if len(filtered_samples) < len(SHORT_IDS):
        print(f"WARNING: Expected {len(SHORT_IDS)} samples, found {len(filtered_samples)}")
        found_ids = {s.id for s in filtered_samples}
        for short_id in SHORT_IDS:
            if not any(short_id in sid for sid in found_ids):
                print(f"  Missing: {short_id}")

    if not filtered_samples:
        print("No samples found! Check if IDs are correct.")
        return

    # Run evaluation
    print(f"\nRunning FinBound + PoT on {len(filtered_samples)} samples...")
    print("(This may take several minutes)")
    print()

    results = harness.run_evaluation(
        samples=filtered_samples,
        task_family="F1_UPDATED",
        methods=["finbound_pot"],
    )

    # Separate results by category
    temporal_avg_ids = ["dc5e217a", "7cd3aedf", "22e20f25"]
    sign_error_ids = ["1238d807", "d7bcc322", "34144864"]

    temporal_results = []
    sign_results = []
    other_results = []

    for r in results:
        if any(tid in r.sample_id for tid in temporal_avg_ids):
            temporal_results.append(r)
        elif any(sid in r.sample_id for sid in sign_error_ids):
            sign_results.append(r)
        else:
            other_results.append(r)

    # Print results by category
    print("\n" + "=" * 70)
    print("RESULTS BY CATEGORY")
    print("=" * 70)

    def print_category(name, results_list):
        if not results_list:
            return 0
        correct = sum(1 for r in results_list if r.is_correct)
        print(f"\n### {name} ({correct}/{len(results_list)})")
        for r in results_list:
            status = "✓" if r.is_correct else "✗"
            print(f"  {status} {r.sample_id}")
            print(f"      Gold: {r.gold_answer}")
            print(f"      Predicted: {r.predicted_answer}")
        return correct

    temporal_correct = print_category("Temporal Average (PoT Target)", temporal_results)
    sign_correct = print_category("Sign Errors (PoT Target)", sign_results)
    other_correct = print_category("Other Failures", other_results)

    # Overall summary
    total = len(results)
    correct = sum(1 for r in results if r.is_correct)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total samples tested: {total}")
    print(f"Correct with PoT: {correct}")
    print(f"Accuracy: {100*correct/total:.1f}%")
    print()
    print(f"GPT-4 baseline: 0/{total} (0%) - all these samples failed")
    print(f"PoT improvement: +{100*correct/total:.1f}%")
    print()

    # Breakdown
    print("By category:")
    if temporal_results:
        print(f"  Temporal average: {temporal_correct}/{len(temporal_results)}")
    if sign_results:
        print(f"  Sign errors: {sign_correct}/{len(sign_results)}")
    if other_results:
        print(f"  Other: {other_correct}/{len(other_results)}")

    print(f"\nEnd time: {datetime.now().isoformat()}")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
