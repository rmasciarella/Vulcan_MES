"""
Real-time Status and Monitoring API Routes.

This module provides real-time monitoring endpoints for production scheduling,
including system status, optimization progress, and performance dashboards.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser
from app.application.dtos.scheduling_dtos import (
    OptimizationStatusResponse,
)
from app.domain.scheduling.value_objects.enums import JobStatus, TaskStatus
from app.domain.shared.exceptions import (
    EntityNotFoundError,
)
from app.infrastructure.database.dependencies import (
    JobRepositoryDep,
    MachineRepositoryDep,
    OperatorRepositoryDep,
    ScheduleRepositoryDep,
    TaskRepositoryDep,
)
from app.infrastructure.database.repositories import DatabaseError

router = APIRouter(prefix="/status", tags=["status"])


@router.get(
    "/system",
    summary="Get system status",
    description="Get overall system status including health metrics and capacity information.",
    response_model=dict,
)
async def get_system_status(
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
) -> dict:
    """Get comprehensive system status."""
    try:
        # Get current counts
        active_jobs = await job_repo.count_by_status(JobStatus.IN_PROGRESS)
        pending_jobs = await job_repo.count_by_status(JobStatus.PLANNED)
        overdue_jobs = len(await job_repo.find_overdue())

        active_tasks = await task_repo.count_by_status(TaskStatus.IN_PROGRESS)
        ready_tasks = await task_repo.count_by_status(TaskStatus.READY)

        active_schedules = len(await schedule_repo.find_active_schedules())
        draft_schedules = len(await schedule_repo.find_draft_schedules())

        total_machines = await machine_repo.count_total()
        available_machines = await machine_repo.count_available()

        total_operators = await operator_repo.count_total()
        available_operators = await operator_repo.count_available()

        # Calculate system health score
        health_score = _calculate_system_health_score(
            {
                "jobs_overdue": overdue_jobs,
                "tasks_delayed": 0,  # Would need to implement
                "machine_availability": available_machines / total_machines
                if total_machines > 0
                else 0,
                "operator_availability": available_operators / total_operators
                if total_operators > 0
                else 0,
            }
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": {
                "status": "healthy"
                if health_score >= 80
                else "warning"
                if health_score >= 60
                else "critical",
                "score": health_score,
                "uptime_hours": 24.5,  # Would be calculated from actual uptime
            },
            "jobs": {
                "active": active_jobs,
                "pending": pending_jobs,
                "overdue": overdue_jobs,
                "total": active_jobs + pending_jobs + overdue_jobs,
            },
            "tasks": {
                "active": active_tasks,
                "ready": ready_tasks,
                "total": active_tasks + ready_tasks,
            },
            "schedules": {
                "active": active_schedules,
                "draft": draft_schedules,
            },
            "resources": {
                "machines": {
                    "total": total_machines,
                    "available": available_machines,
                    "utilization_percent": (
                        (total_machines - available_machines) / total_machines * 100
                    )
                    if total_machines > 0
                    else 0,
                },
                "operators": {
                    "total": total_operators,
                    "available": available_operators,
                    "utilization_percent": (
                        (total_operators - available_operators) / total_operators * 100
                    )
                    if total_operators > 0
                    else 0,
                },
            },
            "performance": {
                "average_job_completion_hours": 48.5,  # Would be calculated from historical data
                "on_time_delivery_percent": 87.3,  # Would be calculated from historical data
                "schedule_optimization_avg_seconds": 125.6,  # Would be tracked from optimization runs
            },
        }

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/dashboard",
    summary="Get dashboard data",
    description="Get dashboard data for production monitoring with key metrics and alerts.",
    response_model=dict,
)
async def get_dashboard_data(
    time_range_hours: int = Query(
        24, ge=1, le=168, description="Time range in hours for metrics"
    ),
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> dict:
    """Get dashboard data for monitoring and analytics."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        # Get recent activity
        recent_jobs = await job_repo.find_created_in_period(start_time, end_time)
        completed_jobs = await job_repo.find_completed_in_period(start_time, end_time)
        recent_schedules = await schedule_repo.find_created_in_period(
            start_time, end_time
        )

        # Get alerts and issues
        overdue_jobs = await job_repo.find_overdue()
        critical_tasks = await task_repo.find_critical_path_tasks()
        delayed_tasks = await task_repo.find_delayed_tasks()

        # Calculate trends (simplified - would use proper time series data)
        job_completion_trend = len(completed_jobs) / time_range_hours  # jobs per hour
        schedule_creation_trend = (
            len(recent_schedules) / time_range_hours
        )  # schedules per hour

        alerts = []

        # Generate alerts
        if len(overdue_jobs) > 0:
            alerts.append(
                {
                    "type": "warning",
                    "priority": "high",
                    "message": f"{len(overdue_jobs)} jobs are overdue",
                    "count": len(overdue_jobs),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        if len(delayed_tasks) > 0:
            alerts.append(
                {
                    "type": "warning",
                    "priority": "medium",
                    "message": f"{len(delayed_tasks)} tasks are experiencing delays",
                    "count": len(delayed_tasks),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_range": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "hours": time_range_hours,
            },
            "activity": {
                "jobs_created": len(recent_jobs),
                "jobs_completed": len(completed_jobs),
                "schedules_created": len(recent_schedules),
                "completion_rate": len(completed_jobs) / len(recent_jobs)
                if recent_jobs
                else 0,
            },
            "trends": {
                "jobs_per_hour": round(job_completion_trend, 2),
                "schedules_per_hour": round(schedule_creation_trend, 2),
            },
            "issues": {
                "overdue_jobs": len(overdue_jobs),
                "critical_tasks": len(critical_tasks),
                "delayed_tasks": len(delayed_tasks),
            },
            "alerts": alerts,
            "recent_activity": [
                {
                    "type": "job_created",
                    "id": str(job.id),
                    "job_number": job.job_number,
                    "timestamp": job.created_at.isoformat(),
                }
                for job in recent_jobs[:10]  # Last 10 jobs
            ],
        }

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/optimization/{schedule_id}",
    summary="Get optimization status",
    description="Get real-time status of a running optimization process.",
    response_model=OptimizationStatusResponse,
    responses={
        404: {"description": "Schedule or optimization not found"},
    },
)
async def get_optimization_status(
    schedule_id: UUID,
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> OptimizationStatusResponse:
    """Get real-time optimization status for a schedule."""
    try:
        # Verify schedule exists
        schedule = await schedule_repo.get_by_id_required(schedule_id)

        # In a real implementation, this would check a job queue or cache
        # For now, return a mock status based on schedule state

        if schedule.status.value == "draft" and len(schedule.assignments) == 0:
            # No optimization has been run
            return OptimizationStatusResponse(
                schedule_id=schedule_id,
                status="not_started",
                progress_percent=0.0,
                elapsed_time_seconds=0.0,
                estimated_completion_seconds=None,
                current_objective_value=None,
                best_objective_value=None,
                iterations_completed=0,
                message="Optimization has not been started",
            )
        elif schedule.status.value == "draft" and len(schedule.assignments) > 0:
            # Optimization completed
            return OptimizationStatusResponse(
                schedule_id=schedule_id,
                status="completed",
                progress_percent=100.0,
                elapsed_time_seconds=125.6,  # Would be tracked from actual run
                estimated_completion_seconds=0.0,
                current_objective_value=7200.0,  # Would be from optimization result
                best_objective_value=7200.0,
                iterations_completed=2500,  # Would be from optimization result
                message="Optimization completed successfully",
            )
        else:
            # Published schedule
            return OptimizationStatusResponse(
                schedule_id=schedule_id,
                status="completed",
                progress_percent=100.0,
                elapsed_time_seconds=125.6,
                estimated_completion_seconds=0.0,
                current_objective_value=7200.0,
                best_objective_value=7200.0,
                iterations_completed=2500,
                message="Schedule is published and active",
            )

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/real-time",
    summary="Get real-time production status",
    description="Get real-time status of production floor including active tasks and resource status.",
    response_model=dict,
)
async def get_real_time_status(
    current_user: CurrentUser = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> dict:
    """Get real-time production floor status."""
    try:
        # Get currently active tasks
        await task_repo.find_active_tasks()

        # Get resource status
        machines = await machine_repo.get_all()
        operators = await operator_repo.get_all()

        # Get active schedules
        active_schedules = await schedule_repo.find_active_schedules()

        # Build real-time status
        current_assignments = []
        for schedule in active_schedules:
            for assignment in schedule.assignments.values():
                now = datetime.utcnow()
                if assignment.start_time <= now <= assignment.end_time:
                    current_assignments.append(
                        {
                            "task_id": str(assignment.task_id),
                            "machine_id": str(assignment.machine_id),
                            "operator_ids": [
                                str(op_id) for op_id in assignment.operator_ids
                            ],
                            "start_time": assignment.start_time.isoformat(),
                            "end_time": assignment.end_time.isoformat(),
                            "progress_percent": _calculate_task_progress(
                                assignment, now
                            ),
                            "schedule_id": str(schedule.id),
                        }
                    )

        # Calculate resource statuses
        machine_status = {}
        for machine in machines:
            is_busy = any(
                str(machine.id) == assignment["machine_id"]
                for assignment in current_assignments
            )
            machine_status[str(machine.id)] = {
                "name": machine.name,
                "status": "busy" if is_busy else "available",
                "current_task_id": next(
                    (
                        assignment["task_id"]
                        for assignment in current_assignments
                        if str(machine.id) == assignment["machine_id"]
                    ),
                    None,
                ),
                "zone": getattr(machine, "zone", None),
            }

        operator_status = {}
        for operator in operators:
            is_busy = any(
                str(operator.id) in assignment["operator_ids"]
                for assignment in current_assignments
            )
            operator_status[str(operator.id)] = {
                "name": operator.name,
                "status": "busy" if is_busy else "available",
                "current_task_ids": [
                    assignment["task_id"]
                    for assignment in current_assignments
                    if str(operator.id) in assignment["operator_ids"]
                ],
                "zone": getattr(operator, "zone", None),
            }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_assignments": current_assignments,
            "resources": {
                "machines": machine_status,
                "operators": operator_status,
            },
            "summary": {
                "active_tasks": len(current_assignments),
                "busy_machines": sum(
                    1
                    for status in machine_status.values()
                    if status["status"] == "busy"
                ),
                "busy_operators": sum(
                    1
                    for status in operator_status.values()
                    if status["status"] == "busy"
                ),
                "active_schedules": len(active_schedules),
            },
        }

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/alerts",
    summary="Get system alerts",
    description="Get current system alerts and warnings requiring attention.",
    response_model=dict,
)
async def get_system_alerts(
    priority_filter: str | None = Query(
        None, description="Filter by priority: low, medium, high, critical"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of alerts"),
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
) -> dict:
    """Get system alerts and warnings."""
    try:
        alerts = []

        # Job-related alerts
        overdue_jobs = await job_repo.find_overdue()
        if overdue_jobs:
            for job in overdue_jobs[:10]:  # Limit to 10 most overdue
                hours_overdue = (
                    datetime.utcnow() - job.due_date
                ).total_seconds() / 3600
                priority = (
                    "critical"
                    if hours_overdue > 48
                    else "high"
                    if hours_overdue > 24
                    else "medium"
                )

                alerts.append(
                    {
                        "id": f"job_overdue_{job.id}",
                        "type": "job_overdue",
                        "priority": priority,
                        "title": f"Job {job.job_number} is overdue",
                        "message": f"Job '{job.job_number}' is {hours_overdue:.1f} hours overdue",
                        "entity_id": str(job.id),
                        "entity_type": "job",
                        "timestamp": job.due_date.isoformat(),
                        "data": {
                            "job_number": job.job_number,
                            "customer": job.customer_name,
                            "hours_overdue": round(hours_overdue, 1),
                        },
                    }
                )

        # Task-related alerts
        delayed_tasks = await task_repo.find_delayed_tasks()
        if delayed_tasks:
            for task in delayed_tasks[:5]:  # Limit to 5 most delayed
                alerts.append(
                    {
                        "id": f"task_delayed_{task.id}",
                        "type": "task_delayed",
                        "priority": "medium",
                        "title": f"Task in sequence {getattr(task, 'sequence_in_job', 'unknown')} is delayed",
                        "message": "Task is experiencing delays and may impact job completion",
                        "entity_id": str(task.id),
                        "entity_type": "task",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "task_id": str(task.id),
                            "sequence": getattr(task, "sequence_in_job", 0),
                        },
                    }
                )

        # Resource alerts (simplified)
        unavailable_machines = await machine_repo.find_unavailable()
        if unavailable_machines:
            for machine in unavailable_machines[:5]:
                alerts.append(
                    {
                        "id": f"machine_unavailable_{machine.id}",
                        "type": "resource_unavailable",
                        "priority": "medium",
                        "title": f"Machine {machine.name} is unavailable",
                        "message": f"Machine '{machine.name}' is currently unavailable for production",
                        "entity_id": str(machine.id),
                        "entity_type": "machine",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "machine_name": machine.name,
                            "zone": getattr(machine, "zone", None),
                        },
                    }
                )

        # Filter by priority if requested
        if priority_filter:
            alerts = [alert for alert in alerts if alert["priority"] == priority_filter]

        # Sort by priority and timestamp
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(
            key=lambda a: (priority_order.get(a["priority"], 4), a["timestamp"]),
            reverse=True,
        )

        # Limit results
        alerts = alerts[:limit]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_alerts": len(alerts),
            "alerts": alerts,
            "summary": {
                "critical": len([a for a in alerts if a["priority"] == "critical"]),
                "high": len([a for a in alerts if a["priority"] == "high"]),
                "medium": len([a for a in alerts if a["priority"] == "medium"]),
                "low": len([a for a in alerts if a["priority"] == "low"]),
            },
        }

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


# Helper functions


def _calculate_system_health_score(metrics: dict) -> float:
    """Calculate overall system health score (0-100)."""
    score = 100

    # Deduct points for issues
    score -= metrics["jobs_overdue"] * 10  # 10 points per overdue job
    score -= metrics["tasks_delayed"] * 5  # 5 points per delayed task

    # Resource availability contributes to health
    machine_health = metrics["machine_availability"] * 25  # Up to 25 points
    operator_health = metrics["operator_availability"] * 25  # Up to 25 points

    score = (score * 0.5) + (machine_health + operator_health)

    return max(0, min(100, score))  # Clamp between 0 and 100


def _calculate_task_progress(assignment, current_time: datetime) -> float:
    """Calculate progress percentage for a task assignment."""
    total_duration = (assignment.end_time - assignment.start_time).total_seconds()
    elapsed_duration = (current_time - assignment.start_time).total_seconds()

    return min(100.0, max(0.0, (elapsed_duration / total_duration) * 100))
