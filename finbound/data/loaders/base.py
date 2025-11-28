from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class BaseLoader(ABC, Generic[T]):
    """
    Base interface for dataset loaders.
    """

    def __init__(self, dataset_dir: str | Path) -> None:
        self.dataset_dir = Path(dataset_dir)

    @abstractmethod
    def load(self, index: int = 0) -> T:
        raise NotImplementedError

    @abstractmethod
    def iter_samples(self) -> Iterable[T]:
        raise NotImplementedError
