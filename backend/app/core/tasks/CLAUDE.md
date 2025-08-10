# Job Patterns and Idempotency

This directory contains Celery tasks for optimization. Use these conventions:

- Naming: tasks are namespaced with `app.core.tasks.optimization.*`
- Queue: default queue is `optimization`; set `queue="optimization"` on each task
- Timeouts: prefer `soft_time_limit` < `time_limit` by ~25% margin; align broker visibility_timeout
- Prefetch: optimization workers should run with `--prefetch-multiplier=1`

Idempotency
- Compute an `idempotency_key` for every logical run: `sha256(f"opt:{schedule_id}:{sorted(params.items())}")`
- Before heavy work, check Postgres optimization_runs for a terminal record with that key
- Insert a `running` row with the key to claim work; handle conflict to avoid duplicate runs
- Stream progress to `optimization_run_events`
- On success/failure, update `optimization_runs` and optionally persist the solution in `optimization_solutions`

Result persistence
- See ../docs/RESULT_SCHEMA.sql for DDL
- Persist: summary metrics, objective value, solution status, constraint violations, utilization
- Include `inputs_snapshot` with effective constraints for reproducibility

Error handling & retries
- Do not retry on: infeasible model, validation errors
- Retry with backoff on: transient DB errors, Redis connectivity, circuit-open after cool-off
- Map exceptions to error_code: SOLVER_TIMEOUT, MEMORY_EXHAUSTION, NO_FEASIBLE_SOLUTION, SOLVER_CRASH, SERVICE_UNAVAILABLE, RETRY_EXHAUSTED

Worker guidance
- Run a dedicated optimization worker pool:
  `celery -A app.core.celery_app:celery_app worker -l info -Q optimization -c ${CELERYD_CONCURRENCY:-2} --prefetch-multiplier=1`
- Avoid blocking group().get() inside the same pool; use async aggregation

Monitoring
- Emit Prometheus metrics: task duration, retries, failures, queue depth
- Log progress every 10-15% to events table

