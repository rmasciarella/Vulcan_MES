"""
Health Check API Routes

Provides health check endpoints for monitoring system status and observability.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.circuit_breaker import get_circuit_breaker_status
from app.core.health import HealthCheckResult, HealthStatus, health_checker
from app.core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", summary="Overall system health")
async def get_health_status() -> JSONResponse:
    """
    Get overall system health status.

    Returns comprehensive health information for all system components.
    """
    try:
        # Run all health checks
        results = await health_checker.run_all_checks()

        # Determine overall status
        overall_status = health_checker.get_overall_status(results)

        # Prepare response
        response_data = {
            "status": overall_status,
            "timestamp": results[list(results.keys())[0]].timestamp.isoformat()
            if results
            else None,
            "checks": {name: result.to_dict() for name, result in results.items()},
            "summary": {
                "total_checks": len(results),
                "healthy": sum(
                    1 for r in results.values() if r.status == HealthStatus.HEALTHY
                ),
                "unhealthy": sum(
                    1 for r in results.values() if r.status == HealthStatus.UNHEALTHY
                ),
                "degraded": sum(
                    1 for r in results.values() if r.status == HealthStatus.DEGRADED
                ),
                "unknown": sum(
                    1 for r in results.values() if r.status == HealthStatus.UNKNOWN
                ),
            },
        }

        # Set appropriate HTTP status code
        if overall_status == HealthStatus.HEALTHY:
            status_code = 200
        elif overall_status == HealthStatus.DEGRADED:
            status_code = 200  # Still operational but with warnings
        else:
            status_code = 503  # Service unavailable

        logger.info(
            "Health check performed",
            overall_status=overall_status,
            checks_count=len(results),
            healthy_count=response_data["summary"]["healthy"],
            unhealthy_count=response_data["summary"]["unhealthy"],
        )

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        return JSONResponse(
            content={
                "status": HealthStatus.UNKNOWN,
                "error": str(e),
                "timestamp": None,
                "checks": {},
                "summary": {
                    "total_checks": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "degraded": 0,
                    "unknown": 0,
                },
            },
            status_code=503,
        )


@router.get("/health/{check_name}", summary="Specific health check")
async def get_specific_health_check(check_name: str) -> JSONResponse:
    """
    Get health status for a specific component.

    Args:
        check_name: Name of the health check to run

    Returns:
        Detailed health information for the specified component
    """
    try:
        result = await health_checker.run_check(check_name)

        # Set appropriate HTTP status code
        if result.status == HealthStatus.HEALTHY:
            status_code = 200
        elif result.status == HealthStatus.DEGRADED:
            status_code = 200
        elif result.status == HealthStatus.UNKNOWN:
            status_code = 404
        else:
            status_code = 503

        logger.info(
            "Specific health check performed",
            check_name=check_name,
            status=result.status,
            duration_ms=result.duration_ms,
        )

        return JSONResponse(content=result.to_dict(), status_code=status_code)

    except Exception as e:
        logger.error(
            "Specific health check failed",
            check_name=check_name,
            error=str(e),
            exc_info=True,
        )
        return JSONResponse(
            content={
                "name": check_name,
                "status": HealthStatus.UNKNOWN,
                "message": f"Health check failed: {str(e)}",
                "details": {},
                "duration_ms": 0.0,
                "timestamp": None,
            },
            status_code=503,
        )


@router.get("/health/live", summary="Liveness probe")
async def liveness_probe() -> dict[str, Any]:
    """
    Simple liveness probe for container orchestration.

    Returns basic application status without deep health checks.
    Suitable for Kubernetes liveness probes.
    """
    return {
        "status": "alive",
        "timestamp": health_checker.last_results.get(
            "application", HealthCheckResult("application")
        ).timestamp.isoformat(),
    }


@router.get("/health/ready", summary="Readiness probe")
async def readiness_probe() -> JSONResponse:
    """
    Readiness probe for container orchestration.

    Checks critical components to determine if the service can accept traffic.
    Suitable for Kubernetes readiness probes.
    """
    try:
        # Check only critical components for readiness
        critical_checks = ["database", "solver"]

        results = {}
        for check_name in critical_checks:
            results[check_name] = await health_checker.run_check(check_name)

        # Determine if service is ready
        all_healthy = all(
            result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            for result in results.values()
        )

        response_data = {
            "status": "ready" if all_healthy else "not_ready",
            "checks": {name: result.to_dict() for name, result in results.items()},
        }

        status_code = 200 if all_healthy else 503

        logger.info(
            "Readiness check performed",
            ready=all_healthy,
            critical_checks=critical_checks,
        )

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error("Readiness check failed", error=str(e), exc_info=True)
        return JSONResponse(
            content={"status": "not_ready", "error": str(e), "checks": {}},
            status_code=503,
        )


@router.get("/health/circuit-breakers", summary="Circuit breaker status")
async def get_circuit_breaker_status_endpoint() -> dict[str, Any]:
    """
    Get status of all circuit breakers.

    Returns current state and configuration of all registered circuit breakers.
    """
    try:
        status = get_circuit_breaker_status()

        logger.info(
            "Circuit breaker status requested",
            breakers_count=len(status),
        )

        return {
            "circuit_breakers": status,
            "summary": {
                "total": len(status),
                "open": sum(1 for cb in status.values() if cb["state"] == "open"),
                "closed": sum(1 for cb in status.values() if cb["state"] == "closed"),
                "half_open": sum(
                    1 for cb in status.values() if cb["state"] == "half-open"
                ),
            },
        }

    except Exception as e:
        logger.error("Circuit breaker status check failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/metrics", summary="Health metrics summary")
async def get_health_metrics(
    include_history: bool = Query(False, description="Include historical data"),
) -> dict[str, Any]:
    """
    Get aggregated health metrics and statistics.

    Args:
        include_history: Whether to include historical health check data

    Returns:
        Health metrics and performance statistics
    """
    try:
        # Get current results
        current_results = health_checker.last_results

        metrics = {
            "current_status": {
                name: {
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp.isoformat(),
                }
                for name, result in current_results.items()
            },
            "performance": {
                "average_check_duration_ms": (
                    sum(r.duration_ms for r in current_results.values())
                    / len(current_results)
                    if current_results
                    else 0
                ),
                "slowest_check": (
                    max(current_results.items(), key=lambda x: x[1].duration_ms)[0]
                    if current_results
                    else None
                ),
                "fastest_check": (
                    min(current_results.items(), key=lambda x: x[1].duration_ms)[0]
                    if current_results
                    else None
                ),
            },
        }

        logger.info("Health metrics requested", include_history=include_history)

        return metrics

    except Exception as e:
        logger.error("Health metrics request failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
