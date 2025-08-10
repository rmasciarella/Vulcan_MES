"""
Health Check System

Comprehensive health checks for all system components including database,
external services, and application health with detailed status reporting.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import psutil
from sqlalchemy import text

from .config import settings
from .db import async_session
from .observability import get_logger

logger = get_logger("health")


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class HealthCheckResult:
    """Result of a health check."""

    def __init__(
        self,
        name: str,
        status: str = HealthStatus.UNKNOWN,
        message: str = "",
        details: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
        timestamp: datetime | None = None,
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.duration_ms = duration_ms
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Centralized health checking system."""

    def __init__(self):
        self.checks: dict[str, callable] = {}
        self.last_results: dict[str, HealthCheckResult] = {}

    def register_check(self, name: str, check_func: callable) -> None:
        """Register a health check function."""
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")

    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not found",
            )

        start_time = time.time()

        try:
            check_func = self.checks[name]
            result = await check_func()

            duration_ms = (time.time() - start_time) * 1000

            if isinstance(result, HealthCheckResult):
                result.duration_ms = duration_ms
                self.last_results[name] = result
                return result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                result = HealthCheckResult(
                    name=name, status=status, duration_ms=duration_ms
                )
                self.last_results[name] = result
                return result
            else:
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message="Invalid check result type",
                    duration_ms=duration_ms,
                )
                self.last_results[name] = result
                return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check failed: {name}", error=str(e), exc_info=True)

            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration_ms,
            )
            self.last_results[name] = result
            return result

    async def run_all_checks(self) -> dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}

        # Run checks concurrently
        tasks = [self.run_check(name) for name in self.checks.keys()]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)

        for _i, (name, result) in enumerate(
            zip(self.checks.keys(), check_results, strict=False)
        ):
            if isinstance(result, Exception):
                results[name] = HealthCheckResult(
                    name=name, status=HealthStatus.UNHEALTHY, message=str(result)
                )
            else:
                results[name] = result

        return results

    def get_overall_status(self, results: dict[str, HealthCheckResult]) -> str:
        """Determine overall system health status."""
        if not results:
            return HealthStatus.UNKNOWN

        statuses = [result.status for result in results.values()]

        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED


# Global health checker instance
health_checker = HealthChecker()


async def check_database_health() -> HealthCheckResult:
    """Check database connectivity and performance with SLI-based thresholds."""
    try:
        async with async_session() as session:
            start_time = time.time()

            # Basic connectivity test
            result = await session.execute(text("SELECT 1"))
            basic_query_time = (time.time() - start_time) * 1000

            # Check if result is correct
            if result.scalar() != 1:
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database query returned unexpected result",
                )

            # Advanced checks for SLI monitoring
            start_time = time.time()

            # Check database version and uptime
            version_result = await session.execute(text("SELECT version()"))
            version = version_result.scalar()

            uptime_result = await session.execute(
                text("""
                SELECT EXTRACT(EPOCH FROM (now() - pg_postmaster_start_time())) as uptime_seconds
            """)
            )
            uptime_seconds = uptime_result.scalar()

            # Check connection statistics for capacity planning
            conn_stats_result = await session.execute(
                text("""
                SELECT
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) as total_connections,
                    max_conn.setting::int as max_connections,
                    round((count(*) * 100.0 / max_conn.setting::int), 2) as connection_utilization_percent
                FROM pg_stat_activity,
                     (SELECT setting FROM pg_settings WHERE name = 'max_connections') max_conn
                GROUP BY max_conn.setting
            """)
            )
            conn_stats = conn_stats_result.fetchone()

            # Check database performance metrics
            perf_stats_result = await session.execute(
                text("""
                SELECT
                    pg_database_size(current_database()) as db_size_bytes,
                    tup_fetched + tup_returned as total_reads,
                    tup_inserted + tup_updated + tup_deleted as total_writes,
                    deadlocks,
                    temp_files,
                    temp_bytes
                FROM pg_stat_database
                WHERE datname = current_database()
            """)
            )
            perf_stats = perf_stats_result.fetchone()

            # Check for long-running queries (potential blocking)
            long_queries_result = await session.execute(
                text("""
                SELECT count(*) as long_running_queries
                FROM pg_stat_activity
                WHERE state = 'active'
                AND now() - query_start > interval '30 seconds'
                AND query NOT LIKE '%pg_stat_activity%'
            """)
            )
            long_queries_count = long_queries_result.scalar()

            advanced_query_time = (time.time() - start_time) * 1000
            total_time = basic_query_time + advanced_query_time

            # SLI-based health determination
            warnings = []
            if total_time > settings.SLA_DATABASE_QUERY_TIMEOUT * 1000:
                warnings.append(f"Query latency high: {total_time:.2f}ms")

            if conn_stats.connection_utilization_percent > 80:
                warnings.append(
                    f"Connection utilization high: {conn_stats.connection_utilization_percent}%"
                )

            if long_queries_count > 0:
                warnings.append(f"Long-running queries detected: {long_queries_count}")

            # Determine status based on SLI violations
            if (
                total_time > settings.SLA_DATABASE_QUERY_TIMEOUT * 2000
                or conn_stats.connection_utilization_percent > 95
            ):
                status = HealthStatus.UNHEALTHY
                message = (
                    f"Database performance critically degraded: {'; '.join(warnings)}"
                )
            elif warnings:
                status = HealthStatus.DEGRADED
                message = f"Database performance issues detected: {'; '.join(warnings)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Database is healthy"

            return HealthCheckResult(
                name="database",
                status=status,
                message=message,
                details={
                    "database_version": version.split(" ")[1] if version else "unknown",
                    "uptime_hours": round(uptime_seconds / 3600, 1)
                    if uptime_seconds
                    else 0,
                    "active_connections": conn_stats.active_connections,
                    "total_connections": conn_stats.total_connections,
                    "max_connections": conn_stats.max_connections,
                    "connection_utilization_percent": conn_stats.connection_utilization_percent,
                    "database_size_mb": round(
                        perf_stats.db_size_bytes / 1024 / 1024, 1
                    ),
                    "long_running_queries": long_queries_count,
                    "query_latency_ms": round(total_time, 2),
                    "sli_latency_threshold_ms": settings.SLA_DATABASE_QUERY_TIMEOUT
                    * 1000,
                    "sli_connection_threshold_percent": 80,
                    "basic_query_time_ms": round(basic_query_time, 2),
                    "advanced_query_time_ms": round(advanced_query_time, 2),
                },
            )

    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database check failed: {str(e)}",
        )


async def check_solver_health() -> HealthCheckResult:
    """Check OR-Tools solver availability and performance against SLI thresholds."""
    try:
        # Test OR-Tools import
        try:
            from ortools.sat.python import cp_model
        except ImportError as e:
            return HealthCheckResult(
                name="solver",
                status=HealthStatus.UNHEALTHY,
                message=f"OR-Tools not available: {str(e)}",
            )

        start_time = time.time()

        # Create a realistic test model that mimics scheduling constraints
        model = cp_model.CpModel()

        # Simple job-shop scheduling test with 3 jobs, 2 machines
        num_jobs = 3
        num_machines = 2
        processing_times = [[3, 2], [2, 1], [4, 3]]  # job x machine

        # Variables: start times for each job on each machine
        start_vars = []
        end_vars = []
        interval_vars = []

        for job in range(num_jobs):
            start_vars.append([])
            end_vars.append([])
            interval_vars.append([])
            for machine in range(num_machines):
                start_var = model.NewIntVar(0, 50, f"start_{job}_{machine}")
                duration = processing_times[job][machine]
                end_var = model.NewIntVar(0, 60, f"end_{job}_{machine}")
                interval_var = model.NewIntervalVar(
                    start_var, duration, end_var, f"interval_{job}_{machine}"
                )

                start_vars[job].append(start_var)
                end_vars[job].append(end_var)
                interval_vars[job].append(interval_var)

        # Constraints: No overlap on machines
        for machine in range(num_machines):
            machine_intervals = [interval_vars[job][machine] for job in range(num_jobs)]
            model.AddNoOverlap(machine_intervals)

        # Objective: minimize makespan
        makespan = model.NewIntVar(0, 60, "makespan")
        for job in range(num_jobs):
            for machine in range(num_machines):
                model.Add(makespan >= end_vars[job][machine])
        model.Minimize(makespan)

        # Solve with realistic timeout for health check
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10  # Reasonable timeout
        status = solver.Solve(model)

        solve_time = (time.time() - start_time) * 1000

        # SLI-based evaluation
        warnings = []

        # Check solve time against SLI threshold
        expected_max_time_ms = 5000  # Health check should complete within 5s
        if solve_time > expected_max_time_ms:
            warnings.append(
                f"Solver performance degraded: {solve_time:.0f}ms > {expected_max_time_ms}ms"
            )

        # Check solver status
        if status == cp_model.OPTIMAL:
            solver_health = "optimal"
        elif status == cp_model.FEASIBLE:
            solver_health = "feasible"
            warnings.append(
                "Solver found feasible solution but not optimal (may indicate performance issues)"
            )
        elif status == cp_model.INFEASIBLE:
            return HealthCheckResult(
                name="solver",
                status=HealthStatus.UNHEALTHY,
                message="Solver reported test problem as infeasible (critical issue)",
            )
        else:
            return HealthCheckResult(
                name="solver",
                status=HealthStatus.UNHEALTHY,
                message=f"Solver failed with status: {solver.StatusName(status)}",
            )

        # Additional performance metrics
        num_branches = solver.NumBranches() if hasattr(solver, "NumBranches") else 0
        num_conflicts = solver.NumConflicts() if hasattr(solver, "NumConflicts") else 0

        # Memory usage check (if solver used excessive branching)
        if num_branches > 1000:
            warnings.append(
                f"High branching detected: {num_branches} (may indicate scaling issues)"
            )

        # Determine overall status
        if solve_time > expected_max_time_ms * 2:
            status_result = HealthStatus.UNHEALTHY
            message = f"Solver critically slow: {solve_time:.0f}ms"
        elif warnings:
            status_result = HealthStatus.DEGRADED
            message = f"Solver performance issues: {'; '.join(warnings)}"
        else:
            status_result = HealthStatus.HEALTHY
            message = "OR-Tools solver is performing optimally"

        return HealthCheckResult(
            name="solver",
            status=status_result,
            message=message,
            details={
                "solver_status": solver.StatusName(status),
                "solve_time_ms": round(solve_time, 2),
                "sli_threshold_ms": expected_max_time_ms,
                "objective_value": solver.ObjectiveValue()
                if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
                else None,
                "num_variables": len(model.Proto().variables),
                "num_constraints": len(model.Proto().constraints),
                "num_branches": num_branches,
                "num_conflicts": num_conflicts,
                "solver_health": solver_health,
                "test_problem_complexity": "3_jobs_2_machines_job_shop",
                "performance_warnings": warnings,
            },
        )

    except Exception as e:
        return HealthCheckResult(
            name="solver",
            status=HealthStatus.UNHEALTHY,
            message=f"Solver health check failed: {str(e)}",
        )


async def check_system_resources() -> HealthCheckResult:
    """Check system resource usage (CPU, memory, disk)."""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Check thresholds
        warnings = []
        if cpu_percent > 80:
            warnings.append(f"High CPU usage: {cpu_percent}%")

        if memory.percent > 85:
            warnings.append(f"High memory usage: {memory.percent}%")

        if disk.percent > 90:
            warnings.append(f"High disk usage: {disk.percent}%")

        # Determine status
        if warnings:
            if cpu_percent > 95 or memory.percent > 95 or disk.percent > 98:
                status = HealthStatus.UNHEALTHY
            else:
                status = HealthStatus.DEGRADED
            message = "; ".join(warnings)
        else:
            status = HealthStatus.HEALTHY
            message = "System resources are healthy"

        return HealthCheckResult(
            name="system_resources",
            status=status,
            message=message,
            details={
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
            },
        )

    except Exception as e:
        return HealthCheckResult(
            name="system_resources",
            status=HealthStatus.UNHEALTHY,
            message=f"System resource check failed: {str(e)}",
        )


async def check_application_health() -> HealthCheckResult:
    """Check application-specific health indicators."""
    try:
        details = {
            "environment": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL,
            "metrics_enabled": settings.ENABLE_METRICS,
            "tracing_enabled": settings.ENABLE_TRACING,
            "uptime_seconds": time.time() - psutil.Process().create_time(),
        }

        # Check configuration
        warnings = []
        if settings.SECRET_KEY == "changethis":
            warnings.append("Default secret key in use")

        if settings.POSTGRES_PASSWORD == "changethis":
            warnings.append("Default database password in use")

        # Check environment-specific issues
        if settings.ENVIRONMENT == "production":
            if not settings.SENTRY_DSN:
                warnings.append("Sentry not configured for production")

            if settings.LOG_LEVEL == "DEBUG":
                warnings.append("Debug logging enabled in production")

        # Determine status
        if warnings:
            status = HealthStatus.DEGRADED
            message = "; ".join(warnings)
        else:
            status = HealthStatus.HEALTHY
            message = "Application is healthy"

        details["warnings"] = warnings

        return HealthCheckResult(
            name="application", status=status, message=message, details=details
        )

    except Exception as e:
        return HealthCheckResult(
            name="application",
            status=HealthStatus.UNHEALTHY,
            message=f"Application health check failed: {str(e)}",
        )


# Register all health checks
def register_default_health_checks():
    """Register default health checks."""
    health_checker.register_check("database", check_database_health)
    health_checker.register_check("solver", check_solver_health)
    health_checker.register_check("system_resources", check_system_resources)
    health_checker.register_check("application", check_application_health)


# Startup health validation
async def validate_startup_health() -> bool:
    """Validate critical system components are healthy on startup."""
    logger.info("Validating startup health...")

    # Check critical components
    critical_checks = ["database", "solver"]

    for check_name in critical_checks:
        result = await health_checker.run_check(check_name)
        if result.status == HealthStatus.UNHEALTHY:
            logger.error(
                f"Critical startup health check failed: {check_name}",
                status=result.status,
                message=result.message,
            )
            return False

    logger.info("Startup health validation passed")
    return True
