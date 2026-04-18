from __future__ import annotations

import os
from argparse import Namespace
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    "hybrid": {
        "enabled": False,
        "schema_path": "config/extraction_output.schema.json",
        "rubric_path": "config/hybrid_scoring.yaml",
        "parse_error_behavior": "force_zero",
        "path_syntax": "jsonpath",
        "unknown_field_policy": {
            "mode": "penalize",
            "penalty_weight": 0.1,
        },
        "array_matching": {
            "fallback_strategy": "best_overlap",
        },
        "schema_scoring": {
            "required_weight": 0.4,
            "type_weight": 0.3,
            "enum_weight": 0.2,
            "additional_properties_weight": 0.1,
        },
    },
}


@dataclass
class ExperimentConfig:
    name: str
    seed: int
    output_dir: str
    num_runs: int


@dataclass
class ProjectDocumentConfig:
    id: str
    document_path: str
    gold_path: str


@dataclass
class DataConfig:
    dataset_path: Optional[str]
    prompt_path: str
    prompt_id: str
    documents: List[ProjectDocumentConfig]
    extraction_fields: List[str]


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
class UnknownFieldPolicyConfig:
    mode: str
    penalty_weight: float


@dataclass
class ArrayMatchingConfig:
    fallback_strategy: str


@dataclass
class SchemaScoringConfig:
    required_weight: float
    type_weight: float
    enum_weight: float
    additional_properties_weight: float


@dataclass
class ComparatorConfig:
    name: str
    type: str
    enabled: bool
    params: Dict[str, Any]


@dataclass
class RubricRuleConfig:
    path: str
    comparator: str
    weight: float
    options: Dict[str, Any]


@dataclass
class HybridScoringConfig:
    enabled: bool
    schema_path: str
    rubric_path: str
    parse_error_behavior: str
    path_syntax: str
    unknown_field_policy: UnknownFieldPolicyConfig
    array_matching: ArrayMatchingConfig
    schema_scoring: SchemaScoringConfig
    comparators: List[ComparatorConfig]
    rules: List[RubricRuleConfig]


@dataclass
class EvalConfig:
    experiment: ExperimentConfig
    data: DataConfig
    model: ModelConfig
    execution: ExecutionConfig
    tracking: TrackingConfig
    exports: ExportConfig
    hybrid: HybridScoringConfig
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


def _load_optional_yaml_mapping(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Rubric file '{path}' must contain a top-level mapping/object.")
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


def _normalize_data_input_mode(
    merged: Dict[str, Any],
    file_config: Dict[str, Any],
    env_config: Dict[str, Any],
    cli_config: Dict[str, Any],
) -> Dict[str, Any]:
    data = merged.get("data", {})
    if not data.get("documents"):
        return merged

    dataset_overridden = any(
        source.get("data", {}).get("dataset_path") is not None
        for source in (file_config, env_config, cli_config)
    )
    if not dataset_overridden:
        data["dataset_path"] = None
    return merged


def _validate_config(config: Dict[str, Any]) -> None:
    required_sections = [
        "experiment",
        "data",
        "model",
        "execution",
        "tracking",
        "exports",
        "hybrid",
    ]
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

    data_config = config["data"]
    dataset_path_value = data_config.get("dataset_path")
    documents = data_config.get("documents") or []
    extraction_fields = data_config.get("extraction_fields") or []

    if dataset_path_value and documents:
        raise ValueError(
            "data.dataset_path and data.documents are mutually exclusive. Choose exactly one input mode."
        )

    if not dataset_path_value and not documents:
        raise ValueError(
            "Provide either data.dataset_path for dataset mode or data.documents for project mode."
        )

    if dataset_path_value:
        dataset_path = Path(dataset_path_value)
        if not dataset_path.exists():
            raise ValueError(
                f"data.dataset_path '{dataset_path}' does not exist. Provide a valid dataset path."
            )

    if documents:
        if not isinstance(documents, list):
            raise ValueError("data.documents must be a list of document specifications.")
        if not documents:
            raise ValueError("data.documents must contain at least one document specification.")
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                raise ValueError(
                    f"data.documents[{index}] must be an object with id, document_path, and gold_path."
                )
            missing = [key for key in ("id", "document_path", "gold_path") if key not in document]
            if missing:
                raise ValueError(
                    f"data.documents[{index}] is missing required field(s): {', '.join(missing)}."
                )

            document_id = str(document["id"])
            document_path = Path(document["document_path"])
            gold_path = Path(document["gold_path"])
            if not document_id.strip():
                raise ValueError(f"data.documents[{index}].id must be a non-empty string.")
            if not document_path.exists():
                raise ValueError(
                    f"Document file for data.documents[{index}] does not exist: '{document_path}'."
                )
            if not gold_path.exists():
                raise ValueError(
                    f"Gold file for data.documents[{index}] does not exist: '{gold_path}'."
                )

    if extraction_fields:
        if not isinstance(extraction_fields, list):
            raise ValueError("data.extraction_fields must be a list of field names.")
        if not all(isinstance(field, str) and field.strip() for field in extraction_fields):
            raise ValueError("data.extraction_fields must contain non-empty strings.")

    prompt_path = Path(config["data"]["prompt_path"])
    if not prompt_path.exists():
        raise ValueError(
            f"data.prompt_path '{prompt_path}' does not exist. Provide a valid prompt path."
        )

    hybrid = config["hybrid"]
    parse_error_behavior = hybrid.get("parse_error_behavior")
    if parse_error_behavior not in {"force_zero"}:
        raise ValueError("hybrid.parse_error_behavior must be 'force_zero'.")

    path_syntax = hybrid.get("path_syntax")
    if path_syntax not in {"jsonpath"}:
        raise ValueError("hybrid.path_syntax must be 'jsonpath'.")

    unknown_field_policy = hybrid.get("unknown_field_policy") or {}
    mode = unknown_field_policy.get("mode")
    if mode not in {"ignore", "penalize", "fail_schema"}:
        raise ValueError(
            "hybrid.unknown_field_policy.mode must be one of: ignore, penalize, fail_schema."
        )

    penalty_weight = unknown_field_policy.get("penalty_weight", 0.0)
    if not isinstance(penalty_weight, (int, float)) or penalty_weight < 0:
        raise ValueError("hybrid.unknown_field_policy.penalty_weight must be a non-negative number.")

    array_matching = hybrid.get("array_matching") or {}
    fallback_strategy = array_matching.get("fallback_strategy")
    if fallback_strategy not in {"best_overlap", "strict_non_match", "error"}:
        raise ValueError(
            "hybrid.array_matching.fallback_strategy must be one of: best_overlap, strict_non_match, error."
        )

    schema_scoring = hybrid.get("schema_scoring") or {}
    schema_weights = [
        schema_scoring.get("required_weight", 0.0),
        schema_scoring.get("type_weight", 0.0),
        schema_scoring.get("enum_weight", 0.0),
        schema_scoring.get("additional_properties_weight", 0.0),
    ]
    if not all(isinstance(weight, (int, float)) and weight >= 0 for weight in schema_weights):
        raise ValueError("hybrid.schema_scoring values must be non-negative numbers.")
    if sum(schema_weights) == 0:
        raise ValueError("hybrid.schema_scoring requires a positive total weight.")

    if hybrid.get("enabled"):
        schema_path = Path(hybrid.get("schema_path", ""))
        rubric_path = Path(hybrid.get("rubric_path", ""))
        if not schema_path.exists():
            raise ValueError(
                f"hybrid.schema_path '{schema_path}' does not exist. Provide a valid schema path."
            )
        if not rubric_path.exists():
            raise ValueError(
                f"hybrid.rubric_path '{rubric_path}' does not exist. Provide a valid rubric path."
            )

        rubric = _load_optional_yaml_mapping(rubric_path)
        comparators = rubric.get("comparators", [])
        rules = rubric.get("rules", [])
        if not isinstance(comparators, list):
            raise ValueError("Rubric key 'comparators' must be a list.")
        if not isinstance(rules, list):
            raise ValueError("Rubric key 'rules' must be a list.")


def _build_data_config(data: Dict[str, Any]) -> DataConfig:
    documents = [ProjectDocumentConfig(**document) for document in data.get("documents", [])]
    return DataConfig(
        dataset_path=data.get("dataset_path"),
        prompt_path=data["prompt_path"],
        prompt_id=data["prompt_id"],
        documents=documents,
        extraction_fields=[str(field) for field in data.get("extraction_fields", [])],
    )


def _build_hybrid_config(hybrid: Dict[str, Any]) -> HybridScoringConfig:
    rubric_path = Path(hybrid["rubric_path"])
    rubric_payload = _load_optional_yaml_mapping(rubric_path)
    comparators_payload = rubric_payload.get("comparators", [])
    rules_payload = rubric_payload.get("rules", [])

    comparators = [
        ComparatorConfig(
            name=str(item["name"]),
            type=str(item["type"]),
            enabled=bool(item.get("enabled", True)),
            params=dict(item.get("params", {})),
        )
        for item in comparators_payload
        if isinstance(item, dict)
    ]
    rules = [
        RubricRuleConfig(
            path=str(item["path"]),
            comparator=str(item["comparator"]),
            weight=float(item.get("weight", 1.0)),
            options=dict(item.get("options", {})),
        )
        for item in rules_payload
        if isinstance(item, dict)
    ]

    return HybridScoringConfig(
        enabled=bool(hybrid["enabled"]),
        schema_path=str(hybrid["schema_path"]),
        rubric_path=str(hybrid["rubric_path"]),
        parse_error_behavior=str(hybrid["parse_error_behavior"]),
        path_syntax=str(hybrid["path_syntax"]),
        unknown_field_policy=UnknownFieldPolicyConfig(**hybrid["unknown_field_policy"]),
        array_matching=ArrayMatchingConfig(**hybrid["array_matching"]),
        schema_scoring=SchemaScoringConfig(**hybrid["schema_scoring"]),
        comparators=comparators,
        rules=rules,
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
    merged = _normalize_data_input_mode(merged, file_config, env_config, cli_config)

    _validate_config(merged)

    return EvalConfig(
        experiment=ExperimentConfig(**merged["experiment"]),
        data=_build_data_config(merged["data"]),
        model=ModelConfig(**merged["model"]),
        execution=ExecutionConfig(**merged["execution"]),
        tracking=TrackingConfig(**merged["tracking"]),
        exports=ExportConfig(**merged["exports"]),
        hybrid=_build_hybrid_config(merged["hybrid"]),
        config_path=str(config_path.resolve()),
    )
