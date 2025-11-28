from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .base import BaseLoader
from ..processors.table_parser import TableParser


@dataclass
class FinQASample:
    question: str
    answer: str
    context_snippets: List[str]
    evidence_texts: List[str]
    table: List[List[str]]
    steps: List[Dict[str, Any]]
    program: str
    program_result: float | None
    id: str
    filename: str
    issuer: str


class FinQALoader(BaseLoader[FinQASample]):
    def __init__(
        self,
        dataset_dir: str | Path = "data/raw/FinQA/dataset",
        split: str = "train",
    ) -> None:
        super().__init__(dataset_dir)
        self.split = split
        self._table_parser = TableParser()
        self._cache: List[Dict[str, Any]] | None = None

    def load(self, index: int = 0) -> FinQASample:
        data = self._load_split()
        sample = data[index % len(data)]
        return self._convert(sample)

    def iter_samples(self) -> Iterable[FinQASample]:
        data = self._load_split()
        for sample in data:
            yield self._convert(sample)

    def _load_split(self) -> List[Dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        path = self.dataset_dir / f"{self.split}.json"
        with path.open("r", encoding="utf-8") as f:
            self._cache = json.load(f)
        return self._cache

    def _convert(self, raw: Dict[str, Any]) -> FinQASample:
        qa = raw.get("qa", {})
        question = qa.get("question", "")
        answer = str(qa.get("answer", ""))
        pre_text = raw.get("pre_text", [])
        post_text = raw.get("post_text", [])

        table = raw.get("table") or raw.get("table_ori") or []
        table = self._table_parser.normalize(table)

        steps = qa.get("steps", [])
        program = qa.get("program", "")
        program_result = _execute_finqa_program(steps)
        evidence_texts = [chunk[1] for chunk in qa.get("model_input", [])]

        sample_id = raw.get("id", "")
        filename = raw.get("filename", "")
        issuer = filename.split("/", 1)[0] if filename else ""

        context_snippets: List[str] = []
        context_snippets.extend(pre_text[:3])
        context_snippets.extend(post_text[:2])

        return FinQASample(
            question=question,
            answer=answer,
            context_snippets=context_snippets,
            evidence_texts=evidence_texts,
            table=table,
            steps=steps,
            program=program,
            program_result=program_result,
            id=sample_id,
            filename=filename,
            issuer=issuer,
        )


def _parse_numeric_token(token: Any, values: List[float]) -> float | None:
    if isinstance(token, str) and token.startswith("#"):
        try:
            idx = int(token[1:])
        except ValueError:
            return None
        if 0 <= idx < len(values):
            return values[idx]
        return None

    text = str(token).replace(",", "").replace("$", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _execute_finqa_program(steps: List[Dict[str, Any]]) -> float | None:
    if not steps:
        return None

    values: List[float] = []
    for step in steps:
        op = str(step.get("op", "")).lower()
        arg1 = _parse_numeric_token(step.get("arg1"), values)
        arg2 = _parse_numeric_token(step.get("arg2"), values)
        if arg1 is None or arg2 is None:
            return None

        base_op = op.split("-")[0]
        if base_op.startswith("divide"):
            if arg2 == 0:
                return None
            res = arg1 / arg2
        elif base_op.startswith(("add", "plus")):
            res = arg1 + arg2
        elif base_op.startswith(("sub", "minus")):
            res = arg1 - arg2
        elif base_op.startswith(("mul", "times")):
            res = arg1 * arg2
        else:
            return None
        values.append(res)

    return values[-1] if values else None

