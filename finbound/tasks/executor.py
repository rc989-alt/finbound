from __future__ import annotations

from typing import Iterable, List

from ..core import FinBound
from ..tracking import MlflowLogger
from .base import BaseTask, TaskResult


class TaskExecutor:
    def __init__(self, finbound: FinBound, logger: MlflowLogger | None = None) -> None:
        self.finbound = finbound
        self.logger = logger or MlflowLogger()

    def run(self, task: BaseTask) -> List[TaskResult]:
        results: List[TaskResult] = []
        for sample in task.iter_samples():
            fb_result = self.finbound.run_unified_sample(
                sample, task_family=task.task_family
            )
            result = TaskResult(
                task_name=task.name,
                sample_id=sample.id,
                verified=fb_result.verified,
                issues={
                    "verification": fb_result.verification_result.issues,
                    "layer1": fb_result.raw_model_output.get("layer1_issues"),
                    "layer2": fb_result.raw_model_output.get("layer2_issues"),
                },
                metadata={
                    "question": sample.question,
                    "source": sample.source,
                },
            )
            results.append(result)
            self.logger.log_task_result(result.__dict__)

        summary = {
            "task": task.name,
            "total": len(results),
            "verified": sum(1 for r in results if r.verified),
            "failed": sum(1 for r in results if not r.verified),
        }
        self.logger.log_task_summary(summary)
        return results
