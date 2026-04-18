from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Dict, List, Mapping, Sequence

from business.metrics import _percentile


def _clamp_01(value: float) -> float:
    return min(1.0, max(0.0, value))


def aggregate_scenario(item_metrics: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    """Aggregate per-item business metrics into scenario-level summary."""

    if not item_metrics:
        raise ValueError("aggregate_scenario requires at least one item metric.")

    success_rates: List[float] = []
    costs: List[float] = []
    variances: List[float] = []
    critical_count = 0
    failure_totals: Dict[str, float] = defaultdict(float)

    for item in item_metrics:
        success_rate = float(item.get("success_rate", 0.0))
        expected_cost = float(item.get("expected_cost", 0.0))
        variance = float(item.get("variance", 0.0))
        failure_probability = float(item.get("failure_probability", 0.0))

        success_rates.append(success_rate)
        costs.append(expected_cost)
        variances.append(variance)

        if failure_probability > 0.5:
            critical_count += 1

        failure_mode_rates = item.get("failure_mode_rates", {})
        if isinstance(failure_mode_rates, Mapping):
            for mode, rate in failure_mode_rates.items():
                failure_totals[str(mode)] += float(rate)

    item_count = float(len(item_metrics))
    failure_breakdown = {
        mode: total / item_count for mode, total in sorted(failure_totals.items())
    }

    return {
        "summary": {
            "success_rate_mean": fmean(success_rates),
            "stability_score": _clamp_01(1.0 - fmean(variances)),
            "expected_cost_per_1000": fmean(costs) * 1000.0,
            "p95_cost": _percentile(costs, 95.0),
            "critical_failure_rate": critical_count / item_count,
        },
        "failure_breakdown": failure_breakdown,
    }
