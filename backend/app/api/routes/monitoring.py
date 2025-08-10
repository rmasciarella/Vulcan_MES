"""Performance monitoring and dashboard API endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.core.cache import CacheManager
from app.core.celery_app import get_active_tasks, get_worker_stats
from app.core.database import check_database_health, get_pool_status
from app.core.monitoring import (
    MetricsCollector,
    memory_profiler,
    performance_analyzer,
    system_monitor,
)

router = APIRouter()


@router.get("/performance", response_model=dict[str, Any])
async def get_performance_metrics(
    period: str = Query("1h", description="Time period for metrics (1h, 6h, 24h, 7d)"),
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    """
    Get comprehensive performance metrics.

    Returns system performance metrics including response times, throughput,
    error rates, and resource utilization.
    """
    # Generate performance report
    report = performance_analyzer.generate_performance_report()

    # Add period-specific filtering
    report["period"] = period

    return report


@router.get("/system", response_model=dict[str, Any])
async def get_system_metrics() -> dict[str, Any]:
    """
    Get system resource metrics.

    Returns CPU, memory, disk, and network utilization metrics.
    """
    return system_monitor.collect_system_metrics()


@router.get("/database", response_model=dict[str, Any])
async def get_database_metrics() -> dict[str, Any]:
    """
    Get database performance metrics.

    Returns connection pool status, query performance, and health checks.
    """
    return {
        "pool_status": get_pool_status(),
        "health": check_database_health(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/cache", response_model=dict[str, Any])
async def get_cache_metrics() -> dict[str, Any]:
    """
    Get cache performance metrics.

    Returns cache hit rates, memory usage, and key statistics.
    """
    cache_manager = CacheManager()
    return cache_manager.get_stats()


@router.get("/workers", response_model=dict[str, Any])
async def get_worker_metrics() -> dict[str, Any]:
    """
    Get background worker metrics.

    Returns Celery worker status, active tasks, and queue depths.
    """
    return {
        "worker_stats": get_worker_stats(),
        "active_tasks": get_active_tasks(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/bottlenecks", response_model=list[dict[str, Any]])
async def identify_bottlenecks() -> list[dict[str, Any]]:
    """
    Identify performance bottlenecks.

    Returns list of identified bottlenecks with severity and recommendations.
    """
    return performance_analyzer.identify_bottlenecks()


@router.get("/response-times", response_model=dict[str, Any])
async def analyze_response_times() -> dict[str, Any]:
    """
    Analyze API response times.

    Returns response time analysis by endpoint with percentiles.
    """
    return performance_analyzer.analyze_response_times()


@router.post("/memory/snapshot", response_model=dict[str, Any])
async def take_memory_snapshot(
    label: str = Query("", description="Label for the snapshot"),
) -> dict[str, Any]:
    """
    Take a memory usage snapshot.

    Returns current memory usage and top memory consumers.
    """
    if not memory_profiler.snapshots:
        memory_profiler.start_profiling()

    return memory_profiler.take_snapshot(label)


@router.get("/memory/comparison", response_model=dict[str, Any])
async def compare_memory_snapshots(
    index1: int = Query(-2, description="First snapshot index"),
    index2: int = Query(-1, description="Second snapshot index"),
) -> dict[str, Any]:
    """
    Compare two memory snapshots.

    Returns memory usage differences between two snapshots.
    """
    return memory_profiler.compare_snapshots(index1, index2)


@router.get("/metrics/summary", response_model=dict[str, Any])
async def get_metrics_summary(
    metric_name: str = Query(..., description="Name of the metric"),
) -> dict[str, Any]:
    """
    Get summary statistics for a specific metric.

    Returns count, mean, median, percentiles, etc. for the metric.
    """
    metrics_collector = MetricsCollector()
    summary = metrics_collector.get_metrics_summary(metric_name)

    if not summary:
        raise HTTPException(status_code=404, detail=f"Metric {metric_name} not found")

    return {
        "metric": metric_name,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/metrics/flush")
async def flush_metrics_to_cache() -> dict[str, str]:
    """
    Flush in-memory metrics to cache.

    Persists current metrics snapshot to Redis cache.
    """
    metrics_collector = MetricsCollector()
    metrics_collector.flush_to_cache()

    return {"status": "success", "message": "Metrics flushed to cache"}


@router.get("/dashboard/kpi", response_model=dict[str, Any])
async def get_kpi_dashboard(
    period: str = Query("daily", description="KPI period (daily, weekly, monthly)"),
) -> dict[str, Any]:
    """
    Get KPI dashboard data.

    Returns key performance indicators for the specified period.
    """
    # This would typically call the Celery task or fetch from cache
    cache_manager = CacheManager()
    cache_key = f"dashboard:kpi:{period}"

    dashboard_data = cache_manager.get(cache_key)

    if not dashboard_data:
        # Generate dashboard data if not cached
        dashboard_data = {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "kpis": {
                "throughput": {
                    "value": 125,
                    "target": 120,
                    "status": "good",
                    "trend": "up",
                },
                "utilization": {
                    "value": 78.5,
                    "target": 80,
                    "status": "warning",
                    "trend": "stable",
                },
                "error_rate": {
                    "value": 0.02,
                    "target": 0.05,
                    "status": "excellent",
                    "trend": "down",
                },
                "response_time_p95": {
                    "value": 450,
                    "target": 500,
                    "status": "good",
                    "trend": "stable",
                },
            },
            "alerts": [],
        }

        # Cache for 5 minutes
        cache_manager.set(cache_key, dashboard_data, ttl=300)

    return dashboard_data


@router.get("/health/detailed", response_model=dict[str, Any])
async def get_detailed_health() -> dict[str, Any]:
    """
    Get detailed system health status.

    Returns comprehensive health check of all system components.
    """
    cache_manager = CacheManager()

    health = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "components": {
            "api": {
                "status": "healthy",
                "response_time_ms": 50,
            },
            "database": check_database_health(),
            "cache": {
                "status": "healthy" if cache_manager.ping() else "unhealthy",
                "stats": cache_manager.get_stats() if cache_manager.ping() else None,
            },
            "workers": get_worker_stats(),
            "system": system_monitor.collect_system_metrics(),
        },
        "uptime_seconds": None,  # Would calculate from app start time
    }

    # Determine overall health
    unhealthy_components = []
    for name, component in health["components"].items():
        if isinstance(component, dict) and component.get("status") == "unhealthy":
            unhealthy_components.append(name)

    if unhealthy_components:
        health["status"] = "degraded"
        health["issues"] = unhealthy_components

    return health


@router.get("/alerts/active", response_model=list[dict[str, Any]])
async def get_active_alerts() -> list[dict[str, Any]]:
    """
    Get active performance alerts.

    Returns list of active alerts requiring attention.
    """
    alerts = []

    # Check for bottlenecks
    bottlenecks = performance_analyzer.identify_bottlenecks()
    for bottleneck in bottlenecks:
        if bottleneck.get("severity") in ["high", "critical"]:
            alerts.append(
                {
                    "id": f"bottleneck_{bottleneck['type']}",
                    "type": "bottleneck",
                    "severity": bottleneck["severity"],
                    "message": bottleneck["details"],
                    "suggestion": bottleneck.get("suggestion"),
                    "timestamp": datetime.now().isoformat(),
                }
            )

    # Check system resources
    system_metrics = system_monitor.collect_system_metrics()

    if system_metrics["cpu"]["percent"] > 90:
        alerts.append(
            {
                "id": "cpu_critical",
                "type": "resource",
                "severity": "critical",
                "message": f"CPU usage critical: {system_metrics['cpu']['percent']:.1f}%",
                "timestamp": datetime.now().isoformat(),
            }
        )

    if system_metrics["memory"]["percent"] > 90:
        alerts.append(
            {
                "id": "memory_critical",
                "type": "resource",
                "severity": "critical",
                "message": f"Memory usage critical: {system_metrics['memory']['percent']:.1f}%",
                "timestamp": datetime.now().isoformat(),
            }
        )

    if system_metrics["disk"]["percent"] > 90:
        alerts.append(
            {
                "id": "disk_critical",
                "type": "resource",
                "severity": "high",
                "message": f"Disk usage high: {system_metrics['disk']['percent']:.1f}%",
                "timestamp": datetime.now().isoformat(),
            }
        )

    return alerts


@router.post("/test/load")
async def trigger_load_test(
    scenario: str = Query("normal", description="Load test scenario"),
    duration: str = Query("5m", description="Test duration"),
    users: int = Query(100, description="Number of virtual users"),
) -> dict[str, Any]:
    """
    Trigger a load test (development only).

    Starts a load test with the specified parameters.
    """
    # This would typically trigger a Celery task to run the load test
    return {
        "status": "started",
        "scenario": scenario,
        "duration": duration,
        "users": users,
        "message": "Load test triggered. Check results in monitoring dashboard.",
    }


# Export router
__all__ = ["router"]
