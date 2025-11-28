#!/usr/bin/env python3
"""Test FinBound FULL mode on GPT-4 v5 failed samples."""

import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from experiments.eval_harness import EvalHarness
from experiments.run_experiments import load_curated_samples, finbound_runner

# Failed sample IDs from GPT-4 v5 (30 samples)
GPT4_FAILED_SAMPLE_IDS = [
    "ABMD/2009/page_56.pdf-1",
    "SLB/2012/page_44.pdf-2",
    "FBHS/2017/page_23.pdf-1",
    "FRT/2005/page_117.pdf-2",
    "PNC/2013/page_62.pdf-2",
    "ABMD/2006/page_75.pdf-1",
    "AMAT/2013/page_18.pdf-2",
    "94ef7822-a201-493e-b557-a640f4ea4d83",
    "a983501d-2eec-486d-9661-e520c7c8af5e",
    "1238d807-aa57-48a3-93b6-591873788625",
    "a9ecc9dd-8348-43b1-a968-e456e1cd2040",
    "889488f7-d2a4-4612-b146-a5dd3db8ff2e",
    "191c3926-7356-4ab8-a8f9-41e7b7c8a492",
    "ecf25a96-a643-4bed-a0bb-c6eaf4999269",
    "af49c57c-91aa-4e69-b3e7-1df2d762b250",
    "34144864-790c-4733-8323-91347f68f5ef",
    "d7bcc322-bec2-4dba-8a02-fd65d023c655",
    "73693527-ed4b-4d07-941e-0e654095a43d",
    "e151e953-f5ab-4041-8e6f-7aec08ed5a60",
    "3502f875-f816-4a00-986c-fef9b08c0f96",
    "df12359b-c35a-4c26-bfbf-a8c05f063be9",
    "e302a7ec-94e5-4bea-bff4-5d4b9d4f6265",
    "8cb754f8-8411-4846-b6f8-8e2467ce08f3",
    "a0414f81-8dc2-44b2-a441-2c9d9c805c4d",
    "bf7abd62-d9cd-48d2-8826-1457684019a3",
    "4d259081-6da6-44bd-8830-e4de0031744c",
    "dc5e217a-a7b3-4fc9-ac0f-13d328f26b20",
    "7cd3aedf-1291-4fea-bc9d-a25c65727b7b",
    "22e20f25-669a-46b9-8779-2768ba391955",
    "2067daa1-9905-456b-bcbf-42bc66b47259",
]


def main():
    # Create eval harness - FULL mode output
    harness = EvalHarness(output_dir=str(PROJECT_ROOT / "experiments" / "gpt4_failed_finbound_full"))

    # Register FinBound method (FULL mode - with verification, low_latency=False)
    harness.register_method("finbound_full", finbound_runner(model="gpt-4o", max_retries=2, low_latency_mode=False))

    # Load curated samples from F1_UPDATED
    samples = load_curated_samples("F1_UPDATED", limit=None)

    # Filter to only GPT-4 failed samples
    filtered_samples = [s for s in samples if s.id in GPT4_FAILED_SAMPLE_IDS]

    print(f"Found {len(filtered_samples)} GPT-4 failed samples to test with FinBound FULL mode")
    print(f"Sample IDs: {[s.id for s in filtered_samples]}")

    if not filtered_samples:
        print("No samples found! Check if IDs are correct.")
        return

    # Run evaluation
    print("\nRunning FinBound FULL mode on GPT-4 failed samples...")
    results = harness.run_evaluation(
        samples=filtered_samples,
        task_family="F1",
        methods=["finbound_full"],
    )

    # Print results
    print("\n" + "=" * 60)
    print("FinBound FULL Mode Results on GPT-4 Failed Samples")
    print("=" * 60)

    correct = 0
    for r in results:
        status = "+" if r.is_correct else "-"
        print(f"\n{status} {r.sample_id}")
        print(f"   Gold: {r.gold_answer}")
        print(f"   Predicted: {r.predicted_answer}")
        print(f"   Latency: {r.latency_ms:.0f}ms")
        if r.is_correct:
            correct += 1

    print(f"\n{'=' * 60}")
    print(f"FinBound FULL on GPT-4 failures: {correct}/{len(results)} ({100*correct/len(results):.1f}%)")
    print(f"(GPT-4 got 0/{len(results)} on these samples)")


if __name__ == "__main__":
    main()
