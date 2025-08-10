"""
Performance monitoring and profiling for the scheduling application.

This module provides comprehensive performance monitoring, profiling,
and optimization utilities for database queries, API endpoints, and
system resources.
"""

import asyncio
import cProfile
import functools
import io
import logging
import pstats
import time
import tracemalloc
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psutil
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric."""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
        }


@dataclass
class QueryPerformance:
    """Query performance tracking."""

    query: str
    execution_time: float
    rows_returned: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    explain_plan: str | None = None

    @property
    def is_slow(self) -> bool:
        """Check if query is slow."""
        return self.execution_time > 1.0  # 1 second threshold


class PerformanceMonitor:
    """
    Central performance monitoring system.
    """

    def __init__(self, enable_profiling: bool = False):
        self.enable_profiling = enable_profiling
        self.metrics: deque[PerformanceMetric] = deque(maxlen=10000)
        self.slow_queries: deque[QueryPerformance] = deque(maxlen=100)
        self.endpoint_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_time": 0,
                "min_time": float("inf"),
                "max_time": 0,
                "errors": 0,
                "status_codes": defaultdict(int),
            }
        )
        self.profiler: cProfile.Profile | None = None
        self.memory_tracer_started = False

        # System resource baseline
        self.baseline_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.baseline_cpu = psutil.cpu_percent(interval=0.1)

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "ms",
        tags: dict[str, str] | None = None,
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(name=name, value=value, unit=unit, tags=tags or {})
        self.metrics.append(metric)

    def record_query(
        self,
        query: str,
        execution_time: float,
        rows_returned: int = 0,
        explain_plan: str | None = None,
    ):
        """Record query performance."""
        perf = QueryPerformance(
            query=query[:500],  # Truncate long queries
            execution_time=execution_time,
            rows_returned=rows_returned,
            explain_plan=explain_plan,
        )

        if perf.is_slow:
            self.slow_queries.append(perf)
            logger.warning(
                f"Slow query detected ({execution_time:.2f}s): {query[:100]}..."
            )

    def record_endpoint(
        self,
        path: str,
        method: str,
        duration: float,
        status_code: int,
        error: Exception | None = None,
    ):
        """Record endpoint performance."""
        key = f"{method} {path}"
        stats = self.endpoint_stats[key]

        stats["count"] += 1
        stats["total_time"] += duration
        stats["min_time"] = min(stats["min_time"], duration)
        stats["max_time"] = max(stats["max_time"], duration)
        stats["status_codes"][status_code] += 1

        if error:
            stats["errors"] += 1

    def start_profiling(self):
        """Start CPU profiling."""
        if not self.enable_profiling:
            return

        self.profiler = cProfile.Profile()
        self.profiler.enable()
        logger.info("CPU profiling started")

    def stop_profiling(self) -> str | None:
        """Stop CPU profiling and return results."""
        if not self.profiler:
            return None

        self.profiler.disable()

        # Generate profiling report
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.print_stats(20)  # Top 20 functions

        report = stream.getvalue()
        self.profiler = None

        logger.info("CPU profiling stopped")
        return report

    def start_memory_tracing(self):
        """Start memory tracing."""
        if not self.memory_tracer_started:
            tracemalloc.start()
            self.memory_tracer_started = True
            logger.info("Memory tracing started")

    def get_memory_snapshot(self) -> dict[str, Any]:
        """Get current memory usage snapshot."""
        if not self.memory_tracer_started:
            self.start_memory_tracing()

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")

        # Get top memory consumers
        top_consumers = []
        for stat in top_stats[:10]:
            top_consumers.append(
                {
                    "file": stat.traceback.format()[0],
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count,
                }
            )

        # Get process memory info
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "top_consumers": top_consumers,
            "baseline_mb": self.baseline_memory,
            "increase_mb": (memory_info.rss / 1024 / 1024) - self.baseline_memory,
        }

    def get_system_resources(self) -> dict[str, Any]:
        """Get current system resource usage."""
        process = psutil.Process()

        # CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)
        system_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

        # Memory usage
        memory = process.memory_info()
        system_memory = psutil.virtual_memory()

        # Disk I/O
        disk_io = psutil.disk_io_counters()

        # Network I/O
        net_io = psutil.net_io_counters()

        # Open file descriptors
        try:
            open_files = len(process.open_files())
            num_connections = len(process.connections())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            open_files = 0
            num_connections = 0

        return {
            "cpu": {
                "process_percent": cpu_percent,
                "system_percent": system_cpu,
                "count": psutil.cpu_count(),
            },
            "memory": {
                "process_rss_mb": memory.rss / 1024 / 1024,
                "process_vms_mb": memory.vms / 1024 / 1024,
                "system_used_gb": system_memory.used / 1024 / 1024 / 1024,
                "system_available_gb": system_memory.available / 1024 / 1024 / 1024,
                "system_percent": system_memory.percent,
            },
            "disk": {
                "read_mb": disk_io.read_bytes / 1024 / 1024,
                "write_mb": disk_io.write_bytes / 1024 / 1024,
                "read_count": disk_io.read_count,
                "write_count": disk_io.write_count,
            },
            "network": {
                "sent_mb": net_io.bytes_sent / 1024 / 1024,
                "recv_mb": net_io.bytes_recv / 1024 / 1024,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            },
            "connections": {
                "open_files": open_files,
                "network_connections": num_connections,
            },
        }

    def get_endpoint_statistics(self) -> dict[str, Any]:
        """Get endpoint performance statistics."""
        stats = {}

        for endpoint, data in self.endpoint_stats.items():
            if data["count"] > 0:
                stats[endpoint] = {
                    "count": data["count"],
                    "avg_time_ms": (data["total_time"] / data["count"]) * 1000,
                    "min_time_ms": data["min_time"] * 1000,
                    "max_time_ms": data["max_time"] * 1000,
                    "error_rate": (data["errors"] / data["count"]) * 100,
                    "status_codes": dict(data["status_codes"]),
                }

        return stats

    def get_slow_queries(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent slow queries."""
        queries = list(self.slow_queries)[-limit:]
        return [
            {
                "query": q.query,
                "execution_time": q.execution_time,
                "rows_returned": q.rows_returned,
                "timestamp": q.timestamp.isoformat(),
                "explain_plan": q.explain_plan,
            }
            for q in queries
        ]

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of all performance metrics."""
        # Group metrics by name
        metric_groups = defaultdict(list)
        for metric in self.metrics:
            metric_groups[metric.name].append(metric.value)

        # Calculate statistics
        summary = {}
        for name, values in metric_groups.items():
            if values:
                summary[name] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1],
                }

        return summary

    def get_full_report(self) -> dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_resources": self.get_system_resources(),
            "memory_snapshot": self.get_memory_snapshot(),
            "endpoint_statistics": self.get_endpoint_statistics(),
            "slow_queries": self.get_slow_queries(),
            "metrics_summary": self.get_metrics_summary(),
        }


# Global performance monitor instance
_monitor: PerformanceMonitor | None = None


def get_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor(enable_profiling=True)
    return _monitor


# Decorators for performance monitoring
def monitor_performance(name: str | None = None, record_args: bool = False):
    """
    Decorator to monitor function performance.

    Args:
        name: Custom metric name
        record_args: Whether to record function arguments
    """

    def decorator(func: Callable) -> Callable:
        metric_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = get_monitor()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000  # Convert to ms

                tags = {"function": func.__name__}
                if record_args:
                    tags["args"] = str(args)[:100]
                    tags["kwargs"] = str(kwargs)[:100]

                monitor.record_metric(metric_name, duration, "ms", tags)
                return result

            except Exception as e:
                duration = (time.time() - start_time) * 1000
                monitor.record_metric(
                    f"{metric_name}_error", duration, "ms", {"error": str(e)}
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitor = get_monitor()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000

                tags = {"function": func.__name__}
                if record_args:
                    tags["args"] = str(args)[:100]
                    tags["kwargs"] = str(kwargs)[:100]

                monitor.record_metric(metric_name, duration, "ms", tags)
                return result

            except Exception as e:
                duration = (time.time() - start_time) * 1000
                monitor.record_metric(
                    f"{metric_name}_error", duration, "ms", {"error": str(e)}
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


@contextmanager
def profile_block(name: str):
    """
    Context manager for profiling code blocks.

    Usage:
        with profile_block("optimization"):
            # Code to profile
            pass
    """
    monitor = get_monitor()
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss / 1024 / 1024

    try:
        yield
    finally:
        duration = (time.time() - start_time) * 1000
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_delta = end_memory - start_memory

        monitor.record_metric(f"{name}_duration", duration, "ms")
        monitor.record_metric(f"{name}_memory_delta", memory_delta, "MB")


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for performance monitoring.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        monitor = get_monitor()
        start_time = time.time()

        # Extract path pattern (remove path parameters)
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            monitor.record_endpoint(
                path=path,
                method=method,
                duration=duration,
                status_code=response.status_code,
            )

            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

            return response

        except Exception as e:
            duration = time.time() - start_time

            monitor.record_endpoint(
                path=path, method=method, duration=duration, status_code=500, error=e
            )

            raise


class QueryProfiler:
    """
    Profile database queries for optimization.
    """

    def __init__(self, session):
        self.session = session
        self.monitor = get_monitor()

    def explain_query(self, query: str) -> str:
        """Get query execution plan."""
        try:
            result = self.session.execute(f"EXPLAIN ANALYZE {query}")
            return "\n".join(row[0] for row in result)
        except Exception as e:
            logger.error(f"Failed to explain query: {e}")
            return ""

    @contextmanager
    def profile_query(self, query_name: str):
        """Profile a query execution."""
        start_time = time.time()
        rows_returned = 0

        try:
            yield
        finally:
            execution_time = time.time() - start_time

            self.monitor.record_query(
                query=query_name,
                execution_time=execution_time,
                rows_returned=rows_returned,
            )

            # Record as metric too
            self.monitor.record_metric(
                f"query_{query_name}", execution_time * 1000, "ms"
            )


# Performance optimization recommendations
class PerformanceAdvisor:
    """
    Provides performance optimization recommendations based on metrics.
    """

    @staticmethod
    def analyze_metrics(monitor: PerformanceMonitor) -> list[str]:
        """Analyze metrics and provide recommendations."""
        recommendations = []

        # Check slow queries
        slow_queries = monitor.get_slow_queries()
        if slow_queries:
            recommendations.append(
                f"Found {len(slow_queries)} slow queries. Consider adding indexes or optimizing query structure."
            )

        # Check endpoint performance
        endpoint_stats = monitor.get_endpoint_statistics()
        for endpoint, stats in endpoint_stats.items():
            if stats["avg_time_ms"] > 1000:
                recommendations.append(
                    f"Endpoint {endpoint} has high average response time ({stats['avg_time_ms']:.0f}ms). "
                    "Consider caching or query optimization."
                )

            if stats["error_rate"] > 5:
                recommendations.append(
                    f"Endpoint {endpoint} has high error rate ({stats['error_rate']:.1f}%). "
                    "Review error handling and input validation."
                )

        # Check system resources
        resources = monitor.get_system_resources()

        if resources["memory"]["system_percent"] > 80:
            recommendations.append(
                "High memory usage detected. Consider increasing server memory or optimizing memory usage."
            )

        if any(cpu > 80 for cpu in resources["cpu"]["system_percent"]):
            recommendations.append(
                "High CPU usage detected. Consider scaling horizontally or optimizing CPU-intensive operations."
            )

        # Check memory leaks
        memory_snapshot = monitor.get_memory_snapshot()
        if memory_snapshot["increase_mb"] > 100:
            recommendations.append(
                f"Potential memory leak detected ({memory_snapshot['increase_mb']:.0f}MB increase). "
                "Review object lifecycle and caching."
            )

        return recommendations


# Export components
__all__ = [
    "PerformanceMonitor",
    "get_monitor",
    "monitor_performance",
    "profile_block",
    "PerformanceMiddleware",
    "QueryProfiler",
    "PerformanceAdvisor",
    "PerformanceMetric",
    "QueryPerformance",
]
