from __future__ import annotations

import pytest

from legalrag.api import create_app
from legalrag.evals import SystemOutput


def test_health_endpoint_is_available():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("api extra is not installed")

    app = create_app(lambda question: SystemOutput("ask"))
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
