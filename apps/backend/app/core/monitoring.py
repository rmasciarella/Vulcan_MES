"""Performance monitoring and metrics collection."""

import functools
import logging
import time
import tracemalloc
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any, ParamSpec, TypeVar

import psutil
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.cache import CacheManager

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class MetricsCollector:
    """Collect and store performance metrics."""

    _instance: "MetricsCollector | None" = None

    def __new__(cls) -> "MetricsCollector":
        """Singleton pattern for metrics collector."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize metrics storage."""
        self.metrics: dict[str, list[float]] = {}
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.cache_manager = CacheManager()

    def record_metric(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Record a metric value."""
        key = self._build_key(name, tags)
        if key not in self.metrics:
            self.metrics[key] = []

        self.metrics[key].append(value)

        # Keep only last 1000 values in memory
        if len(self.metrics[key]) > 1000:
            self.metrics[key] = self.metrics[key][-1000:]

    def increment_counter(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter."""
        key = self._build_key(name, tags)
        if key not in self.counters:
            self.counters[key] = 0
        self.counters[key] += value

    def set_gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Set a gauge value."""
        key = self._build_key(name, tags)
        self.gauges[key] = value

    def get_metrics_summary(
        self, name: str, tags: dict[str, str] | None = None
    ) -> dict[str, float]:
        """Get summary statistics for a metric."""
        key = self._build_key(name, tags)
        values = self.metrics.get(key, [])

        if not values:
            return {}

        import statistics

        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }

    def flush_to_cache(self) -> None:
        """Flush metrics to cache for persistence."""
        timestamp = datetime.now().isoformat()

        # Store metrics snapshot
        snapshot = {
            "timestamp": timestamp,
            "metrics": {k: self.get_metrics_summary(k) for k in self.metrics},
            "counters": self.counters.copy(),
            "gauges": self.gauges.copy(),
        }

        # Store in cache with TTL
        cache_key = f"metrics:snapshot:{timestamp}"
        self.cache_manager.set(cache_key, snapshot, ttl=3600)  # Keep for 1 hour

        # Also store latest snapshot reference
        self.cache_manager.set("metrics:latest", snapshot, ttl=3600)

    @staticmethod
    def _build_key(name: str, tags: dict[str, str] | None) -> str:
        """Build metric key with tags."""
        if not tags:
            return name

        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name},{tag_str}"

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class PerformanceMonitor:
    """Monitor application performance."""

    def __init__(self):
        self.metrics_collector = MetricsCollector()

    @contextmanager
    def measure_time(self, operation: str, tags: dict[str, str] | None = None):
        """Context manager to measure operation time."""
        start_time = time.perf_counter()

        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            self.metrics_collector.record_metric(
                f"{operation}.duration", duration, tags
            )

            if duration > 1.0:  # Log slow operations
                logger.warning(
                    f"Slow operation detected: {operation} took {duration:.2f}s",
                    extra={"operation": operation, "duration": duration, "tags": tags},
                )

    def measure_function(
        self,
        name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to measure function execution time."""

        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            operation_name = name or f"function.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                with self.measure_time(operation_name, tags):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    async def measure_async_function(
        self,
        name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to measure async function execution time."""

        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            operation_name = name or f"async_function.{func.__name__}"

            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start_time
                    self.metrics_collector.record_metric(
                        f"{operation_name}.duration", duration, tags
                    )

            return wrapper

        return decorator


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics_collector = MetricsCollector()

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and collect metrics."""
        start_time = time.perf_counter()

        # Track active requests
        self.metrics_collector.increment_counter("http.requests.active")

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.perf_counter() - start_time

            tags = {
                "method": request.method,
                "path": request.url.path,
                "status": str(response.status_code),
            }

            self.metrics_collector.record_metric(
                "http.request.duration", duration, tags
            )
            self.metrics_collector.increment_counter("http.requests.total", tags=tags)

            if response.status_code >= 400:
                self.metrics_collector.increment_counter(
                    "http.requests.errors", tags=tags
                )

            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}"

            return response

        finally:
            self.metrics_collector.increment_counter("http.requests.active", -1)


class SystemMonitor:
    """Monitor system resources."""

    def __init__(self):
        self.metrics_collector = MetricsCollector()

    def collect_system_metrics(self) -> dict[str, Any]:
        """Collect system resource metrics."""
        metrics = {}

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics["cpu"] = {
            "percent": cpu_percent,
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        }
        self.metrics_collector.set_gauge("system.cpu.percent", cpu_percent)

        # Memory metrics
        memory = psutil.virtual_memory()
        metrics["memory"] = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
        }
        self.metrics_collector.set_gauge("system.memory.percent", memory.percent)

        # Disk metrics
        disk = psutil.disk_usage("/")
        metrics["disk"] = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        }
        self.metrics_collector.set_gauge("system.disk.percent", disk.percent)

        # Network metrics
        net_io = psutil.net_io_counters()
        metrics["network"] = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }

        # Process metrics
        process = psutil.Process()
        metrics["process"] = {
            "cpu_percent": process.cpu_percent(),
            "memory_rss": process.memory_info().rss,
            "memory_vms": process.memory_info().vms,
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, "num_fds") else None,
        }

        return metrics


class MemoryProfiler:
    """Profile memory usage."""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.snapshots: list[Any] = []

    def start_profiling(self) -> None:
        """Start memory profiling."""
        tracemalloc.start()

    def take_snapshot(self, label: str = "") -> dict[str, Any]:
        """Take memory snapshot."""
        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append(snapshot)

        # Get top memory consumers
        top_stats = snapshot.statistics("lineno")[:10]

        memory_info = {
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "current_memory_mb": tracemalloc.get_traced_memory()[0] / 1024 / 1024,
            "peak_memory_mb": tracemalloc.get_traced_memory()[1] / 1024 / 1024,
            "top_consumers": [],
        }

        for stat in top_stats:
            memory_info["top_consumers"].append(
                {
                    "file": stat.traceback.format()[0] if stat.traceback else "unknown",
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count,
                }
            )

        # Record metrics
        self.metrics_collector.set_gauge(
            "memory.current_mb", memory_info["current_memory_mb"]
        )
        self.metrics_collector.set_gauge(
            "memory.peak_mb", memory_info["peak_memory_mb"]
        )

        return memory_info

    def compare_snapshots(self, index1: int = -2, index2: int = -1) -> dict[str, Any]:
        """Compare two memory snapshots."""
        if len(self.snapshots) < 2:
            return {"error": "Not enough snapshots to compare"}

        snapshot1 = self.snapshots[index1]
        snapshot2 = self.snapshots[index2]

        top_stats = snapshot2.compare_to(snapshot1, "lineno")[:10]

        comparison = {
            "timestamp": datetime.now().isoformat(),
            "differences": [],
        }

        for stat in top_stats:
            comparison["differences"].append(
                {
                    "file": stat.traceback.format()[0] if stat.traceback else "unknown",
                    "size_diff_mb": stat.size_diff / 1024 / 1024,
                    "count_diff": stat.count_diff,
                }
            )

        return comparison

    def stop_profiling(self) -> None:
        """Stop memory profiling."""
        tracemalloc.stop()


class PerformanceAnalyzer:
    """Analyze performance data and provide insights."""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.cache_manager = CacheManager()

    def analyze_response_times(self) -> dict[str, Any]:
        """Analyze API response times."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "endpoints": {},
            "recommendations": [],
        }

        # Get metrics for each endpoint
        for key in self.metrics_collector.metrics:
            if key.startswith("http.request.duration"):
                summary = self.metrics_collector.get_metrics_summary(key)

                # Extract endpoint from key
                parts = key.split(",")
                endpoint = parts[1] if len(parts) > 1 else "unknown"

                analysis["endpoints"][endpoint] = summary

                # Generate recommendations
                if summary.get("p95", 0) > 1.0:
                    analysis["recommendations"].append(
                        {
                            "endpoint": endpoint,
                            "issue": "High response time",
                            "p95": summary["p95"],
                            "suggestion": "Consider caching or query optimization",
                        }
                    )

        return analysis

    def identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify performance bottlenecks."""
        bottlenecks = []

        # Check database query times
        db_metrics = self.metrics_collector.get_metrics_summary(
            "database.query.duration"
        )
        if db_metrics.get("p95", 0) > 0.5:
            bottlenecks.append(
                {
                    "type": "database",
                    "severity": "high" if db_metrics["p95"] > 1.0 else "medium",
                    "details": "Slow database queries detected",
                    "metrics": db_metrics,
                }
            )

        # Check cache hit rate
        cache_stats = self.cache_manager.get_stats()
        hit_rate = cache_stats.get("hit_rate", 0)
        if hit_rate < 80:
            bottlenecks.append(
                {
                    "type": "cache",
                    "severity": "medium",
                    "details": f"Low cache hit rate: {hit_rate:.1f}%",
                    "suggestion": "Review caching strategy",
                }
            )

        # Check memory usage
        system_monitor = SystemMonitor()
        system_metrics = system_monitor.collect_system_metrics()

        if system_metrics["memory"]["percent"] > 80:
            bottlenecks.append(
                {
                    "type": "memory",
                    "severity": "high",
                    "details": f"High memory usage: {system_metrics['memory']['percent']:.1f}%",
                    "suggestion": "Investigate memory leaks or optimize memory usage",
                }
            )

        if system_metrics["cpu"]["percent"] > 80:
            bottlenecks.append(
                {
                    "type": "cpu",
                    "severity": "high",
                    "details": f"High CPU usage: {system_metrics['cpu']['percent']:.1f}%",
                    "suggestion": "Profile CPU-intensive operations",
                }
            )

        return bottlenecks

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "response_times": self.analyze_response_times(),
            "bottlenecks": self.identify_bottlenecks(),
            "system_resources": SystemMonitor().collect_system_metrics(),
            "cache_stats": self.cache_manager.get_stats(),
        }

        # Calculate summary metrics
        total_requests = sum(
            v
            for k, v in self.metrics_collector.counters.items()
            if k.startswith("http.requests.total")
        )

        error_requests = sum(
            v
            for k, v in self.metrics_collector.counters.items()
            if k.startswith("http.requests.errors")
        )

        report["summary"] = {
            "total_requests": total_requests,
            "error_rate": (error_requests / total_requests * 100)
            if total_requests > 0
            else 0,
            "active_requests": self.metrics_collector.counters.get(
                "http.requests.active", 0
            ),
            "bottleneck_count": len(report["bottlenecks"]),
        }

        return report


# Global instances
performance_monitor = PerformanceMonitor()
system_monitor = SystemMonitor()
memory_profiler = MemoryProfiler()
performance_analyzer = PerformanceAnalyzer()

# Export main components
__all__ = [
    "MetricsCollector",
    "PerformanceMonitor",
    "RequestMetricsMiddleware",
    "SystemMonitor",
    "MemoryProfiler",
    "PerformanceAnalyzer",
    "performance_monitor",
    "system_monitor",
    "memory_profiler",
    "performance_analyzer",
]
