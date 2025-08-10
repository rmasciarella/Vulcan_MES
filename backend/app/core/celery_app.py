"""Celery application configuration and task management."""

import logging
from typing import Any

from celery import Celery, Task
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_success,
    worker_ready,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


# Create Celery application
celery_app = Celery(
    "vulcan_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.core.tasks.scheduling",
        "app.core.tasks.optimization",
        "app.core.tasks.maintenance",
        "app.core.tasks.reporting",
    ],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Worker settings
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=False,
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_compression="gzip",
    result_backend_always_retry=True,
    # Routing
    task_routes={
        "app.core.tasks.scheduling.*": {"queue": "scheduling"},
        "app.core.tasks.optimization.*": {"queue": "optimization"},
        "app.core.tasks.maintenance.*": {"queue": "maintenance"},
        "app.core.tasks.reporting.*": {"queue": "reporting"},
    },
    # Beat schedule (periodic tasks)
    beat_schedule={
        "cache-cleanup": {
            "task": "app.core.tasks.maintenance.cleanup_expired_cache",
            "schedule": 3600.0,  # Every hour
        },
        "optimize-schedules": {
            "task": "app.core.tasks.optimization.optimize_pending_schedules",
            "schedule": 300.0,  # Every 5 minutes
        },
        "generate-daily-report": {
            "task": "app.core.tasks.reporting.generate_daily_report",
            "schedule": 86400.0,  # Every day
            "kwargs": {"report_type": "daily_summary"},
        },
        "health-check": {
            "task": "app.core.tasks.maintenance.health_check",
            "schedule": 60.0,  # Every minute
        },
    },
)


class BaseTask(Task):
    """Base task with additional functionality."""

    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60  # seconds

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """Handle task failure."""
        logger.error(
            f"Task {self.name} [{task_id}] failed: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "exception": str(exc),
            },
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """Handle task retry."""
        logger.warning(
            f"Task {self.name} [{task_id}] retrying: {exc}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "exception": str(exc),
            },
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Handle task success."""
        logger.info(
            f"Task {self.name} [{task_id}] succeeded",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
            },
        )
        super().on_success(retval, task_id, args, kwargs)


# Set default task base
celery_app.Task = BaseTask


# Signal handlers for monitoring
@task_prerun.connect
def task_prerun_handler(
    task_id: str, task: Task, args: tuple, kwargs: dict, **kw: Any
) -> None:
    """Log task start."""
    logger.info(
        f"Task {task.name} [{task_id}] starting",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "args": args,
            "kwargs": kwargs,
        },
    )


@task_postrun.connect
def task_postrun_handler(
    task_id: str,
    task: Task,
    args: tuple,
    kwargs: dict,
    retval: Any,
    state: str,
    **kw: Any,
) -> None:
    """Log task completion."""
    logger.info(
        f"Task {task.name} [{task_id}] completed with state: {state}",
        extra={
            "task_id": task_id,
            "task_name": task.name,
            "state": state,
        },
    )


@task_failure.connect
def task_failure_handler(
    task_id: str,
    exception: Exception,
    args: tuple,
    kwargs: dict,
    traceback: Any,
    einfo: Any,
    **kw: Any,
) -> None:
    """Log task failure details."""
    logger.error(
        f"Task [{task_id}] failed with exception: {exception}",
        extra={
            "task_id": task_id,
            "exception": str(exception),
            "traceback": str(traceback),
        },
    )


@task_success.connect
def task_success_handler(sender: Task, result: Any, **kw: Any) -> None:
    """Log task success metrics."""
    logger.info(
        f"Task {sender.name} completed successfully",
        extra={
            "task_name": sender.name,
            "result_size": len(str(result)) if result else 0,
        },
    )


@worker_ready.connect
def worker_ready_handler(sender: Any, **kw: Any) -> None:
    """Log when worker is ready."""
    logger.info("Celery worker is ready to accept tasks")


# Task status utilities
class TaskStatus:
    """Task status constants and utilities."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"

    @staticmethod
    def is_terminal(status: str) -> bool:
        """Check if status is terminal (task won't change)."""
        return status in {TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED}

    @staticmethod
    def is_active(status: str) -> bool:
        """Check if task is actively running."""
        return status in {TaskStatus.STARTED, TaskStatus.RETRY}


def get_task_info(task_id: str) -> dict[str, Any]:
    """Get information about a task."""
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.successful() else None,
        "error": str(result.info) if result.failed() else None,
        "traceback": result.traceback,
        "ready": result.ready(),
        "successful": result.successful(),
        "failed": result.failed(),
    }


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """Revoke a task."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} revoked (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False


def get_active_tasks() -> dict[str, list[dict]]:
    """Get all active tasks across workers."""
    inspect = celery_app.control.inspect()

    return {
        "active": inspect.active() or {},
        "scheduled": inspect.scheduled() or {},
        "reserved": inspect.reserved() or {},
    }


def get_worker_stats() -> dict[str, Any]:
    """Get worker statistics."""
    inspect = celery_app.control.inspect()

    stats = inspect.stats()
    if not stats:
        return {}

    # Aggregate stats from all workers
    total_stats = {
        "total_workers": len(stats),
        "total_tasks_processed": 0,
        "workers": {},
    }

    for worker_name, worker_stats in stats.items():
        total_stats["workers"][worker_name] = {
            "pool_size": worker_stats.get("pool", {}).get("max-concurrency"),
            "total_tasks": worker_stats.get("total", {}),
        }

        # Sum total tasks
        for task_count in worker_stats.get("total", {}).values():
            total_stats["total_tasks_processed"] += task_count

    return total_stats


# Priority levels for tasks
class TaskPriority:
    """Task priority levels."""

    LOW = 0
    NORMAL = 5
    HIGH = 7
    CRITICAL = 9

    @staticmethod
    def get_queue(priority: int) -> str:
        """Get queue name based on priority."""
        if priority >= TaskPriority.CRITICAL:
            return "critical"
        elif priority >= TaskPriority.HIGH:
            return "high"
        elif priority >= TaskPriority.NORMAL:
            return "normal"
        else:
            return "low"


# Export main components
__all__ = [
    "celery_app",
    "BaseTask",
    "TaskStatus",
    "TaskPriority",
    "get_task_info",
    "revoke_task",
    "get_active_tasks",
    "get_worker_stats",
]
