"""FastAPI boundary for the deterministic assessment service."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from legalrag.audit import AuditRecord
from legalrag.guardrails import check_input
from legalrag.privacy import PrivacyUnavailableError, redact_personal_data
from legalrag.telemetry import configure_langfuse, configure_metrics, record_request, span


class AssessmentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)


class AssessmentResponse(BaseModel):
    behaviour: str
    provisions: tuple[str, ...]
    findings: tuple[str, ...]
    assumption: str | None = None


def create_app(
    system: Callable[[str], Any],
    *,
    audit_sink: Callable[[AuditRecord], None] | None = None,
) -> Any:
    """Create the API without importing FastAPI until the API is requested."""
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for the API extra") from exc

    app = FastAPI(title="Ambiguity-aware legal QA")
    configure_langfuse()
    configure_metrics()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/assess", response_model=AssessmentResponse)
    async def assess(request: AssessmentRequest) -> AssessmentResponse:
        started = perf_counter()
        with span("legalrag.assess", question_length=len(request.question)) as current_span:
            rail = await check_input(request.question)
            if not rail.allowed:
                record_request(
                    behaviour="blocked",
                    duration_ms=(perf_counter() - started) * 1000,
                    failed=True,
                )
                raise HTTPException(status_code=400, detail=rail.reason)
            try:
                redacted = redact_personal_data(rail.redacted_text)
            except PrivacyUnavailableError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            result = system(redacted.text)
            if current_span is not None:
                current_span.set_attribute("legalrag.behaviour", result.behaviour)
                current_span.set_attribute("legalrag.findings", ",".join(result.findings))
            response = AssessmentResponse(
                behaviour=result.behaviour,
                provisions=tuple(result.provisions),
                findings=tuple(result.findings),
                assumption=result.assumption,
            )
            if audit_sink is not None:
                audit_sink(
                    AuditRecord(
                        question=redacted.text,
                        behaviour=response.behaviour,
                        findings=response.findings,
                        bound_facts={},
                        guardrails={"nemo_input": rail.allowed},
                        sources=(),
                        component_version="0.1.0",
                        index_version="unconfigured",
                        response_ms=0,
                    )
                )
            record_request(
                behaviour=response.behaviour,
                duration_ms=(perf_counter() - started) * 1000,
            )
            return response

    return app
