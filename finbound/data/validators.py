from __future__ import annotations

from typing import Iterable, List


def validate_required_fields(record: dict, fields: Iterable[str]) -> List[str]:
    missing = [field for field in fields if not record.get(field)]
    return missing


def assert_required_fields(record: dict, fields: Iterable[str]) -> None:
    missing = validate_required_fields(record, fields)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
