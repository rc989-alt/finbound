"""TAT-QA dataset loader for hybrid tabular and textual financial QA.

TAT-QA structure (from https://github.com/NExTplusplus/TAT-QA):
- Each document has: table, paragraphs, questions
- Each question has: answer, answer_type, scale, derivation, answer_from
- answer_type: span, multi-span, count, arithmetic
- answer_from: table, text, table-text
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal

from .base import BaseLoader
from ..processors.table_parser import TableParser


@dataclass
class TATQASample:
    """A single TAT-QA sample with hybrid table-text evidence."""

    question: str
    answer: str
    answer_type: str  # span, multi-span, count, arithmetic
    scale: str  # "", thousand, million, billion, percent
    derivation: str  # arithmetic expression if applicable
    answer_from: str  # table, text, table-text
    paragraphs: List[str]
    table: List[List[str]]
    table_id: str
    question_id: str
    doc_id: str

    @property
    def scaled_answer(self) -> str:
        """Return answer with scale suffix if applicable."""
        if not self.scale:
            return self.answer
        return f"{self.answer} {self.scale}"


class TATQALoader(BaseLoader[TATQASample]):
    """
    Loader for TAT-QA dataset (Tabular And Textual QA).

    TAT-QA contains hybrid questions requiring reasoning over both
    tables and text from financial reports.

    Dataset files expected:
        data/raw/TAT-QA/dataset_raw/
        ├── tatqa_dataset_train.json
        ├── tatqa_dataset_dev.json
        └── tatqa_dataset_test.json

    Download from: https://github.com/NExTplusplus/TAT-QA

    Filtering options for task families:
        - answer_type: "arithmetic", "span", "multi-span", "count"
        - answer_from: "table", "text", "table-text"

    Task Family Recommendations:
        - F1 (Ground-Truth): answer_type="arithmetic" (numeric calculations)
        - F2 (Retrieval): answer_from="table-text" (multi-source retrieval)
        - F3 (Explanation): answer_type in ["span", "multi-span"] (text extraction)
        - F4 (Scenario): answer_type="arithmetic" with scale (unit reasoning)
    """

    SPLIT_FILES = {
        "train": "tatqa_dataset_train.json",
        "dev": "tatqa_dataset_dev.json",
        "test": "tatqa_dataset_test.json",
    }

    # Predefined filters for task families
    TASK_FILTERS = {
        "F1": {"answer_type": ["arithmetic"]},  # Numeric ground-truth
        "F2": {"answer_from": ["table-text"]},  # Multi-source retrieval
        "F3": {"answer_type": ["span", "multi-span"]},  # Text extraction
        "F4": {"answer_type": ["arithmetic"], "has_scale": True},  # Scenario with units
    }

    def __init__(
        self,
        dataset_dir: str | Path = "data/raw/TAT-QA/dataset_raw",
        split: Literal["train", "dev", "test"] = "train",
        answer_type: str | List[str] | None = None,
        answer_from: str | List[str] | None = None,
        has_scale: bool | None = None,
        task_filter: str | None = None,
    ) -> None:
        """
        Initialize TAT-QA loader with optional filtering.

        Args:
            dataset_dir: Path to TAT-QA dataset
            split: Dataset split (train, dev, test)
            answer_type: Filter by answer type(s): "arithmetic", "span", "multi-span", "count"
            answer_from: Filter by evidence source(s): "table", "text", "table-text"
            has_scale: If True, only include samples with scale (thousand, million, etc.)
            task_filter: Use predefined filter for task family ("F1", "F2", "F3", "F4")
        """
        super().__init__(dataset_dir)
        self.split = split
        self._table_parser = TableParser()
        self._cache: List[TATQASample] | None = None

        # Apply task filter if specified
        if task_filter and task_filter in self.TASK_FILTERS:
            filter_config = self.TASK_FILTERS[task_filter]
            answer_type = answer_type or filter_config.get("answer_type")
            answer_from = answer_from or filter_config.get("answer_from")
            has_scale = has_scale if has_scale is not None else filter_config.get("has_scale")

        # Normalize filter values to lists
        self._answer_type_filter = [answer_type] if isinstance(answer_type, str) else answer_type
        self._answer_from_filter = [answer_from] if isinstance(answer_from, str) else answer_from
        self._has_scale_filter = has_scale

    def load(self, index: int = 0) -> TATQASample:
        samples = self._load_all()
        return samples[index % len(samples)]

    def iter_samples(self) -> Iterable[TATQASample]:
        yield from self._load_all()

    def __len__(self) -> int:
        return len(self._load_all())

    def _load_all(self) -> List[TATQASample]:
        if self._cache is not None:
            return self._cache

        filename = self.SPLIT_FILES.get(self.split, f"tatqa_dataset_{self.split}.json")
        path = self.dataset_dir / filename

        if not path.exists():
            raise FileNotFoundError(
                f"TAT-QA dataset not found at {path}. "
                f"Download from https://github.com/NExTplusplus/TAT-QA"
            )

        with path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self._cache = []
        for doc in raw_data:
            doc_samples = self._parse_document(doc)
            # Apply filters
            for sample in doc_samples:
                if self._matches_filter(sample):
                    self._cache.append(sample)

        return self._cache

    def _matches_filter(self, sample: TATQASample) -> bool:
        """Check if sample matches the configured filters."""
        # Filter by answer_type
        if self._answer_type_filter:
            if sample.answer_type not in self._answer_type_filter:
                return False

        # Filter by answer_from
        if self._answer_from_filter:
            if sample.answer_from not in self._answer_from_filter:
                return False

        # Filter by has_scale
        if self._has_scale_filter is True:
            if not sample.scale:  # Empty string means no scale
                return False
        elif self._has_scale_filter is False:
            if sample.scale:  # Has scale but we want no scale
                return False

        return True

    def _parse_document(self, doc: Dict[str, Any]) -> List[TATQASample]:
        """Parse a TAT-QA document into individual QA samples."""
        samples: List[TATQASample] = []

        # Extract table
        table_raw = doc.get("table", {})
        table_id = table_raw.get("uid", "")
        table_data = table_raw.get("table", [])
        table = self._table_parser.normalize(table_data)

        # Extract paragraphs
        paragraphs_raw = doc.get("paragraphs", [])
        paragraphs = [p.get("text", "") for p in paragraphs_raw if p.get("text")]

        # Parse each question
        questions = doc.get("questions", [])
        for q in questions:
            sample = self._parse_question(q, table, table_id, paragraphs)
            if sample:
                samples.append(sample)

        return samples

    def _parse_question(
        self,
        q: Dict[str, Any],
        table: List[List[str]],
        table_id: str,
        paragraphs: List[str],
    ) -> TATQASample | None:
        """Parse a single question entry."""
        question = q.get("question", "")
        if not question:
            return None

        # TAT-QA answers can be list (multi-span) or single value
        answer_raw = q.get("answer", "")
        if isinstance(answer_raw, list):
            answer = ", ".join(str(a) for a in answer_raw)
        else:
            answer = str(answer_raw)

        return TATQASample(
            question=question,
            answer=answer,
            answer_type=q.get("answer_type", "span"),
            scale=q.get("scale", ""),
            derivation=q.get("derivation", ""),
            answer_from=q.get("answer_from", ""),
            paragraphs=paragraphs,
            table=table,
            table_id=table_id,
            question_id=q.get("uid", ""),
            doc_id=str(q.get("order", "")),
        )
