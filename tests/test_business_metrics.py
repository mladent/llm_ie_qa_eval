from __future__ import annotations

import pytest

from business.aggregates import aggregate_scenario
from business.metrics import compute_agreement, compute_expected_cost, evaluate_item, five_number_summary
from business.types import BusinessItemInput, BusinessRunInput


def _run(
    run_id: int,
    output: str,
    precision: float,
    recall: float,
    f1: float,
    failure_modes: list[str],
) -> BusinessRunInput:
    return BusinessRunInput(
        run_id=run_id,
        output=output,
        scores={"precision": precision, "recall": recall, "f1": f1},
        failure_modes=failure_modes,
        parse_status="success",
        error_message=None,
    )


def test_five_number_summary_and_agreement() -> None:
    summary = five_number_summary([0.2, 0.4, 0.6, 0.8])
    assert summary["min"] == 0.2
    assert summary["q1"] == pytest.approx(0.35)
    assert summary["median"] == 0.5
    assert summary["q3"] == pytest.approx(0.65)
    assert summary["max"] == 0.8

    agreement = compute_agreement(["a", "a", "b", "a"])
    assert agreement == 0.75


def test_compute_expected_cost() -> None:
    runs = [
        _run(0, "o1", 1.0, 1.0, 1.0, []),
        _run(1, "o2", 0.2, 0.2, 0.2, ["incorrect", "parse_error"]),
    ]

    ecf = compute_expected_cost(runs, {"incorrect": 5.0, "parse_error": 10.0})
    assert ecf == 7.5


def test_evaluate_item_and_aggregate_scenario() -> None:
    item_a = BusinessItemInput(
        item_id="doc1",
        runs=[
            _run(0, "ok", 0.9, 0.9, 0.9, []),
            _run(1, "ok", 0.8, 0.8, 0.8, []),
        ],
        evaluator_aggregates={},
    )
    item_b = BusinessItemInput(
        item_id="doc2",
        runs=[
            _run(0, "bad", 0.1, 0.1, 0.1, ["incorrect"]),
            _run(1, "bad2", 0.0, 0.0, 0.0, ["incorrect", "parse_error"]),
        ],
        evaluator_aggregates={},
    )

    cost_map = {"incorrect": 5.0, "parse_error": 10.0}
    metrics_a = evaluate_item(item_a, cost_map)
    metrics_b = evaluate_item(item_b, cost_map)

    assert metrics_a["item_id"] == "doc1"
    assert metrics_a["success_rate"] == 1.0
    assert metrics_b["failure_probability"] == 1.0
    assert metrics_b["worst_case_cost"] == 15.0

    scenario = aggregate_scenario([metrics_a, metrics_b])
    summary = scenario["summary"]
    assert summary["critical_failure_rate"] == 0.5
    assert summary["expected_cost_per_1000"] == 5000.0
    assert scenario["failure_breakdown"]["incorrect"] == 0.5


def test_evaluate_item_requires_runs() -> None:
    item = BusinessItemInput(item_id="doc-x", runs=[], evaluator_aggregates={})
    with pytest.raises(ValueError, match="has no runs"):
        evaluate_item(item, {"incorrect": 1.0})
