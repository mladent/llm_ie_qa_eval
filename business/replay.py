from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml  # type: ignore[import-not-found]

from evaluation.run_record import utc_now_iso


def _load_yaml_mapping(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"Config file not found at '{config_path}'.")
    with config_path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Config file '{config_path}' must contain a top-level mapping.")
    return parsed


def sha256_json(payload: Mapping[str, Any]) -> str:
    """Hash JSON-serializable payload with stable ordering."""

    packed = json.dumps(dict(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _scenario_override(payload: Mapping[str, Any], scenario: str) -> Dict[str, Any]:
    default_cfg = payload.get("default")
    if not isinstance(default_cfg, dict):
        return {}

    resolved = dict(default_cfg)
    if scenario in payload and isinstance(payload[scenario], dict):
        override = dict(payload[scenario])
        if "hard_gates" in resolved or "hard_gates" in override:
            resolved["hard_gates"] = {
                **resolved.get("hard_gates", {}),
                **override.get("hard_gates", {}),
            }
        for key, value in override.items():
            if key != "hard_gates":
                resolved[key] = value
    return resolved


def build_effective_business_config(
    *,
    scenario: str,
    settings_config_path: str,
    thresholds_config_path: str,
    costs_config_path: str,
    contract_config_path: str,
) -> Dict[str, Any]:
    """Build effective replay config snapshot used to compute business outputs."""

    settings = _load_yaml_mapping(settings_config_path)
    thresholds = _load_yaml_mapping(thresholds_config_path)
    costs = _load_yaml_mapping(costs_config_path)
    contract_cfg = _load_yaml_mapping(contract_config_path)

    effective = {
        "scenario": scenario,
        "business_config_version": str(settings.get("business_config_version", "1.0.0")),
        "business_contract_version": str(contract_cfg.get("business_contract_version", "1.0.0")),
        "settings": {
            "readiness": settings.get("readiness", {}),
            "normalization": settings.get("normalization", {}),
            "rounding": settings.get("rounding", {}),
            "warnings": settings.get("warnings", {}),
        },
        "thresholds": _scenario_override(thresholds, scenario),
        "costs": _scenario_override(costs, scenario),
    }
    effective["business_config_hash"] = sha256_json(effective)
    return effective


def build_replay_metadata(
    *,
    source_experiment_dir: str,
    effective_business_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Create replay lineage payload for audit and reproducibility."""

    source_dir = Path(source_experiment_dir).resolve()
    return {
        "source_experiment_id": source_dir.name,
        "source_experiment_dir": str(source_dir),
        "replay_timestamp": utc_now_iso(),
        "business_contract_version": str(
            effective_business_config.get("business_contract_version", "1.0.0")
        ),
        "business_config_version": str(
            effective_business_config.get("business_config_version", "1.0.0")
        ),
        "business_config_hash": str(effective_business_config.get("business_config_hash", "")),
    }
