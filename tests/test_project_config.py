from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from config_loader import load_eval_config


def test_load_eval_config_supports_project_documents(tmp_path: Path) -> None:
    document_path = tmp_path / "cv1.txt"
    document_path.write_text("Sample CV text", encoding="utf-8")

    gold_path = tmp_path / "cv1.gold.json"
    gold_path.write_text(
        json.dumps({"methods": ["Python"], "tasks": ["NLP"], "datasets": []}),
        encoding="utf-8",
    )

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Extract from {text}", encoding="utf-8")

    config_path = tmp_path / "project.yaml"
    config_path.write_text(
        "\n".join(
            [
                'experiment:',
                '  name: "project-eval"',
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

    config = load_eval_config(Namespace(config=str(config_path)))

    assert config.data.dataset_path is None
    assert len(config.data.documents) == 1
    assert config.data.documents[0].id == "cv1"
    assert config.data.documents[0].document_path == str(document_path)
    assert config.data.documents[0].gold_path == str(gold_path)
    assert config.hybrid.path_syntax == "jsonpath"
    assert config.hybrid.unknown_field_policy.mode == "penalize"