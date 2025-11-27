from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional

from ..data.unified import UnifiedSample


@dataclass
class TaskResult:
    task_name: str
    sample_id: str
    verified: bool
    issues: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTask(ABC):
    name: str
    task_family: str

    def __init__(self, limit: Optional[int] = None) -> None:
        self.limit = limit

    @abstractmethod
    def iter_samples(self) -> Iterable[UnifiedSample]:
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(limit={self.limit})"
