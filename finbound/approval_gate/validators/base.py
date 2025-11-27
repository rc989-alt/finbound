from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ...types import StructuredRequest


class BaseValidator(ABC):
    """Abstract validator contract."""

    name: str = "base"

    @abstractmethod
    def validate(self, request: StructuredRequest) -> List[str]:
        """Return a list of policy violation messages."""
        raise NotImplementedError
