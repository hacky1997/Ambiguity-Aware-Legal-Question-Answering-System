"""Postgres audit persistence adapter."""

from __future__ import annotations

import json
from typing import Any, Protocol

from legalrag.audit import AuditRecord


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...]) -> Any: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> Any: ...


class AuditStore:
    """Persist minimized audit records using an injected psycopg connection."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def write(self, record: AuditRecord) -> None:
        self._connection.cursor().execute(
            """
            INSERT INTO audit_records
              (question, behaviour, findings, bound_facts, guardrails, sources,
               component_version, index_version, response_ms, cost, metadata)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s::jsonb)
            """,
            (
                record.question,
                record.behaviour,
                json.dumps(record.findings),
                json.dumps(record.bound_facts),
                json.dumps(record.guardrails),
                json.dumps(record.sources),
                record.component_version,
                record.index_version,
                record.response_ms,
                record.cost,
                json.dumps(record.metadata),
            ),
        )
        self._connection.commit()
