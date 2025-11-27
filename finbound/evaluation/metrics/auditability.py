from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuditabilityMetric:
    logged_runs: int = 0
    total_count: int = 0

    def update(self, raw_output: dict) -> None:
        self.total_count += 1
        if raw_output.get("layer1_issues") is not None:
            self.logged_runs += 1

    @property
    def value(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.logged_runs / self.total_count
