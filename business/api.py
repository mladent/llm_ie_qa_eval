from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from business.service import BusinessServiceRequest, run_business_service


def _required_str(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Payload field '{key}' is required and must be non-empty.")
    return str(value)


def evaluate_business_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP-friendly adapter that preserves business contract payload shape."""

    request = BusinessServiceRequest(
        experiment_dir=_required_str(payload, "experiment_dir"),
        scenario=str(payload.get("scenario", "default")),
        settings_config_path=str(payload.get("settings_config_path", "config/business_settings.yaml")),
        thresholds_config_path=str(
            payload.get("thresholds_config_path", "config/business_thresholds.yaml")
        ),
        costs_config_path=str(payload.get("costs_config_path", "config/business_costs.yaml")),
        contract_config_path=str(
            payload.get("contract_config_path", "config/business_contract.yaml")
        ),
        output_dir=(str(payload["output_dir"]) if payload.get("output_dir") is not None else None),
        write_artifacts=bool(payload.get("write_artifacts", True)),
    )
    response = run_business_service(request)
    return asdict(response)


def create_fastapi_app() -> Any:
    """Create FastAPI app lazily to avoid mandatory dependency in core runtime."""

    try:
        from fastapi import FastAPI  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "FastAPI is not installed. Install optional deps to enable API serving."
        ) from exc

    app = FastAPI(title="Business Evaluation API", version="1.0.0")

    @app.post("/business/evaluate")
    def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
        return evaluate_business_payload(payload)

    return app
