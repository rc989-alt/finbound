from __future__ import annotations

from dataclasses import dataclass

from ...types import VerificationResult


@dataclass
class RetryHandler:
    max_retries: int = 0

    def should_retry(self, verification_result: VerificationResult, attempt: int) -> bool:
        if verification_result.verified:
            return False
        return attempt <= self.max_retries
