"""
Performance monitoring and optimization API endpoints.

This module provides endpoints for monitoring system performance,
managing caches, and optimizing database queries.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_active_superuser, get_db
from app.core.performance import PerformanceAdvisor, get_monitor
from app.infrastructure.cache.multi_level_cache import (
    CacheInvalidator,
    CacheWarmer,
    MultiLevelCache,
)
from app.infrastructure.database.connection_pool import get_pool_manager
from app.infrastructure.database.indexes import IndexManager, QueryOptimizationHints
from app.models import User

router = APIRouter()


@router.get("/performance/metrics", response_model=dict[str, Any])
async def get_performance_metrics(
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Get current performance metrics.

    Returns comprehensive performance metrics including:
    - System resource usage
    - Endpoint statistics
    - Slow query log
    - Cache performance
    - Connection pool status
    """
    monitor = get_monitor()
    pool_manager = get_pool_manager()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "performance": monitor.get_full_report(),
        "connection_pools": pool_manager.get_all_metrics(),
        "health": pool_manager.health_check(),
    }


@router.get("/performance/recommendations", response_model=list[str])
async def get_performance_recommendations(
    current_user: User = Depends(get_current_active_superuser),
) -> list[str]:
    """
    Get performance optimization recommendations.

    Analyzes current metrics and provides actionable recommendations
    for improving system performance.
    """
    monitor = get_monitor()
    recommendations = PerformanceAdvisor.analyze_metrics(monitor)

    if not recommendations:
        recommendations = [
            "System is performing optimally. No recommendations at this time."
        ]

    return recommendations


@router.get("/performance/slow-queries", response_model=list[dict[str, Any]])
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_superuser),
) -> list[dict[str, Any]]:
    """
    Get recent slow queries.

    Returns a list of queries that exceeded the performance threshold,
    including execution time and query details.
    """
    monitor = get_monitor()
    return monitor.get_slow_queries(limit=limit)


@router.post("/performance/analyze-query", response_model=dict[str, Any])
async def analyze_query(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Analyze a specific query for performance issues.

    Provides execution plan and optimization recommendations for
    the specified query.
    """
    try:
        analysis = QueryOptimizationHints.analyze_query_plan(db, query)

        # Get optimization hints if it's a known pattern
        hints = {}
        for (
            pattern_name,
            pattern,
        ) in QueryOptimizationHints.OPTIMIZATION_PATTERNS.items():
            if pattern["description"].lower() in query.lower():
                hints = QueryOptimizationHints.get_optimization_hints(pattern_name)
                break

        return {"query": query, "analysis": analysis, "optimization_hints": hints}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/performance/cache/stats", response_model=dict[str, Any])
async def get_cache_statistics(
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Get cache statistics.

    Returns statistics for all cache levels including hit rates,
    memory usage, and key distribution.
    """
    # In production, this would get the actual cache instance
    # For now, return sample stats
    cache = MultiLevelCache()
    stats = cache.get_stats()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cache_stats": stats,
        "recommendations": [
            "Consider increasing L1 cache capacity if hit rate < 80%",
            "Monitor L2 cache memory usage",
            "Review cache TTL settings for frequently changing data",
        ],
    }


@router.post("/performance/cache/invalidate")
async def invalidate_cache(
    entity_type: str | None = None,
    entity_id: str | None = None,
    pattern: str | None = None,
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Invalidate cache entries.

    Can invalidate:
    - Specific entity by type and ID
    - All entities of a type
    - Keys matching a pattern
    """
    cache = MultiLevelCache()
    invalidator = CacheInvalidator(cache)

    invalidated_count = 0

    if pattern:
        invalidated_count = await cache.delete_pattern(pattern)
    elif entity_type:
        await invalidator.invalidate_entity(entity_type, entity_id)
        invalidated_count = 1  # Approximate
    else:
        raise HTTPException(
            status_code=400, detail="Must provide either entity_type or pattern"
        )

    return {
        "status": "success",
        "invalidated_count": invalidated_count,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "pattern": pattern,
    }


@router.post("/performance/cache/warm")
async def warm_cache(
    entity_types: list[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Warm cache with specified entity types.

    Loads frequently accessed data into cache to improve performance.
    Runs as a background task to avoid blocking.
    """
    cache = MultiLevelCache()
    CacheWarmer(cache)

    async def warm_task():
        for entity_type in entity_types:
            try:
                # This would warm the actual entities
                # For now, just log the action
                print(f"Warming cache for {entity_type}")
            except Exception as e:
                print(f"Failed to warm {entity_type}: {e}")

    background_tasks.add_task(warm_task)

    return {
        "status": "warming_started",
        "entity_types": entity_types,
        "message": "Cache warming initiated in background",
    }


@router.get("/performance/indexes", response_model=list[dict[str, Any]])
async def get_index_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> list[dict[str, Any]]:
    """
    Get database index usage statistics.

    Returns information about index usage, including unused indexes
    and index bloat.
    """
    usage_stats = IndexManager.get_index_usage_stats(db)
    bloat_stats = IndexManager.get_index_bloat(db)

    # Combine stats
    for usage in usage_stats:
        for bloat in bloat_stats:
            if usage["indexname"] == bloat["indexname"]:
                usage["bloat_percentage"] = bloat.get("bloat_percentage", 0)
                break

    return usage_stats


@router.post("/performance/indexes/create")
async def create_indexes(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Create all recommended database indexes.

    Creates strategic indexes for optimizing query performance.
    Runs as a background task to avoid blocking.
    """

    def create_task():
        results = IndexManager.create_all_indexes(db)
        IndexManager.analyze_tables(db)
        return results

    background_tasks.add_task(create_task)

    return {
        "status": "index_creation_started",
        "message": "Index creation initiated in background",
        "indexes_count": len(IndexManager.INDEXES),
    }


@router.get("/performance/indexes/suggestions", response_model=list[dict[str, Any]])
async def get_index_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> list[dict[str, Any]]:
    """
    Get suggestions for missing indexes.

    Analyzes query patterns and table structure to suggest
    beneficial indexes that don't exist.
    """
    suggestions = IndexManager.get_missing_indexes_suggestions(db)

    if not suggestions:
        suggestions = [{"message": "No missing indexes detected", "status": "optimal"}]

    return suggestions


@router.post("/performance/indexes/rebuild/{index_name}")
async def rebuild_index(
    index_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Rebuild a specific index to reduce bloat.

    Rebuilds the specified index to reclaim space and improve performance.
    Runs as a background task to avoid blocking.
    """

    def rebuild_task():
        return IndexManager.rebuild_index(db, index_name)

    background_tasks.add_task(rebuild_task)

    return {
        "status": "rebuild_started",
        "index_name": index_name,
        "message": "Index rebuild initiated in background",
    }


@router.get("/performance/pools", response_model=dict[str, Any])
async def get_connection_pool_status(
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Get connection pool status and metrics.

    Returns detailed information about database and Redis connection
    pools including usage, health, and performance metrics.
    """
    pool_manager = get_pool_manager()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "pools": pool_manager.get_all_metrics(),
        "health": pool_manager.health_check(),
        "auto_scaling_enabled": pool_manager.auto_scale_enabled,
    }


@router.post("/performance/pools/adjust")
async def adjust_connection_pool(
    pool_type: str,
    pool_name: str,
    new_size: int = Query(..., ge=5, le=200),
    new_overflow: int = Query(..., ge=10, le=400),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Manually adjust connection pool size.

    Allows manual adjustment of connection pool sizes for
    performance tuning.
    """
    pool_manager = get_pool_manager()

    try:
        if pool_type == "database":
            pool = pool_manager.db_pools.get(pool_name)
            if not pool:
                raise HTTPException(
                    status_code=404, detail=f"Database pool '{pool_name}' not found"
                )

            pool.adjust_pool_size(new_size, new_overflow)

        else:
            raise HTTPException(status_code=400, detail="Invalid pool type")

        return {
            "status": "success",
            "pool_type": pool_type,
            "pool_name": pool_name,
            "new_size": new_size,
            "new_overflow": new_overflow,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance/profiling/start")
async def start_profiling(
    duration_seconds: int = Query(60, ge=10, le=300),
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Start CPU profiling.

    Starts CPU profiling for the specified duration to identify
    performance bottlenecks.
    """
    monitor = get_monitor()

    if monitor.profiler:
        raise HTTPException(status_code=400, detail="Profiling already in progress")

    monitor.start_profiling()

    return {
        "status": "profiling_started",
        "duration_seconds": duration_seconds,
        "message": f"Profiling will run for {duration_seconds} seconds",
    }


@router.post("/performance/profiling/stop")
async def stop_profiling(
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Stop CPU profiling and get results.

    Stops the current profiling session and returns the profiling
    report with top time-consuming functions.
    """
    monitor = get_monitor()

    report = monitor.stop_profiling()

    if not report:
        raise HTTPException(status_code=400, detail="No profiling session in progress")

    return {
        "status": "profiling_stopped",
        "report": report,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/performance/memory", response_model=dict[str, Any])
async def get_memory_analysis(
    current_user: User = Depends(get_current_active_superuser),
) -> dict[str, Any]:
    """
    Get memory usage analysis.

    Returns detailed memory usage information including potential
    memory leaks and top memory consumers.
    """
    monitor = get_monitor()

    memory_snapshot = monitor.get_memory_snapshot()

    # Add recommendations based on memory usage
    recommendations = []
    if memory_snapshot["increase_mb"] > 50:
        recommendations.append(
            "Significant memory increase detected. Check for memory leaks."
        )

    if memory_snapshot["percent"] > 80:
        recommendations.append("High memory usage. Consider increasing server memory.")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "memory": memory_snapshot,
        "recommendations": recommendations,
    }


# Add router to main API
def init_router(app):
    """Initialize performance router."""
    app.include_router(
        router,
        prefix="/api/v1",
        tags=["performance"],
        dependencies=[Depends(get_current_active_superuser)],
    )
