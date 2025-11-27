from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class TaskConfig:
    task: str
    dataset_dir: str | None
    split: str
    limit: int | None
    extra: Dict[str, Any]


def load_task_config(path: str | Path) -> TaskConfig:
    data = yaml.safe_load(Path(path).read_text())
    return TaskConfig(
        task=data["task"],
        dataset_dir=data.get("dataset_dir"),
        split=data.get("split", "train"),
        limit=data.get("limit"),
        extra={k: v for k, v in data.items() if k not in {"task", "dataset_dir", "split", "limit"}},
    )
