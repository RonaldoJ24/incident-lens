-- Incident Lens Phase 1 PostgreSQL schema. SQLite uses the equivalent schema
-- in incident_lens.api.store for host-local tests.
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  isolation_scope TEXT NOT NULL CHECK (isolation_scope = 'guest')
);

CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  service TEXT NOT NULL,
  fixture_key TEXT NOT NULL,
  telemetry_origin TEXT NOT NULL,
  source_interval_json JSONB NOT NULL,
  fixture_kind TEXT NOT NULL,
  public_example BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  status TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  provenance_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  idempotency_key TEXT,
  UNIQUE (session_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  payload_json JSONB NOT NULL,
  sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  payload_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS timeline_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  payload_json JSONB NOT NULL,
  sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
  correction_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  payload_json JSONB NOT NULL,
  sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  revision INTEGER NOT NULL,
  provenance_json JSONB NOT NULL,
  finding_ids_json JSONB NOT NULL,
  saved_at TIMESTAMPTZ NOT NULL,
  repair_claim BOOLEAN NOT NULL CHECK (repair_claim = FALSE),
  idempotency_key TEXT,
  UNIQUE (session_id, idempotency_key)
);
