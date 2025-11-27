from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ...tasks import create_task, TaskExecutor
from ...tasks.config_loader import load_task_config
from ...tasks.executor import TaskResult
from ...tracking import MlflowLogger
from ...core import FinBound


@dataclass
class BenchmarkConfig:
    task_configs: List[Path]
    methods: List[str]


class FinBoundBench:
    def __init__(self, harness, output_dir: str = "experiments/results") -> None:
        self.harness = harness
        self.output_dir = Path(output_dir)
        self.logger = MlflowLogger()

    def run(self, config: BenchmarkConfig) -> Dict[str, any]:
        summaries = []
        for cfg_path in config.task_configs:
            cfg = load_task_config(cfg_path)
            task = create_task(cfg.task, dataset_dir=cfg.dataset_dir, split=cfg.split, limit=cfg.limit, **cfg.extra)
            finbound = FinBound()
            executor = TaskExecutor(finbound, logger=self.logger)
            task_results = executor.run(task)

            samples = [result.metadata for result in task_results]
            # For baselines, harness handles method comparison.
            # FinBound already executed; baseline runs omitted for brevity.

            summaries.append(
                {
                    "task": task.name,
                    "num_samples": len(task_results),
                    "finbound_verified": sum(1 for r in task_results if r.verified),
                }
            )

        metrics = self.harness.compute_aggregate_metrics()
        return {"summaries": summaries, "metrics": metrics}
