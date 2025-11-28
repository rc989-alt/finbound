#!/usr/bin/env python3
"""Test GPT-5-nano on multi-step questions that both FinBound and GPT-4 struggle with."""

import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from experiments.eval_harness import EvalHarness
from experiments.run_experiments import load_curated_samples

# Multi-step questions that both methods failed on
MULTI_STEP_SAMPLE_IDS = [
    # FinQA - Off by 1000 (5-value average)
    "ALXN/2007/page_104.pdf-1",  # Gold: 4441, FinBound: 3441.4, GPT-4: 3441

    # TAT-QA - Complex formulas
    "a983501d-2eec-486d-9661-e520c7c8af5e",  # Gold: 3728, avg difference EBITDA
    "a9ecc9dd-8348-43b1-a968-e456e1cd2040",  # Gold: 58.43, percentage of total
    "22e20f25-669a-46b9-8779-2768ba391955",  # Gold: 547.5, change between averages

    # TAT-QA - Complex inference
    "af49c57c-91aa-4e69-b3e7-1df2d762b250",  # Gold: 12.47, R&D from percentage
    "3502f875-f816-4a00-986c-fef9b08c0f96",  # Gold: -168630, COGS calculation

    # Sum vs list
    "PNC/2013/page_62.pdf-2",  # Gold: 3576, sum of two years
]


def main():
    # Create eval harness
    harness = EvalHarness(output_dir=str(PROJECT_ROOT / "experiments" / "nano_multistep"))

    # Register GPT-5-nano method
    from experiments.baselines import gpt5nano_zeroshot_runner
    harness.register_method("gpt5nano", gpt5nano_zeroshot_runner(model="gpt-5-nano"))

    # Load curated samples from F1_UPDATED
    samples = load_curated_samples("F1_UPDATED", limit=None)

    # Filter to only multi-step samples
    filtered_samples = [s for s in samples if s.id in MULTI_STEP_SAMPLE_IDS]

    print(f"Found {len(filtered_samples)} multi-step samples to test")
    print(f"Sample IDs: {[s.id for s in filtered_samples]}")

    if not filtered_samples:
        print("No samples found! Check if IDs are correct.")
        return

    # Run evaluation
    print("\nRunning GPT-5-nano on multi-step questions...")
    results = harness.run_evaluation(
        samples=filtered_samples,
        task_family="F1",  # F1 task family for numerical accuracy
        methods=["gpt5nano"],
    )

    # Print results
    print("\n" + "=" * 60)
    print("GPT-5-nano Results on Multi-Step Questions")
    print("=" * 60)

    correct = 0
    for r in results:
        status = "✓" if r.is_correct else "✗"
        print(f"\n{status} {r.sample_id}")
        print(f"   Gold: {r.gold_answer}")
        print(f"   Predicted: {r.predicted_answer}")
        print(f"   Latency: {r.latency_ms:.0f}ms")
        if r.is_correct:
            correct += 1

    print(f"\n{'=' * 60}")
    print(f"Accuracy: {correct}/{len(results)} ({100*correct/len(results):.1f}%)")


if __name__ == "__main__":
    main()
