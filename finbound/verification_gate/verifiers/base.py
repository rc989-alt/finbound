from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ...types import EvidenceContext, ReasoningResult, StructuredRequest


class BaseVerifier(ABC):
    @abstractmethod
    def verify(
        self,
        request: StructuredRequest,
        reasoning_result: ReasoningResult,
        evidence_context: EvidenceContext | None,
    ) -> List[str]:
        raise NotImplementedError
