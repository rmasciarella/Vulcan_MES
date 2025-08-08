# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vulcan MES is a production-ready Manufacturing Execution System monorepo that combines:
- **Backend**: FastAPI with comprehensive Domain-Driven Design (DDD) implementation, SQLModel ORM, and OR-Tools scheduling optimization
- **Frontend**: Next.js 15 with server components, Supabase for real-time features, and TanStack Query
- **Authentication**: Dual-mode supporting both FastAPI JWT and Supabase Auth
- **Database**: PostgreSQL with Alembic migrations + Supabase for real-time capabilities

## Development Commands

### Monorepo Commands (root directory)
```bash
pnpm dev              # Run all services in development mode
pnpm build            # Build all packages
pnpm test             # Run all tests
pnpm lint             # Lint all packages
pnpm format           # Format all packages
pnpm clean            # Clean all build artifacts and node_modules
```

### Backend Commands (apps/backend/)
```bash
# Install/sync Python dependencies (uses uv package manager)
uv sync

# Run development server
uv run fastapi dev app/main.py

# Database migrations
alembic upgrade head                        # Apply migrations
alembic revision --autogenerate -m "desc"   # Create new migration

# Testing
./scripts/test.sh                          # Run all tests with coverage (min 80%)
pytest -m unit                             # Run unit tests only
pytest -m integration                      # Run integration tests
pytest -c pytest-e2e.ini                   # Run E2E tests

# Code quality
./scripts/format.sh                        # Format with ruff
./scripts/lint.sh                          # Lint with ruff
```

### Frontend Commands (apps/frontend/)
```bash
npm run dev                    # Development server on port 3000
npm run build                  # Production build
npm run test                   # Run vitest tests
npm run type-check             # TypeScript type checking
npm run generate-client        # Generate TypeScript client from backend OpenAPI
```

## Architecture and Code Organization

### Backend Architecture (apps/backend/app/)

**Domain Layer** (`domain/scheduling/`):
- **Entities**: Job, Task, Machine, Operator, Operation, ProductionZone
- **Value Objects**: Duration, TimeWindow, Skill, WorkingHours, Status enums
- **Aggregate Roots**: Job (manages task consistency), Schedule (manages resource allocation)
- **Domain Events**: JobStatusChanged, TaskDelayed, ResourceAssigned
- **Domain Services**: SchedulingService, ConstraintValidationService, ResourceAllocationService
- **Repositories**: Abstract interfaces for persistence (JobRepository, MachineRepository, etc.)

**Application Layer** (`application/`):
- **DTOs**: Data transfer objects for API contracts
- **Services**: Application services that orchestrate domain operations
- **Queries**: CQRS query handlers for read operations
- **Validation**: Request validation logic

**Infrastructure Layer** (`infrastructure/`):
- **Database**: SQLModel entities, repositories implementation, unit of work pattern
- **Cache**: Multi-level caching with Redis, repository caching decorators
- **Events**: Domain event publisher, event bus implementation

**API Layer** (`api/routes/`):
- RESTful endpoints organized by domain context
- WebSocket support for real-time solver updates
- Comprehensive OpenAPI documentation

**Core** (`core/`):
- Configuration, authentication, security, monitoring
- OR-Tools CP-SAT solver integration for scheduling optimization
- Circuit breaker, rate limiting, retry mechanisms
- Observability with OpenTelemetry and Prometheus

### Frontend Architecture (apps/frontend/src/)

**Features** (`features/`):
- Feature-based modules (job-scheduling, resource-allocation, scheduling)
- Each feature contains: components, hooks, stores, utils

**Core** (`core/`):
- Domain models and types
- Zustand stores for state management
- Use cases and event handlers

**Infrastructure** (`infrastructure/`):
- Supabase client configuration and repositories
- Database optimization and monitoring
- State management infrastructure

**Shared** (`shared/`):
- Reusable UI components (using shadcn/ui)
- Common hooks and utilities
- Layout components

## Key Technical Patterns

### Backend Patterns
- **Repository Pattern**: Abstract data access behind interfaces
- **Unit of Work**: Transactional consistency across aggregates
- **CQRS**: Separate read models optimized for queries
- **Domain Events**: Decoupled communication between bounded contexts
- **Factory Pattern**: Complex object creation with validation
- **Circuit Breaker**: Resilient external service calls

### Frontend Patterns
- **Server Components**: Next.js 15 app router with RSC
- **Optimistic Updates**: TanStack Query with optimistic UI updates
- **Real-time Sync**: Supabase subscriptions for live data
- **Virtual Scrolling**: Performance optimization for large datasets

## Testing Strategy

### Backend Testing
- **Unit Tests**: Domain logic, value objects, services (~60% coverage)
- **Integration Tests**: Repository, database, API endpoints (~25% coverage)
- **E2E Tests**: Complete workflows with real database (~10% coverage)
- **Property-Based Tests**: Domain invariants and business rules (~5% coverage)
- Minimum 80% total coverage enforced

### Frontend Testing
- Component testing with Vitest
- Integration tests for critical user flows
- E2E tests with Playwright for key workflows

## Environment Configuration

Required environment variables in root `.env`:
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/vulcan
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=vulcan

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_KEY=xxx

# Backend
SECRET_KEY=xxx
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# Redis
REDIS_URL=redis://localhost:6379
```

## Scheduling Domain Context

The core business domain revolves around production scheduling optimization:

**Key Concepts**:
- Jobs flow through operations (10-100) producing finished goods
- Tasks are individual work assignments requiring machine + operator
- Constraints include skills, time windows, dependencies, WIP limits
- OR-Tools CP-SAT solver optimizes makespan while respecting constraints

**Business Rules**:
- Tasks must complete in operation sequence
- Operators need required skills for machine operation
- Production zones have WIP limits preventing bottlenecks
- Critical path operations determine job completion time