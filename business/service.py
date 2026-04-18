from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from business.reporting import build_business_report, write_business_report_artifacts


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
