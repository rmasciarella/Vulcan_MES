# Vulcan MES - Manufacturing Execution System

Production-ready monorepo combining FastAPI backend with Next.js frontend and Supabase integration.

## Architecture

```
vulcan/
├── apps/
│   ├── backend/      # FastAPI + SQLModel + PostgreSQL
│   └── frontend/     # Next.js 15 + Supabase + TanStack Query
├── packages/
│   ├── domain/       # Shared domain models
│   ├── shared/       # Common utilities
│   └── ui/          # Shared UI components
└── infrastructure/   # Docker, K8s, deployment configs
```

## Quick Start

### Prerequisites
- Node.js 18+
- pnpm 9+
- Docker & Docker Compose
- Python 3.11+

### Development Setup

1. Install dependencies:
```bash
pnpm install
```

2. Start development environment:
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

3. Access services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Database Admin: http://localhost:8080

### Monorepo Commands

```bash
# Run all services in development
pnpm dev

# Build all packages
pnpm build

# Run tests
pnpm test

# Lint and format
pnpm lint
pnpm format

# Clean all build artifacts
pnpm clean
```

### Backend Commands

```bash
cd apps/backend

# Install Python dependencies
uv sync

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run tests
./scripts/test.sh
```

### Frontend Commands

```bash
cd apps/frontend

# Install dependencies
pnpm install

# Generate TypeScript client from backend
npm run generate-client

# Run development server
npm run dev

# Build for production
npm run build
```

## Environment Variables

See ENVIRONMENT.md for centralized environment documentation, required variables by environment, CI/CD rules, and security guidelines.

### Direnv (recommended)
This repo supports automatic environment loading with direnv.

1) Install and hook direnv for zsh:

```bash
brew install direnv
printf '\n# direnv\n' >> ~/.zshrc
printf 'eval "$(direnv hook zsh)"\n' >> ~/.zshrc
source ~/.zshrc
```

2) Allow the project:

```bash
direnv allow .
```

3) Create personal overrides (optional, git-ignored):

```bash
cp .envrc.local.example .envrc.local
# edit .envrc.local with your values
```

Direnv loads from, in order: .env, .env.local, .envrc.local.

### .env file

Create a `.env` file in the root directory (used by direnv and also as fallback):

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vulcan

# Supabase
# Project URL
SUPABASE_URL=your-supabase-url

# Keys
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key   # browser-safe
SUPABASE_SECRET=your-secret-key                             # server-only

# Backend
SECRET_KEY=your-secret-key
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# Redis
REDIS_URL=redis://localhost:6379
```

## Production Deployment

1. Build production images:
```bash
docker-compose build
```

2. Deploy with Docker Compose:
```bash
docker-compose up -d
```

## Key Features

- **Backend**: FastAPI with comprehensive DDD implementation, OR-Tools scheduling optimization
- **Frontend**: Next.js 15 with server components, Supabase real-time features
- **Authentication**: Dual-mode supporting FastAPI JWT and Supabase Auth
- **Database**: PostgreSQL with Alembic migrations + Supabase for real-time
- **Monitoring**: Prometheus + Grafana integration
- **Testing**: 1000+ backend tests, E2E testing with Playwright

## Migration Status

✅ Week 1: Monorepo structure with Turborepo
✅ Backend migration from vulcan_engine
✅ Frontend migration from vulcan_mes
✅ Shared packages setup
✅ Docker Compose configuration

⏳ Week 2-6: Integration and production preparation