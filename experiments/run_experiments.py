#!/usr/bin/env python3
"""
Run FinBound experiments with fair baseline comparison.

Usage:
    # Run with curated samples (recommended for fair evaluation)
    python experiments/run_experiments.py --methods finbound --task F1 --curated --limit 10

    # Run with full dataset (for exploration)
    python experiments/run_experiments.py --methods finbound gpt4_zeroshot --task F1 --limit 10

    # Run from config
    python experiments/run_experiments.py --config experiments/configs/experiment_config.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import yaml

# Load environment variables from .env
load_dotenv()

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.eval_harness import EvalHarness, load_test_samples
from experiments.baselines import (
    gpt4_zeroshot_runner,
    gpt4_fewshot_runner,
    gpt5nano_zeroshot_runner,
    rag_no_verify_runner,
    deepseek_zeroshot_runner,
    claude_zeroshot_runner,
)
from experiments.baselines.finbound_runner import create_runner as finbound_runner

# Paths for curated samples
CURATED_SAMPLES_DIR = PROJECT_ROOT / "data" / "curated_samples"


def setup_methods(
    harness: EvalHarness,
    methods: List[str],
    model: str = "gpt-4o",
    low_latency_mode: bool = False,
) -> None:
    """Register methods with the evaluation harness."""
    method_factories = {
        "finbound": lambda: finbound_runner(model=model, max_retries=2, low_latency_mode=low_latency_mode),
        "gpt4_zeroshot": lambda: gpt4_zeroshot_runner(model=model),
        "gpt4_fewshot": lambda: gpt4_fewshot_runner(model=model),
        "gpt5nano_zeroshot": lambda: gpt5nano_zeroshot_runner(model="gpt-5-nano"),
        "rag_no_verify": lambda: rag_no_verify_runner(model=model),
        "deepseek_zeroshot": lambda: deepseek_zeroshot_runner(model="deepseek-chat"),
        "claude_zeroshot": lambda: claude_zeroshot_runner(model="claude-sonnet-4-20250514"),
    }

    for method in methods:
        if method not in method_factories:
            print(f"Warning: Unknown method '{method}', skipping")
            continue
        harness.register_method(method, method_factories[method]())


def run_from_config(config_path: str) -> None:
    """Run experiments from YAML config."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    harness = EvalHarness(output_dir=config["output"]["results_dir"])

    # Setup methods
    methods = list(config["methods"].keys())
    model = config["methods"].get("finbound", {}).get("model", "gpt-4o")
    setup_methods(harness, methods, model=model)

    # Dataset-Task Family mapping:
    # - F1: FinQA (all) + TAT-QA (arithmetic)
    # - F2: TAT-QA only (table-text) - FinQA has no answer_from tag
    # - F3: TAT-QA only (span/multi-span) - FinQA is 100% arithmetic
    # - F4: TAT-QA only (arithmetic+scale) - FinQA has no scale tag
    TASK_DATASET_SKIP = {
        "F2": ["finqa"],  # FinQA has no answer_from tag for retrieval filtering
        "F3": ["finqa"],  # FinQA is 100% arithmetic, no span questions
        "F4": ["finqa"],  # FinQA has no scale tag for unit reasoning
    }

    # Run on each task family
    for task in config["task_families"]:
        print(f"\n{'='*60}")
        print(f"Task Family: {task}")
        print(f"{'='*60}")

        skip_datasets = TASK_DATASET_SKIP.get(task, [])

        # Run on each dataset
        for dataset_name, dataset_config in config["datasets"].items():
            # Skip datasets that don't fit the task family
            if dataset_name in skip_datasets:
                print(f"\nSkipping {dataset_name} for {task} (not suitable)")
                continue

            limit = dataset_config.get("sample_limit")
            # Get task-specific filter for TAT-QA
            task_filter = task if dataset_name == "tatqa" else None

            for split in dataset_config["splits"]:
                print(f"\nLoading {dataset_name} ({split})" +
                      (f" with filter={task_filter}" if task_filter else ""))

                try:
                    samples = load_test_samples(
                        dataset_name,
                        split=split,
                        limit=limit,
                        task_filter=task_filter,
                    )
                    print(f"Loaded {len(samples)} samples")
                except Exception as e:
                    print(f"Warning: Could not load {dataset_name}/{split}: {e}")
                    continue

                print(f"Running {task} on {dataset_name}/{split}...")
                harness.run_evaluation(samples, task_family=task, methods=methods)

    # Save results
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = harness.save_results(run_id)
    print(f"\nResults saved to: {results_dir}")

    # Print summary
    harness.print_summary()


def load_curated_samples(task: str, limit: Optional[int] = None) -> List:
    """Load curated samples for a specific task family.

    Args:
        task: Task family (F1, F2, F3, F4)
        limit: Optional limit on number of samples

    Returns:
        List of UnifiedSample objects
    """
    from finbound.data import UnifiedSample, to_unified
    from finbound.data.loaders.finqa import FinQASample
    from finbound.data.loaders.tatqa import TATQASample

    task_dir = CURATED_SAMPLES_DIR / task
    if not task_dir.exists():
        raise FileNotFoundError(f"Curated samples not found for {task} at {task_dir}")

    samples = []

    # Load FinQA samples if available
    finqa_file = task_dir / "finqa_samples.json"
    if finqa_file.exists():
        with open(finqa_file) as f:
            finqa_data = json.load(f)
        print(f"  Loaded {len(finqa_data)} FinQA curated samples")

        # Need to load full context from original dataset
        from finbound.data import FinQALoader
        finqa_loader = FinQALoader(split="dev")
        finqa_by_id = {s.id: s for s in finqa_loader.iter_samples()}

        for item in finqa_data:
            sample_id = item["id"]
            if sample_id in finqa_by_id:
                samples.append(to_unified(finqa_by_id[sample_id]))
            else:
                print(f"  Warning: FinQA sample {sample_id} not found in dataset")

    # Load TAT-QA samples if available
    tatqa_file = task_dir / "tatqa_samples.json"
    if tatqa_file.exists():
        with open(tatqa_file) as f:
            tatqa_data = json.load(f)
        print(f"  Loaded {len(tatqa_data)} TAT-QA curated samples")

        # Need to load full context from original dataset
        from finbound.data import TATQALoader
        tatqa_loader = TATQALoader(split="dev")
        # TAT-QA uses question_id not id
        tatqa_by_id = {s.question_id: s for s in tatqa_loader.iter_samples()}

        for item in tatqa_data:
            sample_id = item["id"]
            if sample_id in tatqa_by_id:
                samples.append(to_unified(tatqa_by_id[sample_id]))
            else:
                print(f"  Warning: TAT-QA sample {sample_id} not found in dataset")

    if limit:
        samples = samples[:limit]

    return samples


def run_quick(
    methods: List[str],
    task: str,
    dataset: str = "finqa",
    split: str = "dev",
    limit: int = 10,
    model: str = "gpt-4o",
    use_task_filter: bool = True,
    use_curated: bool = False,
    output_dir: Optional[str] = None,
    low_latency_mode: bool = False,
) -> None:
    """Run quick experiment for testing.

    Args:
        methods: List of method names to evaluate
        task: Task family (F1, F2, F3, F4)
        dataset: Dataset name (finqa, tatqa) - ignored if use_curated=True
        split: Dataset split - ignored if use_curated=True
        limit: Maximum samples to load
        model: Model to use
        use_task_filter: If True and dataset is tatqa, apply task-specific filter
        use_curated: If True, use curated samples from data/curated_samples/{task}/
        output_dir: Custom output directory (default: experiments/{task}_result/all_methods)
        low_latency_mode: If True, enable low latency mode (fewer passes, skip verification)
    """
    # Set output directory - use custom or default based on task
    if output_dir:
        results_output_dir = Path(output_dir)
    else:
        results_output_dir = PROJECT_ROOT / "experiments" / f"{task}_result" / "all_methods"

    harness = EvalHarness(output_dir=str(results_output_dir))
    setup_methods(harness, methods, model=model, low_latency_mode=low_latency_mode)

    if low_latency_mode:
        print("Low latency mode enabled (1 extraction pass, skip verification)")

    if use_curated:
        print(f"Loading curated samples for {task}, limit={limit}")
        samples = load_curated_samples(task, limit=limit)
        print(f"Loaded {len(samples)} curated samples total")
    else:
        # Apply task filter for TAT-QA if enabled
        task_filter = task if (use_task_filter and dataset == "tatqa") else None

        print(f"Loading {dataset} ({split}), limit={limit}" +
              (f", filter={task_filter}" if task_filter else ""))
        samples = load_test_samples(dataset, split=split, limit=limit, task_filter=task_filter)
        print(f"Loaded {len(samples)} samples")

    print(f"\nRunning {task} with methods: {methods}")
    harness.run_evaluation(samples, task_family=task, methods=methods)

    # Save and print
    run_id = f"{'curated' if use_curated else 'quick'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    results_dir = harness.save_results(run_id)
    print(f"\nResults saved to: {results_dir}")
    harness.print_summary()


def main():
    parser = argparse.ArgumentParser(description="Run FinBound experiments")
    parser.add_argument("--config", type=str, help="Path to experiment config YAML")
    parser.add_argument("--methods", nargs="+", default=["finbound"],
                        help="Methods to evaluate")
    parser.add_argument("--task", type=str, default="F1", help="Task family (F1-F4)")
    parser.add_argument("--dataset", type=str, default="finqa", help="Dataset name")
    parser.add_argument("--split", type=str, default="dev", help="Dataset split")
    parser.add_argument("--limit", type=int, default=None, help="Sample limit (default: all samples)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model to use")
    parser.add_argument("--no-task-filter", action="store_true",
                        help="Disable task-based filtering for TAT-QA (use all samples)")
    parser.add_argument("--curated", action="store_true",
                        help="Use curated samples from data/curated_samples/{task}/")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Custom output directory (default: experiments/{task}_result/all_methods)")
    parser.add_argument("--low-latency", action="store_true",
                        help="Enable low latency mode (fewer passes, skip verification)")

    args = parser.parse_args()

    if args.config:
        run_from_config(args.config)
    else:
        run_quick(
            methods=args.methods,
            task=args.task,
            dataset=args.dataset,
            split=args.split,
            limit=args.limit,
            model=args.model,
            use_task_filter=not args.no_task_filter,
            use_curated=args.curated,
            output_dir=args.output_dir,
            low_latency_mode=args.low_latency,
        )


if __name__ == "__main__":
    main()
