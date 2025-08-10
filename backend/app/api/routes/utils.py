import logging
import time
from typing import Any

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic.networks import EmailStr
from sqlmodel import Session, text

from app.api.deps import get_current_active_superuser, get_db
from app.core.config import settings
from app.core.db import engine
from app.models import Message
from app.utils import generate_test_email, send_email

logger = logging.getLogger(__name__)


class DatabaseInfo(BaseModel):
    """Database connection information model."""

    connected: bool
    version: str | None = None
    pool_info: dict[str, int] | None = None
    connection_url: str | None = None
    error: str | None = None


class ServiceHealth(BaseModel):
    """Service health information model."""

    name: str
    status: str
    response_time_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


class HealthCheckResponse(BaseModel):
    """Health check response model with strict typing."""

    status: str
    database: DatabaseInfo
    services: list[ServiceHealth]
    version: str
    timestamp: str
    uptime_seconds: float | None = None


router = APIRouter(prefix="/utils", tags=["utils"])

# Application start time for uptime calculation
app_start_time = time.time()


async def check_redis_health() -> ServiceHealth:
    """Check Redis connectivity and performance."""
    start_time = time.time()
    try:
        # Create Redis connection
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            ssl=settings.REDIS_SSL,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

        # Test connectivity with ping
        result = redis_client.ping()

        # Test set/get operations
        test_key = "health_check_test"
        redis_client.set(test_key, "test_value", ex=60)
        retrieved_value = redis_client.get(test_key)

        # Get Redis info
        redis_info = redis_client.info()

        response_time = (time.time() - start_time) * 1000

        redis_client.delete(test_key)
        redis_client.close()

        return ServiceHealth(
            name="redis",
            status="healthy"
            if result and retrieved_value == b"test_value"
            else "unhealthy",
            response_time_ms=response_time,
            details={
                "version": redis_info.get("redis_version"),
                "connected_clients": redis_info.get("connected_clients"),
                "used_memory_human": redis_info.get("used_memory_human"),
                "uptime_in_seconds": redis_info.get("uptime_in_seconds"),
            },
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            name="redis",
            status="unhealthy",
            response_time_ms=response_time,
            error=str(e),
        )


async def check_external_api_health() -> list[ServiceHealth]:
    """Check external API dependencies."""
    services = []

    # Check if we have external APIs to monitor
    external_apis = [
        {"name": "solver_api", "url": "http://localhost:8001/health", "timeout": 5},
    ]

    for api in external_apis:
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api["url"], timeout=api.get("timeout", 5))
                response_time = (time.time() - start_time) * 1000

                services.append(
                    ServiceHealth(
                        name=api["name"],
                        status="healthy"
                        if response.status_code == 200
                        else "unhealthy",
                        response_time_ms=response_time,
                        details={
                            "status_code": response.status_code,
                            "url": api["url"],
                        },
                    )
                )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            services.append(
                ServiceHealth(
                    name=api["name"],
                    status="unhealthy",
                    response_time_ms=response_time,
                    error=str(e),
                )
            )

    return services


async def check_file_system_health() -> ServiceHealth:
    """Check file system access and disk space."""
    start_time = time.time()
    try:
        import os
        import shutil

        # Check disk space
        disk_usage = shutil.disk_usage("/")
        free_space_gb = disk_usage.free / (1024**3)
        total_space_gb = disk_usage.total / (1024**3)
        used_percentage = (
            (disk_usage.total - disk_usage.free) / disk_usage.total
        ) * 100

        # Test file write/read
        test_file = "/tmp/health_check_test.txt"
        test_content = "health check test"

        with open(test_file, "w") as f:
            f.write(test_content)

        with open(test_file) as f:
            content = f.read()

        os.remove(test_file)

        response_time = (time.time() - start_time) * 1000

        status = "healthy"
        if used_percentage > 90:
            status = "critical"
        elif used_percentage > 80:
            status = "warning"
        elif content != test_content:
            status = "unhealthy"

        return ServiceHealth(
            name="filesystem",
            status=status,
            response_time_ms=response_time,
            details={
                "free_space_gb": round(free_space_gb, 2),
                "total_space_gb": round(total_space_gb, 2),
                "used_percentage": round(used_percentage, 2),
                "writable": content == test_content,
            },
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            name="filesystem",
            status="unhealthy",
            response_time_ms=response_time,
            error=str(e),
        )


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """
    Comprehensive health check endpoint that verifies all system dependencies.
    """
    from datetime import datetime

    services = []
    overall_status = "healthy"

    try:
        # Database health check
        db_start = time.time()
        result = db.execute(text("SELECT version()"))
        db_version = result.scalar()

        # Test connection pool status
        pool_info = {
            "pool_size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
        }

        # Additional database health checks
        db.execute(text("SELECT 1"))
        db.commit()
        db_response_time = (time.time() - db_start) * 1000

        database_info = DatabaseInfo(
            connected=True,
            version=db_version,
            pool_info=pool_info,
            connection_url=str(engine.url).split("@")[1]
            if "@" in str(engine.url)
            else "masked",
        )

        services.append(
            ServiceHealth(
                name="database",
                status="healthy",
                response_time_ms=db_response_time,
                details={"version": db_version, "pool_info": pool_info},
            )
        )

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        overall_status = "unhealthy"
        database_info = DatabaseInfo(connected=False, error=str(e))

        services.append(
            ServiceHealth(name="database", status="unhealthy", error=str(e))
        )

    # Check Redis health
    try:
        redis_health = await check_redis_health()
        services.append(redis_health)
        if redis_health.status != "healthy":
            overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        services.append(ServiceHealth(name="redis", status="unhealthy", error=str(e)))
        overall_status = "degraded" if overall_status == "healthy" else "unhealthy"

    # Check file system health
    try:
        filesystem_health = await check_file_system_health()
        services.append(filesystem_health)
        if filesystem_health.status not in ["healthy", "warning"]:
            overall_status = "unhealthy"
        elif filesystem_health.status == "warning" and overall_status == "healthy":
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Filesystem health check failed: {str(e)}")
        services.append(
            ServiceHealth(name="filesystem", status="unhealthy", error=str(e))
        )
        overall_status = "degraded" if overall_status == "healthy" else "unhealthy"

    # Check external APIs
    try:
        external_services = await check_external_api_health()
        services.extend(external_services)
        for service in external_services:
            if service.status != "healthy":
                overall_status = (
                    "degraded" if overall_status == "healthy" else overall_status
                )
    except Exception as e:
        logger.error(f"External API health check failed: {str(e)}")

    # Calculate uptime
    uptime_seconds = time.time() - app_start_time

    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=503,
            detail=HealthCheckResponse(
                status=overall_status,
                database=database_info,
                services=services,
                version="1.0.0",
                timestamp=datetime.utcnow().isoformat(),
                uptime_seconds=uptime_seconds,
            ).model_dump(),
        )

    return HealthCheckResponse(
        status=overall_status,
        database=database_info,
        services=services,
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=uptime_seconds,
    )


class DatabaseStatusResponse(BaseModel):
    """Detailed database status response model."""

    database_name: str | None = None
    version: str | None = None
    active_connections: int | None = None
    pool_statistics: dict[str, int]
    connection_url: str
    ssl_enabled: bool


@router.get("/db-status/", dependencies=[Depends(get_current_active_superuser)])
async def database_status(db: Session = Depends(get_db)) -> DatabaseStatusResponse:
    """
    Detailed database status endpoint for administrators.
    """
    try:
        # Get database version and connection info
        version_result = db.execute(text("SELECT version()"))
        db_version = version_result.scalar()

        # Get current database name
        db_name_result = db.execute(text("SELECT current_database()"))
        db_name = db_name_result.scalar()

        # Get connection count
        connections_result = db.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
        )
        active_connections = connections_result.scalar()

        # Pool statistics
        pool_stats = {
            "size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "invalid": engine.pool.invalid(),
        }

        return DatabaseStatusResponse(
            database_name=db_name,
            version=db_version,
            active_connections=active_connections,
            pool_statistics=pool_stats,
            connection_url=str(engine.url).split("@")[1]
            if "@" in str(engine.url)
            else "masked",
            ssl_enabled="sslmode" in str(engine.url)
            or (
                hasattr(engine.pool, "_connect_args")
                and "sslmode" in getattr(engine.pool, "_connect_args", {})
            ),
        )
    except Exception as e:
        logger.error(f"Database status check failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Database status check failed: {str(e)}"
        )
