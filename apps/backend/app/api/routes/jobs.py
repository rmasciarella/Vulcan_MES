"""
Jobs Management API Routes.

This module provides comprehensive job management endpoints for production scheduling,
including CRUD operations, status management, and task coordination.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.application.dtos.job_dtos import (
    CreateJobRequest,
    JobResponse,
    JobStatisticsResponse,
    JobSummaryResponse,
    UpdateJobRequest,
)
from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.value_objects.enums import JobStatus, PriorityLevel
from app.domain.shared.exceptions import (
    BusinessRuleViolation,
    EntityNotFoundError,
    ValidationError,
)
from app.infrastructure.database.dependencies import (
    JobRepositoryDep,
    TaskRepositoryDep,
)
from app.infrastructure.database.repositories import DatabaseError
from app.infrastructure.database.service_dependencies import JobServiceDep

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/",
    summary="Create new job",
    description="Create a new production job with tasks and scheduling requirements.",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid job data"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Job number already exists"},
    },
)
async def create_job(
    request: CreateJobRequest,
    session: SessionDep,
    job_service: JobServiceDep,
    current_user: CurrentUser = Depends(require_permission("create_job")),
) -> JobResponse:
    """
    Create a new production job.

    Requires 'create_job' permission.
    """
    try:
        # Convert DTO to domain entity
        job = Job.create(
            job_number=request.job_number,
            due_date=request.due_date,
            customer_name=request.customer_name,
            part_number=request.part_number,
            quantity=request.quantity,
            priority=PriorityLevel(request.priority),
            created_by=current_user.email,
        )

        # Save via service
        created_job = await job_service.create_job(job)

        # Convert to response DTO
        return _convert_job_to_response(created_job)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business rule violation: {e.message}",
        )
    except DatabaseError as e:
        if "job_number" in str(e).lower() and "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job number '{request.job_number}' already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/",
    summary="List jobs",
    description="Get list of jobs with optional filtering, searching, and pagination.",
    response_model=list[JobSummaryResponse],
)
async def list_jobs(
    status_filter: str | None = Query(None, description="Filter by job status"),
    priority_filter: str | None = Query(None, description="Filter by priority"),
    customer_name: str | None = Query(None, description="Filter by customer name"),
    search: str | None = Query(None, description="Search in job number or part number"),
    overdue_only: bool = Query(False, description="Show only overdue jobs"),
    due_within_days: int | None = Query(None, description="Jobs due within N days"),
    limit: int = Query(
        50, ge=1, le=1000, description="Maximum number of jobs to return"
    ),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
) -> list[JobSummaryResponse]:
    """
    Get list of jobs with filtering and pagination.

    Supports various filters including status, priority, customer, and date-based filters.
    """
    try:
        # Build filter criteria
        filters = {}
        if status_filter:
            try:
                filters["status"] = JobStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )

        if priority_filter:
            try:
                filters["priority"] = PriorityLevel(priority_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid priority: {priority_filter}",
                )

        if customer_name:
            filters["customer_name"] = customer_name

        if search:
            filters["search"] = search

        if overdue_only:
            filters["overdue_only"] = True

        if due_within_days:
            filters["due_within_days"] = due_within_days

        # Get jobs from repository
        jobs = await job_repo.find_with_filters(
            filters=filters, limit=limit, offset=offset
        )

        # Convert to response DTOs
        return [_convert_job_to_summary(job) for job in jobs]

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/{job_id}",
    summary="Get job by ID",
    description="Get detailed information about a specific job including tasks and progress.",
    response_model=JobResponse,
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job(
    job_id: UUID,
    include_tasks: bool = Query(True, description="Include task details in response"),
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
) -> JobResponse:
    """Get detailed information about a specific job."""
    try:
        job = await job_repo.get_by_id_required(job_id)

        response = _convert_job_to_response(job)

        if include_tasks:
            tasks = await task_repo.find_by_job_id(job_id)
            response.tasks = [_convert_task_to_summary(task) for task in tasks]

        return response

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/number/{job_number}",
    summary="Get job by number",
    description="Get job information using the human-readable job number.",
    response_model=JobResponse,
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_by_number(
    job_number: str,
    include_tasks: bool = Query(True, description="Include task details in response"),
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
    task_repo: TaskRepositoryDep = Depends(),
) -> JobResponse:
    """Get job information using job number."""
    try:
        job = await job_repo.find_by_job_number_required(job_number)

        response = _convert_job_to_response(job)

        if include_tasks:
            tasks = await task_repo.find_by_job_id(job.id)
            response.tasks = [_convert_task_to_summary(task) for task in tasks]

        return response

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with number '{job_number}' not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.put(
    "/{job_id}",
    summary="Update job",
    description="Update job information. Some fields require specific permissions.",
    response_model=JobResponse,
    responses={
        400: {"description": "Invalid update data"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
        409: {"description": "Business rule violation"},
    },
)
async def update_job(
    job_id: UUID,
    request: UpdateJobRequest,
    job_service: JobServiceDep,
    current_user: CurrentUser = Depends(require_permission("update_job")),
) -> JobResponse:
    """
    Update job information.

    Requires 'update_job' permission.
    """
    try:
        updated_job = await job_service.update_job(
            job_id=job_id,
            update_data=request.dict(exclude_unset=True),
            updated_by=current_user.email,
            reason=request.change_reason,
        )

        return _convert_job_to_response(updated_job)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business rule violation: {e.message}",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.post(
    "/{job_id}/status",
    summary="Change job status",
    description="Change job status with validation of status transitions.",
    response_model=JobResponse,
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
        409: {"description": "Business rule violation"},
    },
)
async def change_job_status(
    job_id: UUID,
    new_status: str,
    job_service: JobServiceDep,
    reason: str | None = Query(None, description="Reason for status change"),
    current_user: CurrentUser = Depends(require_permission("change_job_status")),
) -> JobResponse:
    """
    Change job status.

    Requires 'change_job_status' permission.
    """
    try:
        # Validate status
        try:
            status_enum = JobStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {new_status}",
            )

        updated_job = await job_service.change_job_status(
            job_id=job_id,
            new_status=status_enum,
            reason=reason or f"Status changed by {current_user.email}",
            changed_by=current_user.email,
        )

        return _convert_job_to_response(updated_job)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Status change not allowed: {e.message}",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.post(
    "/{job_id}/schedule",
    summary="Update job schedule",
    description="Update job planned start and end dates.",
    response_model=JobResponse,
    responses={
        400: {"description": "Invalid schedule data"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
        409: {"description": "Schedule conflict"},
    },
)
async def update_job_schedule(
    job_id: UUID,
    job_service: JobServiceDep,
    planned_start: datetime | None = Query(None, description="Planned start date"),
    planned_end: datetime | None = Query(None, description="Planned end date"),
    reason: str = Query("Schedule update", description="Reason for schedule change"),
    current_user: CurrentUser = Depends(require_permission("schedule_job")),
) -> JobResponse:
    """
    Update job schedule.

    Requires 'schedule_job' permission.
    """
    try:
        if planned_start and planned_end and planned_start >= planned_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planned start date must be before planned end date",
            )

        updated_job = await job_service.update_job_schedule(
            job_id=job_id,
            planned_start=planned_start,
            planned_end=planned_end,
            reason=reason,
            scheduled_by=current_user.email,
        )

        return _convert_job_to_response(updated_job)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule conflict: {e.message}",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.delete(
    "/{job_id}",
    summary="Delete job",
    description="Delete a job. Only allowed for jobs not yet in production.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Job not found"},
        409: {"description": "Cannot delete job in current status"},
    },
)
async def delete_job(
    job_id: UUID,
    job_service: JobServiceDep,
    reason: str = Query(..., description="Reason for deletion"),
    current_user: CurrentUser = Depends(require_permission("delete_job")),
):
    """
    Delete a job.

    Requires 'delete_job' permission.
    Only allowed for jobs not yet in production.
    """
    try:
        await job_service.delete_job(
            job_id=job_id, reason=reason, deleted_by=current_user.email
        )

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete job: {e.message}",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/statistics/summary",
    summary="Get job statistics",
    description="Get comprehensive statistics about jobs in the system.",
    response_model=JobStatisticsResponse,
)
async def get_job_statistics(
    current_user: CurrentUser = Depends(),
    job_repo: JobRepositoryDep = Depends(),
) -> JobStatisticsResponse:
    """Get comprehensive job statistics."""
    try:
        stats = await job_repo.get_job_statistics()
        return JobStatisticsResponse(**stats)

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


# Helper functions for DTO conversion


def _convert_job_to_response(job: Job) -> JobResponse:
    """Convert Job domain entity to JobResponse DTO."""
    return JobResponse(
        id=job.id,
        job_number=job.job_number,
        customer_name=job.customer_name,
        part_number=job.part_number,
        quantity=job.quantity.value,
        priority=job.priority.value,
        status=job.status.value,
        release_date=job.release_date,
        due_date=job.due_date,
        planned_start_date=job.planned_start_date,
        planned_end_date=job.planned_end_date,
        actual_start_date=job.actual_start_date,
        actual_end_date=job.actual_end_date,
        current_operation_sequence=job.current_operation_sequence,
        completion_percentage=job.completion_percentage,
        task_count=job.task_count,
        completed_task_count=job.completed_task_count,
        is_active=job.is_active,
        is_complete=job.is_complete,
        is_overdue=job.is_overdue,
        days_until_due=job.days_until_due,
        notes=job.notes,
        created_by=job.created_by,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _convert_job_to_summary(job: Job) -> JobSummaryResponse:
    """Convert Job domain entity to JobSummaryResponse DTO."""
    return JobSummaryResponse(
        id=job.id,
        job_number=job.job_number,
        customer_name=job.customer_name,
        status=job.status.value,
        priority=job.priority.value,
        due_date=job.due_date,
        completion_percentage=job.completion_percentage,
        is_overdue=job.is_overdue,
        days_until_due=job.days_until_due,
        task_count=job.task_count,
        completed_task_count=job.completed_task_count,
    )


def _convert_task_to_summary(task) -> dict:
    """Convert Task domain entity to summary dict."""
    # Simplified task summary - would use proper TaskSummaryResponse DTO
    return {
        "id": task.id,
        "sequence_in_job": task.sequence_in_job,
        "status": task.status.value if hasattr(task, "status") else "unknown",
        "planned_start_time": getattr(task, "planned_start_time", None),
        "planned_end_time": getattr(task, "planned_end_time", None),
        "actual_start_time": getattr(task, "actual_start_time", None),
        "actual_end_time": getattr(task, "actual_end_time", None),
        "is_critical_path": getattr(task, "is_critical_path", False),
    }
