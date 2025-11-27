from __future__ import annotations

from typing import Dict, Type

from .base import BaseTask
from .f1_ground_truth import F1GroundTruthTask
from .f2_retrieval import F2RetrievalConsistencyTask
from .f3_explanation import F3ExplanationVerificationTask
from .f4_scenario import F4ScenarioConsistencyTask

TASK_REGISTRY: Dict[str, Type[BaseTask]] = {
    "f1": F1GroundTruthTask,
    "f2": F2RetrievalConsistencyTask,
    "f3": F3ExplanationVerificationTask,
    "f4": F4ScenarioConsistencyTask,
}


def create_task(name: str, **kwargs) -> BaseTask:
    task_cls = TASK_REGISTRY.get(name.lower())
    if not task_cls:
        raise ValueError(f"Unknown task '{name}'.")
    return task_cls(**kwargs)
