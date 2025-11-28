from __future__ import annotations

from typing import List


class TextExtractor:
    """
    Utility for extracting clean paragraphs from raw SEC filings or dataset snippets.
    """

    def extract_paragraphs(self, text: str, min_length: int = 40) -> List[str]:
        paragraphs: List[str] = []
        for block in text.split("\n\n"):
            normalized = " ".join(block.split())
            if len(normalized) >= min_length:
                paragraphs.append(normalized)
        return paragraphs

