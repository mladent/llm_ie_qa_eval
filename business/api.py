from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from business.service import BusinessServiceRequest, run_business_service

_UI_HTML_PATH = Path(__file__).parent / "ui_app.html"


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _discover_experiments(base_dir: Path) -> List[Dict[str, Any]]:
    if not base_dir.exists() or not base_dir.is_dir():
        return []

    experiments: List[Dict[str, Any]] = []
    for child in sorted(base_dir.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue

        corpus_path = child / "corpus_summary.json"
        if not corpus_path.exists():
            continue

        timestamp_raw: str | None = None
        parsed_timestamp: datetime | None = None
        model: str | None = None
        provider: str | None = None
        try:
            payload = json.loads(corpus_path.read_text(encoding="utf-8"))
            timestamp_raw = payload.get("timestamp") if isinstance(payload.get("timestamp"), str) else None
            parsed_timestamp = _parse_iso_timestamp(timestamp_raw)
            model = str(payload.get("model")) if payload.get("model") is not None else None
            provider = str(payload.get("provider")) if payload.get("provider") is not None else None
        except Exception:  # noqa: BLE001
            timestamp_raw = None
            parsed_timestamp = None

        if parsed_timestamp is None:
            stat = child.stat()
            parsed_timestamp = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            timestamp_raw = parsed_timestamp.isoformat()

        label_bits = [child.name, parsed_timestamp.astimezone().strftime("%Y-%m-%d %H:%M")]
        if model:
            label_bits.append(model)

        experiments.append(
            {
                "experiment_id": child.name,
                "experiment_dir": str(child),
                "timestamp": timestamp_raw,
                "provider": provider,
                "model": model,
                "display_label": " | ".join(label_bits),
                "sort_ts": parsed_timestamp.timestamp(),
            }
        )

    experiments.sort(
        key=lambda item: (
            float(item.get("sort_ts", 0.0)),
            str(item.get("experiment_id", "")).lower(),
        ),
        reverse=True,
    )
    for item in experiments:
        item.pop("sort_ts", None)
    return experiments


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
        from fastapi import FastAPI, HTTPException, Query  # type: ignore[import-not-found]
        from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "FastAPI is not installed. Install optional deps to enable API serving."
        ) from exc

    from business.service import BusinessInlineConfig, run_business_service_inline

    app = FastAPI(title="Business Evaluation API", version="1.0.0")

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        if not _UI_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="UI page not found.")
        return HTMLResponse(content=_UI_HTML_PATH.read_text(encoding="utf-8"))

    @app.get("/business/experiment-info")
    def experiment_info(
        experiment_dir: str = Query(..., description="Path to experiment artifacts directory"),
    ) -> Dict[str, Any]:
        exp_path = Path(experiment_dir)
        corpus_path = exp_path / "corpus_summary.json"
        if not exp_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Experiment directory not found: '{experiment_dir}'",
            )
        if not corpus_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"corpus_summary.json not found in '{experiment_dir}'",
            )
        try:
            return json.loads(corpus_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read corpus_summary.json: {exc}",
            ) from exc

    @app.get("/business/experiments")
    def list_experiments(
        base_dir: str = Query(
            "outputs/experiments",
            description="Directory containing experiment artifact folders.",
        ),
    ) -> Dict[str, Any]:
        discovered = _discover_experiments(Path(base_dir))
        return {"base_dir": base_dir, "experiments": discovered}

    @app.post("/business/evaluate-inline")
    def evaluate_inline(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            experiment_dir = _required_str(payload, "experiment_dir")

            scenario_name = str(payload.get("scenario_name", "custom")).strip()
            if not scenario_name or not all(c.isalnum() or c == "_" for c in scenario_name):
                raise ValueError(
                    "scenario_name must be non-empty and contain only alphanumeric characters and underscores."
                )

            costs_raw = payload.get("costs", {})
            if not isinstance(costs_raw, dict):
                raise ValueError("'costs' must be a JSON object.")
            costs: Dict[str, float] = {}
            for mode in ("parse_error", "runtime_error", "incorrect"):
                v = costs_raw.get(mode, 0.0)
                if not isinstance(v, (int, float)) or float(v) < 0:
                    raise ValueError(f"costs.{mode} must be a non-negative number.")
                costs[mode] = float(v)

            weights_raw = payload.get("weights", {})
            if not isinstance(weights_raw, dict):
                raise ValueError("'weights' must be a JSON object.")
            weights: Dict[str, float] = {}
            for key in ("success", "stability", "quality", "risk", "critical"):
                v = weights_raw.get(key, 0.0)
                if not isinstance(v, (int, float)) or float(v) < 0:
                    raise ValueError(f"weights.{key} must be a non-negative number.")
                weights[key] = float(v)
            weight_sum = sum(weights.values())
            if abs(weight_sum - 1.0) > 0.01:
                raise ValueError(f"weights must sum to 1.0 (got {weight_sum:.4f}).")

            go_threshold = float(payload.get("go_threshold", 0.73))
            conditional_threshold = float(payload.get("conditional_threshold", 0.55))
            if conditional_threshold >= go_threshold:
                raise ValueError("conditional_threshold must be less than go_threshold.")

            config = BusinessInlineConfig(
                experiment_dir=experiment_dir,
                scenario_name=scenario_name,
                costs=costs,
                weights=weights,
                go_threshold=go_threshold,
                conditional_threshold=conditional_threshold,
                max_critical_failure_rate=float(payload.get("max_critical_failure_rate", 0.05)),
                max_expected_cost_per_1000=float(payload.get("max_expected_cost_per_1000", 6000.0)),
                min_stability_score=float(payload.get("min_stability_score", 0.60)),
                cost_cap=float(payload.get("cost_cap", 10000.0)),
            )
            result = run_business_service_inline(config)
            return {
                "dashboard_summary": result["dashboard_summary"],
                "thresholds_yaml": result["thresholds_yaml"],
                "costs_yaml": result["costs_yaml"],
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/business/evaluate")
    def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return evaluate_business_payload(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
