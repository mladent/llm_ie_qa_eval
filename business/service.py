from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from business.reporting import build_business_report, build_business_report_inline, write_business_report_artifacts


@dataclass
class BusinessServiceRequest:
    """Stable boundary request for business evaluation execution."""

    experiment_dir: str
    scenario: str = "default"
    settings_config_path: str = "config/business_settings.yaml"
    thresholds_config_path: str = "config/business_thresholds.yaml"
    costs_config_path: str = "config/business_costs.yaml"
    contract_config_path: str = "config/business_contract.yaml"
    output_dir: Optional[str] = None
    write_artifacts: bool = True


@dataclass
class BusinessInlineConfig:
    """Inline config for UI-driven evaluation — no YAML config files required."""

    experiment_dir: str
    scenario_name: str
    costs: Dict[str, float]
    weights: Dict[str, float]
    go_threshold: float
    conditional_threshold: float
    max_critical_failure_rate: float
    max_expected_cost_per_1000: float
    min_stability_score: float
    cost_cap: float = 10000.0


@dataclass
class BusinessServiceResponse:
    """Stable boundary response that can be reused by future API adapters."""

    dashboard_summary: Dict[str, Any]
    replay_metadata: Dict[str, Any]
    scenario_csv_rows: list[Dict[str, Any]]
    item_csv_rows: list[Dict[str, Any]]
    artifact_paths: Dict[str, str]


def run_business_service(request: BusinessServiceRequest) -> BusinessServiceResponse:
    """Run business evaluation through a service-like boundary contract."""

    report = build_business_report(
        experiment_dir=request.experiment_dir,
        scenario=request.scenario,
        settings_config_path=request.settings_config_path,
        thresholds_config_path=request.thresholds_config_path,
        costs_config_path=request.costs_config_path,
        contract_config_path=request.contract_config_path,
    )

    artifact_paths: Dict[str, str] = {}
    if request.write_artifacts:
        destination = (
            request.output_dir
            if request.output_dir is not None
            else str(Path(request.experiment_dir).resolve() / "business")
        )
        artifact_paths = write_business_report_artifacts(
            report_payload=report,
            output_dir=destination,
        )

    return BusinessServiceResponse(
        dashboard_summary=dict(report["dashboard_summary"]),
        replay_metadata=dict(report["replay_metadata"]),
        scenario_csv_rows=list(report["scenario_csv_rows"]),
        item_csv_rows=list(report["item_csv_rows"]),
        artifact_paths=artifact_paths,
    )


def run_business_service_inline(config: BusinessInlineConfig) -> Dict[str, Any]:
    """Run business evaluation with inline config dicts; returns dashboard + YAML exports."""

    return build_business_report_inline(
        experiment_dir=config.experiment_dir,
        scenario_name=config.scenario_name,
        costs=config.costs,
        weights=config.weights,
        go_threshold=config.go_threshold,
        conditional_threshold=config.conditional_threshold,
        max_critical_failure_rate=config.max_critical_failure_rate,
        max_expected_cost_per_1000=config.max_expected_cost_per_1000,
        min_stability_score=config.min_stability_score,
        cost_cap=config.cost_cap,
    )

    """Run business evaluation through a service-like boundary contract."""

    report = build_business_report(
        experiment_dir=request.experiment_dir,
        scenario=request.scenario,
        settings_config_path=request.settings_config_path,
        thresholds_config_path=request.thresholds_config_path,
        costs_config_path=request.costs_config_path,
        contract_config_path=request.contract_config_path,
    )

    artifact_paths: Dict[str, str] = {}
    if request.write_artifacts:
        destination = (
            request.output_dir
            if request.output_dir is not None
            else str(Path(request.experiment_dir).resolve() / "business")
        )
        artifact_paths = write_business_report_artifacts(
            report_payload=report,
            output_dir=destination,
        )

    return BusinessServiceResponse(
        dashboard_summary=dict(report["dashboard_summary"]),
        replay_metadata=dict(report["replay_metadata"]),
        scenario_csv_rows=list(report["scenario_csv_rows"]),
        item_csv_rows=list(report["item_csv_rows"]),
        artifact_paths=artifact_paths,
    )
