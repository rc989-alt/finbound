from __future__ import annotations

import json
import re


def normalize_answer(answer: str) -> str:
    """
    Normalize numeric answers to benchmark-friendly format.
    - Extracts answer from JSON if LLM returned raw JSON
    - Removes trailing punctuation
    - Ensures consistent decimal precision (max 2 decimals)
    - Preserves percentage/currency suffixes
    """
    if not answer:
        return answer

    text = answer.strip()
    if not text:
        return text

    # Fix 1: Extract answer from JSON response if LLM returned raw JSON
    text = _extract_from_json(text)

    suffix_match = re.search(r"(million|billion|thousand|%)$", text, re.IGNORECASE)
    suffix = ""
    if suffix_match:
        suffix = suffix_match.group(0)
        text = text[: -len(suffix)].strip()

    text = text.rstrip(".")
    try:
        value = float(text.replace(",", "").replace("$", ""))
        normalized = f"{value:.2f}".rstrip("0").rstrip(".")
        if "$" in answer:
            normalized = f"${normalized}"
        if suffix:
            normalized = f"{normalized} {suffix}".strip()
        return normalized
    except ValueError:
        return answer.strip()


def _extract_from_json(text: str) -> str:
    """Extract answer value from JSON response if LLM returned raw JSON."""
    # Check if response looks like JSON (starts with ``` or {)
    stripped = text.strip()

    # Handle markdown code blocks
    if stripped.startswith("```"):
        # Remove ```json or ``` prefix and trailing ```
        lines = stripped.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```") and not in_block:
                in_block = True
                continue
            elif line.strip() == "```":
                break
            elif in_block:
                json_lines.append(line)
        stripped = "\n".join(json_lines)

    # Try to parse as JSON
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            # Look for common answer field names
            for key in ["answer", "result", "value", "final_answer"]:
                if key in data:
                    val = data[key]
                    # Handle numeric values
                    if isinstance(val, (int, float)):
                        return str(val)
                    # Handle string values
                    if isinstance(val, str):
                        return val
            # If no answer field found, return original
            return text
        except json.JSONDecodeError:
            return text

    return text
