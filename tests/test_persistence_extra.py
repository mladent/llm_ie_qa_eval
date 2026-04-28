from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import persistence


@dataclass
class _FakeAggregate:
    run_count: int = 0

    def to_flat_dict(self):
        return {"run_count": self.run_count, "mean_f1": 0.5}


def test_load_runs_jsonl_returns_empty_when_missing(tmp_path: Path) -> None:
    rows = persistence.load_runs_jsonl(tmp_path / "missing.jsonl")
    assert rows == []


def test_load_runs_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    path.write_text('{"a": 1}\n\n {"b": 2}\n', encoding="utf-8")

    rows = persistence.load_runs_jsonl(path)

    assert rows == [{"a": 1}, {"b": 2}]


def test_write_document_aggregates_handles_parquet_error(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "agg.csv"
    parquet_path = tmp_path / "agg.parquet"

    def _fail_parquet(self, path, index=False):
        raise RuntimeError("no parquet backend")

    monkeypatch.setattr("pandas.DataFrame.to_parquet", _fail_parquet)

    status = persistence.write_document_aggregates(
        [_FakeAggregate(run_count=3)],
        csv_path,
        parquet_path,
        write_csv=True,
        write_parquet=True,
    )

    assert csv_path.exists()
    assert status == {"csv_written": True, "parquet_written": False}


def test_write_json_artifact_and_rows_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "artifact.json"
    csv_path = tmp_path / "rows.csv"

    persistence.write_json_artifact(json_path, {"k": "v"})
    persistence.write_rows_csv(csv_path, [{"a": 1}, {"a": 2}])

    assert json.loads(json_path.read_text(encoding="utf-8")) == {"k": "v"}
    assert csv_path.exists()
