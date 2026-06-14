from __future__ import annotations

from typing import Any, Dict

from jsonschema import Draft202012Validator  # type: ignore[import-not-found]


BUSINESS_CONTRACT_VERSION = "1.0.0"

BUSINESS_CONTRACT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "business_contract_version",
        "source_experiment_dir",
        "corpus",
        "items",
    ],
    "properties": {
        "business_contract_version": {"type": "string", "minLength": 1},
        "source_experiment_dir": {"type": "string", "minLength": 1},
        "corpus": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "experiment_id",
                "provider",
                "model",
                "prompt_id",
                "dataset_id",
                "run_count",
                "document_count",
                "mean_f1",
                "parse_error_rate",
                "failure_rate",
            ],
            "properties": {
                "experiment_id": {"type": "string", "minLength": 1},
                "provider": {"type": "string", "minLength": 1},
                "model": {"type": "string", "minLength": 1},
                "prompt_id": {"type": "string", "minLength": 1},
                "dataset_id": {"type": "string", "minLength": 1},
                "run_count": {"type": "integer", "minimum": 0},
                "document_count": {"type": "integer", "minimum": 0},
                "mean_f1": {"type": "number"},
                "parse_error_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "failure_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_id", "runs", "evaluator_aggregates"],
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "runs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "run_id",
                                "output",
                                "scores",
                                "failure_modes",
                                "parse_status",
                                "error_message",
                            ],
                            "properties": {
                                "run_id": {"type": "integer", "minimum": 0},
                                "output": {"type": "string"},
                                "scores": {
                                    "type": "object",
                                    "additionalProperties": {"type": "number"},
                                    "required": ["precision", "recall", "f1"],
                                },
                                "failure_modes": {
                                    "type": "array",
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "parse_status": {"type": "string", "minLength": 1},
                                "error_message": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "evaluator_aggregates": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                        "required": [
                            "mean_precision",
                            "mean_recall",
                            "mean_f1",
                            "parse_error_rate",
                            "exact_match_consistency_rate",
                            "run_count",
                        ],
                    },
                },
            },
        },
    },
}


def validate_business_contract(payload: Dict[str, Any]) -> None:
    """Validate payload shape before business-metric computation starts."""

    validator = Draft202012Validator(BUSINESS_CONTRACT_SCHEMA)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return

    first = errors[0]
    location = ".".join(str(part) for part in first.absolute_path) or "<root>"
    raise ValueError(f"Business contract validation failed at '{location}': {first.message}")
