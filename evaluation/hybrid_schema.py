from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from jsonschema import Draft202012Validator  # type: ignore[import-not-found]

from config_loader import SchemaScoringConfig, UnknownFieldPolicyConfig
from evaluation.hybrid_types import SchemaScoreDetail


def load_json_schema(schema_path: str) -> Dict[str, Any]:
    import json

    path = Path(schema_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Schema must be a JSON object.")
    return payload


def evaluate_schema_score(
    predicted: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    unknown_field_policy: UnknownFieldPolicyConfig,
    schema_scoring: SchemaScoringConfig,
) -> SchemaScoreDetail:
    """Evaluate schema alignment and return an interpretable component score."""

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(dict(predicted)), key=lambda err: list(err.path))

    required_errors = [err for err in errors if err.validator == "required"]
    type_errors = [err for err in errors if err.validator == "type"]
    enum_errors = [err for err in errors if err.validator == "enum"]
    additional_errors = [err for err in errors if err.validator == "additionalProperties"]

    required_total = max(len(schema.get("required", [])), 1)
    properties = schema.get("properties", {}) if isinstance(schema.get("properties", {}), dict) else {}
    type_total = max(len(properties), 1)
    enum_total = max(
        sum(1 for cfg in properties.values() if isinstance(cfg, dict) and "enum" in cfg),
        1,
    )
    additional_total = 1

    required_component = max(0.0, 1.0 - len(required_errors) / required_total)
    type_component = max(0.0, 1.0 - len(type_errors) / type_total)
    enum_component = max(0.0, 1.0 - len(enum_errors) / enum_total)
    additional_component = max(0.0, 1.0 - len(additional_errors) / additional_total)

    weighted = (
        required_component * schema_scoring.required_weight
        + type_component * schema_scoring.type_weight
        + enum_component * schema_scoring.enum_weight
        + additional_component * schema_scoring.additional_properties_weight
    )
    denom = (
        schema_scoring.required_weight
        + schema_scoring.type_weight
        + schema_scoring.enum_weight
        + schema_scoring.additional_properties_weight
    )
    score = weighted / denom if denom else 0.0

    unknown_count = _count_unknown_top_level_fields(predicted, schema)
    unknown_penalty = 0.0
    if unknown_field_policy.mode == "penalize":
        unknown_penalty = min(1.0, unknown_count * unknown_field_policy.penalty_weight)
        score = max(0.0, score - unknown_penalty)
    elif unknown_field_policy.mode == "fail_schema" and unknown_count > 0:
        score = 0.0

    return SchemaScoreDetail(
        score=score,
        is_valid=(not errors and (unknown_count == 0 or unknown_field_policy.mode != "fail_schema")),
        required_error_count=len(required_errors),
        type_error_count=len(type_errors),
        enum_error_count=len(enum_errors),
        additional_properties_error_count=len(additional_errors),
        unknown_field_penalty=unknown_penalty,
        errors=[err.message for err in errors],
    )


def _count_unknown_top_level_fields(predicted: Mapping[str, Any], schema: Mapping[str, Any]) -> int:
    allowed = schema.get("properties", {})
    if not isinstance(allowed, dict):
        return 0
    return sum(1 for key in predicted.keys() if key not in allowed)
