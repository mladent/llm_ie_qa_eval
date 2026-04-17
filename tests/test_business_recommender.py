from __future__ import annotations

from pathlib import Path

import pytest

from business.recommender import (
    load_business_settings,
    load_business_thresholds,
    recommend_deployment,
)


def _configs() -> tuple[dict, dict]:
    settings = load_business_settings("config/business_settings.yaml")
    thresholds = load_business_thresholds("config/business_thresholds.yaml")
    return settings, thresholds


def test_recommend_deployment_returns_go_for_strong_signal() -> None:
    settings, thresholds = _configs()

    scenario_summary = {
        "success_rate_mean": 0.95,
        "stability_score": 0.93,
        "expected_cost_per_1000": 900.0,
        "p95_cost": 2.0,
        "critical_failure_rate": 0.01,
    }
    item_metrics = [
        {"item_id": "a", "mean_score": 0.94, "variance": 0.01, "failure_probability": 0.0, "expected_cost": 0.4},
        {"item_id": "b", "mean_score": 0.92, "variance": 0.02, "failure_probability": 0.0, "expected_cost": 0.5},
    ]

    payload = recommend_deployment(
        scenario="default",
        scenario_summary=scenario_summary,
        failure_breakdown={"incorrect": 0.02},
        item_metrics=item_metrics,
        settings=settings,
        thresholds=thresholds,
    )

    assert payload["deployment_readiness"]["recommendation"] == "go"
    assert payload["deployment_readiness"]["score"] >= 73


def test_recommend_deployment_downgrades_to_hold_on_hard_gate() -> None:
    settings, thresholds = _configs()

    scenario_summary = {
        "success_rate_mean": 0.99,
        "stability_score": 0.95,
        "expected_cost_per_1000": 700.0,
        "p95_cost": 2.0,
        "critical_failure_rate": 0.2,
    }

    payload = recommend_deployment(
        scenario="default",
        scenario_summary=scenario_summary,
        failure_breakdown={"incorrect": 0.2},
        item_metrics=[{"item_id": "a", "mean_score": 0.96, "variance": 0.01, "failure_probability": 0.0, "expected_cost": 0.2}],
        settings=settings,
        thresholds=thresholds,
    )

    assert payload["deployment_readiness"]["recommendation"] == "hold"
    assert "critical_failure_rate" in payload["explainability"]["hard_gate_failures"]


def test_recommend_deployment_returns_conditional_in_mid_band() -> None:
    settings, thresholds = _configs()

    scenario_summary = {
        "success_rate_mean": 0.78,
        "stability_score": 0.68,
        "expected_cost_per_1000": 3000.0,
        "p95_cost": 9.0,
        "critical_failure_rate": 0.03,
    }

    payload = recommend_deployment(
        scenario="default",
        scenario_summary=scenario_summary,
        failure_breakdown={"incorrect": 0.1, "parse_error": 0.04},
        item_metrics=[{"item_id": "a", "mean_score": 0.67, "variance": 0.11, "failure_probability": 0.4, "expected_cost": 3.0}],
        settings=settings,
        thresholds=thresholds,
    )

    assert payload["deployment_readiness"]["recommendation"] in {"conditional", "hold"}
    assert payload["explainability"]["metric_contributions"]["risk"] <= 0


def test_load_business_settings_rejects_invalid_weights(tmp_path: Path) -> None:
    cfg = tmp_path / "bad_settings.yaml"
    cfg.write_text(
        "readiness:\n"
        "  weights:\n"
        "    success: -1\n"
        "normalization:\n"
        "  expected_cost_per_1000_cap: 100\n"
        "rounding:\n"
        "  precision: 2\n"
        "warnings:\n"
        "  soft_warning_margin: 0.05\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing readiness.weights keys|non-negative"):
        load_business_settings(str(cfg))


def test_load_business_thresholds_requires_default(tmp_path: Path) -> None:
    cfg = tmp_path / "bad_thresholds.yaml"
    cfg.write_text("scenario_a:\n  go_threshold: 0.8\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must define a 'default'"):
        load_business_thresholds(str(cfg))
