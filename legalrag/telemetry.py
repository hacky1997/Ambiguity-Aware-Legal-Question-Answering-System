"""OpenTelemetry setup and small tracing helpers.

Tracing is optional for local runs. When the SDK is not installed or no OTLP
endpoint is configured, spans remain no-op rather than breaking legal answers.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

_TRACER_NAME = "legalrag"
_configured = False
_meter_configured = False
_metrics: dict[str, Any] = {}


def configure_tracing(*, service_name: str = "legalrag", endpoint: str | None = None) -> bool:
    """Configure an OTLP exporter when requested; return whether it was enabled."""
    global _configured
    if _configured:
        return True
    target = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not target:
        return False
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
        )
    except ImportError:
        return False

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=target, headers=_otlp_headers() or None)
        )
    )
    trace.set_tracer_provider(provider)
    _configured = True
    return True


def configure_langfuse(*, service_name: str = "legalrag", host: str | None = None) -> bool:
    """Configure the OTLP HTTP exporter for Langfuse."""
    langfuse_host = host if host is not None else os.getenv("LANGFUSE_HOST", "")
    langfuse_host = langfuse_host.rstrip("/")
    if not langfuse_host:
        return False
    return configure_tracing(
        service_name=service_name,
        endpoint=f"{langfuse_host}/api/public/otel",
    )


def _otlp_headers() -> dict[str, str]:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if public_key and secret_key:
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    raw = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    return dict(item.split("=", 1) for item in raw.split(",") if "=" in item)


def configure_metrics(*, service_name: str = "legalrag", endpoint: str | None = None) -> bool:
    """Configure OTLP metrics and create application metric instruments."""
    global _meter_configured
    if _meter_configured:
        return True
    target = endpoint or os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    if not target:
        return False
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # type: ignore[import-not-found]
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.metrics.export import (  # type: ignore[import-not-found]
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        return False
    exporter = OTLPMetricExporter(endpoint=target, headers=_otlp_headers() or None)
    provider = MeterProvider(
        resource=Resource.create({"service.name": service_name}),
        metric_readers=[PeriodicExportingMetricReader(exporter)],
    )
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(_TRACER_NAME)
    _metrics.update(
        requests=meter.create_counter("legalrag.requests", unit="{request}"),
        failures=meter.create_counter("legalrag.failures", unit="{request}"),
        cost=meter.create_counter("legalrag.estimated_cost", unit="USD"),
        latency=meter.create_histogram("legalrag.request.duration", unit="ms"),
    )
    _meter_configured = True
    return True


def record_request(
    *, behaviour: str | None, duration_ms: float, cost: float = 0.0, failed: bool = False
) -> None:
    """Record request metrics when metrics have been configured."""
    if not _metrics:
        return
    attributes = {"behaviour": behaviour or "unknown"}
    _metrics["requests"].add(1, attributes)
    _metrics["latency"].record(duration_ms, attributes)
    if cost:
        _metrics["cost"].add(cost, attributes)
    if failed:
        _metrics["failures"].add(1, attributes)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Create a span when OpenTelemetry is installed, otherwise yield ``None``."""
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return

    tracer = trace.get_tracer(_TRACER_NAME)
    started = perf_counter()
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, str(value))
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_attribute("error.type", type(exc).__name__)
            raise
        finally:
            current.set_attribute("duration_ms", (perf_counter() - started) * 1000)
