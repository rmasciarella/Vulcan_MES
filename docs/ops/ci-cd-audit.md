# CI/CD and Container Audit (Q3 2025)

Scope
- GitHub Actions workflows: .github/workflows/ci.yml, .github/workflows/deploy.yml
- Dockerfiles: apps/backend/Dockerfile, apps/backend/Dockerfile.prod, apps/frontend/Dockerfile
- Compose files: docker-compose.yml, docker-compose.dev.yml
- Image registry: GHCR (ghcr.io)
- Env management: .env*.example files, compose usage
- Build caching/optimization: Docker buildx + GHA cache, uv cache, Node build setup

Summary (TL;DR)
- Python 3.11 alignment is consistent across CI, runtime, and tooling (good).
- CI is solid for tests and caching; Docker build step builds but does not push in CI job (by design); deploy workflow builds+pushes to GHCR (good) but tags are SHA-only and compose on server currently builds locally—mismatch.
- Production deploy uses SSH to a server with docker-compose, but repository compose files are dev-oriented and reference local builds. A production compose with GHCR images is needed to make docker-compose pull work on servers.
- Env variables are documented with examples; recommend unifying naming, adding dotenv for compose, and preventing mock/debug flags in prod.
- Build caching is in place for Docker with GHA; can improve multi-arch, SBOM/provenance, and frontend Docker caching/install steps.

Findings and Recommendations

1) GitHub Actions (CI)
Findings
- ci.yml sets PYTHON_VERSION=3.11 and NODE_VERSION=20 (aligns with codebase).
- Backend tests use uv with postgres/redis services and Codecov upload (good).
- E2E starts services via docker-compose up using docker-compose.yml (dev-focused compose).
- Docker build job uses docker/build-push-action with cache-from/to=gha but push: false.

Recommendations
- Pin action versions explicitly already done; keep updated.
- Add concurrency group to avoid overlapping runs on same branch.
- Add artifact upload for backend htmlcov if needed and pytest junit for PR surfaces.
- Consider using services + compose action or a dedicated e2e compose (leaner) for E2E.
- Ensure playwright install cache (setup-node cache already helps pnpm; consider caching ~/.cache/ms-playwright if runs increase).

2) GitHub Actions (Deploy/GHCR)
Findings
- deploy.yml logs into ghcr.io and builds+pusher backend/frontend with labels from metadata-action.
- Tags published: only SHA tags. metadata-action prepared semver/ref tags but not applied.
- No multi-arch; QEMU not enabled.
- Deploy over SSH uses docker-compose pull/down/up and alembic migration.

Recommendations
- Use docker/metadata-action outputs for tags to publish richer tags:
  with:
    tags: ${{ steps.meta.outputs.tags }}
- Optionally add multi-arch (linux/amd64,linux/arm64) with docker/setup-qemu-action.
- Consider SBOM + provenance:
  - add anchore/sbom-action to attach SBOMs to images or docker/buildx bake with sbom=true.
  - set provenance: mode=max in build-push-action (attestations).
- Add image digest outputs for traceability and deploy with digests if possible.

3) Dockerfiles
Backend
- apps/backend/Dockerfile: FROM python:3.11, uses uv with cache mounts; fastapi run cmd; good for dev or simple runtime; runs as root.
- apps/backend/Dockerfile.prod: FROM python:3.11-slim, non-root user, uv builder venv copied into runtime, healthcheck, EXPOSE 8000, CMD fastapi run, host redacted.

Frontend
- apps/frontend/Dockerfile: multi-stage, pnpm install, builds Next standalone, non-root user, CMD node server.js.

Recommendations
- Backend:
  - In non-prod Dockerfile consider exposing host and port via env; prefer uvicorn/gunicorn config if fastapi CLI is insufficient in prod.
  - Ensure .dockerignore exists to reduce build context.
- Frontend:
  - Add .dockerignore (node_modules, .next, tests, etc.).
  - Consider pnpm fetch + pnpm install --frozen-lockfile --prefer-offline for improved cache usage.
  - Ensure NEXT_TELEMETRY_DISABLED=1 in all non-dev stages (already set in builder and production).

4) docker-compose (dev vs deploy)
Findings
- docker-compose.yml includes dev volumes and dev commands (fastapi dev, reload, volumes mounted).
- docker-compose.dev.yml overrides to dev targets but assumes Dockerfiles declare stages named development (frontend has development stage; backend Dockerfile does not expose a named stage; commands override with uv run fastapi dev).
- Deploy workflow calls docker-compose pull/up on servers, but current compose files build locally and don’t reference GHCR images. This will not pull GHCR images unless a production compose file exists that uses registry images.

Recommendations
- Introduce docker-compose.prod.yml to reference GHCR images by tag/digest and use env files for secrets:
  services:
    backend:
      image: ghcr.io/ORG/REPO/backend:${TAG_OR_DIGEST}
      env_file:
        - /opt/vulcan/env/backend.env
      depends_on:
        postgres:
          condition: service_healthy
    frontend:
      image: ghcr.io/ORG/REPO/frontend:${TAG_OR_DIGEST}
      env_file:
        - /opt/vulcan/env/frontend.env
- Update deploy.yml to use docker compose -f docker-compose.prod.yml pull/up.
- Keep docker-compose.yml strictly for local/dev to avoid confusion.

5) GHCR usage
Findings
- Login with GITHUB_TOKEN in CI works.
- Servers will need a PAT with read:packages to pull GHCR images; deploy.yml does not currently log in on the target server before compose pull.

Recommendations
- Add initial server setup: docker login ghcr.io -u USER -p $GHCR_PAT (once) or add to deploy script before compose pull, sourcing a secure secret.
- Optionally use short lived ghcr PAT via GitHub OIDC + workload identity if environment supports it.

6) Environment variable management
Findings
- .env.example, .env.frontend.example, .env.shared.example exist and are reasonable.
- Compose files set sensitive defaults inline (SECRET_KEY, FIRST_SUPERUSER_PASSWORD) for dev convenience.
- Frontend compose references SUPABASE vars from host env; ensure they’re set locally.

Recommendations
- For production, ensure server-side env files are not committed and are read via env_file in docker-compose.prod.yml.
- Enforce safety checks in CI for production builds (e.g., mock/debug flags must be false; optional dedicated job).
- Align naming between shared and frontend examples (anon/publishable key naming consistency).

7) Build caching & optimization
Findings
- Docker build uses cache-from/to=gha (good).
- Backend uses uv cache mounts (good); production Dockerfile uses builder venv copy (good).
- No QEMU/multi-arch caching (optional).
- Frontend could leverage better cache by separating dependency installation (copy only package.json + lockfile before copying full source—already done). Consider pnpm storeDir to persist cache.

Recommendations
- Enable docker/setup-qemu-action for multi-arch if targeting arm64 hosts (DO droplet types often are amd64 only; App Platform supports both).
- Consider buildx bake + buildkit inline cache for local builds.
- Add --provenance and SBOM generation to builds.

Concrete actions (proposed)
- Add docker-compose.prod.yml to reference GHCR images + env_file.
- Update .github/workflows/deploy.yml to:
  - Use metadata action tags for both images.
  - Optionally add multi-arch and SBOM.
  - Use docker compose -f docker-compose.prod.yml on servers.
- Add .dockerignore files for apps/backend and apps/frontend.
- Add docs/deploy/digitalocean.md (see companion doc) and server bootstrap steps (GHCR login, volumes, firewalls).
- Add a policy CI check to ensure no mock/dev flags are true in production image builds.

Appendix: File references inspected
- .github/workflows/ci.yml
- .github/workflows/deploy.yml
- apps/backend/Dockerfile, apps/backend/Dockerfile.prod
- apps/frontend/Dockerfile
- docker-compose.yml, docker-compose.dev.yml
- pyproject.toml, apps/backend/pyproject.toml
- .python-version
- .env*.example
- Makefile

