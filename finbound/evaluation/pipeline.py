from __future__ import annotations

import yaml
from pathlib import Path
from typing import List

from ..experiments.eval_harness import EvalHarness, load_test_samples
from .benchmark import FinBoundBench, BenchmarkConfig


def run_benchmark(config_path: str | Path) -> dict:
    config_data = yaml.safe_load(Path(config_path).read_text())
    task_configs = [Path(p) for p in config_data["task_configs"]]
    methods: List[str] = config_data.get("methods", ["finbound"])

    harness = EvalHarness()
    bench = FinBoundBench(harness)
    result = bench.run(BenchmarkConfig(task_configs=task_configs, methods=methods))
    harness.print_summary()
    return result
