from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..loaders.base import BaseLoader


@dataclass
class CorpusDocument:
    doc_id: str
    text: str
    metadata: dict


class CorpusBuilder:
    """
    Simple in-memory corpus builder for experimentation.
    """

    def __init__(self) -> None:
        self.documents: List[CorpusDocument] = []

    def ingest(self, loader: BaseLoader, field: str = "question", limit: int | None = None) -> None:
        for idx, sample in enumerate(loader.iter_samples()):
            if limit is not None and idx >= limit:
                break
            text = getattr(sample, field, "") or ""
            metadata = sample.__dict__.copy()
            self.documents.append(
                CorpusDocument(
                    doc_id=f"{sample.__class__.__name__}-{idx}",
                    text=text,
                    metadata=metadata,
                )
            )

    def __iter__(self):
        return iter(self.documents)
