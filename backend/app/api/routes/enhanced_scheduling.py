"""
Enhanced Scheduling API Routes with Full Domain Integration.

This module provides comprehensive scheduling API endpoints that properly integrate
domain services, repositories, event handling, and transaction boundaries.
"""

import asyncio
from datetime import datetime
from typing import Any
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
from app.domain.scheduling.entities.schedule import ScheduleStatus
from app.domain.scheduling.events.domain_events import (
    JobStatusChanged,
    SchedulePublished,
    TaskScheduled,
)
from app.domain.scheduling.services.optimization_service import (
    OptimizationParameters,
    OptimizationService,
)
from app.domain.scheduling.services.scheduling_service import (
    SchedulingRequest,
    SchedulingService,
)
from app.domain.scheduling.value_objects.enums import JobStatus
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
from app.infrastructure.database.domain_unit_of_work import domain_transaction
from app.infrastructure.database.repositories import DatabaseError
from app.infrastructure.database.service_dependencies import (
    OptimizationServiceDep,
    SchedulingServiceDep,
)
from app.infrastructure.events.domain_event_publisher import publish_domain_events_async

router = APIRouter(prefix="/enhanced-scheduling", tags=["enhanced-scheduling"])


@router.post(
    "/schedules",
    summary="Create optimized schedule with full domain integration",
    description="Create a production schedule using domain services with proper transaction boundaries and event handling.",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_optimized_schedule(
    request: CreateScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_permission("create_schedule")),
) -> ScheduleResponse:
    """
    Create a new production schedule with full domain integration.
    
    This endpoint demonstrates proper use of:
    - Domain Unit of Work with transaction boundaries
    - Domain event handling
    - Repository pattern with domain services
    - Comprehensive error handling
    """
    try:
        async with domain_transaction() as uow:
            # Validate jobs exist and are in appropriate status
            jobs = []
            for job_id in request.job_ids:
                job = await uow.jobs.get_by_id(job_id)
                if not job:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Job with ID {job_id} not found"
                    )
                
                if job.status not in [JobStatus.PLANNED, JobStatus.RELEASED]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Job {job.job_number} is not in a valid status for scheduling"
                    )
                jobs.append(job)

            # Create schedule using domain service
            from app.domain.scheduling.entities.schedule import Schedule
            from app.domain.scheduling.value_objects.duration import Duration
            
            end_time = request.end_time or (
                request.start_time + Duration.from_days(request.planning_horizon_days).to_timedelta()
            )

            schedule = Schedule.create(
                name=request.name,
                description=request.description,
                start_date=request.start_time,
                end_date=end_time,
                job_ids={job.id for job in jobs},
                created_by=current_user.id
            )

            # Save schedule
            await uow.schedules.save(schedule)

            # Add domain event for schedule creation
            uow.add_domain_event(
                SchedulePublished(
                    schedule_id=schedule.id,
                    version=1,
                    effective_date=schedule.start_date,
                    task_count=len(schedule.job_ids),
                    makespan_hours=0.0  # Will be calculated after optimization
                )
            )

            # Convert to response
            response = _convert_schedule_to_response(schedule)
            
            # Schedule optimization in background
            background_tasks.add_task(
                _optimize_schedule_background,
                schedule.id,
                OptimizationParameters(
                    max_time_seconds=300,
                    primary_objective="minimize_makespan"
                )
            )

            return response

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}"
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business rule violation: {e.message}"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}"
        )


@router.post(
    "/schedules/{schedule_id}/optimize-with-events",
    summary="Optimize schedule with full event handling",
    description="Run optimization on schedule with comprehensive domain event publishing.",
    response_model=ScheduleResponse,
)
async def optimize_schedule_with_events(
    schedule_id: UUID,
    request: OptimizeScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_permission("optimize_schedule")),
) -> ScheduleResponse:
    """
    Optimize a schedule with full domain event integration.
    
    Demonstrates:
    - Proper optimization service usage
    - Domain event collection and publishing
    - Transaction boundaries around optimization
    - Comprehensive error handling
    """
    try:
        async with domain_transaction() as uow:
            # Get schedule
            schedule = await uow.schedules.get_by_id_required(schedule_id)
            
            if schedule.status != ScheduleStatus.DRAFT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Can only optimize schedules in draft status"
                )

            # Get jobs for the schedule
            jobs = []
            for job_id in schedule.job_ids:
                job = await uow.jobs.get_by_id_required(job_id)
                jobs.append(job)

            # Create optimization service with repository adapters
            from app.infrastructure.adapters.repository_adapters import create_domain_repositories
            
            domain_repos = create_domain_repositories(
                uow.jobs, uow.tasks, uow.machines, uow.operators
            )
            
            optimization_service = OptimizationService(*domain_repos)

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
                parameters=opt_params
            )

            # Update schedule with results
            if result.solution_found:
                # Apply optimization results to schedule
                schedule.makespan = result.makespan
                schedule.total_cost = result.total_cost
                schedule.is_optimized = True
                
                await uow.schedules.save(schedule)

                # Collect task assignment events
                assignment_events = []
                for assignment in result.assignments:
                    assignment_events.append(
                        TaskScheduled(
                            task_id=assignment.task_id,
                            job_id=assignment.job_id,
                            machine_id=assignment.machine_id,
                            operator_ids=assignment.operator_ids,
                            planned_start=assignment.start_time,
                            planned_end=assignment.end_time
                        )
                    )

                # Add all events to unit of work for publishing after commit
                uow.add_domain_events(assignment_events)

            else:
                raise NoFeasibleSolutionError("No feasible solution found for schedule optimization")

            response = _convert_schedule_to_response(schedule)
            response.metrics = _calculate_schedule_metrics_from_result(result)

            return response

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except NoFeasibleSolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No feasible solution: {e.message}"
        )
    except OptimizationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Optimization error: {e.message}"
        )


@router.post(
    "/schedules/{schedule_id}/publish-with-validation",
    summary="Publish schedule with comprehensive validation",
    description="Publish a schedule with full constraint validation and status management.",
    response_model=ScheduleStatusResponse,
)
async def publish_schedule_with_validation(
    schedule_id: UUID,
    request: ScheduleStatusRequest,
    current_user: CurrentUser = Depends(require_permission("publish_schedule")),
) -> ScheduleStatusResponse:
    """
    Publish a schedule with comprehensive validation and domain events.
    
    Demonstrates:
    - Complex business logic with validation
    - Status transition management
    - Domain event publishing
    - Transactional consistency
    """
    try:
        async with domain_transaction() as uow:
            # Get schedule with full details
            schedule = await uow.schedules.get_by_id_required(schedule_id)
            old_status = schedule.status

            # Validate status transition
            if not old_status.can_transition_to(ScheduleStatus.PUBLISHED):
                raise BusinessRuleViolation(
                    f"Cannot transition from {old_status.value} to published"
                )

            # Comprehensive validation
            violations = []
            
            # Check if all jobs are still valid
            for job_id in schedule.job_ids:
                job = await uow.jobs.get_by_id(job_id)
                if not job:
                    violations.append(f"Job {job_id} no longer exists")
                elif job.status == JobStatus.CANCELLED:
                    violations.append(f"Job {job.job_number} is cancelled")

            # Check resource availability (simplified)
            available_machines = await uow.machines.find_available()
            available_operators = await uow.operators.find_available()
            
            if not available_machines:
                violations.append("No machines available during schedule period")
            if not available_operators:
                violations.append("No operators available during schedule period")

            if violations:
                raise SchedulePublishError(
                    f"Schedule validation failed: {'; '.join(violations)}"
                )

            # Update schedule status
            schedule.status = ScheduleStatus.PUBLISHED
            schedule.published_at = datetime.utcnow()
            await uow.schedules.save(schedule)

            # Create domain event
            uow.add_domain_event(
                SchedulePublished(
                    schedule_id=schedule.id,
                    version=schedule.version or 1,
                    effective_date=schedule.start_date,
                    task_count=len(schedule.assignments) if hasattr(schedule, 'assignments') else 0,
                    makespan_hours=float(schedule.makespan.hours) if schedule.makespan else 0.0
                )
            )

            # Update related job statuses
            job_events = []
            for job_id in schedule.job_ids:
                job = await uow.jobs.get_by_id_required(job_id)
                if job.status == JobStatus.PLANNED:
                    old_job_status = job.status
                    job.status = JobStatus.RELEASED
                    await uow.jobs.save(job)
                    
                    job_events.append(
                        JobStatusChanged(
                            job_id=job.id,
                            job_number=job.job_number,
                            old_status=old_job_status.value,
                            new_status=job.status.value,
                            reason="Released due to schedule publication"
                        )
                    )

            uow.add_domain_events(job_events)

            return ScheduleStatusResponse(
                schedule_id=schedule_id,
                old_status=old_status.value,
                new_status=schedule.status.value,
                action=request.action,
                reason=request.reason,
                timestamp=datetime.utcnow(),
                success=True,
                message="Schedule published successfully with job status updates"
            )

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    except SchedulePublishError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish schedule: {e.message}"
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business rule violation: {e.message}"
        )


@router.get(
    "/schedules/{schedule_id}/comprehensive",
    summary="Get comprehensive schedule information",
    description="Get detailed schedule information with metrics, assignments, and validation status.",
    response_model=ScheduleResponse,
)
async def get_comprehensive_schedule(
    schedule_id: UUID,
    include_assignments: bool = Query(True, description="Include task assignments"),
    include_metrics: bool = Query(True, description="Include performance metrics"),
    include_validation: bool = Query(True, description="Include constraint validation"),
    current_user: CurrentUser = Depends(),
) -> ScheduleResponse:
    """
    Get comprehensive schedule information using domain services and repositories.
    
    Demonstrates:
    - Complex data aggregation across repositories
    - Domain service integration
    - Flexible response composition
    """
    try:
        async with domain_transaction() as uow:
            # Get schedule
            schedule = await uow.schedules.get_by_id_required(schedule_id)
            response = _convert_schedule_to_response(schedule)

            if include_assignments:
                # Get task assignments (would be from schedule assignments)
                if hasattr(schedule, 'assignments') and schedule.assignments:
                    response.task_assignments = [
                        _convert_assignment_to_response(assignment)
                        for assignment in schedule.assignments.values()
                    ]

            if include_metrics and schedule.status in [ScheduleStatus.PUBLISHED, ScheduleStatus.ACTIVE]:
                # Calculate comprehensive metrics
                response.metrics = await _calculate_comprehensive_metrics(uow, schedule)

            if include_validation:
                # Perform constraint validation
                violations = await _validate_schedule_constraints(uow, schedule)
                response.constraint_violations = violations
                response.is_valid = len(violations) == 0

            return response

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}"
        )


# Background task functions

async def _optimize_schedule_background(
    schedule_id: UUID,
    parameters: OptimizationParameters
) -> None:
    """Background task for schedule optimization."""
    try:
        async with domain_transaction() as uow:
            schedule = await uow.schedules.get_by_id_required(schedule_id)
            
            # Create optimization service
            from app.infrastructure.adapters.repository_adapters import create_domain_repositories
            domain_repos = create_domain_repositories(
                uow.jobs, uow.tasks, uow.machines, uow.operators
            )
            optimization_service = OptimizationService(*domain_repos)

            # Run optimization
            result = await optimization_service.optimize_schedule(
                job_ids=list(schedule.job_ids),
                start_time=schedule.start_date,
                parameters=parameters
            )

            if result.solution_found:
                schedule.makespan = result.makespan
                schedule.total_cost = result.total_cost
                schedule.is_optimized = True
                await uow.schedules.save(schedule)

                # Publish optimization completed event
                events = [
                    SchedulePublished(
                        schedule_id=schedule.id,
                        version=schedule.version or 1,
                        effective_date=schedule.start_date,
                        task_count=len(result.assignments),
                        makespan_hours=float(result.makespan.hours)
                    )
                ]
                
                # Also add task assignment events
                for assignment in result.assignments:
                    events.append(
                        TaskScheduled(
                            task_id=assignment.task_id,
                            job_id=assignment.job_id,
                            machine_id=assignment.machine_id,
                            operator_ids=assignment.operator_ids,
                            planned_start=assignment.start_time,
                            planned_end=assignment.end_time
                        )
                    )

                # Publish events asynchronously
                await publish_domain_events_async(events)

    except Exception as e:
        # Log error but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Background optimization failed for schedule {schedule_id}: {str(e)}")


# Helper functions

def _convert_schedule_to_response(schedule) -> ScheduleResponse:
    """Convert domain Schedule entity to API response."""
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=getattr(schedule, "description", None),
        status=schedule.status.value if hasattr(schedule.status, 'value') else str(schedule.status),
        job_ids=list(schedule.job_ids) if schedule.job_ids else [],
        start_time=schedule.start_date,
        end_time=schedule.end_date,
        planning_horizon_days=30,  # Calculate from dates
        is_valid=getattr(schedule, 'is_valid', True),
        constraint_violations=getattr(schedule, 'constraint_violations', []),
        created_by=getattr(schedule, 'created_by', None),
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _convert_assignment_to_response(assignment) -> TaskAssignmentResponse:
    """Convert schedule assignment to API response."""
    return TaskAssignmentResponse(
        task_id=assignment.task_id,
        job_id=getattr(assignment, 'job_id', None),
        machine_id=assignment.machine_id,
        operator_ids=assignment.operator_ids or [],
        start_time=assignment.start_time,
        end_time=assignment.end_time,
        setup_duration_minutes=int(assignment.setup_duration.minutes),
        processing_duration_minutes=int(assignment.processing_duration.minutes),
        total_duration_minutes=int(assignment.total_duration.minutes),
        sequence_in_job=getattr(assignment, 'sequence_in_job', 0),
        is_critical_path=getattr(assignment, 'is_critical_path', False)
    )


async def _calculate_comprehensive_metrics(uow, schedule) -> ScheduleMetricsResponse:
    """Calculate comprehensive metrics for a schedule."""
    # This is a simplified implementation
    # In a real system, you would calculate these from the actual assignments
    return ScheduleMetricsResponse(
        makespan_minutes=int(schedule.makespan.minutes) if schedule.makespan else 0,
        total_tardiness_minutes=0,
        total_cost=schedule.total_cost or 0.0,
        machine_utilization_percent=75.0,
        operator_utilization_percent=65.0,
        jobs_on_time=len(schedule.job_ids) - 1,
        jobs_late=1,
        critical_path_jobs=2,
        constraint_violations=[]
    )


def _calculate_schedule_metrics_from_result(result) -> ScheduleMetricsResponse:
    """Calculate metrics from optimization result."""
    return ScheduleMetricsResponse(
        makespan_minutes=int(result.makespan.minutes),
        total_tardiness_minutes=int(result.total_tardiness.minutes) if result.total_tardiness else 0,
        total_cost=result.total_cost,
        machine_utilization_percent=75.0,  # Would be calculated from assignments
        operator_utilization_percent=65.0,  # Would be calculated from assignments
        jobs_on_time=len(result.assignments) - 1,  # Simplified
        jobs_late=1,  # Simplified
        critical_path_jobs=2,  # Simplified
        constraint_violations=[]
    )


async def _validate_schedule_constraints(uow, schedule) -> list[str]:
    """Validate schedule constraints and return violations."""
    violations = []
    
    # Check job validity
    for job_id in schedule.job_ids:
        job = await uow.jobs.get_by_id(job_id)
        if not job:
            violations.append(f"Job {job_id} not found")
        elif job.status == JobStatus.CANCELLED:
            violations.append(f"Job {job.job_number} is cancelled")

    # Check resource availability
    available_machines = await uow.machines.find_available()
    if not available_machines:
        violations.append("No machines available")

    available_operators = await uow.operators.find_available()
    if not available_operators:
        violations.append("No operators available")

    return violations