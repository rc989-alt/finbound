from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroundingAccuracy:
    total_score: float = 0.0
    sample_count: int = 0

    def update(self, score: float) -> None:
        self.total_score += score
        self.sample_count += 1

    @property
    def value(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.total_score / self.sample_count
