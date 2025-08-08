"""
Observability Infrastructure

Provides comprehensive logging, metrics, tracing, and monitoring capabilities
for the scheduling system with structured logging and performance tracking.
"""

import contextlib
import contextvars
import functools
import logging
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from .config import settings

# Context variables for correlation tracking
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")

F = TypeVar("F", bound=Callable[..., Any])

# Prometheus metrics
REQUEST_COUNT = Counter(
    "vulcan_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "vulcan_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)

SCHEDULER_OPERATIONS = Counter(
    "vulcan_scheduler_operations_total",
    "Total scheduler operations",
    ["operation_type", "status"],
)

SCHEDULER_DURATION = Histogram(
    "vulcan_scheduler_operation_duration_seconds",
    "Scheduler operation duration",
    ["operation_type"],
)

SOLVER_METRICS = Histogram(
    "vulcan_solver_solve_time_seconds", "OR-Tools solver execution time", ["status"]
)

SOLVER_STATUS = Counter(
    "vulcan_solver_status_total", "OR-Tools solver status", ["status"]
)

DATABASE_OPERATIONS = Counter(
    "vulcan_database_operations_total", "Database operations", ["operation", "table"]
)

DATABASE_DURATION = Histogram(
    "vulcan_database_operation_duration_seconds",
    "Database operation duration",
    ["operation", "table"],
)

CIRCUIT_BREAKER_STATE = Gauge(
    "vulcan_circuit_breaker_state", "Circuit breaker state", ["service"]
)

ACTIVE_JOBS = Gauge("vulcan_active_jobs", "Number of active jobs")

COMPLETED_TASKS = Counter("vulcan_completed_tasks_total", "Total completed tasks")

# Enhanced error tracking metrics
SOLVER_ERRORS = Counter(
    "vulcan_solver_errors_total",
    "Total solver errors by type",
    ["error_type", "retry_attempt"],
)

OPTIMIZATION_FAILURES = Counter(
    "vulcan_optimization_failures_total",
    "Total optimization failures by reason",
    ["failure_reason", "fallback_used"],
)

FALLBACK_ACTIVATIONS = Counter(
    "vulcan_fallback_activations_total",
    "Fallback strategy activations",
    ["strategy", "reason"],
)

MEMORY_USAGE = Gauge(
    "vulcan_solver_memory_usage_mb",
    "Current solver memory usage in MB",
    ["execution_id"],
)

SOLVER_PERFORMANCE = Histogram(
    "vulcan_solver_performance_metrics",
    "Solver performance metrics",
    ["metric_type", "solver_status"],
)

RESOURCE_EXHAUSTION = Counter(
    "vulcan_resource_exhaustion_total",
    "Resource exhaustion events",
    ["resource_type", "limit_type"],
)

ERROR_RECOVERY_TIME = Histogram(
    "vulcan_error_recovery_time_seconds",
    "Time taken to recover from errors",
    ["error_type", "recovery_method"],
)


class CorrelationIdProcessor:
    """Structlog processor to add correlation ID to all log entries."""

    def __call__(
        self, logger: Any, name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        correlation_id = correlation_id_var.get("")
        user_id = user_id_var.get("")

        if correlation_id:
            event_dict["correlation_id"] = correlation_id
        if user_id:
            event_dict["user_id"] = user_id

        return event_dict


def setup_structured_logging() -> None:
    """Configure structured logging with JSON output and correlation tracking."""

    # Configure log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure processors based on environment
    processors = [
        structlog.contextvars.merge_contextvars,
        CorrelationIdProcessor(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.add_logger_name,
    ]

    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=settings.ENVIRONMENT == "local"),
            ]
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set specific loggers
    if settings.LOG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def setup_tracing() -> None:
    """Configure OpenTelemetry tracing."""
    if not settings.ENABLE_TRACING:
        return

    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider())

    # Instrument FastAPI and SQLAlchemy
    FastAPIInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()


def setup_metrics() -> None:
    """Configure Prometheus metrics collection."""
    if not settings.ENABLE_METRICS:
        return

    # Set up metrics provider
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)

    # Start Prometheus HTTP server
    start_http_server(settings.METRICS_PORT)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set correlation ID for request tracking."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_var.set(correlation_id)
    return correlation_id


def set_user_id(user_id: str) -> None:
    """Set user ID for request tracking."""
    user_id_var.set(user_id)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get("")


def log_performance_metrics(
    operation: str,
    duration_seconds: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log performance metrics for operations."""
    logger = get_logger("performance")

    metrics_data = {
        "operation": operation,
        "duration_seconds": duration_seconds,
        "correlation_id": get_correlation_id(),
    }

    if metadata:
        metrics_data.update(metadata)

    logger.info("Performance metric recorded", **metrics_data)


def log_solver_metrics(
    status: str,
    solve_time_seconds: float,
    makespan_minutes: float = 0.0,
    total_tardiness_minutes: float = 0.0,
    num_variables: int = 0,
    num_constraints: int = 0,
    objective_value: float = 0.0,
    execution_id: str | None = None,
) -> None:
    """Log comprehensive solver metrics."""
    logger = get_logger("solver_metrics")

    metrics_data = {
        "solver_status": status,
        "solve_time_seconds": solve_time_seconds,
        "makespan_minutes": makespan_minutes,
        "total_tardiness_minutes": total_tardiness_minutes,
        "num_variables": num_variables,
        "num_constraints": num_constraints,
        "objective_value": objective_value,
        "execution_id": execution_id or get_correlation_id(),
        "correlation_id": get_correlation_id(),
    }

    logger.info("Solver metrics recorded", **metrics_data)

    # Record Prometheus metrics
    SOLVER_STATUS.labels(status=status).inc()
    SOLVER_METRICS.labels(status=status).observe(solve_time_seconds)

    # Record performance metrics
    if num_variables > 0:
        SOLVER_PERFORMANCE.labels(
            metric_type="variables", solver_status=status
        ).observe(num_variables)

    if num_constraints > 0:
        SOLVER_PERFORMANCE.labels(
            metric_type="constraints", solver_status=status
        ).observe(num_constraints)


def log_optimization_failure(
    failure_reason: str,
    error_details: dict[str, Any],
    fallback_used: bool = False,
    fallback_strategy: str | None = None,
    recovery_time_seconds: float = 0.0,
) -> None:
    """Log optimization failure with detailed context."""
    logger = get_logger("optimization_failures")

    failure_data = {
        "failure_reason": failure_reason,
        "fallback_used": fallback_used,
        "fallback_strategy": fallback_strategy,
        "recovery_time_seconds": recovery_time_seconds,
        "correlation_id": get_correlation_id(),
        **error_details,
    }

    logger.error("Optimization failure recorded", **failure_data)

    # Record Prometheus metrics
    OPTIMIZATION_FAILURES.labels(
        failure_reason=failure_reason, fallback_used=str(fallback_used).lower()
    ).inc()

    if fallback_used and fallback_strategy:
        FALLBACK_ACTIVATIONS.labels(
            strategy=fallback_strategy, reason=failure_reason
        ).inc()

    if recovery_time_seconds > 0:
        ERROR_RECOVERY_TIME.labels(
            error_type=failure_reason,
            recovery_method="fallback" if fallback_used else "retry",
        ).observe(recovery_time_seconds)


def log_resource_exhaustion(
    resource_type: str,
    limit_type: str,
    current_usage: float,
    limit_value: float,
    action_taken: str,
    execution_id: str | None = None,
) -> None:
    """Log resource exhaustion events."""
    logger = get_logger("resource_exhaustion")

    exhaustion_data = {
        "resource_type": resource_type,
        "limit_type": limit_type,
        "current_usage": current_usage,
        "limit_value": limit_value,
        "usage_percentage": (current_usage / limit_value * 100)
        if limit_value > 0
        else 0,
        "action_taken": action_taken,
        "execution_id": execution_id or get_correlation_id(),
        "correlation_id": get_correlation_id(),
    }

    logger.warning("Resource exhaustion detected", **exhaustion_data)

    # Record Prometheus metrics
    RESOURCE_EXHAUSTION.labels(resource_type=resource_type, limit_type=limit_type).inc()


def log_circuit_breaker_event(
    service_name: str,
    event_type: str,  # "opened", "closed", "half_open", "call_blocked"
    failure_count: int = 0,
    success_count: int = 0,
    error_details: dict[str, Any] | None = None,
) -> None:
    """Log circuit breaker state changes and events."""
    logger = get_logger("circuit_breaker")

    event_data = {
        "service_name": service_name,
        "event_type": event_type,
        "failure_count": failure_count,
        "success_count": success_count,
        "correlation_id": get_correlation_id(),
    }

    if error_details:
        event_data.update(error_details)

    log_level = "error" if event_type == "opened" else "info"
    logger.log(log_level, f"Circuit breaker {event_type}", **event_data)


def log_fallback_execution(
    strategy: str,
    reason: str,
    execution_time_seconds: float,
    quality_score: float,
    jobs_scheduled: int,
    tasks_scheduled: int,
    warnings: list | None = None,
) -> None:
    """Log fallback strategy execution details."""
    logger = get_logger("fallback_execution")

    fallback_data = {
        "fallback_strategy": strategy,
        "fallback_reason": reason,
        "execution_time_seconds": execution_time_seconds,
        "quality_score": quality_score,
        "jobs_scheduled": jobs_scheduled,
        "tasks_scheduled": tasks_scheduled,
        "warning_count": len(warnings) if warnings else 0,
        "correlation_id": get_correlation_id(),
    }

    if warnings:
        fallback_data["warnings"] = warnings[:5]  # Log first 5 warnings

    logger.info("Fallback strategy executed", **fallback_data)

    # Record metrics
    FALLBACK_ACTIVATIONS.labels(strategy=strategy, reason=reason).inc()


def log_error_with_context(
    error: Exception,
    operation: str,
    context: dict[str, Any] | None = None,
    severity: str = "error",
    include_traceback: bool = True,
) -> None:
    """Log errors with comprehensive context and structured information."""
    logger = get_logger("error_tracking")

    error_data = {
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "severity": severity,
        "correlation_id": get_correlation_id(),
    }

    # Add error-specific details
    if hasattr(error, "details") and error.details:
        error_data["error_details"] = error.details

    # Add context information
    if context:
        error_data.update(context)

    # Log with appropriate level
    if severity == "critical":
        logger.critical(
            "Critical error occurred", **error_data, exc_info=include_traceback
        )
    elif severity == "error":
        logger.error("Error occurred", **error_data, exc_info=include_traceback)
    elif severity == "warning":
        logger.warning("Warning occurred", **error_data)
    else:
        logger.info("Issue occurred", **error_data)


def track_solver_memory_usage(execution_id: str, memory_mb: float) -> None:
    """Track solver memory usage metrics."""
    MEMORY_USAGE.labels(execution_id=execution_id).set(memory_mb)

    logger = get_logger("solver_memory")
    logger.debug(
        "Solver memory usage tracked",
        execution_id=execution_id,
        memory_mb=memory_mb,
        correlation_id=get_correlation_id(),
    )


def monitor_performance(operation_type: str, include_args: bool = False):
    """Decorator to monitor function performance with metrics and logging."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()

            # Prepare log context
            log_context = {
                "operation": operation_type,
                "function": func.__name__,
                "correlation_id": get_correlation_id(),
            }

            if include_args:
                log_context.update(
                    {
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    }
                )

            logger.info("Operation started", **log_context)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Record metrics
                SCHEDULER_OPERATIONS.labels(
                    operation_type=operation_type, status="success"
                ).inc()
                SCHEDULER_DURATION.labels(operation_type=operation_type).observe(
                    duration
                )

                # Log success
                logger.info(
                    "Operation completed successfully",
                    **log_context,
                    duration_seconds=duration,
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record failure metrics
                SCHEDULER_OPERATIONS.labels(
                    operation_type=operation_type, status="error"
                ).inc()

                # Log error
                logger.error(
                    "Operation failed",
                    **log_context,
                    duration_seconds=duration,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()

            # Prepare log context
            log_context = {
                "operation": operation_type,
                "function": func.__name__,
                "correlation_id": get_correlation_id(),
            }

            if include_args:
                log_context.update(
                    {
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    }
                )

            logger.info("Operation started", **log_context)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record metrics
                SCHEDULER_OPERATIONS.labels(
                    operation_type=operation_type, status="success"
                ).inc()
                SCHEDULER_DURATION.labels(operation_type=operation_type).observe(
                    duration
                )

                # Log success
                logger.info(
                    "Operation completed successfully",
                    **log_context,
                    duration_seconds=duration,
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record failure metrics
                SCHEDULER_OPERATIONS.labels(
                    operation_type=operation_type, status="error"
                ).inc()

                # Log error
                logger.error(
                    "Operation failed",
                    **log_context,
                    duration_seconds=duration,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextlib.asynccontextmanager
async def trace_operation(
    operation_name: str,
    attributes: dict[str, str | int | float] | None = None,
):
    """Context manager for tracing operations with OpenTelemetry."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        span.set_attribute("correlation_id", get_correlation_id())

        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def log_solver_metrics(
    status: str,
    solve_time_seconds: float,
    makespan_minutes: float = 0.0,
    total_tardiness_minutes: float = 0.0,
    num_variables: int = 0,
    num_constraints: int = 0,
    objective_value: float = 0.0,
) -> None:
    """Log detailed OR-Tools solver metrics."""
    logger = get_logger("solver")

    # Record Prometheus metrics
    SOLVER_METRICS.labels(status=status).observe(solve_time_seconds)
    SOLVER_STATUS.labels(status=status).inc()

    # Log detailed metrics
    solver_data = {
        "status": status,
        "solve_time_seconds": solve_time_seconds,
        "makespan_minutes": makespan_minutes,
        "total_tardiness_minutes": total_tardiness_minutes,
        "num_variables": num_variables,
        "num_constraints": num_constraints,
        "objective_value": objective_value,
        "correlation_id": get_correlation_id(),
    }

    logger.info("Solver metrics recorded", **solver_data)


def log_database_operation(
    operation: str,
    table: str,
    duration_seconds: float,
    records_affected: int = 0,
    error: str | None = None,
) -> None:
    """Log database operation metrics."""
    logger = get_logger("database")

    # Record Prometheus metrics
    DATABASE_OPERATIONS.labels(operation=operation, table=table).inc()
    DATABASE_DURATION.labels(operation=operation, table=table).observe(duration_seconds)

    # Log operation details
    db_data = {
        "operation": operation,
        "table": table,
        "duration_seconds": duration_seconds,
        "records_affected": records_affected,
        "correlation_id": get_correlation_id(),
    }

    if error:
        db_data["error"] = error
        logger.error("Database operation failed", **db_data)
    else:
        logger.info("Database operation completed", **db_data)


def initialize_observability() -> None:
    """Initialize all observability components."""
    setup_structured_logging()
    setup_tracing()
    setup_metrics()

    logger = get_logger("observability")
    logger.info(
        "Observability system initialized",
        log_format=settings.LOG_FORMAT,
        metrics_enabled=settings.ENABLE_METRICS,
        tracing_enabled=settings.ENABLE_TRACING,
        metrics_port=settings.METRICS_PORT if settings.ENABLE_METRICS else None,
    )
