CREATE TABLE IF NOT EXISTS audit_records (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    question TEXT NOT NULL,
    behaviour TEXT NOT NULL,
    findings JSONB NOT NULL,
    bound_facts JSONB NOT NULL,
    guardrails JSONB NOT NULL,
    sources JSONB NOT NULL,
    component_version TEXT NOT NULL,
    index_version TEXT NOT NULL,
    response_ms INTEGER NOT NULL CHECK (response_ms >= 0),
    cost DOUBLE PRECISION,
    metadata JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_records_created_at_idx
    ON audit_records (created_at);
