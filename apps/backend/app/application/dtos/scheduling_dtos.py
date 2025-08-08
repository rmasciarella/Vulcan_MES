"""
Scheduling Data Transfer Objects.

This module contains DTOs for scheduling operations including schedule creation,
optimization requests, resource assignments, and status responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, validator


class CreateScheduleRequest(BaseModel):
    """DTO for creating a new production schedule."""

    name: str = Field(..., min_length=1, max_length=100, description="Schedule name")
    description: str | None = Field(
        None, max_length=500, description="Schedule description"
    )
    job_ids: list[UUID] = Field(
        ..., min_items=1, description="List of job IDs to include in schedule"
    )
    start_time: datetime = Field(..., description="Schedule start time")
    end_time: datetime | None = Field(
        None, description="Schedule end time (defaults to start + 30 days)"
    )
    planning_horizon_days: int = Field(
        30, ge=1, le=365, description="Planning horizon in days"
    )
    created_by: str | None = Field(
        None, max_length=100, description="Who created the schedule"
    )

    @validator("end_time")
    def validate_end_after_start(cls, v, values):
        """Validate end time is after start time."""
        if v and "start_time" in values and v <= values["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "Weekly Production Schedule",
                "description": "Production schedule for the week of Jan 15-22",
                "job_ids": [
                    "123e4567-e89b-12d3-a456-426614174001",
                    "123e4567-e89b-12d3-a456-426614174002",
                ],
                "start_time": "2024-01-15T08:00:00Z",
                "end_time": "2024-01-22T17:00:00Z",
                "planning_horizon_days": 7,
                "created_by": "scheduler.admin",
            }
        }


class OptimizeScheduleRequest(BaseModel):
    """DTO for schedule optimization request."""

    schedule_id: UUID = Field(..., description="Schedule ID to optimize")
    optimization_parameters: dict[str, Any] | None = Field(
        default_factory=dict, description="Optimization parameters"
    )
    max_time_seconds: int = Field(
        300, ge=10, le=3600, description="Maximum optimization time"
    )
    enable_hierarchical_optimization: bool = Field(
        True, description="Enable hierarchical optimization"
    )
    primary_objective: str = Field(
        "makespan", description="Primary optimization objective"
    )
    secondary_objective: str = Field(
        "cost", description="Secondary optimization objective"
    )

    @validator("primary_objective")
    def validate_primary_objective(cls, v):
        """Validate primary objective."""
        valid_objectives = ["makespan", "tardiness", "cost", "utilization"]
        if v not in valid_objectives:
            raise ValueError(
                f"Primary objective must be one of: {', '.join(valid_objectives)}"
            )
        return v

    class Config:
        schema_extra = {
            "example": {
                "schedule_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_time_seconds": 600,
                "enable_hierarchical_optimization": True,
                "primary_objective": "makespan",
                "secondary_objective": "cost",
            }
        }


class TaskAssignmentResponse(BaseModel):
    """DTO for task assignment in schedule response."""

    task_id: UUID
    job_id: UUID
    machine_id: UUID
    operator_ids: list[UUID]
    start_time: datetime
    end_time: datetime
    setup_duration_minutes: int
    processing_duration_minutes: int
    total_duration_minutes: int
    sequence_in_job: int
    is_critical_path: bool = False

    class Config:
        schema_extra = {
            "example": {
                "task_id": "123e4567-e89b-12d3-a456-426614174010",
                "job_id": "123e4567-e89b-12d3-a456-426614174001",
                "machine_id": "123e4567-e89b-12d3-a456-426614174020",
                "operator_ids": ["123e4567-e89b-12d3-a456-426614174030"],
                "start_time": "2024-01-15T08:00:00Z",
                "end_time": "2024-01-15T09:30:00Z",
                "setup_duration_minutes": 15,
                "processing_duration_minutes": 75,
                "total_duration_minutes": 90,
                "sequence_in_job": 1,
                "is_critical_path": True,
            }
        }


class ScheduleMetricsResponse(BaseModel):
    """DTO for schedule performance metrics."""

    makespan_minutes: int
    total_tardiness_minutes: int
    total_cost: float
    machine_utilization_percent: float
    operator_utilization_percent: float
    jobs_on_time: int
    jobs_late: int
    critical_path_jobs: int
    constraint_violations: list[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "makespan_minutes": 7200,
                "total_tardiness_minutes": 240,
                "total_cost": 15750.50,
                "machine_utilization_percent": 78.5,
                "operator_utilization_percent": 65.2,
                "jobs_on_time": 8,
                "jobs_late": 2,
                "critical_path_jobs": 3,
                "constraint_violations": [],
            }
        }


class ScheduleResponse(BaseModel):
    """DTO for schedule response with full details."""

    id: UUID
    name: str
    description: str | None
    status: str
    job_ids: list[UUID]
    start_time: datetime
    end_time: datetime | None
    planning_horizon_days: int

    # Schedule content
    task_assignments: list[TaskAssignmentResponse] = Field(default_factory=list)

    # Metrics
    metrics: ScheduleMetricsResponse | None = None

    # Validation
    is_valid: bool
    constraint_violations: list[str] = Field(default_factory=list)

    # Metadata
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Weekly Production Schedule",
                "description": "Production schedule for the week of Jan 15-22",
                "status": "published",
                "job_ids": [
                    "123e4567-e89b-12d3-a456-426614174001",
                    "123e4567-e89b-12d3-a456-426614174002",
                ],
                "start_time": "2024-01-15T08:00:00Z",
                "end_time": "2024-01-22T17:00:00Z",
                "planning_horizon_days": 7,
                "is_valid": True,
                "created_at": "2024-01-10T10:00:00Z",
                "updated_at": "2024-01-12T14:30:00Z",
            }
        }


class ScheduleSummaryResponse(BaseModel):
    """DTO for schedule summary information."""

    id: UUID
    name: str
    status: str
    job_count: int
    task_count: int
    start_time: datetime
    end_time: datetime | None
    is_valid: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Weekly Production Schedule",
                "status": "published",
                "job_count": 5,
                "task_count": 25,
                "start_time": "2024-01-15T08:00:00Z",
                "end_time": "2024-01-22T17:00:00Z",
                "is_valid": True,
                "created_at": "2024-01-10T10:00:00Z",
                "updated_at": "2024-01-12T14:30:00Z",
            }
        }


class ResourceAvailabilityRequest(BaseModel):
    """DTO for checking resource availability."""

    resource_type: str = Field(
        ..., description="Type of resource (machine, operator, all)"
    )
    start_time: datetime = Field(..., description="Start time window")
    end_time: datetime = Field(..., description="End time window")
    zone_filter: str | None = Field(None, description="Filter by production zone")
    skill_requirements: list[str] | None = Field(
        None, description="Required skills for operators"
    )

    @validator("resource_type")
    def validate_resource_type(cls, v):
        """Validate resource type."""
        valid_types = ["machine", "operator", "all"]
        if v not in valid_types:
            raise ValueError(f"Resource type must be one of: {', '.join(valid_types)}")
        return v

    @validator("end_time")
    def validate_end_after_start(cls, v, values):
        """Validate end time is after start time."""
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    class Config:
        schema_extra = {
            "example": {
                "resource_type": "all",
                "start_time": "2024-01-15T08:00:00Z",
                "end_time": "2024-01-15T17:00:00Z",
                "zone_filter": "Assembly",
                "skill_requirements": ["welding", "inspection"],
            }
        }


class ResourceSummaryResponse(BaseModel):
    """DTO for resource summary information."""

    resource_id: UUID
    resource_type: str
    name: str
    status: str
    zone: str | None
    capabilities: list[str] = Field(default_factory=list)
    current_utilization_percent: float
    is_available: bool

    class Config:
        schema_extra = {
            "example": {
                "resource_id": "123e4567-e89b-12d3-a456-426614174020",
                "resource_type": "machine",
                "name": "CNC Machine 001",
                "status": "operational",
                "zone": "Machining",
                "capabilities": ["milling", "drilling", "tapping"],
                "current_utilization_percent": 75.5,
                "is_available": True,
            }
        }


class ResourceAvailabilityResponse(BaseModel):
    """DTO for resource availability response."""

    machines: list[ResourceSummaryResponse] = Field(default_factory=list)
    operators: list[ResourceSummaryResponse] = Field(default_factory=list)
    availability_summary: dict[str, int] = Field(default_factory=dict)
    time_window: dict[str, datetime]

    class Config:
        schema_extra = {
            "example": {
                "availability_summary": {
                    "available_machines": 8,
                    "available_operators": 12,
                    "total_machines": 10,
                    "total_operators": 15,
                },
                "time_window": {
                    "start_time": "2024-01-15T08:00:00Z",
                    "end_time": "2024-01-15T17:00:00Z",
                },
            }
        }


class ScheduleStatusRequest(BaseModel):
    """DTO for schedule status updates."""

    action: str = Field(
        ..., description="Action to perform (publish, activate, complete, cancel)"
    )
    reason: str | None = Field(
        None, max_length=200, description="Reason for status change"
    )

    @validator("action")
    def validate_action(cls, v):
        """Validate action type."""
        valid_actions = ["publish", "activate", "complete", "cancel"]
        if v not in valid_actions:
            raise ValueError(f"Action must be one of: {', '.join(valid_actions)}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "action": "publish",
                "reason": "Schedule validated and ready for production",
            }
        }


class ScheduleStatusResponse(BaseModel):
    """DTO for schedule status response."""

    schedule_id: UUID
    old_status: str
    new_status: str
    action: str
    reason: str | None
    timestamp: datetime
    success: bool
    message: str

    class Config:
        schema_extra = {
            "example": {
                "schedule_id": "123e4567-e89b-12d3-a456-426614174000",
                "old_status": "draft",
                "new_status": "published",
                "action": "publish",
                "reason": "Schedule validated and ready for production",
                "timestamp": "2024-01-15T10:00:00Z",
                "success": True,
                "message": "Schedule published successfully",
            }
        }


class OptimizationStatusResponse(BaseModel):
    """DTO for optimization status response."""

    schedule_id: UUID
    status: str  # "running", "completed", "failed", "cancelled"
    progress_percent: float
    elapsed_time_seconds: float
    estimated_completion_seconds: float | None
    current_objective_value: float | None
    best_objective_value: float | None
    iterations_completed: int
    message: str

    class Config:
        schema_extra = {
            "example": {
                "schedule_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "running",
                "progress_percent": 65.5,
                "elapsed_time_seconds": 120.5,
                "estimated_completion_seconds": 45.2,
                "current_objective_value": 7350.0,
                "best_objective_value": 7200.0,
                "iterations_completed": 1250,
                "message": "Optimization in progress - 65% complete",
            }
        }
