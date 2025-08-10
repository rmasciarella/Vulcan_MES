# Vulcan MES Monorepo Makefile

.PHONY: help install dev build test lint format clean docker-up docker-down migrate

# Default target
help:
	@echo "Vulcan MES Monorepo Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install all dependencies (pnpm + uv)"
	@echo "  make sync          - Sync all dependencies"
	@echo "  make env-setup     - Create .envrc.local and allow direnv"
	@echo ""
	@echo "Development:"
	@echo "  make dev           - Start all services in development mode"
	@echo "  make backend       - Start backend only"
	@echo "  make frontend      - Start frontend only"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     - Start all services with Docker Compose"
	@echo "  make docker-down   - Stop all Docker services"
	@echo "  make docker-logs   - View Docker logs"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make test-backend  - Run backend tests"
	@echo "  make test-frontend - Run frontend tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          - Lint all code"
	@echo "  make format        - Format all code"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       - Run database migrations"
	@echo "  make db-sync       - Sync database with Supabase"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Clean all build artifacts"
	@echo "  make api-client    - Generate TypeScript API client"

# Installation
install:
	@echo "📦 Installing dependencies..."
	@command -v uv >/dev/null 2>&1 || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	@command -v pnpm >/dev/null 2>&1 || (echo "Installing pnpm..." && npm install -g pnpm)
	@pnpm install
	@cd apps/backend && uv sync
	@echo "✅ Installation complete!"

# Environment setup
env-setup:
	@echo "🔐 Setting up local environment (.envrc.local) ..."
	@[ -f .envrc.local ] && echo "✔️  .envrc.local already exists" || (cp .envrc.local.example .envrc.local && echo "🆕 Created .envrc.local from example")
	@command -v direnv >/dev/null 2>&1 && direnv allow . || echo "⚠️  direnv not installed. Install with 'brew install direnv' and add the hook to your shell."
	@echo "✅ Environment setup complete. Edit .envrc.local with your values if needed."

sync:
	@echo "🔄 Syncing dependencies..."
	@pnpm install --frozen-lockfile
	@uv sync
	@echo "✅ Sync complete!"

# Development
dev:
	@echo "🚀 Starting development servers..."
	@pnpm dev

backend:
	@echo "🔧 Starting backend server..."
	@cd apps/backend && uv run fastapi dev app/main.py --reload

frontend:
	@echo "🎨 Starting frontend server..."
	@cd apps/frontend && pnpm dev

# Docker
docker-up:
	@echo "🐳 Starting Docker services..."
	@docker-compose -f config/docker/docker-compose.yml -f config/docker/docker-compose.dev.yml up -d
	@echo "✅ Services started!"
	@echo "   Frontend: http://localhost:3000"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"
	@echo "   Adminer:  http://localhost:8080"

docker-down:
	@echo "🛑 Stopping Docker services..."
	@docker-compose -f config/docker/docker-compose.yml down

docker-logs:
	@docker-compose -f config/docker/docker-compose.yml logs -f

docker-build:
	@echo "🏗️ Building Docker images..."
	@docker-compose -f config/docker/docker-compose.yml build

# Testing
test:
	@echo "🧪 Running all tests..."
	@pnpm test
	@cd apps/backend && uv run pytest

test-backend:
	@echo "🧪 Running backend tests..."
	@cd apps/backend && uv run pytest -v

test-frontend:
	@echo "🧪 Running frontend tests..."
	@cd apps/frontend && pnpm test

test-e2e:
	@echo "🧪 Running E2E tests..."
	@cd apps/frontend && npx playwright test

# Code Quality
lint:
	@echo "🔍 Linting code..."
	@pnpm lint
	@uv run ruff check apps/backend

format:
	@echo "✨ Formatting code..."
	@pnpm format
	@uv run ruff format apps/backend

type-check:
	@echo "🔍 Type checking..."
	@pnpm type-check
	@cd apps/backend && uv run mypy app

# Database
migrate:
	@echo "🗄️ Running database migrations..."
	@cd apps/backend && uv run alembic upgrade head

migrate-create:
	@echo "📝 Creating new migration..."
	@read -p "Enter migration message: " msg; \
	cd apps/backend && uv run alembic revision --autogenerate -m "$$msg"

db-sync:
	@echo "🔄 Syncing database with Supabase..."
	@cd apps/backend && uv run python app/db/sync_supabase.py

# API Client Generation
api-client:
	@echo "🏗️ Generating TypeScript API client..."
	@./scripts/generate-api-client.sh

# Clean
clean:
	@echo "🧹 Cleaning build artifacts..."
	@pnpm clean
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete!"

# Production
build:
	@echo "🏗️ Building for production..."
	@pnpm build
	@docker-compose -f config/docker/docker-compose.yml build

# Netlify: Set Production env vars for frontend from direnv and deploy
netlify-env-prod:
	@echo "🔐 Loading direnv and setting Netlify Production env vars for frontend..."
	@cd apps/frontend && eval "$(direnv export bash)" >/dev/null 2>&1 || true; \
	  cd apps/frontend && \
	  netlify status --json >/dev/null; \
	  netlify env:set NEXT_PUBLIC_API_URL --context production <<< "https://vulcan-mes.com" && \
	  netlify env:set NEXT_PUBLIC_SUPABASE_URL --context production <<< "$${NEXT_PUBLIC_SUPABASE_URL}" && \
	  netlify env:set NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY --context production <<< "$${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY}" && \
	  netlify env:set NEXT_PUBLIC_SUPABASE_ANON_KEY --context production <<< "$${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY}" && \
	  netlify env:set NEXT_PUBLIC_APP_ENV --context production <<< "production" && \
	  netlify env:set NEXT_PUBLIC_ENABLE_MOCK_DATA --context production <<< "false" && \
	  netlify env:set NEXT_PUBLIC_ENABLE_DEBUG_UI --context production <<< "false" && \
	  echo "✅ Netlify production env vars set."

netlify-deploy-prod:
	@echo "🚀 Triggering Netlify production deploy (clean build)..."
	@cd apps/frontend && netlify deploy --prod --build
	@echo "✅ Netlify production deploy triggered."

deploy-staging:
	@echo "🚀 Deploying to staging..."
	@git push origin main
	@echo "✅ Deployment triggered via GitHub Actions"

deploy-prod:
	@echo "🚀 Deploying to production..."
	@echo "⚠️  Use GitHub Actions workflow for production deployment"
	@echo "   Go to: https://github.com/$(shell git remote get-url origin | sed 's/.*://;s/.git//')/actions"

# Quick commands
up: docker-up
down: docker-down
logs: docker-logs
i: install
d: dev
t: test
f: format
l: lint