from __future__ import annotations

from typing import Any, Dict, List, Optional

from providers.openai_provider import run_openai
from providers.gemini_provider import run_gemini

# Expected extraction output schema: each field must be a list of strings.
_EXPECTED_FIELDS: List[str] = ["methods", "tasks", "datasets"]


def normalize_extraction_output(
    parsed: Dict[str, Any],
    expected_fields: Optional[List[str]] = None,
) -> tuple[Optional[Dict[str, List[str]]], Optional[str]]:
    """Normalize provider output into list[str] values for all expected fields.

    Normalization rules:
    - missing or null field -> []
    - string field -> [string]
    - list field -> list of strings (coerced with str)
    """

    fields = expected_fields or _EXPECTED_FIELDS
    normalized: Dict[str, List[str]] = {}

    for field in fields:
        value = parsed.get(field)
        if value is None:
            normalized[field] = []
            continue
        if isinstance(value, str):
            normalized[field] = [value]
            continue
        if isinstance(value, list):
            normalized[field] = [str(item) for item in value if item is not None]
            continue
        return None, (
            f"Field '{field}' must be a list, string, or null, got {type(value).__name__}."
        )

    return normalized, None


def validate_extraction_schema(
    parsed: Dict[str, Any],
    expected_fields: Optional[List[str]] = None,
) -> Optional[str]:
    """Validate parsed extraction output against the expected schema.

    Returns an error message string if validation fails, or None on success.
    """
    fields = expected_fields or _EXPECTED_FIELDS
    for field in fields:
        if field not in parsed:
            return f"Missing required field '{field}' in extraction output."
        value = parsed[field]
        if not isinstance(value, list):
            return f"Field '{field}' must be a list, got {type(value).__name__}."
        for i, item in enumerate(value):
            if not isinstance(item, str):
                return (
                    f"Field '{field}[{i}]' must be a string, got {type(item).__name__}."
                )
    return None


def run_extraction(
    provider: str,
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 2048,
    expected_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Route extraction to the selected provider and normalize the payload."""

    if provider == "openai":
        result = run_openai(
            prompt,
            model=model or "gpt-4o-mini",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
    elif provider == "gemini":
        result = run_gemini(
            prompt,
            model=model or "gemini-1.5-pro",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. Supported values: 'openai', 'gemini'."
        )

    # 3.4 — explicit schema validation at the normalization boundary
    if result["parse_status"] == "success":
        normalized_output, normalize_error = normalize_extraction_output(
            result["parsed_output_json"],
            expected_fields=expected_fields,
        )
        if normalize_error:
            result["parse_status"] = "schema_error"
            result["error_message"] = normalize_error
            result["parsed_output_json"] = {}
        else:
            assert normalized_output is not None
            result["parsed_output_json"] = normalized_output
            schema_error = validate_extraction_schema(
                normalized_output,
                expected_fields=expected_fields,
            )
            if schema_error:
                result["parse_status"] = "schema_error"
                result["error_message"] = schema_error
                result["parsed_output_json"] = {}

    return result
