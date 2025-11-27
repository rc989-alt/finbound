from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TransparencyScore:
    sample_total: int = 0
    score_sum: float = 0.0

    def update(self, raw_output: dict) -> None:
        steps = raw_output.get("chain_of_evidence", {}).get("steps", [])
        if not steps:
            self.sample_total += 1
            return
        cited = sum(1 for step in steps if step.get("citations"))
        self.score_sum += cited / len(steps)
        self.sample_total += 1

    @property
    def value(self) -> float:
        if self.sample_total == 0:
            return 0.0
        return self.score_sum / self.sample_total
