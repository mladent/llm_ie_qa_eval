from __future__ import annotations

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
