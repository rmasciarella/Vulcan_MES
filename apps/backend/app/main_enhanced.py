"""
Enhanced FastAPI Application with Comprehensive Security

This module configures the FastAPI application with:
- RS256 JWT authentication
- Rate limiting
- Input validation
- Security headers
- Audit logging
- RBAC support
"""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_enhanced import AuditLogger

# Import security modules
from app.core.validation import ValidationMiddleware

# Initialize structured logger
logger = get_logger(__name__)
audit_logger = AuditLogger()


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
        client_ip = request.client.host if request.client else None

        # Log request start
        logger.info(
            "Request started",
            method=method,
            path=path,
            correlation_id=correlation_id,
            user_id=user_id,
            client_ip=client_ip,
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

            # Audit log for sensitive endpoints
            if path.startswith("/api/v1/users") or path.startswith("/api/v1/admin"):
                audit_logger.log_data_access(
                    user_id=user_id or "anonymous",
                    resource_type="api",
                    resource_id=path,
                    action=method,
                    ip_address=client_ip,
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

            # Audit log security events
            audit_logger.log_security_event(
                event_type="request_error",
                severity="MEDIUM",
                description=f"Request failed: {method} {path}",
                ip_address=client_ip,
                user_id=user_id if user_id else None,
                details={"error": str(e), "error_type": type(e).__name__},
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

        # Log successful startup
        logger.info(
            "Application started successfully",
            project_name=settings.PROJECT_NAME,
            environment=settings.ENVIRONMENT,
            api_version=settings.API_V1_STR,
            metrics_enabled=settings.ENABLE_METRICS,
            tracing_enabled=settings.ENABLE_TRACING,
            metrics_port=settings.METRICS_PORT if settings.ENABLE_METRICS else None,
            security_features={
                "jwt_algorithm": "RS256",
                "rate_limiting": "enabled",
                "input_validation": "enabled",
                "audit_logging": "enabled",
                "rbac": "enabled",
            },
        )

        # Audit log application start
        audit_logger.log_security_event(
            event_type="application_start",
            severity="INFO",
            description=f"Application started in {settings.ENVIRONMENT} environment",
            details={
                "project": settings.PROJECT_NAME,
                "environment": settings.ENVIRONMENT,
                "version": "1.0.0",
            },
        )

        yield

    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        audit_logger.log_security_event(
            event_type="startup_failure",
            severity="CRITICAL",
            description="Application failed to start",
            details={"error": str(e)},
        )
        raise

    finally:
        # Shutdown
        logger.info("Shutting down application")
        audit_logger.log_security_event(
            event_type="application_shutdown",
            severity="INFO",
            description="Application shutting down",
        )


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

    ## Enhanced Security Features

    * **RS256 JWT Authentication**: Asymmetric key cryptography for secure token generation
    * **Rate Limiting**: Adaptive rate limiting with burst protection
    * **Input Validation**: Comprehensive validation against injection attacks
    * **Field Encryption**: AES-256 encryption for sensitive data
    * **RBAC System**: Role-based access control with granular permissions
    * **Audit Logging**: Complete audit trail for security events
    * **Security Headers**: HSTS, CSP, X-Frame-Options, and more

    ## Features

    * **Schedule Optimization**: Advanced scheduling algorithms using CP-SAT solver
    * **Resource Management**: Multi-skill workforce and equipment constraints
    * **Task Planning**: Precedence relationships and duration optimization
    * **Multi-objective Optimization**: Minimize makespan, costs, and tardiness
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
    docs_url="/docs"
    if settings.ENVIRONMENT != "production"
    else None,  # Disable in production
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Add security middleware stack (order matters - execute from bottom to top)

# 1. Add observability middleware
app.add_middleware(ObservabilityMiddleware)

# 2. Add validation middleware for input sanitization
app.add_middleware(ValidationMiddleware)

# 3. Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# 4. Add trusted host middleware for production
if settings.ENVIRONMENT != "local":
    # Only allow specific hosts in production
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.example.com", "localhost"],  # Configure based on your domain
    )

# 5. Set all CORS enabled origins with secure configuration
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "X-Correlation-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
        ],
        max_age=3600,  # Cache preflight requests for 1 hour
    )


# Add security headers to all responses
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add comprehensive security headers to all responses."""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # HSTS header for HTTPS (only in production)
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    # CSP header with nonce for inline scripts
    csp_nonce = str(uuid.uuid4())
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{csp_nonce}'; "
        f"style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: https:; "
        f"font-src 'self' data:; "
        f"connect-src 'self'; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )

    return response


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)
