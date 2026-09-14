-- Phase 4 durable workflow checkpoints. State is typed JSON owned by the workflow.
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
  run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
  checkpoint_id TEXT NOT NULL,
  state_json JSONB NOT NULL,
  status TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
