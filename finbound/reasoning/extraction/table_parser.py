from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StructuredTable:
    headers: List[str]
    rows: List[List[str]]  # Each row: [label, value1, value2, ...]

    def to_markdown(self) -> str:
        if not self.rows:
            return ""
        header_line = " | ".join(["Row #", "Label", *self.headers])
        separator = " | ".join(["---"] * (len(self.headers) + 2))
        body_lines = []
        for idx, row in enumerate(self.rows, start=1):
            label = row[0] if row else ""
            values = row[1:]
            padded = values + [""] * (len(self.headers) - len(values))
            body_lines.append(
                " | ".join(
                    [str(idx), label or "", *[cell or "" for cell in padded]]
                )
            )
        return "\n".join([header_line, separator, *body_lines])


class StructuredTableParser:
    """Utility to normalize EvidenceContext tables into structured form."""

    def parse(self, table: List[List[str]]) -> StructuredTable:
        if not table:
            return StructuredTable(headers=[], rows=[])

        headers = [self._clean_cell(cell) for cell in table[0]]
        data_rows: List[List[str]] = []
        for row in table[1:]:
            cleaned_row = [self._clean_cell(cell) for cell in row]
            if not cleaned_row:
                continue
            label = cleaned_row[0]
            values = cleaned_row[1:]
            data_rows.append([label, *values])
        return StructuredTable(headers=headers[1:], rows=data_rows)

    def to_markdown(self, table: List[List[str]]) -> str:
        structured = self.parse(table)
        return structured.to_markdown()

    def _clean_cell(self, cell: str) -> str:
        return str(cell).replace("\n", " ").strip()
