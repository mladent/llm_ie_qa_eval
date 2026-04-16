from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import run_evaluation


class FakeTracker:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.logged_run_metrics = 0
        self.logged_artifacts = []

    def start(self):
        return type("Ctx", (), {"enabled": True, "run_id": "fake-run-id"})()

    def end(self) -> None:
        return None

    def log_global_params(self, params):
        return None

    def log_run_record_metrics(self, record, *, step: int):
        self.logged_run_metrics += 1

    def log_document_aggregates(self, aggregates):
        return None

    def log_corpus_aggregate(self, aggregate, *, total_failures: int):
        return None

    def log_artifacts(self, artifact_paths):
        self.logged_artifacts.extend(str(p) for p in artifact_paths)


def test_mocked_repeated_run_persists_outputs_and_handles_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = [
        {
            "id": "doc1",
            "text": "doc one text",
            "gold": {"methods": ["BERT"], "tasks": ["NER"], "datasets": ["CoNLL"]},
        },
        {
            "id": "doc2",
            "text": "doc two text",
            "gold": {"methods": ["GNN"], "tasks": ["RE"], "datasets": []},
        },
    ]

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Extract entities from: {text}", encoding="utf-8")

    out_dir = tmp_path / "outputs"

    calls = {"n": 0}

    def fake_run_extraction(
        provider,
        prompt,
        model=None,
        temperature=0.0,
        top_p=1.0,
        max_tokens=2048,
        expected_fields=None,
    ):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated provider failure")
        return {
            "provider": provider,
            "model": model or "gpt-4o-mini",
            "raw_response_text": "{}",
            "parsed_output_json": {"methods": ["BERT"], "tasks": ["NER"], "datasets": ["CoNLL"]},
            "parse_status": "success",
            "error_message": None,
            "latency_ms": 5.0,
            "input_tokens": 10,
            "output_tokens": 5,
            "estimated_cost": 0.001,
            "model_params_used": {},
        }

    tracker = FakeTracker()

    monkeypatch.setattr(run_evaluation, "run_extraction", fake_run_extraction)
    monkeypatch.setattr(run_evaluation, "MLflowTracker", lambda **kwargs: tracker)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_evaluation.py",
            "--dataset-path",
            str(dataset_path),
            "--prompt-path",
            str(prompt_path),
            "--output-dir",
            str(out_dir),
            "--num-runs",
            "3",
            "--max-retries",
            "0",
            "--provider",
            "openai",
            "--model",
            "gpt-4o-mini",
        ],
    )

    run_evaluation.main()

    exp_dirs = list((out_dir / "experiments").iterdir())
    assert len(exp_dirs) == 1
    exp_dir = exp_dirs[0]

    runs_path = exp_dir / "runs.jsonl"
    failures_path = exp_dir / "failures.jsonl"
    doc_agg_path = exp_dir / "document_aggregates.csv"

    runs_lines = [line for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures_lines = [line for line in failures_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # 2 docs * 3 runs each
    assert len(runs_lines) == 6
    assert len(failures_lines) == 1

    with doc_agg_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2

    assert tracker.logged_run_metrics == 6
    assert tracker.logged_artifacts
