"""
Schedule Management API Routes.

This module provides comprehensive schedule management endpoints for production scheduling,
including schedule creation, optimization, status management, and real-time monitoring.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, require_permission
from app.application.dtos.scheduling_dtos import (
    CreateScheduleRequest,
    OptimizeScheduleRequest,
    ScheduleMetricsResponse,
    ScheduleResponse,
    ScheduleStatusRequest,
    ScheduleStatusResponse,
    ScheduleSummaryResponse,
    TaskAssignmentResponse,
)
from app.domain.scheduling.entities.schedule import Schedule, ScheduleStatus
from app.domain.scheduling.services.optimization_service import OptimizationParameters
from app.domain.scheduling.services.scheduling_service import SchedulingRequest
from app.domain.shared.exceptions import (
    BusinessRuleViolation,
    EntityNotFoundError,
    NoFeasibleSolutionError,
    OptimizationError,
    SchedulePublishError,
    ValidationError,
)
from app.infrastructure.database.dependencies import (
    JobRepositoryDep,
    ScheduleRepositoryDep,
)
from app.infrastructure.database.repositories import DatabaseError
from app.infrastructure.database.service_dependencies import (
    OptimizationServiceDep,
    SchedulingServiceDep,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post(
    "/",
    summary="Create new schedule",
    description="Create a new production schedule with specified jobs and parameters.",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid schedule data"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Schedule conflict"},
    },
)
async def create_schedule(
    request: CreateScheduleRequest,
    scheduling_service: SchedulingServiceDep,
    current_user: CurrentUser = Depends(require_permission("create_schedule")),
) -> ScheduleResponse:
    """
    Create a new production schedule.

    Requires 'create_schedule' permission.
    """
    try:
        # Validate end time
        end_time = request.end_time or (
            request.start_time + timedelta(days=request.planning_horizon_days)
        )

        # Create scheduling request
        scheduling_request = SchedulingRequest(
            job_ids=request.job_ids,
            start_time=request.start_time,
            end_time=end_time,
            optimization_params=None,  # Will be set during optimization
            constraints={},
        )

        # Create schedule via domain service
        schedule = await scheduling_service.create_schedule(
            name=request.name,
            description=request.description,
            scheduling_request=scheduling_request,
            created_by_user_id=current_user.id,
        )

        return _convert_schedule_to_response(schedule)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}",
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


@router.get(
    "/",
    summary="List schedules",
    description="Get list of schedules with optional filtering and pagination.",
    response_model=list[ScheduleSummaryResponse],
)
async def list_schedules(
    status_filter: str | None = Query(None, description="Filter by schedule status"),
    name_filter: str | None = Query(None, description="Filter by schedule name"),
    created_by: str | None = Query(None, description="Filter by creator"),
    start_date_from: datetime | None = Query(
        None, description="Filter schedules starting from this date"
    ),
    start_date_to: datetime | None = Query(
        None, description="Filter schedules starting before this date"
    ),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of schedules"),
    offset: int = Query(0, ge=0, description="Number of schedules to skip"),
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> list[ScheduleSummaryResponse]:
    """Get list of schedules with filtering and pagination."""
    try:
        # Build filter criteria
        filters = {}
        if status_filter:
            try:
                filters["status"] = ScheduleStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )

        if name_filter:
            filters["name"] = name_filter

        if created_by:
            filters["created_by"] = created_by

        if start_date_from:
            filters["start_date_from"] = start_date_from

        if start_date_to:
            filters["start_date_to"] = start_date_to

        # Get schedules from repository
        schedules = await schedule_repo.find_with_filters(
            filters=filters, limit=limit, offset=offset
        )

        # Convert to response DTOs
        return [_convert_schedule_to_summary(schedule) for schedule in schedules]

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/{schedule_id}",
    summary="Get schedule by ID",
    description="Get detailed information about a specific schedule including assignments and metrics.",
    response_model=ScheduleResponse,
    responses={
        404: {"description": "Schedule not found"},
    },
)
async def get_schedule(
    schedule_id: UUID,
    include_assignments: bool = Query(True, description="Include task assignments"),
    include_metrics: bool = Query(True, description="Include performance metrics"),
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> ScheduleResponse:
    """Get detailed information about a specific schedule."""
    try:
        schedule = await schedule_repo.get_by_id_required(schedule_id)

        response = _convert_schedule_to_response(schedule)

        if include_assignments:
            # Get task assignments
            assignments = schedule.assignments
            response.task_assignments = [
                _convert_assignment_to_response(assignment)
                for assignment in assignments.values()
            ]

        if include_metrics and schedule.is_published:
            # Calculate and include metrics
            response.metrics = _calculate_schedule_metrics(schedule)

        return response

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


@router.post(
    "/{schedule_id}/optimize",
    summary="Optimize schedule",
    description="Run optimization algorithm on the schedule to find optimal task assignments.",
    response_model=ScheduleResponse,
    responses={
        400: {"description": "Invalid optimization parameters"},
        404: {"description": "Schedule not found"},
        408: {"description": "Optimization timeout"},
        422: {"description": "No feasible solution found"},
        500: {"description": "Optimization error"},
    },
)
async def optimize_schedule(
    schedule_id: UUID,
    request: OptimizeScheduleRequest,
    background_tasks: BackgroundTasks,
    optimization_service: OptimizationServiceDep,
    scheduling_service: SchedulingServiceDep,
    current_user: CurrentUser = Depends(require_permission("optimize_schedule")),
) -> ScheduleResponse:
    """
    Optimize schedule using OR-Tools solver.

    Requires 'optimize_schedule' permission.
    """
    try:
        # Get schedule
        schedule = await scheduling_service.get_schedule(schedule_id)

        if schedule.status != ScheduleStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Can only optimize schedules in draft status",
            )

        # Configure optimization parameters
        opt_params = OptimizationParameters(
            max_time_seconds=request.max_time_seconds,
            enable_hierarchical_optimization=request.enable_hierarchical_optimization,
            primary_objective=request.primary_objective,
            secondary_objective=request.secondary_objective,
            **request.optimization_parameters,
        )

        # Run optimization
        result = await optimization_service.optimize_schedule(
            job_ids=list(schedule.job_ids),
            start_time=schedule.start_date,
            parameters=opt_params,
        )

        # Update schedule with optimization results
        optimized_schedule = await scheduling_service.apply_optimization_result(
            schedule_id=schedule_id, optimization_result=result
        )

        return _convert_schedule_to_response(optimized_schedule)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found",
        )
    except NoFeasibleSolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No feasible solution found: {e.message}",
        )
    except OptimizationError as e:
        if "timeout" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Optimization timeout: {e.message}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Optimization error: {e.message}",
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
    "/{schedule_id}/status",
    summary="Change schedule status",
    description="Change schedule status (publish, activate, complete, cancel) with validation.",
    response_model=ScheduleStatusResponse,
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
        409: {"description": "Business rule violation"},
    },
)
async def change_schedule_status(
    schedule_id: UUID,
    request: ScheduleStatusRequest,
    scheduling_service: SchedulingServiceDep,
    current_user: CurrentUser = Depends(require_permission("manage_schedule")),
) -> ScheduleStatusResponse:
    """
    Change schedule status.

    Requires 'manage_schedule' permission.
    """
    try:
        # Get current schedule
        schedule = await scheduling_service.get_schedule(schedule_id)
        old_status = schedule.status.value

        # Perform status change
        if request.action == "publish":
            updated_schedule = await scheduling_service.publish_schedule(
                schedule_id=schedule_id, reason=request.reason
            )
        elif request.action == "activate":
            updated_schedule = await scheduling_service.activate_schedule(
                schedule_id=schedule_id, reason=request.reason
            )
        elif request.action == "complete":
            updated_schedule = await scheduling_service.complete_schedule(
                schedule_id=schedule_id, reason=request.reason
            )
        elif request.action == "cancel":
            updated_schedule = await scheduling_service.cancel_schedule(
                schedule_id=schedule_id, reason=request.reason
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {request.action}",
            )

        return ScheduleStatusResponse(
            schedule_id=schedule_id,
            old_status=old_status,
            new_status=updated_schedule.status.value,
            action=request.action,
            reason=request.reason,
            timestamp=datetime.utcnow(),
            success=True,
            message=f"Schedule {request.action} successful",
        )

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found",
        )
    except SchedulePublishError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish schedule: {e.message}",
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


@router.get(
    "/{schedule_id}/assignments",
    summary="Get schedule assignments",
    description="Get all task assignments for a schedule, optionally filtered by resource or time.",
    response_model=list[TaskAssignmentResponse],
)
async def get_schedule_assignments(
    schedule_id: UUID,
    machine_id: UUID | None = Query(None, description="Filter by machine"),
    operator_id: UUID | None = Query(None, description="Filter by operator"),
    start_time: datetime | None = Query(
        None, description="Filter assignments after this time"
    ),
    end_time: datetime | None = Query(
        None, description="Filter assignments before this time"
    ),
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> list[TaskAssignmentResponse]:
    """Get task assignments for a schedule with optional filtering."""
    try:
        schedule = await schedule_repo.get_by_id_required(schedule_id)

        assignments = schedule.assignments.values()

        # Apply filters
        if machine_id:
            assignments = [a for a in assignments if a.machine_id == machine_id]

        if operator_id:
            assignments = [a for a in assignments if operator_id in a.operator_ids]

        if start_time:
            assignments = [a for a in assignments if a.start_time >= start_time]

        if end_time:
            assignments = [a for a in assignments if a.end_time <= end_time]

        # Sort by start time
        assignments = sorted(assignments, key=lambda a: a.start_time)

        return [
            _convert_assignment_to_response(assignment) for assignment in assignments
        ]

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
    "/{schedule_id}/metrics",
    summary="Get schedule metrics",
    description="Get performance metrics for a published schedule.",
    response_model=ScheduleMetricsResponse,
)
async def get_schedule_metrics(
    schedule_id: UUID,
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
    job_repo: JobRepositoryDep = Depends(),
) -> ScheduleMetricsResponse:
    """Get performance metrics for a schedule."""
    try:
        schedule = await schedule_repo.get_by_id_required(schedule_id)

        if not schedule.is_published:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Metrics only available for published schedules",
            )

        # Get job due dates for tardiness calculation
        jobs = await job_repo.find_by_ids(list(schedule.job_ids))
        job_due_dates = {job.id: job.due_date for job in jobs}

        # Calculate metrics
        schedule.calculate_metrics(job_due_dates)

        return _calculate_schedule_metrics(schedule)

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


@router.delete(
    "/{schedule_id}",
    summary="Delete schedule",
    description="Delete a schedule. Only allowed for draft schedules.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Schedule not found"},
        409: {"description": "Cannot delete schedule in current status"},
    },
)
async def delete_schedule(
    schedule_id: UUID,
    scheduling_service: SchedulingServiceDep,
    reason: str = Query(..., description="Reason for deletion"),
    current_user: CurrentUser = Depends(require_permission("delete_schedule")),
):
    """
    Delete a schedule.

    Requires 'delete_schedule' permission.
    Only allowed for draft schedules.
    """
    try:
        await scheduling_service.delete_schedule(
            schedule_id=schedule_id, reason=reason, deleted_by=current_user.email
        )

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found",
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete schedule: {e.message}",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/{schedule_id}/validation",
    summary="Validate schedule",
    description="Validate schedule constraints and get list of violations.",
    response_model=dict,
)
async def validate_schedule(
    schedule_id: UUID,
    current_user: CurrentUser = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> dict:
    """Validate schedule constraints."""
    try:
        schedule = await schedule_repo.get_by_id_required(schedule_id)

        # Validate constraints
        violations = schedule.validate_constraints()

        return {
            "schedule_id": schedule_id,
            "is_valid": len(violations) == 0,
            "constraint_violations": violations,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "total_violations": len(violations),
        }

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


# Helper functions for DTO conversion


def _convert_schedule_to_response(schedule: Schedule) -> ScheduleResponse:
    """Convert Schedule domain entity to ScheduleResponse DTO."""
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=getattr(schedule, "description", None),
        status=schedule.status.value,
        job_ids=list(schedule.job_ids),
        start_time=schedule.start_date,
        end_time=schedule.end_date,
        planning_horizon_days=getattr(schedule, "planning_horizon_days", 30),
        is_valid=schedule.is_valid,
        constraint_violations=schedule.constraint_violations,
        created_by=getattr(schedule, "created_by", None),
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _convert_schedule_to_summary(schedule: Schedule) -> ScheduleSummaryResponse:
    """Convert Schedule domain entity to ScheduleSummaryResponse DTO."""
    return ScheduleSummaryResponse(
        id=schedule.id,
        name=schedule.name,
        status=schedule.status.value,
        job_count=len(schedule.job_ids),
        task_count=len(schedule.assignments),
        start_time=schedule.start_date,
        end_time=schedule.end_date,
        is_valid=schedule.is_valid,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _convert_assignment_to_response(assignment) -> TaskAssignmentResponse:
    """Convert ScheduleAssignment to TaskAssignmentResponse DTO."""
    return TaskAssignmentResponse(
        task_id=assignment.task_id,
        job_id=getattr(
            assignment, "job_id", None
        ),  # Would need to be added to assignment
        machine_id=assignment.machine_id,
        operator_ids=assignment.operator_ids,
        start_time=assignment.start_time,
        end_time=assignment.end_time,
        setup_duration_minutes=assignment.setup_duration.minutes,
        processing_duration_minutes=assignment.processing_duration.minutes,
        total_duration_minutes=assignment.total_duration.minutes,
        sequence_in_job=getattr(
            assignment, "sequence_in_job", 0
        ),  # Would need to be added
        is_critical_path=False,  # Would be calculated
    )


def _calculate_schedule_metrics(schedule: Schedule) -> ScheduleMetricsResponse:
    """Calculate metrics for a schedule."""
    # This would be properly implemented with real calculations
    return ScheduleMetricsResponse(
        makespan_minutes=schedule.makespan.minutes if schedule.makespan else 0,
        total_tardiness_minutes=schedule.total_tardiness.minutes
        if schedule.total_tardiness
        else 0,
        total_cost=schedule.total_cost or 0.0,
        machine_utilization_percent=75.0,  # Simplified
        operator_utilization_percent=65.0,  # Simplified
        jobs_on_time=len(schedule.job_ids) - 1,  # Simplified
        jobs_late=1,  # Simplified
        critical_path_jobs=2,  # Simplified
        constraint_violations=schedule.constraint_violations,
    )
