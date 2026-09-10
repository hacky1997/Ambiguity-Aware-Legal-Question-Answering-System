"""Serializable request audit records with personal-data-minimized fields."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditRecord:
    question: str
    behaviour: str
    findings: tuple[str, ...]
    bound_facts: dict[str, str]
    guardrails: dict[str, bool]
    sources: tuple[str, ...]
    component_version: str
    index_version: str
    response_ms: int
    cost: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True, sort_keys=True)


def redact_record(record: AuditRecord, *, redacted_question: str) -> AuditRecord:
    """Return an equivalent audit record with the sanitized question only."""
    return AuditRecord(
        question=redacted_question,
        behaviour=record.behaviour,
        findings=record.findings,
        bound_facts=dict(record.bound_facts),
        guardrails=dict(record.guardrails),
        sources=record.sources,
        component_version=record.component_version,
        index_version=record.index_version,
        response_ms=record.response_ms,
        cost=record.cost,
        metadata=dict(record.metadata),
    )
