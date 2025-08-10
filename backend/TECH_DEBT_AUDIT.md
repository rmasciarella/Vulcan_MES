Audit: FastAPI backend architecture and technical debt (Step 3)

Scope
- Review routes and endpoints for duplicates/legacy
- Identify JWT auth code to remove (migrate to Supabase auth)
- Check Python version inconsistencies (target 3.11)
- Audit domain boundaries and DDD alignment
- Review API contracts and versioning
- Document deprecated/unused modules
- Check dependency conflicts in requirements/pyproject
- Review error handling and logging patterns

Summary of findings
1) Routes and endpoints
- apps/backend/app/api/main.py aggregates routers. Production routes:
  - /scheduling/jobs -> app/api/routes/jobs.py
  - /scheduling/schedules -> app/api/routes/schedules.py
  - /scheduling/resources -> app/api/routes/resources.py
  - /scheduling/status -> app/api/routes/status.py
  - utils, health, users, login, websockets
- Legacy/duplicate routes included:
  - scheduling.py (router prefixless, included with prefix "/scheduling" and tag "scheduling"). Overlaps with jobs/resources/schedules. Recommendation: deprecate app/api/routes/scheduling.py. Several endpoints duplicate summaries provided by jobs/resources and leak repository internals.
  - domain_scheduling.py (prefixed as /scheduling/domain). Appears demo/experimental domain exposure. Recommendation: deprecate or move under /internal or /experiments and hide from OpenAPI, or extract into versioned experimental API (e.g. /api/v1/experimental).
  - enhanced_scheduling.py mounted under /enhanced-scheduling — consider merging into schedules endpoints or keeping as v2 once stable.
  - Multiple websocket routers (websockets.py, websocket_client.py, websockets/realtime.py, websockets_scheduling.py) and inclusion in api/main.py both websocket_rest_router and router. Verify only one outward-facing REST shim is present; non-REST websocket endpoints should not be exposed under REST tag.

Action items:
- Mark scheduling.py and domain_scheduling.py as deprecated in code and docs; plan removal after client cutoff.
- Consolidate status metrics across status.py and utils health.
- Ensure only one WebSocket REST shim is visible; others behind include_in_schema=False.

2) JWT auth migration to Supabase
- Current JWT implementations:
  - app/core/security.py and security_enhanced.py: RS256 JWT creation/verification; password hashing; token types.
  - app/api/routes/login.py: issues and verifies local JWTs at /login/access-token and /login/test-token; password reset flows.
  - app/api/deps.py get_current_user supports dual-mode: checks settings.USE_SUPABASE_AUTH to verify via app/core/supabase_jwt.py (JWKS) or via local RS256 via rsa_key_manager.
  - app/core/supabase_jwt.py: JWKS cache, verification with RS256 — keep for Supabase.
- To remove legacy JWT issuance once migrated:
  - Deprecate endpoints in app/api/routes/login.py (access-token, test-token, password recovery/reset paths) if Supabase email/password flows and magic links are adopted.
  - Remove token creation in app/core/security.py (create_access_token/refresh_token) after all callers removed. Keep password hashing utilities if still used for internal users; otherwise remove users table auth responsibility.
  - Remove rsa_key_manager and key rotation logic if no longer issuing/verifying local tokens. Keep only Supabase JWKS verify (app/core/supabase_jwt.py) and simplify deps.get_current_user to only Supabase path.
  - Audit tests under app/tests/api/routes/test_login.py and security tests to update for Supabase.

Action items (proposed sequence):
- Flip default settings.USE_SUPABASE_AUTH=True; add feature flag deprecation warning when False.
- Mark /login/* endpoints deprecated; provide 410 timeline.
- Refactor get_current_user to depend solely on verify_supabase_jwt and extract user claims mapping (sub, email, role) to domain user or a lightweight principal model.

3) Python version standardization
- Root pyproject.toml requires >=3.11,<4.0 (OK, mypy target py311). Backend pyproject required >=3.10 prior; updated to >=3.11.
- Dockerfiles used python:3.10 and 3.10-slim; updated to 3.11 and 3.11-slim. CI should align.
- Check .github/workflows/ci.yml references: ensure runtime matrix uses 3.11 for backend jobs.

4) DDD alignment and domain boundaries
- Clear domain packages under app/domain/scheduling (entities, value_objects, services, repositories interfaces, events, optimization). Infrastructure adapters in app/infrastructure/database/... with repositories and UoW; application layer DTOs and services exist under app/application.
- Anti-patterns/bleed-through:
  - app/api/routes/scheduling.py directly imports repo deps and exposes convenience endpoints that partially duplicate jobs/resources; better to serve via application layer services.
  - domain_scheduling.py exposes factories and domain internals directly (e.g., JobFactory), suitable only for internal/demo; violates encapsulation.
  - enhanced_scheduling.py shows better layering with unit_of_work and events; consider promoting to primary schedules flow and merging with schedules.py.

Recommendations:
- Official surface: jobs.py, schedules.py, resources.py, status.py, users.py. Deprecate legacy scheduling.py and domain_scheduling.py.
- Keep application-level DTOs between API and domain; remove direct domain exposure from controllers.

5) API contracts and versioning
- FastAPI app mounts at settings.API_V1_STR with openapi_url=f"{settings.API_V1_STR}/openapi.json"; app/main.py indicates version "1.0.0".
- No explicit route versioning on path segments beyond /api/v1. For experimental endpoints, add tags and include_in_schema flags or /experimental under v1 but with x-deprecated or explicit deprecation headers.
- scripts/generate-api-client.sh present — ensure it excludes deprecated routes.

6) Deprecated/unused modules to mark
- app/api/routes/scheduling.py (duplicate functionality)
- app/api/routes/domain_scheduling.py (demo/legacy exposure)
- app/core/security.py and security_enhanced.py: token creation portions become deprecated post-Supabase. Keep password hashing utilities only if still needed.
- app/api/routes/login.py: to deprecate when Supabase auth is live.
- Multiple websocket modules: review and consolidate; leave a single outward facing entrypoint and mark others internal.

7) Dependency conflicts and observations (apps/backend/pyproject.toml)
- fastapi[standard] >=0.114.2,<1.0.0 paired with pydantic >2.0 (compatible with FastAPI 0.114+).
- email-validator pinned weirdly (“<*******,>=2.1.0.post1”) — malformed version constraint; fix to a real upper bound e.g., <3.0.0.
- opentelemetry-exporter-prometheus pinned <=1.12.0rc1 while instrumentation packages at 0.42b0; validate compatibility or move to OTEL Stable 1.27+ and matching exporters.
- redis <6.0.0 with current latest v5 OK; Celery 5.3 + redis <6 constraint acceptable; ensure kombu/billiard versions match (handled by uv.lock).
- pyjwt >=2.8.0 used both for legacy and Supabase JWKS; keep.
- ortools <10.0.0; if needing performance features, consider 9.10+. Verify platform wheels with Python 3.11.

Action items:
- Fix email-validator constraint.
- Evaluate OTEL versions for consistency.

8) Error handling and logging
- Structured logging via structlog in app/core/observability.py; middleware ObservabilityMiddleware logs start/completion with correlation_id and user_id; Prometheus metrics REQUEST_COUNT/REQUEST_DURATION used; Sentry initialized for non-local.
- Endpoints consistently raise HTTPException with specific codes; many convert DatabaseError and domain exceptions to HTTP codes. Good pattern.
- Some routes contain rich responses and logging in health/utils; ensure sensitive data not logged.
- Recommend: add exception handlers for common domain exceptions at app level to reduce repetition and enforce consistent payloads; ensure request bodies aren’t logged.

Concrete recommendations and next steps
- Deprecations (introduce deprecation warnings and tags):
  - routes: scheduling.py, domain_scheduling.py
  - login endpoints in login.py
- Auth migration:
  - Default USE_SUPABASE_AUTH=True.
  - Simplify get_current_user to only Supabase verification after deprecation period.
  - Remove RSA key generation and local token creation thereafter.
- Contract hygiene:
  - Introduce x-deprecated in OpenAPI for deprecated endpoints.
  - Add /experimental tag prefix or include_in_schema=False for non-stable routes.
- Versioning:
  - Keep /api/v1 stable set; prepare /api/v2 for enhanced scheduling if breaking.
- Dependencies:
  - Fix malformed email-validator constraint; review OTEL alignment.
- Python:
  - Updated Dockerfiles and backend pyproject to 3.11. Align CI matrix to 3.11 for backend jobs.
- Logging/Errors:
  - Add FastAPI exception handlers mapping domain exceptions to codes uniformly.
  - Ensure correlation IDs propagate to background tasks.

Appendix: Notable files
- Routers: app/api/routes/*.py; aggregator app/api/main.py
- Auth/JWT: app/core/security.py, app/core/security_enhanced.py, app/api/routes/login.py, app/api/deps.py, app/core/supabase_jwt.py
- Observability: app/core/observability.py, app/main.py
- DDD: app/domain/*, app/infrastructure/*, app/application/*
- Versioning: app/main.py, app/api/main.py, scripts/generate-api-client.sh

