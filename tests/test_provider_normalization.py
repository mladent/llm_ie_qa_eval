from __future__ import annotations

import pytest

from extraction.extractor import run_extraction, validate_extraction_schema


def test_validate_extraction_schema_missing_field() -> None:
    error = validate_extraction_schema({"methods": [], "tasks": []})
    assert error is not None
    assert "datasets" in error


def test_validate_extraction_schema_wrong_item_type() -> None:
    error = validate_extraction_schema(
        {"methods": ["A"], "tasks": [1], "datasets": []}
    )
    assert error is not None
    assert "tasks[0]" in error


def test_run_extraction_marks_schema_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_openai(*args, **kwargs):
        return {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "raw_response_text": "{}",
            "parsed_output_json": {"methods": ["A"], "tasks": ["T"]},
            "parse_status": "success",
            "error_message": None,
            "latency_ms": 10.0,
            "input_tokens": 1,
            "output_tokens": 1,
            "estimated_cost": 0.0,
            "model_params_used": {},
        }

    monkeypatch.setattr("extraction.extractor.run_openai", fake_openai)

    result = run_extraction("openai", "prompt", model="gpt-4o-mini")

    assert result["parse_status"] == "schema_error"
    assert result["parsed_output_json"] == {}
    assert result["error_message"] is not None


def test_run_extraction_unknown_provider() -> None:
    with pytest.raises(ValueError):
        run_extraction("unknown", "prompt")
