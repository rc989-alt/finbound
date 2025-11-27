from __future__ import annotations

from typing import Iterable, Optional, Type

from ..data import FinQALoader, TATQALoader
from ..data.unified import UnifiedSample, to_unified


def iter_unified_samples(
    loader_cls: Type,
    dataset_dir: Optional[str] = None,
    split: str = "train",
    limit: Optional[int] = None,
) -> Iterable[UnifiedSample]:
    loader_kwargs = {"split": split}
    if dataset_dir:
        loader_kwargs["dataset_dir"] = dataset_dir
    loader = loader_cls(**loader_kwargs)
    for idx, sample in enumerate(loader.iter_samples()):
        if limit is not None and idx >= limit:
            break
        yield to_unified(sample)

