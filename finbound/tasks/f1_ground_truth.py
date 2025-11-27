from __future__ import annotations

from typing import Iterable, Optional

from ..data import FinQALoader
from ..data.unified import UnifiedSample, to_unified
from .base import BaseTask
from .common import iter_unified_samples


class F1GroundTruthTask(BaseTask):
    name = "F1_GroundTruth"
    task_family = "F1"

    def __init__(
        self,
        dataset_dir: Optional[str] = None,
        split: str = "train",
        limit: Optional[int] = None,
    ) -> None:
        super().__init__(limit=limit)
        self.dataset_dir = dataset_dir
        self.split = split

    def iter_samples(self) -> Iterable[UnifiedSample]:
        yield from iter_unified_samples(
            FinQALoader,
            dataset_dir=self.dataset_dir,
            split=self.split,
            limit=self.limit,
        )
