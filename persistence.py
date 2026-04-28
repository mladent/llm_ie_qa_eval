from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

from config_loader import EvalConfig
from evaluation.run_record import (
    CanonicalRunRecord,
    CorpusAggregateRecord,
    DocumentAggregateRecord,
    ExperimentProvenance,
)


def ensure_experiment_dir(output_dir: str, experiment_id: str) -> Path:
    """Create and return the experiment output directory."""

    experiment_dir = Path(output_dir) / "experiments" / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    return experiment_dir


def append_jsonl_row(path: Path, payload: Dict[str, Any]) -> None:
    """Append one JSON row to a JSONL artifact."""

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def append_run_record(path: Path, record: CanonicalRunRecord) -> None:
    """Append one canonical run record to JSONL."""

    append_jsonl_row(path, record.to_dict())


def write_config_snapshot(path: Path, config: EvalConfig) -> None:
    """Write a normalized config snapshot for reproducibility."""

    payload = {
        "experiment": asdict(config.experiment),
        "data": asdict(config.data),
        "model": asdict(config.model),
        "execution": asdict(config.execution),
        "tracking": asdict(config.tracking),
        "exports": asdict(config.exports),
        "hybrid": asdict(config.hybrid),
        "config_path": config.config_path,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def write_provenance(path: Path, provenance: ExperimentProvenance) -> None:
    """Write experiment provenance metadata to JSON."""

    with path.open("w", encoding="utf-8") as handle:
        json.dump(provenance.to_dict(), handle, ensure_ascii=True, indent=2)


def write_document_aggregates(
    records: Iterable[DocumentAggregateRecord],
    csv_path: Path,
    parquet_path: Path,
    *,
    write_csv: bool,
    write_parquet: bool,
) -> Dict[str, bool]:
    """Write per-document aggregate artifacts in flat table formats."""

    rows = [record.to_flat_dict() for record in records]
    frame = pd.DataFrame(rows)
    status = {"csv_written": False, "parquet_written": False}

    if write_csv:
        frame.to_csv(csv_path, index=False)
        status["csv_written"] = True

    if write_parquet:
        try:
            frame.to_parquet(parquet_path, index=False)
            status["parquet_written"] = True
        except Exception as exc:  # noqa: BLE001
            print(
                "[warning] Failed to write parquet artifact "
                f"'{parquet_path}': {exc}. Continuing without parquet export."
            )

    return status


def write_corpus_summary(
    path: Path,
    aggregate: CorpusAggregateRecord,
    *,
    total_failures: int,
) -> None:
    """Write corpus-level summary including failure counters."""

    payload = aggregate.to_flat_dict()
    payload["total_failures"] = total_failures
    payload["failure_rate"] = total_failures / aggregate.run_count if aggregate.run_count else 0.0

    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def load_runs_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load run JSONL rows for offline analysis and resumability workflows."""

    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json_artifact(path: Path, payload: Dict[str, Any]) -> None:
    """Write a JSON artifact with stable formatting for offline analysis."""

    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def write_rows_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Write table-like rows to CSV for notebook and BI workflows."""

    frame = pd.DataFrame(list(rows))
    frame.to_csv(path, index=False)
