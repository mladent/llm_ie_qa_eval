from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from business.api import create_fastapi_app, evaluate_business_payload


def test_evaluate_business_payload_requires_experiment_dir() -> None:
    with pytest.raises(ValueError, match="experiment_dir"):
        evaluate_business_payload({"scenario": "default"})


def test_create_fastapi_app_or_import_error() -> None:
    try:
        app = create_fastapi_app()
    except ImportError as exc:
        assert "FastAPI is not installed" in str(exc)
    else:
        assert hasattr(app, "router")


def test_openapi_and_endpoint_contract_when_fastapi_available() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("fastapi.testclient")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    app = create_fastapi_app()
    client = TestClient(app)

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json().get("paths", {})
    assert "/business/evaluate" in paths
    assert "post" in paths["/business/evaluate"]

    response = client.post("/business/evaluate", json={"scenario": "default"})
    assert response.status_code == 400
    assert "experiment_dir" in response.json().get("detail", "")


def test_list_experiments_returns_timestamped_options(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("fastapi.testclient")

    from fastapi.testclient import TestClient  # type: ignore[import-not-found]

    exp_a = tmp_path / "exp-a"
    exp_b = tmp_path / "exp-b"
    exp_c = tmp_path / "exp-c"
    exp_a.mkdir()
    exp_b.mkdir()
    exp_c.mkdir()

    (exp_a / "corpus_summary.json").write_text(
        json.dumps({"timestamp": "2026-01-01T10:00:00+00:00", "model": "gpt-a"}),
        encoding="utf-8",
    )
    (exp_b / "corpus_summary.json").write_text(
        json.dumps({"timestamp": "2026-01-02T10:00:00+00:00", "model": "gpt-b"}),
        encoding="utf-8",
    )
    (exp_c / "corpus_summary.json").write_text(
        json.dumps({"model": "fallback"}),
        encoding="utf-8",
    )
    os.utime(exp_c, (1_600_000_000, 1_600_000_000))

    app = create_fastapi_app()
    client = TestClient(app)

    response = client.get("/business/experiments", params={"base_dir": str(tmp_path)})
    assert response.status_code == 200
    payload = response.json()

    experiments = payload.get("experiments", [])
    assert len(experiments) == 3
    assert experiments[0]["experiment_id"] == "exp-b"
    assert experiments[1]["experiment_id"] == "exp-a"

    labels = [item.get("display_label", "") for item in experiments]
    assert any("2026-01-02" in label and "gpt-b" in label for label in labels)
    assert all(item.get("experiment_dir") for item in experiments)
