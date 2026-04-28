from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from config_loader import ComparatorConfig, RubricRuleConfig
from evaluation.hybrid_comparators import (
    best_overlap_fallback_match,
    exact_match,
    fuzzy_lexical_match,
    key_based_array_object_match,
    set_jaccard_match,
)
from evaluation.hybrid_normalize import extract_values_by_jsonpath
from evaluation.hybrid_schema import evaluate_schema_score
from evaluation.hybrid_types import HybridScoreResult, PathScoreDetail


DEFAULT_SCHEMA_WEIGHT = 0.35
DEFAULT_VALUE_WEIGHT = 0.65


def evaluate_hybrid(
    predicted: Dict[str, Any],
    gold: Dict[str, Any],
    *,
    rubric_rules: Iterable[RubricRuleConfig],
    comparator_configs: Iterable[ComparatorConfig],
    schema: Mapping[str, Any],
    schema_scoring: Any,
    unknown_field_policy: Any,
    parse_status: str,
    parse_error_behavior: str = "force_zero",
    array_fallback_strategy: str = "best_overlap",
) -> HybridScoreResult:
    """Compute hybrid score with schema + rubric value components."""

    rules = list(rubric_rules)

    if parse_status != "success" and parse_error_behavior == "force_zero":
        schema_detail = evaluate_schema_score(
            predicted,
            schema,
            unknown_field_policy=unknown_field_policy,
            schema_scoring=schema_scoring,
        )
        schema_detail.score = 0.0
        return HybridScoreResult(
            total_score=0.0,
            schema_score=0.0,
            value_score=0.0,
            unknown_field_penalty=schema_detail.unknown_field_penalty,
            rule_coverage=0.0,
            path_scores=[],
            schema_detail=schema_detail,
        )

    schema_detail = evaluate_schema_score(
        predicted,
        schema,
        unknown_field_policy=unknown_field_policy,
        schema_scoring=schema_scoring,
    )

    comparator_by_name = {cfg.name: cfg for cfg in comparator_configs if cfg.enabled}
    path_scores: list[PathScoreDetail] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for rule in rules:
        comparator_cfg = comparator_by_name.get(rule.comparator)
        if comparator_cfg is None:
            continue

        comparator_fn = _resolve_comparator_fn(comparator_cfg.type)
        pred_values = extract_values_by_jsonpath(predicted, rule.path)
        gold_values = extract_values_by_jsonpath(gold, rule.path)
        comparator_kwargs = dict(comparator_cfg.params)
        comparator_kwargs.update(rule.options)
        comparator_kwargs.setdefault("fallback_strategy", array_fallback_strategy)

        raw_score = comparator_fn(pred_values, gold_values, **comparator_kwargs)
        weighted_score = raw_score * rule.weight
        weighted_sum += weighted_score
        weight_total += rule.weight

        path_scores.append(
            PathScoreDetail(
                path=rule.path,
                comparator=comparator_cfg.name,
                raw_score=raw_score,
                weight=rule.weight,
                weighted_score=weighted_score,
            )
        )

    value_score = weighted_sum / weight_total if weight_total else 0.0
    total_score = DEFAULT_SCHEMA_WEIGHT * schema_detail.score + DEFAULT_VALUE_WEIGHT * value_score
    rule_coverage = len(path_scores) / len(rules) if rules else 0.0

    return HybridScoreResult(
        total_score=total_score,
        schema_score=schema_detail.score,
        value_score=value_score,
        unknown_field_penalty=schema_detail.unknown_field_penalty,
        rule_coverage=rule_coverage,
        path_scores=path_scores,
        schema_detail=schema_detail,
    )


def _resolve_comparator_fn(comparator_type: str):
    mapping = {
        "exact_match": exact_match,
        "set_jaccard_match": set_jaccard_match,
        "fuzzy_lexical_match": fuzzy_lexical_match,
        "key_based_array_object_match": key_based_array_object_match,
        "best_overlap_fallback_match": best_overlap_fallback_match,
    }
    if comparator_type not in mapping:
        raise ValueError(f"Unsupported comparator type '{comparator_type}'.")
    return mapping[comparator_type]
