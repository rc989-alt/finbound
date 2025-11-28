from __future__ import annotations

from typing import List


class TableParser:
    """
    Minimal table parser that normalizes FinQA-style tables into strings.
    """

    def normalize(self, table: List[List[str]]) -> List[List[str]]:
        normalized: List[List[str]] = []
        for row in table:
            normalized.append([self._clean_cell(cell) for cell in row])
        return normalized

    def _clean_cell(self, cell: str) -> str:
        return str(cell).replace("\n", " ").strip()

