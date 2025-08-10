"""Celery background tasks."""

from app.core.tasks.maintenance import *
from app.core.tasks.optimization import *
from app.core.tasks.reporting import *
from app.core.tasks.scheduling import *

__all__ = [
    # Scheduling tasks
    "schedule_job",
    "reschedule_job",
    "validate_schedule",
    # Optimization tasks
    "optimize_schedule",
    "optimize_pending_schedules",
    "optimize_resource_allocation",
    # Maintenance tasks
    "cleanup_expired_cache",
    "cleanup_old_schedules",
    "health_check",
    # Reporting tasks
    "generate_daily_report",
    "generate_performance_report",
    "export_schedule",
]
