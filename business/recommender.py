from __future__ import annotations

from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Mapping, Sequence

import yaml  # type: ignore[import-not-found]

from business.explainability import (
    dominant_failure_modes,
    metric_contributions,
    threshold_proximity,
    top_failing_items,
)


def _load_yaml_mapping(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"Config file not found at '{config_path}'.")
    with config_path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Config file '{config_path}' must contain a top-level mapping.")
    return parsed


def load_business_settings(path: str) -> Dict[str, Any]:
    """Load and validate business settings used by recommendation scoring."""

    settings = _load_yaml_mapping(path)
    weights = settings.get("readiness", {}).get("weights", {})
    required_weights = ("success", "stability", "quality", "risk", "critical")
    if not isinstance(weights, dict) or any(key not in weights for key in required_weights):
        raise ValueError("business_settings.yaml is missing readiness.weights keys.")

    for key in required_weights:
        value = weights[key]
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"readiness.weights.{key} must be a non-negative number.")

    if sum(float(weights[key]) for key in required_weights) <= 0:
        raise ValueError("readiness.weights must have positive total weight.")

    cap = settings.get("normalization", {}).get("expected_cost_per_1000_cap")
    if not isinstance(cap, (int, float)) or cap <= 0:
        raise ValueError("normalization.expected_cost_per_1000_cap must be > 0.")

    precision = settings.get("rounding", {}).get("precision")
    if not isinstance(precision, int) or precision < 0:
        raise ValueError("rounding.precision must be a non-negative integer.")

    margin = settings.get("warnings", {}).get("soft_warning_margin")
    if not isinstance(margin, (int, float)) or margin < 0:
        raise ValueError("warnings.soft_warning_margin must be >= 0.")

    return settings


def load_business_thresholds(path: str) -> Dict[str, Any]:
    """Load scenario threshold config with hard-gate requirements."""

    thresholds = _load_yaml_mapping(path)
    if "default" not in thresholds or not isinstance(thresholds["default"], dict):
        raise ValueError("business_thresholds.yaml must define a 'default' mapping.")

    for scenario_name, scenario_cfg in thresholds.items():
        if scenario_name == "business_config_version":
            continue
        if not isinstance(scenario_cfg, dict):
            raise ValueError(f"Threshold scenario '{scenario_name}' must be a mapping.")

        for key in ("go_threshold", "conditional_threshold", "hard_gates"):
            if key not in scenario_cfg:
                raise ValueError(f"Threshold scenario '{scenario_name}' is missing '{key}'.")

        go_threshold = scenario_cfg["go_threshold"]
        conditional_threshold = scenario_cfg["conditional_threshold"]
        if not isinstance(go_threshold, (int, float)) or not isinstance(conditional_threshold, (int, float)):
            raise ValueError(f"Thresholds for '{scenario_name}' must be numeric.")
        if conditional_threshold > go_threshold:
            raise ValueError(
                f"Threshold scenario '{scenario_name}' has conditional_threshold > go_threshold."
            )

        hard_gates = scenario_cfg["hard_gates"]
        if not isinstance(hard_gates, dict):
            raise ValueError(f"hard_gates for '{scenario_name}' must be a mapping.")

        for gate_key in (
            "max_critical_failure_rate",
            "max_expected_cost_per_1000",
            "min_stability_score",
        ):
            value = hard_gates.get(gate_key)
            if not isinstance(value, (int, float)):
                raise ValueError(f"hard_gates.{gate_key} for '{scenario_name}' must be numeric.")

    return thresholds


def _normalize_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    total = sum(float(value) for value in weights.values())
    if total <= 0:
        raise ValueError("Weight normalization requires positive total.")
    return {key: float(value) / total for key, value in weights.items()}


def _scenario_thresholds(thresholds: Mapping[str, Any], scenario: str) -> Dict[str, Any]:
    default_cfg = dict(thresholds["default"])
    if scenario in thresholds and isinstance(thresholds[scenario], dict):
        scenario_cfg = dict(thresholds[scenario])
        scenario_hard = scenario_cfg.get("hard_gates", {})
        merged_hard = {**default_cfg.get("hard_gates", {}), **scenario_hard}
        return {
            **default_cfg,
            **scenario_cfg,
            "hard_gates": merged_hard,
        }
    return default_cfg


def _soft_warnings(
    *,
    readiness_score: float,
    scenario_summary: Mapping[str, float],
    go_threshold: float,
    hard_gates: Mapping[str, float],
    margin: float,
) -> list[str]:
    warnings: list[str] = []
    if go_threshold - readiness_score <= margin and readiness_score < go_threshold:
        warnings.append("readiness_near_go_threshold")

    critical = float(scenario_summary.get("critical_failure_rate", 0.0))
    if float(hard_gates["max_critical_failure_rate"]) - critical <= margin and critical <= float(
        hard_gates["max_critical_failure_rate"]
    ):
        warnings.append("critical_failure_rate_near_gate")

    stability = float(scenario_summary.get("stability_score", 0.0))
    if stability - float(hard_gates["min_stability_score"]) <= margin and stability >= float(
        hard_gates["min_stability_score"]
    ):
        warnings.append("stability_near_gate")

    cost = float(scenario_summary.get("expected_cost_per_1000", 0.0))
    if float(hard_gates["max_expected_cost_per_1000"]) - cost <= margin * float(
        hard_gates["max_expected_cost_per_1000"]
    ) and cost <= float(hard_gates["max_expected_cost_per_1000"]):
        warnings.append("expected_cost_near_gate")

    return sorted(set(warnings))


def recommend_deployment(
    *,
    scenario: str,
    scenario_summary: Mapping[str, float],
    failure_breakdown: Mapping[str, float],
    item_metrics: Sequence[Mapping[str, object]],
    settings: Mapping[str, Any],
    thresholds: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build configurable recommendation payload with explainability fields."""

    scenario_cfg = _scenario_thresholds(thresholds, scenario)
    weights = _normalize_weights(settings["readiness"]["weights"])
    hard_gates = scenario_cfg["hard_gates"]

    success_rate = float(scenario_summary.get("success_rate_mean", 0.0))
    stability_score = float(scenario_summary.get("stability_score", 0.0))
    critical_failure_rate = float(scenario_summary.get("critical_failure_rate", 0.0))
    expected_cost_per_1000 = float(scenario_summary.get("expected_cost_per_1000", 0.0))

    mean_score = fmean(float(item.get("mean_score", 0.0)) for item in item_metrics) if item_metrics else 0.0
    cost_cap = float(settings["normalization"]["expected_cost_per_1000_cap"])
    normalized_cost = min(1.0, max(0.0, expected_cost_per_1000 / cost_cap))

    contributions = metric_contributions(
        success_rate=success_rate,
        stability_score=stability_score,
        mean_score=mean_score,
        normalized_expected_cost=normalized_cost,
        critical_failure_rate=critical_failure_rate,
        weights=weights,
    )
    readiness = sum(contributions.values())

    hard_gate_failures: list[str] = []
    if critical_failure_rate > float(hard_gates["max_critical_failure_rate"]):
        hard_gate_failures.append("critical_failure_rate")
    if expected_cost_per_1000 > float(hard_gates["max_expected_cost_per_1000"]):
        hard_gate_failures.append("expected_cost_per_1000")
    if stability_score < float(hard_gates["min_stability_score"]):
        hard_gate_failures.append("stability_score")

    go_threshold = float(scenario_cfg["go_threshold"])
    conditional_threshold = float(scenario_cfg["conditional_threshold"])
    margin = float(settings["warnings"]["soft_warning_margin"])
    soft_warnings = _soft_warnings(
        readiness_score=readiness,
        scenario_summary=scenario_summary,
        go_threshold=go_threshold,
        hard_gates=hard_gates,
        margin=margin,
    )

    if hard_gate_failures:
        recommendation = "hold"
    elif readiness >= go_threshold and not soft_warnings:
        recommendation = "go"
    elif readiness >= conditional_threshold:
        recommendation = "conditional"
    else:
        recommendation = "hold"

    precision = int(settings["rounding"]["precision"])
    proximity = threshold_proximity(
        readiness_score=readiness,
        critical_failure_rate=critical_failure_rate,
        expected_cost_per_1000=expected_cost_per_1000,
        stability_score=stability_score,
        go_threshold=go_threshold,
        conditional_threshold=conditional_threshold,
        hard_gates=hard_gates,
    )

    return {
        "deployment_readiness": {
            "score": round(max(0.0, min(1.0, readiness)) * 100.0, 2),
            "recommendation": recommendation,
        },
        "risk": {
            "expected_cost_per_1000": round(expected_cost_per_1000, precision),
            "tail_risk_p95": round(float(scenario_summary.get("p95_cost", 0.0)), precision),
            "critical_failure_rate": round(critical_failure_rate, precision),
        },
        "stability": {
            "overall": round(stability_score, precision),
            "high_variance_items": round(
                (
                    sum(1 for item in item_metrics if float(item.get("variance", 0.0)) > 0.2)
                    / float(len(item_metrics))
                )
                if item_metrics
                else 0.0,
                precision,
            ),
        },
        "explainability": {
            "metric_contributions": {k: round(v, precision) for k, v in contributions.items()},
            "top_failing_items": top_failing_items(item_metrics),
            "dominant_failure_modes": dominant_failure_modes(failure_breakdown),
            "threshold_proximity": {k: round(v, precision) for k, v in proximity.items()},
            "hard_gate_failures": hard_gate_failures,
            "soft_warnings": soft_warnings,
            "effective_thresholds": {
                "scenario": scenario,
                "go_threshold": go_threshold,
                "conditional_threshold": conditional_threshold,
                "hard_gates": hard_gates,
            },
        },
    }
