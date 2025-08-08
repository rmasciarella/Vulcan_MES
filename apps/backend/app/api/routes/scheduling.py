"""
Scheduling API routes.

This module provides API endpoints for scheduling operations,
demonstrating the usage of the repository pattern for data access.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.domain.scheduling.value_objects.enums import JobStatus
from app.infrastructure.database.dependencies import (
    JobRepositoryDep,
    RepositoryContainerDep,
    ResourceRepositoryDep,
    TaskRepositoryDep,
)
from app.infrastructure.database.models import (
    JobPublic,
    TaskPublic,
)
from app.infrastructure.database.repositories import (
    DatabaseError,
    EntityNotFoundError,
)

# Import the solve endpoints
from .solve import router as solve_router

router = APIRouter()

# Include the solve endpoints
router.include_router(solve_router, tags=["solve"])


@router.get("/data", summary="Get scheduling data summary")
async def get_scheduling_data(repos: RepositoryContainerDep) -> JSONResponse:
    """
    Get summary of available data for scheduling analysis.

    This endpoint provides an overview of jobs, tasks, and resources
    available in the system for scheduling operations.

    Returns:
        JSONResponse: Summary of available data for scheduling
    """
    try:
        # Get active jobs that need scheduling
        active_jobs = repos.jobs.find_active_jobs()
        ready_tasks = repos.tasks.find_ready_tasks()

        # Get available resources
        available_machines = repos.machines.find_available()
        available_operators = repos.operators.find_available()

        # Get resource summary for capacity planning
        resource_summary = repos.resources.get_resource_summary()

        # Create scheduling summary
        scheduling_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "jobs": {
                "active_count": len(active_jobs),
                "job_numbers": [job.job_number for job in active_jobs[:10]],  # First 10
                "overdue_count": len(repos.jobs.find_overdue()),
            },
            "tasks": {
                "ready_count": len(ready_tasks),
                "scheduled_count": len(repos.tasks.find_scheduled_tasks()),
                "active_count": len(repos.tasks.find_active_tasks()),
            },
            "resources": {
                "available_machines": len(available_machines),
                "available_operators": len(available_operators),
                "resource_summary": resource_summary,
            },
            "constraints": {
                "critical_path_tasks": len(repos.tasks.find_critical_path_tasks()),
                "delayed_tasks": len(repos.tasks.find_delayed_tasks()),
            },
        }

        return JSONResponse(
            status_code=200,
            content={
                "message": "Scheduling data retrieved successfully",
                "data": scheduling_data,
            },
        )

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/jobs", summary="Get all jobs")
async def get_jobs(
    job_repo: JobRepositoryDep,
    status: JobStatus | None = Query(None, description="Filter by job status"),
    limit: int = Query(100, description="Maximum number of jobs to return"),
    offset: int = Query(0, description="Number of jobs to skip"),
) -> list[JobPublic]:
    """
    Get jobs with optional status filtering and pagination.

    Args:
        job_repo: Job repository from dependency injection
        status: Optional job status filter
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip

    Returns:
        List of jobs
    """
    try:
        if status:
            jobs = job_repo.find_by_status(status)
            # Apply pagination manually since find_by_status doesn't support it
            return jobs[offset : offset + limit]
        else:
            return job_repo.get_all(limit=limit, offset=offset)

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")


@router.get("/jobs/{job_number}", summary="Get job by number")
async def get_job_by_number(job_number: str, job_repo: JobRepositoryDep) -> JobPublic:
    """
    Get job by job number.

    Args:
        job_number: Unique job number
        job_repo: Job repository from dependency injection

    Returns:
        Job details
    """
    try:
        job = job_repo.find_by_job_number_required(job_number)
        return job

    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {e.message}")
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")


@router.get("/jobs/{job_id}/tasks", summary="Get tasks for job")
async def get_job_tasks(job_id: UUID, task_repo: TaskRepositoryDep) -> list[TaskPublic]:
    """
    Get all tasks for a specific job.

    Args:
        job_id: UUID of the job
        task_repo: Task repository from dependency injection

    Returns:
        List of tasks for the job
    """
    try:
        tasks = task_repo.find_by_job_id(job_id)
        return tasks

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")


@router.get("/tasks/ready", summary="Get ready tasks")
async def get_ready_tasks(
    task_repo: TaskRepositoryDep,
    limit: int = Query(50, description="Maximum number of tasks to return"),
) -> list[TaskPublic]:
    """
    Get tasks that are ready to be scheduled.

    Args:
        task_repo: Task repository from dependency injection
        limit: Maximum number of tasks to return

    Returns:
        List of ready tasks
    """
    try:
        tasks = task_repo.find_ready_tasks()
        return tasks[:limit]

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")


@router.get("/resources/available", summary="Get available resources")
async def get_available_resources(
    resource_repo: ResourceRepositoryDep,
    resource_type: str = Query(
        "all", description="Resource type: 'machine', 'operator', or 'all'"
    ),
    zone: str | None = Query(None, description="Filter by production zone"),
) -> dict:
    """
    Get available resources for scheduling.

    Args:
        resource_repo: Resource repository from dependency injection
        resource_type: Type of resources to find
        zone: Optional zone filter

    Returns:
        Dictionary with available resources
    """
    try:
        resources = resource_repo.find_available_resources(
            resource_type=resource_type, zone=zone
        )

        # Add counts for summary
        summary = {}
        if "machines" in resources:
            summary["machine_count"] = len(resources["machines"])
        if "operators" in resources:
            summary["operator_count"] = len(resources["operators"])

        return {"resources": resources, "summary": summary}

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")


@router.get("/statistics", summary="Get scheduling statistics")
async def get_scheduling_statistics(repos: RepositoryContainerDep) -> dict:
    """
    Get comprehensive statistics about the scheduling system.

    Args:
        repos: Repository container from dependency injection

    Returns:
        Dictionary with scheduling statistics
    """
    try:
        job_stats = repos.jobs.get_job_statistics()
        task_stats = repos.tasks.get_task_statistics()
        resource_summary = repos.resources.get_resource_summary()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "jobs": job_stats,
            "tasks": task_stats,
            "resources": resource_summary,
        }

    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
