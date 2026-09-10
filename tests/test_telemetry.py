from __future__ import annotations

from legalrag.telemetry import configure_tracing, span


def test_tracing_is_optional_without_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert configure_tracing(service_name="test", endpoint=None) is False
    with span("test.operation", component="unit"):
        pass
