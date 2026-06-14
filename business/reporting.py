from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml  # type: ignore[import-not-found]

from business.aggregates import aggregate_scenario
from business.artifacts_loader import load_business_contract_input
from business.metrics import evaluate_item
from business.recommender import (
    load_business_settings,
    load_business_thresholds,
    recommend_deployment,
)
from business.replay import build_effective_business_config, build_replay_metadata, sha256_json
from persistence import write_json_artifact, write_rows_csv


def _load_yaml_mapping(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"Config file not found at '{config_path}'.")
    with config_path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Config file '{config_path}' must contain a top-level mapping.")
    return parsed


def load_business_costs(path: str, scenario: str) -> Dict[str, float]:
    """Load failure cost map with scenario override fallback to default."""

    payload = _load_yaml_mapping(path)
    default_map = payload.get("default")
    if not isinstance(default_map, dict):
        raise ValueError("business_costs.yaml must include a 'default' mapping.")

    selected = dict(default_map)
    if scenario in payload and isinstance(payload[scenario], dict):
        selected.update(payload[scenario])

    for key, value in selected.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"Cost for failure mode '{key}' must be a non-negative number.")

    return {str(key): float(value) for key, value in selected.items()}


def build_business_report(
    *,
    experiment_dir: str,
    scenario: str,
    settings_config_path: str,
    thresholds_config_path: str,
    costs_config_path: str,
    contract_config_path: str = "config/business_contract.yaml",
) -> Dict[str, Any]:
    """Build dashboard payload and tabular outputs from evaluator artifacts."""

    contract = load_business_contract_input(experiment_dir)
    settings = load_business_settings(settings_config_path)
    thresholds = load_business_thresholds(thresholds_config_path)
    cost_map = load_business_costs(costs_config_path, scenario)
    effective_config = build_effective_business_config(
        scenario=scenario,
        settings_config_path=settings_config_path,
        thresholds_config_path=thresholds_config_path,
        costs_config_path=costs_config_path,
        contract_config_path=contract_config_path,
    )

    item_metrics = [evaluate_item(item, cost_map) for item in contract.items]
    scenario_view = aggregate_scenario(item_metrics)
    recommendation = recommend_deployment(
        scenario=scenario,
        scenario_summary=scenario_view["summary"],
        failure_breakdown=scenario_view["failure_breakdown"],
        item_metrics=item_metrics,
        settings=settings,
        thresholds=thresholds,
    )

    dashboard_summary = {
        **recommendation,
        "scenario": scenario,
        "business_contract_version": contract.business_contract_version,
        "business_config_version": effective_config["business_config_version"],
        "business_config_hash": effective_config["business_config_hash"],
        "source_experiment_dir": contract.source_experiment_dir,
        "scenario_summary": scenario_view["summary"],
        "failure_breakdown": scenario_view["failure_breakdown"],
    }

    scenario_csv_row = {
        "scenario": scenario,
        **{key: float(value) for key, value in scenario_view["summary"].items()},
        "recommendation": recommendation["deployment_readiness"]["recommendation"],
        "readiness_score": recommendation["deployment_readiness"]["score"],
    }

    item_csv_rows = []
    for metric in item_metrics:
        row = {
            "item_id": metric["item_id"],
            "success_rate": float(metric["success_rate"]),
            "mean_score": float(metric["mean_score"]),
            "variance": float(metric["variance"]),
            "agreement_rate": float(metric["agreement_rate"]),
            "expected_cost": float(metric["expected_cost"]),
            "worst_case_cost": float(metric["worst_case_cost"]),
            "failure_probability": float(metric["failure_probability"]),
            "run_count": int(metric["run_count"]),
            "failure_modes": json.dumps(metric["failure_mode_rates"], ensure_ascii=True, sort_keys=True),
        }
        item_csv_rows.append(row)

    return {
        "dashboard_summary": dashboard_summary,
        "replay_metadata": build_replay_metadata(
            source_experiment_dir=contract.source_experiment_dir,
            effective_business_config=effective_config,
        ),
        "scenario_csv_rows": [scenario_csv_row],
        "item_csv_rows": item_csv_rows,
    }


def build_business_report_inline(
    *,
    experiment_dir: str,
    scenario_name: str,
    costs: Dict[str, float],
    weights: Dict[str, float],
    go_threshold: float,
    conditional_threshold: float,
    max_critical_failure_rate: float,
    max_expected_cost_per_1000: float,
    min_stability_score: float,
    cost_cap: float = 10000.0,
    soft_warning_margin: float = 0.01,
    rounding_precision: int = 4,
) -> Dict[str, Any]:
    """Build business report from inline config dicts without loading YAML files."""

    contract = load_business_contract_input(experiment_dir)

    settings: Dict[str, Any] = {
        "business_config_version": "1.0.0",
        "rounding": {"precision": rounding_precision},
        "readiness": {"weights": dict(weights)},
        "normalization": {"expected_cost_per_1000_cap": cost_cap},
        "warnings": {"soft_warning_margin": soft_warning_margin},
    }

    scenario_block: Dict[str, Any] = {
        "go_threshold": go_threshold,
        "conditional_threshold": conditional_threshold,
        "hard_gates": {
            "max_critical_failure_rate": max_critical_failure_rate,
            "max_expected_cost_per_1000": max_expected_cost_per_1000,
            "min_stability_score": min_stability_score,
        },
    }
    # Put the block under both "default" and the scenario name so _scenario_thresholds() resolves correctly.
    thresholds: Dict[str, Any] = {
        "business_config_version": "1.0.0",
        "default": scenario_block,
        scenario_name: scenario_block,
    }

    item_metrics = [evaluate_item(item, costs) for item in contract.items]
    scenario_view = aggregate_scenario(item_metrics)
    recommendation = recommend_deployment(
        scenario=scenario_name,
        scenario_summary=scenario_view["summary"],
        failure_breakdown=scenario_view["failure_breakdown"],
        item_metrics=item_metrics,
        settings=settings,
        thresholds=thresholds,
    )

    effective_config: Dict[str, Any] = {
        "scenario": scenario_name,
        "business_config_version": "1.0.0",
        "business_contract_version": contract.business_contract_version,
        "settings": {
            "readiness": settings["readiness"],
            "normalization": settings["normalization"],
            "rounding": settings["rounding"],
            "warnings": settings["warnings"],
        },
        "thresholds": scenario_block,
        "costs": dict(costs),
    }
    config_hash = sha256_json(effective_config)
    effective_config["business_config_hash"] = config_hash

    dashboard_summary: Dict[str, Any] = {
        **recommendation,
        "scenario": scenario_name,
        "business_contract_version": contract.business_contract_version,
        "business_config_version": "1.0.0",
        "business_config_hash": config_hash,
        "source_experiment_dir": contract.source_experiment_dir,
        "scenario_summary": dict(scenario_view["summary"]),
        "failure_breakdown": dict(scenario_view["failure_breakdown"]),
    }

    thresholds_export: Dict[str, Any] = {
        "business_config_version": "1.0.0",
        scenario_name: {
            "go_threshold": go_threshold,
            "conditional_threshold": conditional_threshold,
            "hard_gates": {
                "max_critical_failure_rate": max_critical_failure_rate,
                "max_expected_cost_per_1000": max_expected_cost_per_1000,
                "min_stability_score": min_stability_score,
            },
        },
    }
    costs_export: Dict[str, Any] = {
        "business_config_version": "1.0.0",
        scenario_name: {k: float(v) for k, v in costs.items()},
    }

    scenario_csv_row = {
        "scenario": scenario_name,
        **{key: float(value) for key, value in scenario_view["summary"].items()},
        "recommendation": recommendation["deployment_readiness"]["recommendation"],
        "readiness_score": recommendation["deployment_readiness"]["score"],
    }

    item_csv_rows = []
    for metric in item_metrics:
        row: Dict[str, Any] = {
            "item_id": metric["item_id"],
            "success_rate": float(metric["success_rate"]),
            "mean_score": float(metric["mean_score"]),
            "variance": float(metric["variance"]),
            "agreement_rate": float(metric["agreement_rate"]),
            "expected_cost": float(metric["expected_cost"]),
            "worst_case_cost": float(metric["worst_case_cost"]),
            "failure_probability": float(metric["failure_probability"]),
            "run_count": int(metric["run_count"]),
            "failure_modes": json.dumps(metric["failure_mode_rates"], ensure_ascii=True, sort_keys=True),
        }
        item_csv_rows.append(row)

    return {
        "dashboard_summary": dashboard_summary,
        "replay_metadata": build_replay_metadata(
            source_experiment_dir=contract.source_experiment_dir,
            effective_business_config=effective_config,
        ),
        "scenario_csv_rows": [scenario_csv_row],
        "item_csv_rows": item_csv_rows,
        "thresholds_yaml": yaml.dump(thresholds_export, default_flow_style=False, sort_keys=True),
        "costs_yaml": yaml.dump(costs_export, default_flow_style=False, sort_keys=True),
    }


def write_business_report_artifacts(
    *,
    report_payload: Mapping[str, Any],
    output_dir: str,
) -> Dict[str, str]:
    """Write dashboard and BI-friendly business artifacts to disk."""

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dashboard_path = out_dir / "dashboard_summary.json"
    replay_metadata_path = out_dir / "replay_metadata.json"
    scenario_csv_path = out_dir / "scenario_business_summary.csv"
    item_csv_path = out_dir / "item_business_breakdown.csv"

    write_json_artifact(dashboard_path, dict(report_payload["dashboard_summary"]))
    write_json_artifact(replay_metadata_path, dict(report_payload["replay_metadata"]))
    write_rows_csv(scenario_csv_path, report_payload["scenario_csv_rows"])
    write_rows_csv(item_csv_path, report_payload["item_csv_rows"])

    return {
        "dashboard_summary": str(dashboard_path),
        "replay_metadata": str(replay_metadata_path),
        "scenario_business_summary": str(scenario_csv_path),
        "item_business_breakdown": str(item_csv_path),
    }
