from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_evaluation


class FakeTracker:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.global_params = None
        self.logged_artifacts = []

    def start(self):
        return type("Ctx", (), {"enabled": True, "run_id": "fake-run-id"})()

    def end(self) -> None:
        return None

    def log_global_params(self, params):
        self.global_params = params

    def log_run_record_metrics(self, record, *, step: int):
        return None

    def log_document_aggregates(self, aggregates):
        return None

    def log_corpus_aggregate(self, aggregate, *, total_failures: int):
        return None

    def log_artifacts(self, artifact_paths):
        self.logged_artifacts.extend(str(p) for p in artifact_paths)


def test_project_config_run_writes_manifest_and_logs_project_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_path = tmp_path / "cv1.txt"
    document_path.write_text("Jane Doe knows Python and NLP.", encoding="utf-8")

    gold_path = tmp_path / "cv1.gold.json"
    gold_path.write_text(
        json.dumps(
            {
                "programming_languages": ["Python"],
                "programming_tools_skills": ["MLflow"],
                "human_languages": ["English"],
            }
        ),
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Extract from {text}", encoding="utf-8")

    output_dir = tmp_path / "outputs"
    config_path = tmp_path / "project.yaml"
    config_path.write_text(
        "\n".join(
            [
                'experiment:',
                '  name: "project-eval"',
                '  output_dir: "' + str(output_dir) + '"',
                '  num_runs: 2',
                'data:',
                '  prompt_path: "' + str(prompt_path) + '"',
                '  prompt_id: "cv-extract-v1"',
                '  documents:',
                '    - id: "cv1"',
                '      document_path: "' + str(document_path) + '"',
                '      gold_path: "' + str(gold_path) + '"',
                'model:',
                '  provider: "openai"',
                '  model: "gpt-4o-mini"',
                'execution:',
                '  max_retries: 0',
                '  retry_backoff_seconds: 0',
                '  timeout_seconds: 60',
                '  continue_on_error: true',
                'tracking:',
                '  enable_mlflow: false',
                '  tracking_uri: "sqlite:///mlflow.db"',
                '  tags: {}',
                'exports:',
                '  write_jsonl: true',
                '  write_csv: true',
                '  write_parquet: false',
                '',
            ]
        ),
        encoding="utf-8",
    )

    def fake_run_extraction(provider, prompt, model=None, temperature=0.0, top_p=1.0, max_tokens=2048):
        return {
            "provider": provider,
            "model": model or "gpt-4o-mini",
            "raw_response_text": "{}",
            "parsed_output_json": {
                "programming_languages": ["Python"],
                "programming_tools_skills": ["MLflow"],
                "human_languages": ["English"],
            },
            "parse_status": "success",
            "error_message": None,
            "latency_ms": 10.0,
            "input_tokens": 12,
            "output_tokens": 6,
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
            "--config",
            str(config_path),
        ],
    )

    run_evaluation.main()

    exp_dirs = list((output_dir / "experiments").iterdir())
    assert len(exp_dirs) == 1

    exp_dir = exp_dirs[0]
    project_manifest_path = exp_dir / "project_manifest.json"
    runs_path = exp_dir / "runs.jsonl"
    provenance_path = exp_dir / "provenance.json"

    assert project_manifest_path.exists()
    assert provenance_path.exists()

    runs_lines = [line for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(runs_lines) == 2

    project_manifest = json.loads(project_manifest_path.read_text(encoding="utf-8"))
    assert project_manifest["project_config_path"] == str(config_path.resolve())
    assert project_manifest["documents"][0]["id"] == "cv1"
    assert project_manifest["extraction_fields"] == [
        "programming_languages",
        "programming_tools_skills",
        "human_languages",
    ]

    assert tracker.global_params is not None
    assert tracker.global_params["input_mode"] == "project"
    assert tracker.global_params["document_count"] == 1
    assert tracker.global_params["project_config_path"] == str(config_path.resolve())