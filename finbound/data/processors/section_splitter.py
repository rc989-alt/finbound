from __future__ import annotations

import re
from typing import Dict, List

class SectionSplitter:
    """
    Splits a 10-K/10-Q style document into coarse sections based on headings.
    """

    HEADING_PATTERN = re.compile(r"^(Item\s+\d+[A-Z]?\.)\s*(.+)$", re.IGNORECASE)

    def split(self, text: str) -> Dict[str, str]:
        sections: Dict[str, List[str]] = {}
        current_heading = "Preamble"
        sections[current_heading] = []

        for line in text.splitlines():
            match = self.HEADING_PATTERN.match(line.strip())
            if match:
                current_heading = match.group(1).title()
                sections.setdefault(current_heading, [])
                continue
            sections[current_heading].append(line)

        return {heading: "\n".join(body).strip() for heading, body in sections.items()}
