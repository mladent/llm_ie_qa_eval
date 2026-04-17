from __future__ import annotations

from config_loader import (
    ComparatorConfig,
    RubricRuleConfig,
    SchemaScoringConfig,
    UnknownFieldPolicyConfig,
)
from evaluation.hybrid_scoring import evaluate_hybrid


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "programming_languages": {"type": "array", "items": {"type": "string"}},
            "human_languages": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["programming_languages", "human_languages"],
    }


def test_evaluate_hybrid_success_path() -> None:
    predicted = {"programming_languages": ["Python"], "human_languages": ["English"]}
    gold = {"programming_languages": ["Python"], "human_languages": ["English"]}

    comparators = [
        ComparatorConfig(name="set_jaccard", type="set_jaccard_match", enabled=True, params={})
    ]
    rules = [
        RubricRuleConfig(
            path="$.programming_languages[*]",
            comparator="set_jaccard",
            weight=0.5,
            options={},
        ),
        RubricRuleConfig(
            path="$.human_languages[*]",
            comparator="set_jaccard",
            weight=0.5,
            options={},
        ),
    ]

    result = evaluate_hybrid(
        predicted,
        gold,
        rubric_rules=rules,
        comparator_configs=comparators,
        schema=_schema(),
        schema_scoring=SchemaScoringConfig(0.4, 0.3, 0.2, 0.1),
        unknown_field_policy=UnknownFieldPolicyConfig("ignore", 0.0),
        parse_status="success",
    )

    assert result.total_score == 1.0
    assert result.rule_coverage == 1.0
    assert len(result.path_scores) == 2


def test_evaluate_hybrid_forces_zero_on_parse_error() -> None:
    predicted = {}
    gold = {"programming_languages": ["Python"], "human_languages": ["English"]}

    result = evaluate_hybrid(
        predicted,
        gold,
        rubric_rules=[],
        comparator_configs=[],
        schema=_schema(),
        schema_scoring=SchemaScoringConfig(0.4, 0.3, 0.2, 0.1),
        unknown_field_policy=UnknownFieldPolicyConfig("ignore", 0.0),
        parse_status="parse_error",
        parse_error_behavior="force_zero",
    )

    assert result.total_score == 0.0
    assert result.value_score == 0.0
