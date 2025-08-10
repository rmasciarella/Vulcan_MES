-- Result storage schema for CP-SAT optimization runs
-- Safe to apply in a dedicated migration; adjust schema name as needed

BEGIN;

CREATE TABLE IF NOT EXISTS optimization_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key TEXT NOT NULL,
  schedule_id TEXT NULL,
  task_name TEXT NOT NULL,
  queue_name TEXT NOT NULL DEFAULT 'optimization',
  status TEXT NOT NULL CHECK (status IN ('queued','running','success','failed','canceled')),
  requested_by TEXT NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ NULL,
  finished_at TIMESTAMPTZ NULL,
  last_heartbeat_at TIMESTAMPTZ NULL,
  task_id TEXT NULL, -- Celery task id

  -- Inputs and snapshots for reproducibility
  input_params JSONB NULL,
  inputs_snapshot JSONB NULL,

  -- Summary metrics
  makespan_minutes NUMERIC NULL,
  total_tardiness_minutes NUMERIC NULL,
  total_cost NUMERIC NULL,
  objective_value NUMERIC NULL,
  solve_time_seconds NUMERIC NULL,
  quality_score NUMERIC NULL,

  -- Error details
  error_code TEXT NULL,
  error_message TEXT NULL,
  error_details JSONB NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_optimization_runs_idempotency
  ON optimization_runs (idempotency_key);

CREATE INDEX IF NOT EXISTS ix_optimization_runs_status
  ON optimization_runs (status);

CREATE INDEX IF NOT EXISTS ix_optimization_runs_schedule
  ON optimization_runs (schedule_id);


CREATE TABLE IF NOT EXISTS optimization_run_events (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_type TEXT NOT NULL, -- progress|log|warning|error|checkpoint
  progress_percent NUMERIC NULL,
  message TEXT NULL,
  payload JSONB NULL
);

CREATE INDEX IF NOT EXISTS ix_optimization_run_events_run
  ON optimization_run_events (run_id, created_at);


CREATE TABLE IF NOT EXISTS optimization_solutions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL CHECK (status IN ('optimal','feasible','infeasible','unknown','model_invalid')),
  assignments JSONB NOT NULL, -- denormalized task assignments
  resource_utilization JSONB NULL,
  constraint_violations JSONB NULL,
  metadata JSONB NULL
);

CREATE INDEX IF NOT EXISTS ix_optimization_solutions_run
  ON optimization_solutions (run_id);

COMMIT;

