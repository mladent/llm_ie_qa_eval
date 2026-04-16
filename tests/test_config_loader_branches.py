from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import config_loader


def _write_base_files(tmp_path: Path) -> tuple[Path, Path]:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("[]", encoding="utf-8")
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt", encoding="utf-8")
    return dataset_path, prompt_path


def _write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "cfg.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_bool_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid boolean value"):
        config_loader._parse_bool("maybe")


def test_load_yaml_file_requires_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level mapping"):
        config_loader._load_yaml_file(p)


def test_env_overrides_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIE_NUM_RUNS", "abc")
    with pytest.raises(ValueError, match="Invalid value for LIE_NUM_RUNS"):
        config_loader._env_overrides()


def test_normalize_data_input_mode_respects_dataset_override() -> None:
    merged = {"data": {"dataset_path": "x.json", "documents": [{"id": "d"}]}}

    out = config_loader._normalize_data_input_mode(
        merged,
        file_config={"data": {}},
        env_config={"data": {"dataset_path": "override.json"}},
        cli_config={"data": {}},
    )

    assert out["data"]["dataset_path"] == "x.json"


def test_validate_config_rejects_provider(tmp_path: Path) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {"dataset_path": str(dataset_path), "prompt_path": str(prompt_path)},
            "model": {"provider": "bad"},
        },
    )
    with pytest.raises(ValueError, match="model.provider"):
        config_loader._validate_config(cfg)


@pytest.mark.parametrize(
    ("patch", "pattern"),
    [
        ({"experiment": {"num_runs": 0}}, "experiment.num_runs"),
        ({"execution": {"max_retries": -1}}, "execution.max_retries"),
        ({"execution": {"retry_backoff_seconds": -1}}, "retry_backoff_seconds"),
        ({"execution": {"timeout_seconds": 0}}, "timeout_seconds"),
        ({"model": {"max_tokens": 0}}, "model.max_tokens"),
        ({"model": {"temperature": 3.0}}, "model.temperature"),
        ({"model": {"top_p": 0.0}}, "model.top_p"),
    ],
)
def test_validate_config_rejects_invalid_scalar_ranges(
    tmp_path: Path,
    patch,
    pattern: str,
) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {"data": {"dataset_path": str(dataset_path), "prompt_path": str(prompt_path)}},
    )
    cfg = config_loader._deep_merge(cfg, patch)

    with pytest.raises(ValueError, match=pattern):
        config_loader._validate_config(cfg)


def test_validate_config_rejects_missing_dataset_and_documents(tmp_path: Path) -> None:
    _, prompt_path = _write_base_files(tmp_path)
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {"data": {"dataset_path": None, "documents": [], "prompt_path": str(prompt_path)}},
    )
    with pytest.raises(ValueError, match="Provide either data.dataset_path"):
        config_loader._validate_config(cfg)


def test_validate_config_rejects_both_dataset_and_documents(tmp_path: Path) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)
    doc_path = tmp_path / "doc.txt"
    gold_path = tmp_path / "gold.json"
    doc_path.write_text("doc", encoding="utf-8")
    gold_path.write_text("{}", encoding="utf-8")

    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": str(dataset_path),
                "prompt_path": str(prompt_path),
                "documents": [
                    {
                        "id": "doc1",
                        "document_path": str(doc_path),
                        "gold_path": str(gold_path),
                    }
                ],
            }
        },
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        config_loader._validate_config(cfg)


def test_validate_config_rejects_missing_required_section(tmp_path: Path) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {"data": {"dataset_path": str(dataset_path), "prompt_path": str(prompt_path)}},
    )
    cfg.pop("exports")

    with pytest.raises(ValueError, match="Missing required config section 'exports'"):
        config_loader._validate_config(cfg)


def test_validate_config_rejects_project_documents_validation_errors(tmp_path: Path) -> None:
    _, prompt_path = _write_base_files(tmp_path)

    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": None,
                "prompt_path": str(prompt_path),
                "documents": ["bad"],
            }
        },
    )
    with pytest.raises(ValueError, match="must be an object"):
        config_loader._validate_config(cfg)

    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": None,
                "prompt_path": str(prompt_path),
                "documents": [{"id": "doc1"}],
            }
        },
    )
    with pytest.raises(ValueError, match="missing required field"):
        config_loader._validate_config(cfg)

    missing_doc = tmp_path / "missing.txt"
    missing_gold = tmp_path / "missing.gold.json"
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": None,
                "prompt_path": str(prompt_path),
                "documents": [
                    {
                        "id": "  ",
                        "document_path": str(missing_doc),
                        "gold_path": str(missing_gold),
                    }
                ],
            }
        },
    )
    with pytest.raises(ValueError, match="non-empty string"):
        config_loader._validate_config(cfg)


def test_validate_config_rejects_path_and_extraction_field_errors(tmp_path: Path) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)
    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": str(tmp_path / "does-not-exist.json"),
                "prompt_path": str(prompt_path),
            }
        },
    )
    with pytest.raises(ValueError, match="does not exist"):
        config_loader._validate_config(cfg)

    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": str(dataset_path),
                "prompt_path": str(prompt_path),
                "extraction_fields": ["ok", ""],
            }
        },
    )
    with pytest.raises(ValueError, match="non-empty strings"):
        config_loader._validate_config(cfg)

    cfg = config_loader._deep_merge(
        config_loader.DEFAULT_CONFIG,
        {
            "data": {
                "dataset_path": str(dataset_path),
                "prompt_path": str(tmp_path / "missing-prompt.txt"),
            }
        },
    )
    with pytest.raises(ValueError, match="data.prompt_path"):
        config_loader._validate_config(cfg)


def test_load_eval_config_applies_cli_and_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset_path, prompt_path = _write_base_files(tmp_path)

    config_path = _write_config(
        tmp_path,
        "\n".join(
            [
                "experiment:",
                '  name: "from-file"',
                "data:",
                f'  dataset_path: "{dataset_path}"',
                f'  prompt_path: "{prompt_path}"',
                '  prompt_id: "p1"',
                "model:",
                '  provider: "openai"',
                '  model: "gpt-4o-mini"',
                "execution:",
                "  max_retries: 1",
                "  retry_backoff_seconds: 0",
                "  timeout_seconds: 60",
                "  continue_on_error: true",
                "tracking:",
                "  enable_mlflow: true",
                '  tracking_uri: "sqlite:///mlflow.db"',
                "  tags: {}",
                "exports:",
                "  write_jsonl: true",
                "  write_csv: true",
                "  write_parquet: false",
                "",
            ]
        ),
    )

    monkeypatch.setenv("LIE_PROVIDER", "gemini")

    args = Namespace(
        config=str(config_path),
        provider=None,
        model="gemini-1.5-pro",
        dataset_path=None,
        prompt_path=None,
        num_runs=3,
        output_dir=None,
        experiment_name=None,
        tracking_uri=None,
        enable_mlflow=None,
        max_retries=None,
        retry_backoff=None,
        prompt_id=None,
        temperature=0.1,
        top_p=0.8,
        max_tokens=100,
    )

    loaded = config_loader.load_eval_config(args)

    assert loaded.model.provider == "gemini"
    assert loaded.model.model == "gemini-1.5-pro"
    assert loaded.experiment.num_runs == 3
    assert loaded.model.temperature == 0.1
    assert loaded.model.max_tokens == 100
