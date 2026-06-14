from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from business.contracts import BUSINESS_CONTRACT_VERSION, validate_business_contract
from business.types import BusinessContractInput, BusinessCorpusInput, BusinessItemInput, BusinessRunInput


REQUIRED_ARTIFACTS = ("runs.jsonl", "document_aggregates.csv", "corpus_summary.json")


def _to_float(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _to_int(value: Any) -> int:
    return int(value) if value is not None else 0


def _derive_failure_modes(row: Dict[str, Any]) -> List[str]:
    failure_modes: List[str] = []

    if str(row.get("parse_status", "")) != "success":
        failure_modes.append("parse_error")

    if row.get("error_message"):
        failure_modes.append("runtime_error")

    exact_match = bool(row.get("exact_match_with_gold", False))
    if not exact_match:
        failure_modes.append("incorrect")

    return sorted(set(failure_modes))


def _load_runs(path: Path) -> Dict[str, List[BusinessRunInput]]:
    by_item: Dict[str, List[BusinessRunInput]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue

            row = json.loads(line)
            item_id = str(row.get("document_id", ""))
            if not item_id:
                raise ValueError("runs.jsonl includes a row without document_id.")

            run_input = BusinessRunInput(
                run_id=_to_int(row.get("run_index")),
                output=str(row.get("raw_response_text") or ""),
                scores={
                    "precision": _to_float(row.get("precision")),
                    "recall": _to_float(row.get("recall")),
                    "f1": _to_float(row.get("f1")),
                },
                failure_modes=_derive_failure_modes(row),
                parse_status=str(row.get("parse_status") or "unknown"),
                error_message=row.get("error_message"),
            )
            by_item.setdefault(item_id, []).append(run_input)

    return by_item


def _load_document_aggregates(path: Path) -> Dict[str, Dict[str, float]]:
    frame = pd.read_csv(path)
    if "document_id" not in frame.columns:
        raise ValueError("document_aggregates.csv must include a 'document_id' column.")

    by_item: Dict[str, Dict[str, float]] = {}
    required_fields = (
        "mean_precision",
        "mean_recall",
        "mean_f1",
        "parse_error_rate",
        "exact_match_consistency_rate",
        "run_count",
    )

    for _, row in frame.iterrows():
        item_id = str(row["document_id"])
        by_item[item_id] = {}
        for field in required_fields:
            if field not in frame.columns:
                raise ValueError(f"document_aggregates.csv is missing required field '{field}'.")
            by_item[item_id][field] = _to_float(row.get(field))

    return by_item


def _load_corpus_summary(path: Path) -> BusinessCorpusInput:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    required = [
        "experiment_id",
        "provider",
        "model",
        "prompt_id",
        "dataset_id",
        "run_count",
        "document_count",
        "mean_f1",
        "parse_error_rate",
        "failure_rate",
    ]
    for key in required:
        if key not in payload:
            raise ValueError(f"corpus_summary.json is missing required field '{key}'.")

    return BusinessCorpusInput(
        experiment_id=str(payload["experiment_id"]),
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        prompt_id=str(payload["prompt_id"]),
        dataset_id=str(payload["dataset_id"]),
        run_count=_to_int(payload["run_count"]),
        document_count=_to_int(payload["document_count"]),
        mean_f1=_to_float(payload["mean_f1"]),
        parse_error_rate=_to_float(payload["parse_error_rate"]),
        failure_rate=_to_float(payload["failure_rate"]),
    )


def load_business_contract_input(experiment_dir: str) -> BusinessContractInput:
    """Load evaluator artifacts and map them to phase-1 business contract input."""

    exp_dir = Path(experiment_dir)
    if not exp_dir.exists():
        raise ValueError(f"Experiment directory '{exp_dir}' does not exist.")

    for artifact in REQUIRED_ARTIFACTS:
        path = exp_dir / artifact
        if not path.exists():
            raise ValueError(f"Missing required artifact '{artifact}' in '{exp_dir}'.")

    runs_by_item = _load_runs(exp_dir / "runs.jsonl")
    aggregate_by_item = _load_document_aggregates(exp_dir / "document_aggregates.csv")
    corpus = _load_corpus_summary(exp_dir / "corpus_summary.json")

    all_item_ids = sorted(set(runs_by_item) | set(aggregate_by_item))
    items: List[BusinessItemInput] = []
    for item_id in all_item_ids:
        items.append(
            BusinessItemInput(
                item_id=item_id,
                runs=sorted(runs_by_item.get(item_id, []), key=lambda run: run.run_id),
                evaluator_aggregates=aggregate_by_item.get(item_id, {}),
            )
        )

    contract_input = BusinessContractInput(
        business_contract_version=BUSINESS_CONTRACT_VERSION,
        source_experiment_dir=str(exp_dir.resolve()),
        corpus=corpus,
        items=items,
    )

    validate_business_contract(contract_input.to_dict())
    return contract_input
