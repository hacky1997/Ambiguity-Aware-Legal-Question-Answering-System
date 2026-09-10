from __future__ import annotations

import base64

from legalrag.telemetry import _otlp_headers


def test_langfuse_headers_use_basic_auth(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    expected = base64.b64encode(b"public:secret").decode()
    assert _otlp_headers() == {"Authorization": f"Basic {expected}"}


def test_generic_otlp_headers_are_supported(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-api-key=value,tenant=legal")
    assert _otlp_headers() == {"x-api-key": "value", "tenant": "legal"}
