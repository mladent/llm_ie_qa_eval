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
