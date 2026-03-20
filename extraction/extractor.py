from __future__ import annotations

from typing import Any, Dict, List, Optional

from providers.openai_provider import run_openai
from providers.gemini_provider import run_gemini

# Expected extraction output schema: each field must be a list of strings.
_EXPECTED_FIELDS: List[str] = ["methods", "tasks", "datasets"]


def validate_extraction_schema(parsed: Dict[str, Any]) -> Optional[str]:
    """Validate parsed extraction output against the expected schema.

    Returns an error message string if validation fails, or None on success.
    """
    for field in _EXPECTED_FIELDS:
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
) -> Dict[str, Any]:
    """Route extraction to the selected provider and normalize the payload."""

    kwargs = dict(
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )

    if provider == "openai":
        result = run_openai(prompt, model=model or "gpt-4o-mini", **kwargs)
    elif provider == "gemini":
        result = run_gemini(prompt, model=model or "gemini-1.5-pro", **kwargs)
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. Supported values: 'openai', 'gemini'."
        )

    # 3.4 — explicit schema validation at the normalization boundary
    if result["parse_status"] == "success":
        schema_error = validate_extraction_schema(result["parsed_output_json"])
        if schema_error:
            result["parse_status"] = "schema_error"
            result["error_message"] = schema_error
            result["parsed_output_json"] = {}

    return result
