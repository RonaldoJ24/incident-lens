-- Phase 2 artifact metadata only. Raw and derived bytes stay in object storage.
-- Runtime verification requires PostgreSQL/containers and is intentionally
-- pending on this host.
CREATE TABLE IF NOT EXISTS artifact_references (
  artifact_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('raw', 'normalized', 'quality', 'manifest')),
  object_bucket TEXT NOT NULL,
  object_key TEXT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
  source_version TEXT NOT NULL,
  manifest_hash CHAR(64),
  access_scope TEXT NOT NULL CHECK (access_scope IN ('private', 'guest_session', 'public_derived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (object_bucket, object_key),
  UNIQUE (case_id, artifact_kind, sha256)
);

CREATE INDEX IF NOT EXISTS artifact_references_case_idx
  ON artifact_references (case_id, artifact_kind, created_at DESC);
