# CP-SAT Scheduler + Job Queue Audit and Design

Scope covered
- Celery + Redis configuration audit
- Worker service architecture review
- Job idempotency patterns and conventions
- Result storage schema (Postgres) for optimization runs
- Optimization task flow + error recovery
- Resource allocation and work cell constraints (CP-SAT)
- Actionable recommendations

---

1) Celery + Redis configuration audit

What’s in place
- Celery app at app/core/celery_app.py
  - Broker: settings.celery_broker_url (defaults to Redis via Settings.REDIS_URL)
  - Result backend: settings.celery_result_backend (defaults to Redis URL)
  - JSON serialization, UTC, task_track_started enabled
  - acks_late=True, task_reject_on_worker_lost=True
  - worker_prefetch_multiplier from settings (default 4)
  - result_expires=3600, result_compression=gzip
  - Task routing to queues: scheduling, optimization, maintenance, reporting
  - Beat schedule: periodic cache cleanup, optimize_pending_schedules (5 min), daily report, health check
- Docker Compose provides redis:7-alpine and backend with REDIS_URL injected
- Tasks defined in app/core/tasks/optimization.py including long-running optimize_schedule and periodic optimize_pending_schedules

Gaps and risks
- Redis as result backend with result_expires=3600 means results are ephemeral and not queryable for history/analytics; no persistence for audit trails.
- acks_late=True without explicit visibility_timeout configuration at broker layer may cause redelivery issues under long tasks; also soft/hard timeouts need alignment with broker visibility.
- worker_max_tasks_per_child=100 helps mitigate memory leaks, but no autoscaling guidance; concurrency and prefetch default may starve other queues under heavy optimization load.
- No explicit task_queues / queue QoS definitions beyond routes; priority mapping exists (TaskPriority) but no broker priority lanes configured.
- Idempotency not enforced at task boundary (no idempotency keys or de-dup checks).
- No explicit chords/callbacks result storage beyond Redis; group().get(timeout=900) in a periodic task can block and risk worker hangs.
- No dedicated Celery worker command/process definitions in docs (e.g., separate pool for optimization with low prefetch and limited concurrency to cap CPU/memory pressure).

Recommendations
- Persist results in Postgres: use dedicated tables for optimization_runs, optimization_run_events, optimization_summaries (DDL included below). Keep Redis as transient backend for in-flight state; write terminal results to Postgres in on_success/on_failure hooks or inside task logic.
- Tune QoS for long-running optimization:
  - Set worker_prefetch_multiplier=1 for optimization queue workers to prevent head-of-line blocking.
  - Use separate worker deployments per queue: e.g., worker-optimization (–queues optimization –concurrency=N –prefetch-multiplier=1), worker-default (scheduling, reporting, maintenance).
  - Consider solo or threads pool for CP-SAT if GIL/CPU behavior is CPU bound; typically use process pool with lower concurrency matching cores.
- Visibility timeout alignment: if using Redis broker, set broker_transport_options: visibility_timeout to > max(time_limit) for long tasks to avoid premature redelivery.
- Explicit task_queues in config to declare available queues and their default priorities; document routing rules.
- Use task_annotations for per-task acks_late, rate limits, soft_time_limit overrides where appropriate.
- For periodic optimize_pending_schedules: avoid blocking get(timeout=900) from the same worker pool running the subtasks (deadlock / capacity risk). Instead, dispatch group and return quickly; track results asynchronously and aggregate in Postgres.
- Observability: emit Prometheus counters/gauges for task latency, retries, failures by queue; Sentry integration for exceptions.


2) Worker service architecture review

Current
- Single Celery app with multiple queues; not clear separation of worker processes at runtime.

Proposed baseline
- Process types:
  - worker-optimization: handles app.core.tasks.optimization.*
    - env: CELERYD_CONCURRENCY=<num_cores_or_half>, CELERY_PREFETCH=1
    - flags: –queues optimization –concurrency ${CELERYD_CONCURRENCY} –prefetch-multiplier=1 –time-limit=1200 –soft-time-limit=900
  - worker-default: handles scheduling, reporting, maintenance
    - flags: –queues scheduling,reporting,maintenance –concurrency 4 –prefetch-multiplier=4
  - beat: runs periodic schedules only
- Optional: flower/monitoring behind auth in non-prod; or rely on prometheus metrics + logs.
- Autoscaling: for optimization, scale by queue length and average task runtime; cap by CPU/memory limits to protect DB and solver stability.


3) Job idempotency patterns

Principles
- Every enqueue for a logical job must be associated with an idempotency_key; the key is derived from domain inputs (e.g., schedule_id + hash(params)).
- Task must check Postgres for existing terminal result for the same key before computation; if found, return that result.
- During execution, record a RUN record with status=running; upon success/failure, upsert terminal record with idempotency_key unique constraint to prevent duplicates.
- For periodic bulk operations (optimize_pending_schedules), compute keys per target entity to avoid duplicate concurrent runs.

Implementation sketch
- Postgres DDL below defines unique index on optimization_runs(idempotency_key).
- In Celery task optimize_schedule:
  - Compute key = sha256(f"opt:{schedule_id}:{sorted(params.items())}")
  - SELECT existing run with terminal status, return if present.
  - INSERT run(status=running, started_at=now(), task_id=current_task.request.id) ON CONFLICT DO NOTHING; if conflict and existing is running but stale (heartbeat > X), adopt or skip based on policy.
  - Execute solver; stream progress to optimization_run_events.
  - UPDATE run SET status=success, finished_at=now(), metrics=..., result_ref=... WHERE id=...
  - Handle exceptions: map to status=failed with error payload.
- Use BaseTask.on_success/on_failure to ensure Postgres is updated even on unexpected exits.


4) Result storage schema (Postgres)

Core tables
- optimization_runs: one row per logical run; dedupe via idempotency_key; stores inputs hash, status, timings, and summary metrics.
- optimization_run_events: append-only log of state changes/progress; useful for debugging and UI streaming.
- optimization_solutions: optional denormalized solution artifacts (assignments) for retrieval; alternatively store to object storage and reference via URL.

See docs/RESULT_SCHEMA.sql in this folder for complete DDL.


5) Optimization task flow + error recovery

Current
- API routes/solve.py relies on ResilientOptimizationService for request-time solves (not Celery). Celery tasks in app/core/tasks/optimization.py perform background/periodic optimizations. Circuit breaker / fallback logic lives in core + domain service.
- Celery BaseTask has autoretry_for=(Exception,), max_retries=3, default_retry_delay=60.

Issues
- Background periodic task blocks waiting for group().get(), which can tie up worker slots.
- Lack of persistent result storage means recovery after worker crash loses context.

Recommended flow
- For API-triggered long-running solves, enqueue a Celery task and return 202 with task_id (or store a Job row) if SLA allows async. For synchronous small solves, keep current path.
- For periodic bulk: enqueue subtasks and return immediately; a separate aggregator task (or beat in next tick) composes results from Postgres.
- Error taxonomy mapping: ensure domain exceptions (NoFeasibleSolutionError, SolverTimeoutError, MemoryError, CircuitBreaker) map to well-defined terminal statuses in optimization_runs, with retry policy driven by error type (e.g., do not retry for infeasible, do retry with backoff for transient resource errors).
- Heartbeats: periodically update optimization_runs.last_heartbeat_at from the task to support orphan detection and adoption.


6) Resource allocation and work cell constraints (CP-SAT)

- Domain model exists in app/domain/scheduling/optimization/constraint_models.py and cp_sat_scheduler.py with ResourceConstraints, TemporalConstraints, SkillConstraints, OptimizationObjective.
- Ensure we externalize the following as inputs for transparency and auditability:
  - Work cell capacity (machines per cell), machine calendars, maintenance windows
  - Operator shift calendars, skills matrix and proficiency levels
  - Task precedence/order, setup/teardown durations, WIP limits per cell
  - Routing alternatives (machine families), changeover penalties
- For each optimization run, persist the effective constraint snapshot (hash and optional JSON) to optimization_runs.inputs_snapshot to enable deterministic replay.


7) Actionable configuration deltas (safe defaults)

Celery settings (celery_app.conf.update)
- worker_prefetch_multiplier: 1 (for optimization pool)
- task_acks_late: true (already set)
- task_reject_on_worker_lost: true (already set)
- result_expires: increase to 24h if still using Redis, but rely on Postgres persistence for long-term
- broker_transport_options:
  - visibility_timeout: 3600-5400 (must exceed max task time)
- task_queues declaration with Queue("optimization", routing_key="optimization.#"), etc.

Process commands (examples)
- beat: celery -A app.core.celery_app:celery_app beat -l info
- worker-optimization: celery -A app.core.celery_app:celery_app worker -l info -Q optimization -c ${CELERYD_CONCURRENCY:-2} --prefetch-multiplier=1
- worker-default: celery -A app.core.celery_app:celery_app worker -l info -Q scheduling,reporting,maintenance -c 4 --prefetch-multiplier=4


8) Deliverables in this PR
- This audit document
- RESULT_SCHEMA.sql with Postgres DDL for result persistence
- CLAUDE.md in app/core/tasks and domain/scheduling/optimization documenting job patterns, idempotency, and constraint semantics

If you want, I can wire the Postgres persistence hooks into BaseTask on_success/on_failure and refactor optimize_schedule to implement idempotency and event streaming.

