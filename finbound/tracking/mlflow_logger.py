from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional


class MlflowLogger:
    """
    Optional MLflow logger for FinBound runs. Enabled by setting
    FINBOUND_ENABLE_MLFLOW=1 and installing the mlflow package.
    """

    def __init__(self) -> None:
        self._enabled = os.getenv("FINBOUND_ENABLE_MLFLOW", "0").lower() in (
            "1",
            "true",
            "yes",
        )
        self._mlflow = None
        self._run_name = os.getenv("FINBOUND_MLFLOW_RUN_NAME", "finbound")
        if self._enabled:
            try:
                import mlflow  # type: ignore

                self._mlflow = mlflow
            except Exception:
                self._enabled = False
                self._mlflow = None

    def log_tool_events(self, events: List[Dict[str, Any]]) -> None:
        if not (self._enabled and self._mlflow and events):
            return
        path = f"tool_events/{uuid.uuid4().hex}.json"
        self._log_dict({"events": events}, path)

    def log_retrieval_query(self, query_spec: Optional[Dict[str, Any]]) -> None:
        if not (self._enabled and self._mlflow and query_spec):
            return
        path = f"retrieval_queries/{uuid.uuid4().hex}.json"
        self._log_dict(query_spec, path)

    def log_verification(self, result: Dict[str, Any]) -> None:
        if not (self._enabled and self._mlflow):
            return
        path = f"verification/{uuid.uuid4().hex}.json"
        self._log_dict(result, path)

    def log_task_result(self, result: Dict[str, Any]) -> None:
        if not (self._enabled and self._mlflow):
            return
        path = f"tasks/{uuid.uuid4().hex}.json"
        self._log_dict(result, path)

    def log_task_summary(self, summary: Dict[str, Any]) -> None:
        if not (self._enabled and self._mlflow):
            return
        path = f"tasks/summary_{uuid.uuid4().hex}.json"
        self._log_dict(summary, path)

    def _log_dict(self, data: Dict[str, Any], artifact_path: str) -> None:
        assert self._mlflow is not None

        def action() -> None:
            self._mlflow.log_dict(data, artifact_path)

        active = self._mlflow.active_run()
        if active:
            action()
            return

        with self._mlflow.start_run(run_name=self._run_name):
            action()
