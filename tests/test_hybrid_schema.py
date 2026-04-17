from __future__ import annotations

from config_loader import SchemaScoringConfig, UnknownFieldPolicyConfig
from evaluation.hybrid_schema import evaluate_schema_score


SCHEMA = {
    "type": "object",
    "properties": {
        "programming_languages": {"type": "array", "items": {"type": "string"}},
        "human_languages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["programming_languages", "human_languages"],
}

SCORING = SchemaScoringConfig(
    required_weight=0.4,
    type_weight=0.3,
    enum_weight=0.2,
    additional_properties_weight=0.1,
)


def test_schema_score_penalize_unknown_fields() -> None:
    predicted = {
        "programming_languages": ["Python"],
        "human_languages": ["English"],
        "extra": ["unexpected"],
    }
    detail = evaluate_schema_score(
        predicted,
        SCHEMA,
        unknown_field_policy=UnknownFieldPolicyConfig(mode="penalize", penalty_weight=0.2),
        schema_scoring=SCORING,
    )

    assert detail.unknown_field_penalty == 0.2
    assert detail.score < 1.0


def test_schema_score_fail_schema_on_unknown_fields() -> None:
    predicted = {
        "programming_languages": ["Python"],
        "human_languages": ["English"],
        "extra": ["unexpected"],
    }
    detail = evaluate_schema_score(
        predicted,
        SCHEMA,
        unknown_field_policy=UnknownFieldPolicyConfig(mode="fail_schema", penalty_weight=0.0),
        schema_scoring=SCORING,
    )

    assert detail.score == 0.0


def test_schema_score_captures_required_errors() -> None:
    predicted = {"programming_languages": ["Python"]}
    detail = evaluate_schema_score(
        predicted,
        SCHEMA,
        unknown_field_policy=UnknownFieldPolicyConfig(mode="ignore", penalty_weight=0.0),
        schema_scoring=SCORING,
    )

    assert detail.required_error_count >= 1
    assert detail.score < 1.0
