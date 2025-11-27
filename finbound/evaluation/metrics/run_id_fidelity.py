from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunIDFidelity:
    recorded_count: int = 0
    total_count: int = 0

    def update(self, raw_output: dict) -> None:
        self.total_count += 1
        if raw_output.get("tracking_run_id"):
            self.recorded_count += 1

    @property
    def value(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.recorded_count / self.total_count
