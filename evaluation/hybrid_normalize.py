from __future__ import annotations

import re
from typing import Any, Dict, List

from jsonpath_ng import parse as parse_jsonpath  # type: ignore[import-not-found]


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(
    text: str,
    *,
    trim: bool = True,
    casefold: bool = True,
    collapse_whitespace: bool = True,
) -> str:
    """Normalize text values so lexical comparison is deterministic."""

    out = text
    if trim:
        out = out.strip()
    if collapse_whitespace:
        out = _WHITESPACE_RE.sub(" ", out)
    if casefold:
        out = out.casefold()
    return out


def normalize_scalar(value: Any, *, casefold_strings: bool = True) -> Any:
    if isinstance(value, str):
        return normalize_text(value, casefold=casefold_strings)
    return value


def normalize_json_value(value: Any, *, casefold_strings: bool = True) -> Any:
    """Recursively normalize nested JSON values for stable matching."""

    if isinstance(value, dict):
        return {
            str(k): normalize_json_value(v, casefold_strings=casefold_strings)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [normalize_json_value(v, casefold_strings=casefold_strings) for v in value]
    return normalize_scalar(value, casefold_strings=casefold_strings)


def extract_values_by_jsonpath(payload: Dict[str, Any], path: str) -> List[Any]:
    """Extract values for a JSONPath expression; return empty on parse errors."""

    try:
        expr = parse_jsonpath(path)
    except Exception:
        return []
    return [match.value for match in expr.find(payload)]
