"""
Resource Management API Routes.

This module provides resource management endpoints for machines and operators,
including availability checking, capability management, and utilization tracking.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser
from app.application.dtos.scheduling_dtos import (
    ResourceAvailabilityResponse,
    ResourceSummaryResponse,
)
from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.value_objects.enums import MachineStatus, OperatorStatus
from app.domain.shared.exceptions import (
    EntityNotFoundError,
)
from app.infrastructure.database.dependencies import (
    MachineRepositoryDep,
    OperatorRepositoryDep,
    ScheduleRepositoryDep,
)
from app.infrastructure.database.repositories import DatabaseError

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get(
    "/availability",
    summary="Check resource availability",
    description="Check availability of machines and operators for a given time window.",
    response_model=ResourceAvailabilityResponse,
)
async def check_resource_availability(
    resource_type: str = Query(
        "all", description="Resource type: machine, operator, or all"
    ),
    start_time: datetime = Query(..., description="Start of time window"),
    end_time: datetime = Query(..., description="End of time window"),
    zone_filter: str | None = Query(None, description="Filter by production zone"),
    skill_requirements: list[str] | None = Query(
        None, description="Required operator skills"
    ),
    current_user: CurrentUser = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> ResourceAvailabilityResponse:
    """Check resource availability for a time window."""
    try:
        # Validate time window
        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be after start time",
            )

        # Validate resource type
        valid_types = ["machine", "operator", "all"]
        if resource_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resource type must be one of: {', '.join(valid_types)}",
            )

        machines = []
        operators = []

        # Get machines if requested
        if resource_type in ["machine", "all"]:
            all_machines = await machine_repo.find_available_in_time_window(
                start_time=start_time, end_time=end_time, zone_filter=zone_filter
            )

            machines = [_convert_machine_to_resource_summary(m) for m in all_machines]

        # Get operators if requested
        if resource_type in ["operator", "all"]:
            all_operators = await operator_repo.find_available_in_time_window(
                start_time=start_time,
                end_time=end_time,
                zone_filter=zone_filter,
                skill_requirements=skill_requirements,
            )

            operators = [
                _convert_operator_to_resource_summary(o) for o in all_operators
            ]

        # Get total counts for summary
        total_machines = (
            len(await machine_repo.get_all())
            if resource_type in ["machine", "all"]
            else 0
        )
        total_operators = (
            len(await operator_repo.get_all())
            if resource_type in ["operator", "all"]
            else 0
        )

        availability_summary = {
            "available_machines": len(machines),
            "available_operators": len(operators),
            "total_machines": total_machines,
            "total_operators": total_operators,
        }

        return ResourceAvailabilityResponse(
            machines=machines,
            operators=operators,
            availability_summary=availability_summary,
            time_window={"start_time": start_time, "end_time": end_time},
        )

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/machines",
    summary="List machines",
    description="Get list of all machines with optional filtering.",
    response_model=list[ResourceSummaryResponse],
)
async def list_machines(
    status_filter: str | None = Query(None, description="Filter by machine status"),
    zone_filter: str | None = Query(None, description="Filter by production zone"),
    capability_filter: str | None = Query(None, description="Filter by capability"),
    available_only: bool = Query(False, description="Show only available machines"),
    current_user: CurrentUser = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
) -> list[ResourceSummaryResponse]:
    """Get list of machines with optional filtering."""
    try:
        filters = {}

        if status_filter:
            try:
                filters["status"] = MachineStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid machine status: {status_filter}",
                )

        if zone_filter:
            filters["zone"] = zone_filter

        if capability_filter:
            filters["capability"] = capability_filter

        if available_only:
            filters["available_only"] = True

        machines = await machine_repo.find_with_filters(filters)

        return [_convert_machine_to_resource_summary(machine) for machine in machines]

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/machines/{machine_id}",
    summary="Get machine details",
    description="Get detailed information about a specific machine.",
    response_model=ResourceSummaryResponse,
    responses={
        404: {"description": "Machine not found"},
    },
)
async def get_machine(
    machine_id: UUID,
    current_user: CurrentUser = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
) -> ResourceSummaryResponse:
    """Get detailed information about a specific machine."""
    try:
        machine = await machine_repo.get_by_id_required(machine_id)
        return _convert_machine_to_resource_summary(machine)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID {machine_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/machines/{machine_id}/schedule",
    summary="Get machine schedule",
    description="Get current and upcoming task assignments for a machine.",
    response_model=list[dict],
)
async def get_machine_schedule(
    machine_id: UUID,
    start_date: datetime | None = Query(None, description="Start date for schedule"),
    end_date: datetime | None = Query(None, description="End date for schedule"),
    current_user: CurrentUser = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> list[dict]:
    """Get task assignments for a specific machine."""
    try:
        # Verify machine exists
        await machine_repo.get_by_id_required(machine_id)

        # Default to next 7 days if no dates provided
        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=7)

        # Get active schedules
        active_schedules = await schedule_repo.find_active_schedules()

        assignments = []
        for schedule in active_schedules:
            machine_assignments = schedule.get_assignments_for_machine(machine_id)

            # Filter by date range
            filtered_assignments = [
                assignment
                for assignment in machine_assignments
                if assignment.start_time >= start_date
                and assignment.end_time <= end_date
            ]

            assignments.extend(filtered_assignments)

        # Convert to response format
        return [
            {
                "task_id": assignment.task_id,
                "start_time": assignment.start_time,
                "end_time": assignment.end_time,
                "setup_duration_minutes": assignment.setup_duration.minutes,
                "processing_duration_minutes": assignment.processing_duration.minutes,
                "operator_ids": assignment.operator_ids,
                "schedule_id": schedule.id,  # Would need to track this in assignment
            }
            for assignment in sorted(assignments, key=lambda a: a.start_time)
        ]

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID {machine_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/operators",
    summary="List operators",
    description="Get list of all operators with optional filtering.",
    response_model=list[ResourceSummaryResponse],
)
async def list_operators(
    status_filter: str | None = Query(None, description="Filter by operator status"),
    zone_filter: str | None = Query(None, description="Filter by production zone"),
    skill_filter: str | None = Query(None, description="Filter by skill"),
    available_only: bool = Query(False, description="Show only available operators"),
    current_user: CurrentUser = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
) -> list[ResourceSummaryResponse]:
    """Get list of operators with optional filtering."""
    try:
        filters = {}

        if status_filter:
            try:
                filters["status"] = OperatorStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operator status: {status_filter}",
                )

        if zone_filter:
            filters["zone"] = zone_filter

        if skill_filter:
            filters["skill"] = skill_filter

        if available_only:
            filters["available_only"] = True

        operators = await operator_repo.find_with_filters(filters)

        return [
            _convert_operator_to_resource_summary(operator) for operator in operators
        ]

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/operators/{operator_id}",
    summary="Get operator details",
    description="Get detailed information about a specific operator.",
    response_model=ResourceSummaryResponse,
    responses={
        404: {"description": "Operator not found"},
    },
)
async def get_operator(
    operator_id: UUID,
    current_user: CurrentUser = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
) -> ResourceSummaryResponse:
    """Get detailed information about a specific operator."""
    try:
        operator = await operator_repo.get_by_id_required(operator_id)
        return _convert_operator_to_resource_summary(operator)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator with ID {operator_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/operators/{operator_id}/schedule",
    summary="Get operator schedule",
    description="Get current and upcoming task assignments for an operator.",
    response_model=list[dict],
)
async def get_operator_schedule(
    operator_id: UUID,
    start_date: datetime | None = Query(None, description="Start date for schedule"),
    end_date: datetime | None = Query(None, description="End date for schedule"),
    current_user: CurrentUser = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> list[dict]:
    """Get task assignments for a specific operator."""
    try:
        # Verify operator exists
        await operator_repo.get_by_id_required(operator_id)

        # Default to next 7 days if no dates provided
        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=7)

        # Get active schedules
        active_schedules = await schedule_repo.find_active_schedules()

        assignments = []
        for schedule in active_schedules:
            operator_assignments = schedule.get_assignments_for_operator(operator_id)

            # Filter by date range
            filtered_assignments = [
                assignment
                for assignment in operator_assignments
                if assignment.start_time >= start_date
                and assignment.end_time <= end_date
            ]

            assignments.extend(filtered_assignments)

        # Convert to response format
        return [
            {
                "task_id": assignment.task_id,
                "machine_id": assignment.machine_id,
                "start_time": assignment.start_time,
                "end_time": assignment.end_time,
                "setup_duration_minutes": assignment.setup_duration.minutes,
                "processing_duration_minutes": assignment.processing_duration.minutes,
                "schedule_id": schedule.id,  # Would need to track this in assignment
            }
            for assignment in sorted(assignments, key=lambda a: a.start_time)
        ]

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator with ID {operator_id} not found",
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


@router.get(
    "/utilization",
    summary="Get resource utilization",
    description="Get utilization statistics for machines and operators over a time period.",
    response_model=dict,
)
async def get_resource_utilization(
    start_date: datetime = Query(..., description="Start date for utilization period"),
    end_date: datetime = Query(..., description="End date for utilization period"),
    resource_type: str = Query(
        "all", description="Resource type: machine, operator, or all"
    ),
    zone_filter: str | None = Query(None, description="Filter by production zone"),
    current_user: CurrentUser = Depends(),
    machine_repo: MachineRepositoryDep = Depends(),
    operator_repo: OperatorRepositoryDep = Depends(),
    schedule_repo: ScheduleRepositoryDep = Depends(),
) -> dict:
    """Get resource utilization statistics."""
    try:
        # Validate parameters
        if end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date",
            )

        valid_types = ["machine", "operator", "all"]
        if resource_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resource type must be one of: {', '.join(valid_types)}",
            )

        utilization_data = {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "duration_hours": (end_date - start_date).total_seconds() / 3600,
            },
            "machines": {},
            "operators": {},
            "summary": {},
        }

        # Get schedules in the time period
        schedules = await schedule_repo.find_schedules_in_period(start_date, end_date)

        # Calculate machine utilization
        if resource_type in ["machine", "all"]:
            machines = await machine_repo.find_with_filters(
                {"zone": zone_filter} if zone_filter else {}
            )

            machine_utilization = {}
            total_machine_hours = 0
            busy_machine_hours = 0

            for machine in machines:
                busy_time = 0
                assignment_count = 0

                for schedule in schedules:
                    machine_assignments = schedule.get_assignments_for_machine(
                        machine.id
                    )
                    for assignment in machine_assignments:
                        if (
                            assignment.start_time < end_date
                            and assignment.end_time > start_date
                        ):
                            # Calculate overlap with our time period
                            overlap_start = max(assignment.start_time, start_date)
                            overlap_end = min(assignment.end_time, end_date)
                            overlap_minutes = (
                                overlap_end - overlap_start
                            ).total_seconds() / 60
                            busy_time += overlap_minutes
                            assignment_count += 1

                total_period_minutes = (end_date - start_date).total_seconds() / 60
                utilization_percent = (
                    (busy_time / total_period_minutes * 100)
                    if total_period_minutes > 0
                    else 0
                )

                machine_utilization[str(machine.id)] = {
                    "name": machine.name,
                    "zone": getattr(machine, "zone", None),
                    "busy_hours": busy_time / 60,
                    "utilization_percent": round(utilization_percent, 2),
                    "assignment_count": assignment_count,
                }

                total_machine_hours += total_period_minutes / 60
                busy_machine_hours += busy_time / 60

            utilization_data["machines"] = machine_utilization
            utilization_data["summary"]["machine_utilization_percent"] = (
                round(busy_machine_hours / total_machine_hours * 100, 2)
                if total_machine_hours > 0
                else 0
            )

        # Calculate operator utilization
        if resource_type in ["operator", "all"]:
            operators = await operator_repo.find_with_filters(
                {"zone": zone_filter} if zone_filter else {}
            )

            operator_utilization = {}
            total_operator_hours = 0
            busy_operator_hours = 0

            for operator in operators:
                busy_time = 0
                assignment_count = 0

                for schedule in schedules:
                    operator_assignments = schedule.get_assignments_for_operator(
                        operator.id
                    )
                    for assignment in operator_assignments:
                        if (
                            assignment.start_time < end_date
                            and assignment.end_time > start_date
                        ):
                            # Calculate overlap with our time period
                            overlap_start = max(assignment.start_time, start_date)
                            overlap_end = min(assignment.end_time, end_date)
                            overlap_minutes = (
                                overlap_end - overlap_start
                            ).total_seconds() / 60
                            busy_time += overlap_minutes
                            assignment_count += 1

                total_period_minutes = (end_date - start_date).total_seconds() / 60
                utilization_percent = (
                    (busy_time / total_period_minutes * 100)
                    if total_period_minutes > 0
                    else 0
                )

                operator_utilization[str(operator.id)] = {
                    "name": operator.name,
                    "zone": getattr(operator, "zone", None),
                    "busy_hours": busy_time / 60,
                    "utilization_percent": round(utilization_percent, 2),
                    "assignment_count": assignment_count,
                }

                total_operator_hours += total_period_minutes / 60
                busy_operator_hours += busy_time / 60

            utilization_data["operators"] = operator_utilization
            utilization_data["summary"]["operator_utilization_percent"] = (
                round(busy_operator_hours / total_operator_hours * 100, 2)
                if total_operator_hours > 0
                else 0
            )

        return utilization_data

    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}",
        )


# Helper functions for DTO conversion


def _convert_machine_to_resource_summary(machine: Machine) -> ResourceSummaryResponse:
    """Convert Machine domain entity to ResourceSummaryResponse DTO."""
    return ResourceSummaryResponse(
        resource_id=machine.id,
        resource_type="machine",
        name=machine.name,
        status=machine.status.value if hasattr(machine, "status") else "unknown",
        zone=getattr(machine, "zone", None),
        capabilities=getattr(machine, "capabilities", []),
        current_utilization_percent=getattr(
            machine, "current_utilization_percent", 0.0
        ),
        is_available=getattr(machine, "is_available", True),
    )


def _convert_operator_to_resource_summary(
    operator: Operator,
) -> ResourceSummaryResponse:
    """Convert Operator domain entity to ResourceSummaryResponse DTO."""
    return ResourceSummaryResponse(
        resource_id=operator.id,
        resource_type="operator",
        name=operator.name,
        status=operator.status.value if hasattr(operator, "status") else "unknown",
        zone=getattr(operator, "zone", None),
        capabilities=getattr(operator, "skills", []),
        current_utilization_percent=getattr(
            operator, "current_utilization_percent", 0.0
        ),
        is_available=getattr(operator, "is_available", True),
    )
