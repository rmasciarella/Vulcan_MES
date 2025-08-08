# DigitalOcean Deployment Requirements (Target: Q4 2025)

Goal
- Standardize production deployment on DigitalOcean (Droplets or App Platform) using GHCR images, environment files, and a production docker-compose file.
- Support blue/green or rolling-style updates with zero/minimal downtime and safe database migrations.

Assumptions
- One or more Droplets (Ubuntu 22.04+) with Docker Engine and docker compose V2 installed
- External managed PostgreSQL (prefer DO Managed PG) or self-hosted Postgres container
- Redis via DO Managed Redis or container
- Images published to GHCR under ghcr.io/<org>/<repo>/(backend|frontend)

Recommended Architecture
- Network
  - VPC: place Droplets and DB/Redis in the same VPC for low latency and private networking.
  - Firewall: allow inbound 80/443 from Internet to LB or Nginx; restrict SSH by IP; allow internal ports only within VPC.
- Compute
  - 1–3 Droplets behind DO Load Balancer for HA. Start with 2 x s-2vcpu-4gb for app tier; adjust after load test.
  - Use systemd or Compose with restart policies (always) to ensure resilience.
- Data
  - Managed PostgreSQL preferred. Configure trusted sources from Droplet VPC. Create a read-only replica if needed.
  - Managed Redis for cache/queues if using Celery. Otherwise, Redis container on a separate node with persistence.
- Storage
  - Persistent volumes only for Postgres/Redis if self-hosted. App containers should be stateless.

Container Images
- GHCR authentication
  - Create a GitHub PAT with read:packages or configure a GitHub Actions–issued deploy token stored as DO secret.
  - On each Droplet: docker login ghcr.io -u <user> -p $GHCR_PAT (store in root-only file or DO Secrets Manager if available).
- Tags and digests
  - Deploy by digest for immutability when possible: ghcr.io/<org>/<repo>/backend@sha256:...
  - Maintain semver and release branch tags for human tracking.

Runtime Configuration
- Production compose file (docker-compose.prod.yml)
  - backend:
    - image: ghcr.io/<org>/<repo>/backend:${TAG_OR_DIGEST}
    - env_file: /opt/vulcan/env/backend.env
    - ports: ["8000:8000"] or, if behind reverse proxy, expose internal only
    - depends_on: [postgres, redis] only if self-hosted
    - healthcheck endpoint: /api/v1/utils/health-check/
  - frontend:
    - image: ghcr.io/<org>/<repo>/frontend:${TAG_OR_DIGEST}
    - env_file: /opt/vulcan/env/frontend.env
    - ports: ["3000:3000"] or fronted by Nginx
  - postgres/redis only for self-hosted; for managed, remove and set URLs via env

Environment Variables
- Store in /opt/vulcan/env/*.env with 600 permissions, owned by root.
- Backend (backend.env)
  - DATABASE_URL=postgresql://...
  - REDIS_URL=redis://...
  - SECRET_KEY=...
  - BACKEND_CORS_ORIGINS=["https://app.example.com"]
  - SUPABASE_URL=...
  - SUPABASE_SECRET=...
- Frontend (frontend.env)
  - NEXT_PUBLIC_API_URL=https://api.example.com
  - NEXT_PUBLIC_SUPABASE_URL=...
  - NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=...
  - NEXT_PUBLIC_ENABLE_DEBUG_MODE=false

Operational Runbooks
- Provisioning
  - Create Droplets (Ubuntu 22.04 LTS), add to VPC, attach firewall rules.
  - Install Docker Engine and compose V2; add deploy user with limited sudo.
  - docker login ghcr.io.
  - mkdir -p /opt/vulcan/{env,compose,backups,logs}
  - Place docker-compose.prod.yml in /opt/vulcan/compose
  - Place env files in /opt/vulcan/env with correct permissions.

- Deployment via GitHub Actions (SSH)
  - Steps executed on server:
    - docker compose -f /opt/vulcan/compose/docker-compose.prod.yml pull
    - docker compose -f /opt/vulcan/compose/docker-compose.prod.yml up -d
    - docker compose exec -T backend alembic upgrade head
    - Health check endpoint(s); rollback if failing

- Rollback
  - Keep previous image digests in a release log; set TAG_OR_DIGEST to prior value and re-run up -d.
  - Automated rollback job can be triggered on failure.

Security and Compliance
- Least-privilege GHCR token (read:packages only) on servers
- Non-root user inside containers (backend prod Dockerfile already uses appuser; frontend uses nextjs)
- Secrets never hardcoded in compose; use env_file; never echo secrets in CI logs
- Enable HTTPS end-to-end; terminate TLS at LB or Nginx with auto-renewing certs (Let’s Encrypt)

Observability
- Centralized logs using Docker logging driver or sidecar (e.g., vector/fluent-bit) to ship to DO Logs or ELK
- Metrics: expose Prometheus endpoints; scrape via DO Managed Grafana Cloud or self-hosted Prometheus
- Traces: OTEL exporter configured in backend to a collector endpoint

Capacity Planning (Q4 2025)
- Start with:
  - 2 x app Droplets: s-2vcpu-4gb (amd64)
  - DO Managed PG: 2 vCPU / 4GB RAM primary (add replica if needed)
  - DO Managed Redis: basic plan
- Perform load testing with Locust; scale horizontally by increasing app Droplets behind the LB.

Blue/Green Strategy (Optional)
- Duplicate stack on green namespace (compose project name suffix), register to LB target pool, switch traffic after health check passes.
- Keep previous stack warm until post-deploy verification completes.

Checklists
- Pre-deploy
  - Images exist in GHCR with expected tags/digests
  - GHCR login valid on servers
  - Env files present and correct; debug flags false
  - DB migrations reviewed and backward-compatible
- Post-deploy
  - Health checks pass; SLOs within thresholds
  - Error rates stable; logs clean of sensitive data
  - Rollback plan verified

References
- Files in repo:
  - .github/workflows/deploy.yml (to be updated to use docker-compose.prod.yml)
  - docs/ops/ci-cd-audit.md (companion audit)
- External:
  - DigitalOcean docs for Droplets, Load Balancers, Managed DB/Redis
  - GitHub Packages (GHCR) authentication

