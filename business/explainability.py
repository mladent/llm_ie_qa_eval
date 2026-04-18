from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


def metric_contributions(
    *,
    success_rate: float,
    stability_score: float,
    mean_score: float,
    normalized_expected_cost: float,
    critical_failure_rate: float,
    weights: Mapping[str, float],
) -> Dict[str, float]:
    """Return signed contribution of each component to readiness score."""

    return {
        "success": float(weights["success"]) * success_rate,
        "stability": float(weights["stability"]) * stability_score,
        "quality": float(weights["quality"]) * mean_score,
        "risk": -float(weights["risk"]) * normalized_expected_cost,
        "critical": -float(weights["critical"]) * critical_failure_rate,
    }


def threshold_proximity(
    *,
    readiness_score: float,
    critical_failure_rate: float,
    expected_cost_per_1000: float,
    stability_score: float,
    go_threshold: float,
    conditional_threshold: float,
    hard_gates: Mapping[str, float],
) -> Dict[str, float]:
    """Return absolute distances to important decision thresholds and gates."""

    return {
        "to_go_threshold": abs(readiness_score - go_threshold),
        "to_conditional_threshold": abs(readiness_score - conditional_threshold),
        "to_max_critical_failure_rate": abs(
            critical_failure_rate - float(hard_gates["max_critical_failure_rate"])
        ),
        "to_max_expected_cost_per_1000": abs(
            expected_cost_per_1000 - float(hard_gates["max_expected_cost_per_1000"])
        ),
        "to_min_stability_score": abs(stability_score - float(hard_gates["min_stability_score"])),
    }


def dominant_failure_modes(failure_breakdown: Mapping[str, float], top_k: int = 3) -> List[Dict[str, float]]:
    """Return highest-rate failure modes for explainability payloads."""

    ranked = sorted(failure_breakdown.items(), key=lambda item: item[1], reverse=True)
    return [{"mode": mode, "rate": float(rate)} for mode, rate in ranked[:top_k]]


def top_failing_items(item_metrics: Sequence[Mapping[str, object]], top_k: int = 3) -> List[Dict[str, float]]:
    """Return items with highest failure probability and expected cost."""

    ranked = sorted(
        item_metrics,
        key=lambda item: (
            float(item.get("failure_probability", 0.0)),
            float(item.get("expected_cost", 0.0)),
        ),
        reverse=True,
    )
    output: List[Dict[str, float]] = []
    for item in ranked[:top_k]:
        output.append(
            {
                "item_id": str(item.get("item_id", "")),
                "failure_probability": float(item.get("failure_probability", 0.0)),
                "expected_cost": float(item.get("expected_cost", 0.0)),
            }
        )
    return output
