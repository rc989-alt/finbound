#!/usr/bin/env python3
"""
Run a FinBound task using a YAML configuration (Milestone 6).
"""

import argparse

from finbound import FinBound
from finbound.tasks import TaskExecutor
from finbound.tasks.config_loader import load_task_config
from finbound.tasks.registry import create_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a FinBound task from config YAML.")
    parser.add_argument("config", help="Path to task config YAML")
    parser.add_argument("--max-retries", type=int, default=0, help="Verification retry attempts")
    args = parser.parse_args()

    cfg = load_task_config(args.config)
    task = create_task(
        cfg.task,
        dataset_dir=cfg.dataset_dir,
        split=cfg.split,
        limit=cfg.limit,
        **cfg.extra,
    )

    fb = FinBound(max_retries=args.max_retries)
    executor = TaskExecutor(fb)
    results = executor.run(task)
    print(f"Completed task {task.name} on {len(results)} samples.")


if __name__ == "__main__":
    main()

