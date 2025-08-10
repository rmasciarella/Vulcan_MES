# Environment Configuration

## Overview
- Frontend environment variables documentation: apps/frontend/.env.docs.md
- Backend environment variables documentation: apps/backend/README.md#environment-variables

This repository centralizes environment configuration for all apps and CI. Validation runs locally via Turborepo and in CI to fail fast with actionable errors.

## Required Variables by Environment

The following summarize required variables by environment. See linked app docs for full details and defaults.

### Development
- Frontend (public):
  - NEXT_PUBLIC_SUPABASE_URL
  - NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  - Optional toggles: NEXT_PUBLIC_ENABLE_DEBUG_UI, NEXT_PUBLIC_ENABLE_MOCK_DATA
- Server-only:
  - SUPABASE_SECRET (required for server-side Supabase features)
- Backend:
  - DATABASE_URL, REDIS_URL, SECRET_KEY (see backend README)

### Staging
- Frontend (public):
  - NEXT_PUBLIC_SUPABASE_URL
  - NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  - NEXT_PUBLIC_APP_ENV=staging
  - Optional: NEXT_PUBLIC_ENABLE_DEBUG_UI=true (for testing)
- Server-only:
  - SUPABASE_SECRET (required)
- Backend:
  - DATABASE_URL, REDIS_URL, SECRET_KEY, BACKEND_CORS_ORIGINS

### Production
- Frontend (public):
  - NEXT_PUBLIC_SUPABASE_URL
  - NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  - NEXT_PUBLIC_APP_ENV=production
  - NEXT_PUBLIC_ENABLE_DEBUG_UI=false
  - NEXT_PUBLIC_ENABLE_MOCK_DATA=false
- Server-only:
  - SUPABASE_SECRET (required)
- Backend:
  - DATABASE_URL, REDIS_URL, SECRET_KEY, BACKEND_CORS_ORIGINS

## CI/CD Variables

CI runs a centralized validation step before builds:
- Validates presence and shape of core variables for each app
- Enforces production safeguards:
  - NEXT_PUBLIC_ENABLE_MOCK_DATA must be false in production
  - NEXT_PUBLIC_ENABLE_DEBUG_UI must be false in production
- Supports values coming from repository/organization secrets

Common CI secrets (names are suggestions; map to your actual secrets store):
- SUPABASE_SECRET
- NEXT_PUBLIC_SUPABASE_URL
- NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
- DATABASE_URL
- REDIS_URL
- SECRET_KEY

## Security Guidelines
- Never commit secrets (.env, .env.local, .env.*). Use CI secrets and runtime injectors.
- Separate projects and credentials per environment (dev/staging/prod).
- Rotate keys regularly; prefer short-lived tokens where possible.
- Limit production toggles that expose debug or mock functionality.
- Review apps/frontend/.env.docs.md "Production Security Guidelines" for frontend-specific rules.
