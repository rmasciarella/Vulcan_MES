"""
Domain-Driven Scheduling API Routes

Additional FastAPI routes for domain-specific scheduling functionality.
These routes expose the rich domain model and services.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.domain.scheduling.factories.job_factory import JobFactory
from app.domain.scheduling.services.critical_sequence_manager import (
    CriticalSequenceManager,
)
from app.domain.scheduling.services.schedule_validator import ScheduleValidator
from app.domain.scheduling.value_objects.business_calendar import BusinessCalendar
from app.domain.shared.exceptions import BusinessRuleError, ValidationError

router = APIRouter(prefix="/domain", tags=["domain-scheduling"])


# Request/Response Models
class CreateStandardJobRequest(BaseModel):
    """Request for creating a standard job."""

    job_number: str
    operation_count: int = 100
    priority: int = 0
    due_date: datetime | None = None


class JobSummaryResponse(BaseModel):
    """Response with job summary."""

    id: str
    job_number: str
    task_count: int
    priority: str
    due_date: str | None = None
    critical_task_count: int
    estimated_duration_hours: float


class BusinessCalendarResponse(BaseModel):
    """Response with business calendar info."""

    is_working_time: bool
    next_working_time: str | None = None
    calendar_description: str


class SkillAnalysisResponse(BaseModel):
    """Response with skill analysis results."""

    operators_analyzed: int
    total_skills: int
    skill_gaps: list[dict[str, Any]]
    training_priorities: list[dict[str, Any]]
    coverage_percentage: float


class CriticalPathResponse(BaseModel):
    """Response with critical path analysis."""

    critical_sequences_count: int
    total_critical_tasks: int
    critical_path_duration_hours: float
    bottleneck_operations: list[dict[str, Any]]


class ValidationResponse(BaseModel):
    """Response with validation results."""

    is_valid: bool
    violations: list[str]
    warnings: list[str]
    validation_timestamp: str


# Job Factory Endpoints
@router.post("/jobs/standard", response_model=JobSummaryResponse)
async def create_standard_job(request: CreateStandardJobRequest):
    """
    Create a standard manufacturing job using the domain factory.

    This endpoint demonstrates the use of JobFactory.create_standard_job()
    as specified in DOMAIN.md, creating a job with 90% single machine options
    and 10% with 2 machine options.
    """
    try:
        job = JobFactory.create_standard_job(
            job_number=request.job_number,
            operation_count=request.operation_count,
            priority=request.priority,
            due_date=request.due_date,
        )

        # Calculate metrics
        critical_tasks = job.get_critical_tasks()
        tasks = job.get_tasks_in_sequence()

        # Estimate duration from task machine options
        total_minutes = 0
        for task in tasks:
            if task.machine_options:
                min_duration = min(
                    opt.total_duration().minutes for opt in task.machine_options
                )
                total_minutes += float(min_duration)

        return JobSummaryResponse(
            id=str(job.id),
            job_number=job.job_number,
            task_count=len(tasks),
            priority=job.priority.value if hasattr(job, "priority") else "normal",
            due_date=job.due_date.isoformat() if job.due_date else None,
            critical_task_count=len(critical_tasks),
            estimated_duration_hours=total_minutes / 60,
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}",
        )
    except BusinessRuleError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Business rule violation: {e.message}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {str(e)}",
        )


@router.post("/jobs/rush", response_model=JobSummaryResponse)
async def create_rush_job(
    job_number: str,
    operation_count: int = Query(50, description="Number of operations"),
    due_hours: int = Query(24, description="Hours until due date"),
):
    """Create a rush job with high priority and tight deadline."""
    try:
        job = JobFactory.create_rush_job(
            job_number=job_number, operation_count=operation_count, due_hours=due_hours
        )

        tasks = job.get_tasks_in_sequence()
        critical_tasks = job.get_critical_tasks()

        total_minutes = 0
        for task in tasks:
            if task.machine_options:
                min_duration = min(
                    opt.total_duration().minutes for opt in task.machine_options
                )
                total_minutes += float(min_duration)

        return JobSummaryResponse(
            id=str(job.id),
            job_number=job.job_number,
            task_count=len(tasks),
            priority=job.priority.value if hasattr(job, "priority") else "critical",
            due_date=job.due_date.isoformat() if job.due_date else None,
            critical_task_count=len(critical_tasks),
            estimated_duration_hours=total_minutes / 60,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rush job creation failed: {str(e)}",
        )


# Business Calendar Endpoints
@router.get("/calendar/working-time", response_model=BusinessCalendarResponse)
async def check_working_time(
    check_datetime: datetime = Query(..., description="DateTime to check"),
):
    """
    Check if a datetime falls within business working hours.
    Uses BusinessCalendar.standard_calendar() as specified in DOMAIN.md.
    """
    try:
        calendar = BusinessCalendar.standard_calendar()
        is_working = calendar.is_working_time(check_datetime)
        next_working = None

        if not is_working:
            next_working = calendar.next_working_time(check_datetime)

        return BusinessCalendarResponse(
            is_working_time=is_working,
            next_working_time=next_working.isoformat() if next_working else None,
            calendar_description=str(calendar),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Working time check failed: {str(e)}",
        )


@router.get("/calendar/standard", response_model=dict)
async def get_standard_calendar():
    """Get the standard business calendar configuration."""
    try:
        calendar = BusinessCalendar.standard_calendar()

        # Convert to serializable format
        weekday_hours = {}
        for weekday, hours in calendar.weekday_hours.items():
            weekday_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            weekday_hours[weekday_names[weekday]] = {
                "start": hours.start_time.strftime("%H:%M"),
                "end": hours.end_time.strftime("%H:%M"),
            }

        return {
            "weekday_hours": weekday_hours,
            "holidays": [d.isoformat() for d in calendar.holidays],
            "description": str(calendar),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calendar retrieval failed: {str(e)}",
        )


# Skill Analysis Endpoints
@router.get("/skills/analysis", response_model=SkillAnalysisResponse)
async def analyze_skills():
    """
    Demonstrate skill analysis capabilities using SkillMatcher.
    In a real implementation, this would analyze actual operator data.
    """
    try:
        # This is a demonstration - in real implementation:
        # operators = operator_repository.find_all()
        # machines = machine_repository.find_all()
        # skill_matcher = SkillMatcher()
        # ... perform actual analysis

        return SkillAnalysisResponse(
            operators_analyzed=0,  # Placeholder
            total_skills=0,  # Placeholder
            skill_gaps=[],  # Placeholder
            training_priorities=[],  # Placeholder
            coverage_percentage=85.5,  # Placeholder
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Skill analysis failed: {str(e)}",
        )


# Critical Path Analysis Endpoints
@router.get("/analysis/critical-path", response_model=CriticalPathResponse)
async def analyze_critical_path():
    """
    Demonstrate critical path analysis using CriticalSequenceManager.
    In a real implementation, this would analyze actual job data.
    """
    try:
        CriticalSequenceManager()

        # This is a demonstration - in real implementation:
        # jobs = job_repository.find_all()
        # bottlenecks = critical_mgr.identify_bottleneck_sequences(jobs)
        # ... perform actual analysis

        return CriticalPathResponse(
            critical_sequences_count=0,  # Placeholder
            total_critical_tasks=0,  # Placeholder
            critical_path_duration_hours=0.0,  # Placeholder
            bottleneck_operations=[],  # Placeholder
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Critical path analysis failed: {str(e)}",
        )


# Schedule Validation Endpoints
@router.post("/schedule/validate", response_model=ValidationResponse)
async def validate_schedule_constraints():
    """
    Demonstrate schedule validation using ScheduleValidator.
    In a real implementation, this would validate an actual schedule.
    """
    try:
        calendar = BusinessCalendar.standard_calendar()
        ScheduleValidator(calendar)

        # This is a demonstration - in real implementation:
        # schedule = schedule_repository.find_by_id(schedule_id)
        # job = job_repository.find_by_id(job_id)
        # is_valid, violations = validator.validate_complete(job, schedule)

        return ValidationResponse(
            is_valid=True,  # Placeholder
            violations=[],  # Placeholder
            warnings=[],  # Placeholder
            validation_timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schedule validation failed: {str(e)}",
        )


# Domain Model Demonstration Endpoints
@router.get("/demo/value-objects", response_model=dict)
async def demonstrate_value_objects():
    """
    Demonstrate the rich value objects from the domain model.
    Shows MachineOption, Duration, SkillProficiency, etc.
    """
    try:
        from datetime import date
        from uuid import uuid4

        from app.domain.scheduling.value_objects.duration import Duration
        from app.domain.scheduling.value_objects.machine_option import MachineOption
        from app.domain.scheduling.value_objects.skill_proficiency import (
            SkillProficiency,
            SkillType,
        )

        # Create example value objects
        duration = Duration.from_hours(2.5)
        machine_option = MachineOption.from_minutes(
            machine_id=uuid4(),
            setup_minutes=15,
            processing_minutes=90,
            requires_operator_full_duration=True,
        )
        skill = SkillProficiency.create(
            skill_type=SkillType.MACHINING, level=2, certified_date=date(2023, 1, 1)
        )

        return {
            "duration": {
                "minutes": float(duration.minutes),
                "hours": float(duration.hours),
                "string_repr": str(duration),
            },
            "machine_option": {
                "machine_id": str(machine_option.machine_id),
                "setup_duration": str(machine_option.setup_duration),
                "processing_duration": str(machine_option.processing_duration),
                "total_duration": str(machine_option.total_duration()),
                "requires_operator_full_duration": machine_option.requires_operator_full_duration,
            },
            "skill_proficiency": {
                "skill_type": str(skill.skill_type),
                "level": skill.level,
                "level_name": skill.level_name,
                "certified_date": skill.certified_date.isoformat(),
                "is_expired": skill.is_expired,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Value object demonstration failed: {str(e)}",
        )


@router.get("/demo/domain-services", response_model=dict)
async def demonstrate_domain_services():
    """
    Demonstrate the domain services capabilities.
    Shows SkillMatcher, CriticalSequenceManager, ScheduleValidator.
    """
    try:
        return {
            "skill_matcher": {
                "description": "Matches operators to machines based on skills",
                "capabilities": [
                    "find_qualified_operators",
                    "find_best_operator",
                    "rank_operators_by_skills",
                    "get_skill_gap_analysis",
                    "suggest_training_priorities",
                ],
            },
            "critical_sequence_manager": {
                "description": "Manages critical operation sequences",
                "capabilities": [
                    "identify_critical_sequences",
                    "calculate_sequence_duration",
                    "prioritize_job_sequence",
                    "find_critical_path_tasks",
                    "identify_bottleneck_sequences",
                ],
            },
            "schedule_validator": {
                "description": "Validates schedule constraints",
                "capabilities": [
                    "validate_precedence_constraints",
                    "validate_calendar_constraints",
                    "validate_resource_conflicts",
                    "validate_skill_requirements",
                    "validate_complete",
                ],
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Domain services demonstration failed: {str(e)}",
        )
