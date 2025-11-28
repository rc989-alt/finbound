#!/usr/bin/env python3
"""
Run experiments on specific failed samples only.

This script allows testing improvements on known failure cases
without re-running the entire dataset.

Usage:
    python experiments/run_failed_samples.py --results_file experiments/results/quick_100_samples/quick_150841/results.json
    python experiments/run_failed_samples.py --sample_ids "ABMD/2006/page_75.pdf-1,ZBH/2003/page_58.pdf-1"
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from experiments.eval_harness import EvalHarness, load_test_samples
from experiments.baselines import (
    gpt4_zeroshot_runner,
    gpt4_fewshot_runner,
    rag_no_verify_runner,
    deepseek_zeroshot_runner,
    claude_zeroshot_runner,
)
from experiments.baselines.finbound_runner import create_runner as finbound_runner


def get_failed_sample_ids(results_file: str) -> List[str]:
    """Extract sample IDs that failed from a results file."""
    with open(results_file) as f:
        results = json.load(f)

    failed = []
    for r in results:
        if not r.get("is_correct", True):
            failed.append(r["sample_id"])
        elif r.get("error"):
            failed.append(r["sample_id"])

    return failed


def main():
    parser = argparse.ArgumentParser(description="Run experiments on failed samples only")
    parser.add_argument(
        "--results_file",
        type=str,
        help="Path to results.json file to extract failed samples from"
    )
    parser.add_argument(
        "--sample_ids",
        type=str,
        help="Comma-separated list of sample IDs to run"
    )
    parser.add_argument(
        "--methods",
        type=str,
        default="finbound",
        help="Comma-separated list of methods to run (default: finbound)"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="F1",
        help="Task family (default: F1)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="finqa",
        help="Dataset to use (default: finqa)"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="dev",
        help="Dataset split (default: dev)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="Base model for FinBound/GPT-4 runners (default: gpt-4o)"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output directory (default: experiments/results/failed_HHMMSS)"
    )
    parser.add_argument(
        "--compare_with",
        type=str,
        default=None,
        help="Previous results file to compare against"
    )

    args = parser.parse_args()

    # Get sample IDs
    if args.sample_ids:
        sample_ids = [s.strip() for s in args.sample_ids.split(",")]
    elif args.results_file:
        sample_ids = get_failed_sample_ids(args.results_file)
    else:
        print("Error: Must specify either --results_file or --sample_ids")
        sys.exit(1)

    if not sample_ids:
        print("No failed samples found!")
        sys.exit(0)

    print(f"Running {len(sample_ids)} failed samples:")
    for sid in sample_ids:
        print(f"  - {sid}")
    print()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Setup output directory
    timestamp = datetime.now().strftime("%H%M%S")
    output_dir = args.output_dir or f"experiments/results/failed_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    # Load samples from dataset
    print(f"Loading {args.dataset} ({args.split})...")
    all_samples = load_test_samples(args.dataset, split=args.split, limit=None)

    # Filter to only the specified sample IDs
    # UnifiedSample uses 'id' attribute, but results use 'sample_id'
    sample_id_set = set(sample_ids)
    filtered_samples = [s for s in all_samples if s.id in sample_id_set]

    if not filtered_samples:
        print(f"Warning: No matching samples found in dataset for IDs: {sample_ids}")
        print(f"Available sample IDs (first 10): {[s.id for s in all_samples[:10]]}")
        sys.exit(1)

    print(f"Found {len(filtered_samples)} matching samples in dataset")
    print()

    requested_methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    if not requested_methods:
        requested_methods = ["finbound"]

    harness = EvalHarness(output_dir=output_dir)
    method_factories = {
        "finbound": lambda: finbound_runner(model=args.model, max_retries=2),
        "gpt4_zeroshot": lambda: gpt4_zeroshot_runner(model=args.model),
        "gpt4_fewshot": lambda: gpt4_fewshot_runner(model=args.model),
        "rag_no_verify": lambda: rag_no_verify_runner(model=args.model),
        "deepseek_zeroshot": lambda: deepseek_zeroshot_runner(model="deepseek-chat"),
        "claude_zeroshot": lambda: claude_zeroshot_runner(model="claude-sonnet-4-20250514"),
    }

    active_methods: List[str] = []
    for method in requested_methods:
        factory = method_factories.get(method)
        if not factory:
            print(f"Warning: Unknown method '{method}', skipping.")
            continue
        harness.register_method(method, factory())
        active_methods.append(method)

    if not active_methods:
        print("Error: No valid methods selected.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Running evaluation on {len(filtered_samples)} samples with methods: {active_methods}")
    print(f"{'='*60}")

    harness.run_evaluation(filtered_samples, task_family=args.task, methods=active_methods)
    all_results = harness._results

    # Save results
    run_id = f"failed_{timestamp}"
    results_dir = harness.save_results(run_id)

    # Convert results to list of dicts for comparison
    all_results_dicts = [r.__dict__ if hasattr(r, '__dict__') else r for r in all_results]

    # Print summary
    print("\n" + "="*80)
    print("FAILED SAMPLES EVALUATION SUMMARY")
    print("="*80)

    correct = sum(1 for r in all_results if getattr(r, "is_correct", False))
    total = len(all_results)

    print(f"Samples tested: {total}")
    print(f"Correct: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"Results saved to: {results_dir}")

    # Compare with previous results if provided (FinBound only)
    if (args.compare_with or args.results_file) and "finbound" in active_methods:
        compare_file = args.compare_with or args.results_file
        print(f"\n{'='*60}")
        print(f"COMPARISON WITH PREVIOUS RUN")
        print(f"{'='*60}")

        with open(compare_file) as f:
            prev_results = json.load(f)

        prev_by_id = {
            (r["sample_id"], r.get("method", "finbound")): r for r in prev_results
        }
        new_by_id = {
            (getattr(r, "sample_id", None), getattr(r, "method", None)): r
            for r in all_results
        }

        improved = []
        regressed = []
        unchanged = []

        for sid in sample_ids:
            key = (sid, "finbound")
            prev = prev_by_id.get(key)
            new = new_by_id.get(key)

            if not prev or not new:
                continue

            prev_correct = prev.get("is_correct", False)
            new_correct = getattr(new, "is_correct", False)

            if not prev_correct and new_correct:
                improved.append({
                    "sample_id": sid,
                    "prev_answer": prev.get("predicted_answer"),
                    "new_answer": getattr(new, "predicted_answer", ""),
                    "gold": getattr(new, "gold_answer", ""),
                })
            elif prev_correct and not new_correct:
                regressed.append({
                    "sample_id": sid,
                    "prev_answer": prev.get("predicted_answer"),
                    "new_answer": getattr(new, "predicted_answer", ""),
                    "gold": getattr(new, "gold_answer", ""),
                })
            else:
                unchanged.append(sid)
    elif args.compare_with or args.results_file:
        print("\nComparison skipped because FinBound was not included in the current method list.")

        print(f"\nIMPROVED ({len(improved)}):")
        for item in improved:
            print(f"  {item['sample_id']}:")
            print(f"    OLD: {item['prev_answer']} -> NEW: {item['new_answer']} (gold: {item['gold']})")

        print(f"\nREGRESSED ({len(regressed)}):")
        for item in regressed:
            print(f"  {item['sample_id']}:")
            print(f"    OLD: {item['prev_answer']} -> NEW: {item['new_answer']} (gold: {item['gold']})")

        print(f"\nUNCHANGED ({len(unchanged)}):")
        for sid in unchanged:
            new = new_by_id.get(sid)
            if new:
                status = "still wrong" if not getattr(new, "is_correct", False) else "still correct"
                print(f"  {sid}: {status} (pred: {getattr(new, 'predicted_answer', '')}, gold: {getattr(new, 'gold_answer', '')})")

        # Save comparison
        comparison = {
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
            "summary": {
                "improved_count": len(improved),
                "regressed_count": len(regressed),
                "unchanged_count": len(unchanged),
                "net_improvement": len(improved) - len(regressed),
            }
        }
        comparison_file = os.path.join(results_dir, "comparison.json")
        with open(comparison_file, "w") as f:
            json.dump(comparison, f, indent=2)

    print(f"\nResults saved to: {results_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
