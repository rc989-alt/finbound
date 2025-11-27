from __future__ import annotations

import re
from typing import List


def within_tolerance(
    a: float,
    b: float,
    rel_tolerance: float = 0.005,
    abs_tolerance: float = 1.0,
) -> bool:
    if a == b:
        return True
    if abs(a - b) <= abs_tolerance:
        return True
    if b != 0 and abs(a - b) / abs(b) <= rel_tolerance:
        return True
    return False


def extract_numbers(text: str) -> List[float]:
    if not text:
        return []
    matches = re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    numbers: List[float] = []
    for match in matches:
        try:
            numbers.append(float(match))
        except ValueError:
            continue
    return numbers
