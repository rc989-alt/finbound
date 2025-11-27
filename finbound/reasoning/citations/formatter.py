from __future__ import annotations

from typing import Iterable, List


def format_citation(snippets: Iterable[str]) -> List[str]:
    """Ensure citations are normalized strings."""
    formatted: List[str] = []
    for snippet in snippets:
        snippet = str(snippet).strip()
        if snippet:
            formatted.append(snippet)
    return formatted
