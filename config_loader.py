from __future__ import annotations

import os
from argparse import Namespace
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml  # type: ignore[import-not-found]


DEFAULT_SETTINGS_PATH = "config/eval_settings.yaml"

DEFAULT_CONFIG: Dict[str, Dict[str, Any]] = {
    "experiment": {
        "name": "llm-json-eval",
        "seed": 42,
        "output_dir": "outputs",
        "num_runs": 5,
    },
    "data": {
        "dataset_path": "data/dataset.json",
        "prompt_path": "prompts/extraction_prompt.txt",
        "prompt_id": "extraction-v1",
    },
    "model": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "top_p": 1.0,
        "max_tokens": 2048,
    },
    "execution": {
        "max_retries": 3,
        "retry_backoff_seconds": 2,
        "timeout_seconds": 60,
        "continue_on_error": True,
    },
    "tracking": {
        "enable_mlflow": True,
        "tracking_uri": "sqlite:///mlflow.db",
        "tags": {
            "project": "llm_ie_qa_eval",
            "corpus": "default",
        },
    },
    "exports": {
        "write_jsonl": True,
        "write_csv": True,
        "write_parquet": True,
    },
}


@dataclass
class ExperimentConfig:
    name: str
    seed: int
    output_dir: str
    num_runs: int


@dataclass
class DataConfig:
    dataset_path: str
    prompt_path: str
    prompt_id: str


@dataclass
class ModelConfig:
    provider: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int


@dataclass
class ExecutionConfig:
    max_retries: int
    retry_backoff_seconds: int
    timeout_seconds: int
    continue_on_error: bool


@dataclass
class TrackingConfig:
    enable_mlflow: bool
    tracking_uri: str
    tags: Dict[str, str]


@dataclass
class ExportConfig:
    write_jsonl: bool
    write_csv: bool
    write_parquet: bool


@dataclass
class EvalConfig:
    experiment: ExperimentConfig
    data: DataConfig
    model: ModelConfig
    execution: ExecutionConfig
    tracking: TrackingConfig
    exports: ExportConfig
    config_path: str


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value '{value}'. Use true/false style values.")


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(
            f"Config file not found at '{path}'. Pass --config with a valid path or create the file."
        )
    with path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Config file '{path}' must contain a top-level mapping/object.")
    return parsed


def _env_overrides() -> Dict[str, Dict[str, Any]]:
    mapping = {
        "LIE_PROVIDER": ("model", "provider", str),
        "LIE_MODEL": ("model", "model", str),
        "LIE_NUM_RUNS": ("experiment", "num_runs", int),
        "LIE_DATASET_PATH": ("data", "dataset_path", str),
        "LIE_PROMPT_PATH": ("data", "prompt_path", str),
        "LIE_OUTPUT_DIR": ("experiment", "output_dir", str),
        "LIE_ENABLE_MLFLOW": ("tracking", "enable_mlflow", _parse_bool),
        "LIE_TRACKING_URI": ("tracking", "tracking_uri", str),
        "LIE_EXPERIMENT_NAME": ("experiment", "name", str),
        "LIE_PROMPT_ID": ("data", "prompt_id", str),
        "LIE_MAX_RETRIES": ("execution", "max_retries", int),
        "LIE_RETRY_BACKOFF": ("execution", "retry_backoff_seconds", int),
    }

    overrides: Dict[str, Dict[str, Any]] = {}
    for env_var, (section, key, cast_fn) in mapping.items():
        raw = os.getenv(env_var)
        if raw is None:
            continue
        try:
            value = cast_fn(raw)
        except Exception as exc:
            raise ValueError(f"Invalid value for {env_var}: {exc}") from exc
        overrides.setdefault(section, {})[key] = value

    return overrides


def _cli_overrides(args: Namespace) -> Dict[str, Dict[str, Any]]:
    mapping = {
        "provider": ("model", "provider"),
        "model": ("model", "model"),
        "dataset_path": ("data", "dataset_path"),
        "prompt_path": ("data", "prompt_path"),
        "num_runs": ("experiment", "num_runs"),
        "output_dir": ("experiment", "output_dir"),
        "experiment_name": ("experiment", "name"),
        "tracking_uri": ("tracking", "tracking_uri"),
        "enable_mlflow": ("tracking", "enable_mlflow"),
        "max_retries": ("execution", "max_retries"),
        "retry_backoff": ("execution", "retry_backoff_seconds"),
        "prompt_id": ("data", "prompt_id"),
        "temperature": ("model", "temperature"),
        "top_p": ("model", "top_p"),
        "max_tokens": ("model", "max_tokens"),
    }

    overrides: Dict[str, Dict[str, Any]] = {}
    for attr_name, (section, key) in mapping.items():
        value = getattr(args, attr_name, None)
        if value is None:
            continue
        overrides.setdefault(section, {})[key] = value

    return overrides


def _validate_config(config: Dict[str, Any]) -> None:
    required_sections = ["experiment", "data", "model", "execution", "tracking", "exports"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section '{section}'.")

    provider = config["model"]["provider"]
    if provider not in {"openai", "gemini"}:
        raise ValueError("model.provider must be either 'openai' or 'gemini'.")

    if config["experiment"]["num_runs"] < 1:
        raise ValueError("experiment.num_runs must be >= 1.")

    if config["execution"]["max_retries"] < 0:
        raise ValueError("execution.max_retries must be >= 0.")

    if config["execution"]["retry_backoff_seconds"] < 0:
        raise ValueError("execution.retry_backoff_seconds must be >= 0.")

    if config["execution"]["timeout_seconds"] <= 0:
        raise ValueError("execution.timeout_seconds must be > 0.")

    if config["model"]["max_tokens"] <= 0:
        raise ValueError("model.max_tokens must be > 0.")

    if not 0 <= config["model"]["temperature"] <= 2:
        raise ValueError("model.temperature must be between 0 and 2.")

    if not 0 < config["model"]["top_p"] <= 1:
        raise ValueError("model.top_p must be in the range (0, 1].")

    dataset_path = Path(config["data"]["dataset_path"])
    if not dataset_path.exists():
        raise ValueError(
            f"data.dataset_path '{dataset_path}' does not exist. Provide a valid dataset path."
        )

    prompt_path = Path(config["data"]["prompt_path"])
    if not prompt_path.exists():
        raise ValueError(
            f"data.prompt_path '{prompt_path}' does not exist. Provide a valid prompt path."
        )


def load_eval_config(args: Namespace) -> EvalConfig:
    """Load and validate config with precedence CLI > env > file > defaults."""

    config_path = Path(getattr(args, "config", DEFAULT_SETTINGS_PATH))

    file_config = _load_yaml_file(config_path)
    env_config = _env_overrides()
    cli_config = _cli_overrides(args)

    merged = _deep_merge(DEFAULT_CONFIG, file_config)
    merged = _deep_merge(merged, env_config)
    merged = _deep_merge(merged, cli_config)

    _validate_config(merged)

    return EvalConfig(
        experiment=ExperimentConfig(**merged["experiment"]),
        data=DataConfig(**merged["data"]),
        model=ModelConfig(**merged["model"]),
        execution=ExecutionConfig(**merged["execution"]),
        tracking=TrackingConfig(**merged["tracking"]),
        exports=ExportConfig(**merged["exports"]),
        config_path=str(config_path.resolve()),
    )
