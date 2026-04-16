from __future__ import annotations

import pytest

from extraction.extractor import (
    normalize_extraction_output,
    run_extraction,
    validate_extraction_schema,
)


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


def test_run_extraction_normalizes_missing_field(monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert result["parse_status"] == "success"
    assert result["parsed_output_json"]["datasets"] == []
    assert result["error_message"] is None


def test_run_extraction_marks_schema_error_for_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_openai(*args, **kwargs):
        return {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "raw_response_text": "{}",
            "parsed_output_json": {"methods": {"bad": "value"}, "tasks": ["T"]},
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


def test_run_extraction_routes_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_gemini(*args, **kwargs):
        return {
            "provider": "gemini",
            "model": "gemini-1.5-pro",
            "raw_response_text": "{}",
            "parsed_output_json": {"methods": [], "tasks": [], "datasets": []},
            "parse_status": "success",
            "error_message": None,
            "latency_ms": 10.0,
            "input_tokens": 1,
            "output_tokens": 1,
            "estimated_cost": 0.0,
            "model_params_used": {},
        }

    monkeypatch.setattr("extraction.extractor.run_gemini", fake_gemini)

    result = run_extraction("gemini", "prompt")

    assert result["provider"] == "gemini"
    assert result["parse_status"] == "success"


def test_run_extraction_marks_schema_error_after_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_openai(*args, **kwargs):
        return {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "raw_response_text": "{}",
            "parsed_output_json": {"methods": ["A"], "tasks": ["T"], "datasets": []},
            "parse_status": "success",
            "error_message": None,
            "latency_ms": 10.0,
            "input_tokens": 1,
            "output_tokens": 1,
            "estimated_cost": 0.0,
            "model_params_used": {},
        }

    monkeypatch.setattr("extraction.extractor.run_openai", fake_openai)
    monkeypatch.setattr(
        "extraction.extractor.validate_extraction_schema",
        lambda parsed, expected_fields=None: "forced schema error",
    )

    result = run_extraction("openai", "prompt")

    assert result["parse_status"] == "schema_error"
    assert result["parsed_output_json"] == {}


def test_validate_extraction_schema_custom_fields() -> None:
    error = validate_extraction_schema(
        {"programming_languages": ["Python"], "human_languages": ["English"]},
        expected_fields=["programming_languages", "human_languages"],
    )
    assert error is None


def test_normalize_extraction_output_coerces_null_and_scalar() -> None:
    normalized, error = normalize_extraction_output(
        {
            "programming_languages": "Python",
            "programming_tools_skills": ["MLflow"],
            "education_degree": None,
            "human_languages": None,
        },
        expected_fields=[
            "programming_languages",
            "programming_tools_skills",
            "education_degree",
            "human_languages",
        ],
    )
    assert error is None
    assert normalized == {
        "programming_languages": ["Python"],
        "programming_tools_skills": ["MLflow"],
        "education_degree": [],
        "human_languages": [],
    }
