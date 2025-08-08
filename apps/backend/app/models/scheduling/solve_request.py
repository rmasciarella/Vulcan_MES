"""
Solve API Request/Response Models

Defines the API contract for the /solve endpoint that accepts scheduling problems
and returns optimized schedules using OR-Tools CP-SAT solver.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, validator
from sqlmodel import SQLModel

from .base import PriorityLevel


class OptimizationParameters(BaseModel):
    """Configuration parameters for optimization engine."""

    max_time_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Maximum solver time in seconds (10s to 1 hour)",
    )
    num_workers: int = Field(
        default=8, ge=1, le=16, description="Number of parallel search workers"
    )
    horizon_days: int = Field(
        default=30, ge=1, le=90, description="Scheduling horizon in days"
    )
    enable_hierarchical_optimization: bool = Field(
        default=True,
        description="Use two-phase optimization (makespan+tardiness, then cost)",
    )
    primary_objective_weight: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Weight for tardiness vs makespan in primary objective",
    )
    cost_optimization_tolerance: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="Tolerance for cost optimization phase (0-50%)",
    )


class BusinessConstraints(BaseModel):
    """Business rules and constraints for scheduling."""

    work_start_hour: int = Field(
        default=7, ge=0, le=23, description="Work start hour (0-23)"
    )
    work_end_hour: int = Field(
        default=16, ge=1, le=24, description="Work end hour (1-24)"
    )
    lunch_start_hour: int = Field(
        default=12, ge=0, le=23, description="Lunch start hour (0-23)"
    )
    lunch_duration_minutes: int = Field(
        default=45, ge=15, le=120, description="Lunch duration in minutes"
    )
    holiday_days: list[int] = Field(
        default_factory=list,
        description="List of holiday days within horizon (1-indexed)",
    )
    enforce_business_hours: bool = Field(
        default=True, description="Enforce business hours for attended operations"
    )

    @validator("work_end_hour")
    def end_after_start(cls, v, values):
        """Work end hour must be after start hour."""
        if "work_start_hour" in values and v <= values["work_start_hour"]:
            raise ValueError("Work end hour must be after start hour")
        return v

    @validator("holiday_days")
    def validate_holidays(cls, v):
        """Holiday days must be positive and unique."""
        if any(day <= 0 for day in v):
            raise ValueError("Holiday days must be positive integers")
        if len(v) != len(set(v)):
            raise ValueError("Holiday days must be unique")
        return sorted(v)


class SolveJobRequest(BaseModel):
    """Job specification for solving."""

    job_number: str = Field(..., min_length=1, max_length=50)
    priority: PriorityLevel = Field(default=PriorityLevel.NORMAL)
    due_date: datetime | None = None
    quantity: int = Field(default=1, ge=1, le=10000)
    customer_name: str | None = Field(None, max_length=255)
    part_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=1000)

    # Task specifications for this job
    task_sequences: list[int] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of operation sequence numbers (1-100) for this job",
    )

    @validator("task_sequences")
    def validate_sequences(cls, v):
        """Task sequences must be valid operation numbers."""
        if not all(1 <= seq <= 100 for seq in v):
            raise ValueError("Task sequences must be between 1 and 100")
        if len(v) != len(set(v)):
            raise ValueError("Task sequences must be unique")
        return sorted(v)


class SolveRequest(BaseModel):
    """Complete scheduling problem specification for /solve endpoint."""

    problem_name: str = Field(
        default="Scheduling Problem",
        min_length=1,
        max_length=255,
        description="Descriptive name for this scheduling problem",
    )

    schedule_start_time: datetime = Field(
        default_factory=lambda: datetime.now(datetime.timezone.utc),
        description="When the schedule should start",
    )

    # Job specifications
    jobs: list[SolveJobRequest] = Field(
        ..., min_items=1, max_items=50, description="Jobs to be scheduled"
    )

    # Optional resource constraints
    available_machine_ids: list[UUID] | None = Field(
        None, description="Specific machines to use (if None, uses all available)"
    )
    available_operator_ids: list[UUID] | None = Field(
        None, description="Specific operators to use (if None, uses all available)"
    )

    # Optimization configuration
    optimization_parameters: OptimizationParameters = Field(
        default_factory=OptimizationParameters, description="Solver configuration"
    )

    business_constraints: BusinessConstraints = Field(
        default_factory=BusinessConstraints,
        description="Business rules and working hours",
    )

    @validator("jobs")
    def validate_unique_job_numbers(cls, v):
        """Job numbers must be unique within the problem."""
        job_numbers = [job.job_number for job in v]
        if len(job_numbers) != len(set(job_numbers)):
            raise ValueError("Job numbers must be unique")
        return v

    @validator("schedule_start_time")
    def validate_start_time(cls, v):
        """Schedule start time cannot be more than 30 days in the past."""
        from datetime import timezone

        now = datetime.now(timezone.utc)
        # Make both datetimes timezone-aware for comparison
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if (now - v).days > 30:
            raise ValueError(
                "Schedule start time cannot be more than 30 days in the past"
            )
        return v


class TaskAssignment(BaseModel):
    """Individual task assignment in the solution."""

    job_number: str
    operation_sequence: int = Field(ge=1, le=100)

    # Timing
    planned_start_time: datetime
    planned_end_time: datetime
    setup_duration_minutes: int = Field(ge=0)
    processing_duration_minutes: int = Field(ge=0)

    # Resource assignments
    assigned_machine_id: UUID
    assigned_operator_ids: list[UUID] = Field(default_factory=list)

    # Metadata
    is_critical_path: bool = Field(default=False)
    routing_option: int = Field(
        default=0, ge=0, description="Which routing option was selected"
    )


class JobSolution(BaseModel):
    """Solution details for a single job."""

    job_number: str
    completion_time: datetime
    due_date: datetime | None = None
    tardiness_minutes: float = Field(ge=0.0)
    total_processing_time_minutes: float = Field(ge=0.0)
    is_on_time: bool
    task_assignments: list[TaskAssignment]


class SolutionMetrics(BaseModel):
    """Overall solution quality metrics."""

    makespan_minutes: float = Field(ge=0.0, description="Total schedule duration")
    total_tardiness_minutes: float = Field(
        ge=0.0, description="Sum of all job tardiness"
    )
    total_operator_cost: float = Field(ge=0.0, description="Total labor cost")

    # Performance metrics
    machine_utilization_percent: float = Field(ge=0.0, le=100.0)
    operator_utilization_percent: float = Field(ge=0.0, le=100.0)

    # Solution quality
    jobs_on_time: int = Field(ge=0)
    jobs_late: int = Field(ge=0)
    critical_path_jobs: int = Field(ge=0)

    # Solver statistics
    solve_time_seconds: float = Field(ge=0.0)
    solver_status: str
    gap_percent: float | None = Field(
        None, ge=0.0, le=100.0, description="Optimality gap if not optimal"
    )


class SolveResponse(SQLModel):
    """Complete solution returned by /solve endpoint."""

    # Request identification
    problem_name: str
    request_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(datetime.timezone.utc)
    )

    # Solution status
    status: str = Field(
        ..., description="OPTIMAL, FEASIBLE, INFEASIBLE, TIMEOUT, ERROR"
    )
    success: bool
    message: str | None = None

    # Solution data (only if successful)
    jobs: list[JobSolution] = Field(default_factory=list)
    metrics: SolutionMetrics | None = None

    # Schedule metadata
    schedule_start_time: datetime | None = None
    schedule_end_time: datetime | None = None
    total_jobs: int = Field(default=0, ge=0)
    total_tasks: int = Field(default=0, ge=0)

    # Error details (only if failed)
    error_code: str | None = None
    error_details: dict[str, Any] | None = None

    # Performance tracking
    processing_time_seconds: float = Field(default=0.0, ge=0.0)

    class Config:
        schema_extra = {
            "example": {
                "problem_name": "Weekly Production Schedule",
                "request_timestamp": "2024-01-15T08:00:00Z",
                "status": "OPTIMAL",
                "success": True,
                "message": "Optimal solution found",
                "jobs": [
                    {
                        "job_number": "JOB001",
                        "completion_time": "2024-01-17T15:30:00Z",
                        "due_date": "2024-01-18T16:00:00Z",
                        "tardiness_minutes": 0.0,
                        "total_processing_time_minutes": 480.0,
                        "is_on_time": True,
                        "task_assignments": [
                            {
                                "job_number": "JOB001",
                                "operation_sequence": 10,
                                "planned_start_time": "2024-01-15T08:00:00Z",
                                "planned_end_time": "2024-01-15T10:00:00Z",
                                "setup_duration_minutes": 15,
                                "processing_duration_minutes": 105,
                                "assigned_machine_id": "00000000-0000-0000-0000-000000000001",
                                "assigned_operator_ids": [
                                    "00000000-0000-0000-0000-000000000002"
                                ],
                                "is_critical_path": True,
                                "routing_option": 0,
                            }
                        ],
                    }
                ],
                "metrics": {
                    "makespan_minutes": 2880.0,
                    "total_tardiness_minutes": 0.0,
                    "total_operator_cost": 1250.0,
                    "machine_utilization_percent": 65.5,
                    "operator_utilization_percent": 72.3,
                    "jobs_on_time": 5,
                    "jobs_late": 0,
                    "critical_path_jobs": 2,
                    "solve_time_seconds": 45.2,
                    "solver_status": "OPTIMAL",
                    "gap_percent": 0.0,
                },
                "schedule_start_time": "2024-01-15T08:00:00Z",
                "schedule_end_time": "2024-01-17T16:00:00Z",
                "total_jobs": 5,
                "total_tasks": 25,
                "processing_time_seconds": 47.8,
            }
        }


class SolveErrorResponse(SQLModel):
    """Error response for failed solve requests."""

    problem_name: str
    request_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(datetime.timezone.utc)
    )
    status: str = "ERROR"
    success: bool = False
    message: str
    error_code: str
    error_details: dict[str, Any] | None = None
    processing_time_seconds: float = Field(default=0.0, ge=0.0)

    class Config:
        schema_extra = {
            "example": {
                "problem_name": "Invalid Production Schedule",
                "request_timestamp": "2024-01-15T08:00:00Z",
                "status": "ERROR",
                "success": False,
                "message": "No feasible solution found",
                "error_code": "NO_FEASIBLE_SOLUTION",
                "error_details": {
                    "reason": "Resource constraints cannot be satisfied",
                    "conflicting_jobs": ["JOB001", "JOB003"],
                    "suggested_actions": [
                        "Reduce job quantities",
                        "Extend schedule horizon",
                    ],
                },
                "processing_time_seconds": 15.3,
            }
        }
