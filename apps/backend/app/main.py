import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.health import register_default_health_checks, validate_startup_health
from app.core.observability import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    get_logger,
    initialize_observability,
    set_correlation_id,
    set_user_id,
)

# Initialize structured logger
logger = get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request observability and metrics collection."""

    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID for request tracing
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Extract user ID from auth headers if available
        user_id = request.headers.get("X-User-ID", "")
        if user_id:
            set_user_id(user_id)

        # Track request start
        start_time = time.time()
        method = request.method
        path = request.url.path

        # Log request start
        logger.info(
            "Request started",
            method=method,
            path=path,
            correlation_id=correlation_id,
            user_id=user_id,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", ""),
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time
            status_code = response.status_code

            # Record metrics
            REQUEST_COUNT.labels(
                method=method, endpoint=path, status=str(status_code)
            ).inc()
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            # Log request completion
            logger.info(
                "Request completed",
                method=method,
                path=path,
                status_code=status_code,
                duration_seconds=duration,
                correlation_id=correlation_id,
            )

            return response

        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time

            # Record error metrics
            REQUEST_COUNT.labels(method=method, endpoint=path, status="500").inc()
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)

            # Log error
            logger.error(
                "Request failed",
                method=method,
                path=path,
                duration_seconds=duration,
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            raise


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for FastAPI application with comprehensive startup."""
    # Startup
    logger.info("Starting application initialization")

    try:
        # Initialize observability system
        initialize_observability()
        logger.info("Observability system initialized")

        # Register health checks
        register_default_health_checks()
        logger.info("Health checks registered")

        # Validate startup health
        if not await validate_startup_health():
            logger.error("Startup health validation failed")
            raise RuntimeError("Critical system components are unhealthy")

        logger.info(
            "Application started successfully",
            project_name=settings.PROJECT_NAME,
            environment=settings.ENVIRONMENT,
            api_version=settings.API_V1_STR,
            metrics_enabled=settings.ENABLE_METRICS,
            tracing_enabled=settings.ENABLE_TRACING,
            metrics_port=settings.METRICS_PORT if settings.ENABLE_METRICS else None,
        )

        yield

    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise

    finally:
        # Shutdown
        logger.info("Shutting down application")


# Initialize Sentry for error tracking
if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        enable_tracing=True,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "staging" else 0.1,
        environment=settings.ENVIRONMENT,
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    Vulcan Engine - Resource-Constrained Project Scheduling API

    A FastAPI-based scheduling optimization engine using OR-Tools for solving
    complex manufacturing and resource allocation problems.

    ## Features

    * **Schedule Optimization**: Advanced scheduling algorithms using CP-SAT solver
    * **Resource Management**: Multi-skill workforce and equipment constraints
    * **Task Planning**: Precedence relationships and duration optimization
    * **Multi-objective Optimization**: Minimize makespan, costs, and tardiness
    * **Authentication**: Secure API access with JWT tokens
    * **Real-time Solving**: Efficient constraint programming for large-scale problems

    ## Architecture

    Built with FastAPI, SQLModel, PostgreSQL, and OR-Tools CP-SAT solver.
    Optimized for manufacturing scheduling, workforce planning, and resource allocation.
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "admin@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Add observability middleware
app.add_middleware(ObservabilityMiddleware)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
