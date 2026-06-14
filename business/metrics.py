from __future__ import annotations

from collections import Counter, defaultdict
from statistics import fmean, median
from typing import Dict, List, Mapping, Sequence

from business.types import BusinessItemInput, BusinessRunInput


def _percentile(values: Sequence[float], p: float) -> float:
    """Return percentile using linear interpolation over sorted samples."""

    if not values:
        raise ValueError("Percentile requires at least one value.")

    sorted_values = sorted(float(v) for v in values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def five_number_summary(values: Sequence[float]) -> Dict[str, float]:
    """Compute min, quartiles, median, and max over numeric values."""

    if not values:
        raise ValueError("five_number_summary requires at least one value.")

    numbers = [float(v) for v in values]
    return {
        "min": min(numbers),
        "q1": _percentile(numbers, 25.0),
        "median": float(median(numbers)),
        "q3": _percentile(numbers, 75.0),
        "max": max(numbers),
    }


def compute_agreement(outputs: Sequence[str]) -> float:
    """Return exact-match agreement rate based on the most frequent output."""

    if not outputs:
        return 0.0
    counts = Counter(outputs)
    most_common = counts.most_common(1)[0][1]
    return float(most_common) / float(len(outputs))


def compute_expected_cost(runs: Sequence[BusinessRunInput], cost_map: Mapping[str, float]) -> float:
    """Approximate ECF as average failure cost per run."""

    if not runs:
        return 0.0

    total_cost = 0.0
    for run in runs:
        for failure in run.failure_modes:
            total_cost += float(cost_map.get(failure, 0.0))
    return total_cost / float(len(runs))


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 0.0

    mean_value = fmean(values)
    return fmean((value - mean_value) ** 2 for value in values)


def evaluate_item(item: BusinessItemInput, cost_map: Mapping[str, float]) -> Dict[str, object]:
    """Compute run-aggregated business metrics for a single item."""

    runs = item.runs
    if not runs:
        raise ValueError(f"Item '{item.item_id}' has no runs.")

    scores: List[float] = []
    outputs: List[str] = []
    failure_counts = 0
    failure_mode_counts: Dict[str, int] = defaultdict(int)
    worst_case_cost = 0.0

    for run in runs:
        score_values = [float(value) for value in run.scores.values()]
        scores.append(fmean(score_values) if score_values else 0.0)
        outputs.append(run.output)

        run_cost = 0.0
        for failure in run.failure_modes:
            failure_mode_counts[failure] += 1
            run_cost += float(cost_map.get(failure, 0.0))

        if run.failure_modes:
            failure_counts += 1
        worst_case_cost = max(worst_case_cost, run_cost)

    run_count = float(len(runs))
    return {
        "item_id": item.item_id,
        "success_rate": 1.0 - (failure_counts / run_count),
        "mean_score": fmean(scores),
        "variance": _variance(scores),
        "agreement_rate": compute_agreement(outputs),
        "five_number_summary": five_number_summary(scores),
        "expected_cost": compute_expected_cost(runs, cost_map),
        "worst_case_cost": worst_case_cost,
        "failure_probability": failure_counts / run_count,
        "failure_mode_rates": {
            mode: count / run_count for mode, count in sorted(failure_mode_counts.items())
        },
        "run_count": int(run_count),
    }
