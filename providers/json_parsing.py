from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


def parse_json_object_text(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse a JSON object from provider text output.

    Handles common provider formatting, including markdown fences like:
    ```json
    { ... }
    ```
    """

    candidates = _candidate_json_strings(text)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed, None
        return None, "Parsed JSON is not an object"

    return None, "JSON decode error: unable to parse object from provider response"


def _candidate_json_strings(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []

    if stripped:
        candidates.append(stripped)

    unfenced = _remove_markdown_fences(stripped)
    if unfenced and unfenced not in candidates:
        candidates.append(unfenced)

    bracket_slice = _extract_outer_brace_object(unfenced)
    if bracket_slice and bracket_slice not in candidates:
        candidates.append(bracket_slice)

    return candidates


def _remove_markdown_fences(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if not lines:
        return text

    # Remove opening fence (``` or ```json) and trailing closing fence.
    body = lines[1:]
    if body and body[-1].strip() == "```":
        body = body[:-1]
    return "\n".join(body).strip()


def _extract_outer_brace_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1].strip()
