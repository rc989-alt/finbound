#!/usr/bin/env python3
"""
Run FinBound end-to-end on UnifiedSample datasets (FinQA/TAT-QA) using the new
prompt builder integration.
"""

import argparse
import json
from pathlib import Path

from finbound import FinBound
from finbound.data import FinQALoader, TATQALoader
from finbound.data.unified import to_unified


DATASETS = {
    "finqa": FinQALoader,
    "tatqa": TATQALoader,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinBound on UnifiedSample datasets.")
    parser.add_argument("--dataset", choices=DATASETS.keys(), default="finqa")
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--task-family", default="F1")
    parser.add_argument("--output", type=Path, default=Path("results/unified_runs.jsonl"))
    args = parser.parse_args()

    loader_cls = DATASETS[args.dataset]
    loader = loader_cls(split=args.split)
    fb = FinBound()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for idx, sample in enumerate(loader.iter_samples()):
            if args.limit is not None and idx >= args.limit:
                break
            unified = to_unified(sample)
            result = fb.run_unified_sample(unified, task_family=args.task_family)
            record = {
                "dataset": args.dataset,
                "sample_id": unified.id,
                "question": unified.question,
                "answer": result.answer,
                "verified": result.verified,
                "citations": result.citations,
                "layer1_issues": result.raw_model_output.get("layer1_issues"),
                "layer2_issues": result.raw_model_output.get("layer2_issues"),
            }
            f.write(json.dumps(record) + "\n")
            print(f"[INFO] Processed {args.dataset} sample {unified.id}")


if __name__ == "__main__":
    main()

