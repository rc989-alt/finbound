from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Citation:
    """Lightweight citation representation."""

    text: str
    source: str | None = None
    location: str | None = None

