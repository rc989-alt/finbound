from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HallucinationRate:
    hallucination_count: int = 0
    total_count: int = 0

    def update(self, hallucinated: bool) -> None:
        self.total_count += 1
        if hallucinated:
            self.hallucination_count += 1

    @property
    def value(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.hallucination_count / self.total_count
