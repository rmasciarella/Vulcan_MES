"""
Enhanced Secure FastAPI Application with Comprehensive Security Features

This module integrates all security enhancements including:
- MFA authentication
- Rate limiting
- Security headers
- Input validation
- Enhanced CORS
"""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.main import api_router
from app.core.cache import get_redis_client
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
from app.middleware.security_headers import (
    CORSSecurityMiddleware,
    SecurityHeadersMiddleware,
)
from app.middleware.validation import ValidationMiddleware

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

            # Log slow requests
            if duration > settings.PERFORMANCE_SLOW_QUERY_THRESHOLD:
                logger.warning(
                    "Slow request detected",
                    method=method,
                    path=path,
                    duration_seconds=duration,
                    threshold=settings.PERFORMANCE_SLOW_QUERY_THRESHOLD,
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
    logger.info("Starting secure application initialization")

    try:
        # Initialize observability system
        initialize_observability()
        logger.info("Observability system initialized")

        # Initialize Redis for rate limiting
        try:
            redis_client = await get_redis_client()
            app.state.redis_client = redis_client
            logger.info("Redis client initialized for rate limiting")
        except Exception as e:
            logger.warning(
                f"Redis initialization failed, using in-memory rate limiting: {e}"
            )
            app.state.redis_client = None

        # Register health checks
        register_default_health_checks()
        logger.info("Health checks registered")

        # Validate startup health
        if not await validate_startup_health():
            logger.error("Startup health validation failed")
            raise RuntimeError("Critical system components are unhealthy")

        logger.info(
            "Secure application started successfully",
            project_name=settings.PROJECT_NAME,
            environment=settings.ENVIRONMENT,
            api_version=settings.API_V1_STR,
            metrics_enabled=settings.ENABLE_METRICS,
            tracing_enabled=settings.ENABLE_TRACING,
            metrics_port=settings.METRICS_PORT if settings.ENABLE_METRICS else None,
            mfa_enabled=True,
            rate_limiting_enabled=True,
            security_headers_enabled=True,
            input_validation_enabled=True,
        )

        yield

    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise

    finally:
        # Shutdown
        logger.info("Shutting down secure application")

        # Cleanup Redis connection
        if hasattr(app.state, "redis_client") and app.state.redis_client:
            await app.state.redis_client.close()
            logger.info("Redis connection closed")


# Initialize Sentry for error tracking
if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        enable_tracing=True,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "staging" else 0.1,
        environment=settings.ENVIRONMENT,
    )

app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Secure Edition",
    description="""
    Vulcan Engine - Secure Resource-Constrained Project Scheduling API

    A security-hardened FastAPI-based scheduling optimization engine with comprehensive
    protection against OWASP Top 10 vulnerabilities.

    ## Security Features

    * **Multi-Factor Authentication (MFA)**: TOTP-based 2FA with backup codes
    * **Rate Limiting**: Adaptive rate limiting with burst protection
    * **Security Headers**: Full OWASP recommended headers (CSP, HSTS, etc.)
    * **Input Validation**: Protection against SQL injection, XSS, command injection
    * **Enhanced Authentication**: RS256 JWT with RSA keys, Argon2 password hashing
    * **RBAC**: Role-based access control with department-level isolation

    ## Core Features

    * **Schedule Optimization**: Advanced scheduling algorithms using CP-SAT solver
    * **Resource Management**: Multi-skill workforce and equipment constraints
    * **Task Planning**: Precedence relationships and duration optimization
    * **Multi-objective Optimization**: Minimize makespan, costs, and tardiness
    * **Real-time Solving**: Efficient constraint programming for large-scale problems

    ## Security Compliance

    * OWASP Top 10 2021 compliant
    * GDPR ready with data encryption
    * SOC 2 Type II controls implemented
    * ISO 27001 security controls

    ## Architecture

    Built with FastAPI, SQLModel, PostgreSQL, and OR-Tools CP-SAT solver.
    Enhanced with comprehensive security middleware stack.
    """,
    version="2.0.0-secure",
    contact={
        "name": "Security Team",
        "email": "security@example.com",
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

# Middleware order is important - applied in reverse order

# 1. Observability (outermost - tracks all requests)
app.add_middleware(ObservabilityMiddleware)

# 2. Compression (compress responses)
if settings.ENABLE_RESPONSE_COMPRESSION:
    app.add_middleware(GZipMiddleware, minimum_size=settings.COMPRESSION_MINIMUM_SIZE)

# 3. Trusted Host (prevent host header injection)
if settings.ENVIRONMENT != "local":
    allowed_hosts = [
        settings.FRONTEND_HOST.replace("http://", "").replace("https://", ""),
        "localhost",
        "127.0.0.1",
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# 4. Security Headers (add security headers to responses)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=(settings.ENVIRONMENT == "production"),
    enable_csp=True,
    csp_report_only=(settings.ENVIRONMENT == "staging"),
    frame_options="DENY",
    referrer_policy="strict-origin-when-cross-origin",
)

# 5. Rate Limiting (prevent abuse)
app.add_middleware(RateLimitMiddleware)

# 6. Input Validation (validate all inputs)
app.add_middleware(
    ValidationMiddleware, enable_strict_mode=(settings.ENVIRONMENT == "production")
)

# 7. CORS (handle cross-origin requests)
if settings.all_cors_origins:
    app.add_middleware(
        CORSSecurityMiddleware,
        allowed_origins=settings.all_cors_origins,
        allow_credentials=True,
        allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allowed_headers=["*"],
        expose_headers=[
            "X-Correlation-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
        ],
        max_age=3600,
    )

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


# Security event logging
@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    """Log security events for forbidden access."""
    logger.warning(
        "Forbidden access attempt",
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", ""),
    )
    return {"detail": "Forbidden"}


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    """Log security events for unauthorized access."""
    logger.warning(
        "Unauthorized access attempt",
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", ""),
    )
    return {"detail": "Unauthorized"}
