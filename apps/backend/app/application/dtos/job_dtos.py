"""
Job-related Data Transfer Objects.

This module contains DTOs for job creation, updates, and responses.
These DTOs provide a stable API interface independent of domain model changes.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator


class CreateJobRequest(BaseModel):
    """DTO for creating a new job."""

    job_number: str = Field(
        ..., min_length=1, max_length=50, description="Unique job number"
    )
    customer_name: str | None = Field(None, max_length=100, description="Customer name")
    part_number: str | None = Field(
        None, max_length=50, description="Part number being manufactured"
    )
    quantity: int = Field(1, ge=1, description="Quantity to produce")
    priority: str = Field(
        "normal", description="Priority level (low, normal, high, critical)"
    )
    due_date: datetime = Field(..., description="When job must be completed")
    notes: str | None = Field(None, max_length=1000, description="Additional notes")
    created_by: str | None = Field(
        None, max_length=100, description="Who created the job"
    )

    @validator("priority")
    def validate_priority(cls, v):
        """Validate priority is a valid enum value."""
        valid_priorities = ["low", "normal", "high", "critical"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v

    @validator("due_date")
    def validate_due_date_future(cls, v):
        """Validate due date is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Due date must be in the future")
        return v

    class Config:
        schema_extra = {
            "example": {
                "job_number": "JOB-2024-001",
                "customer_name": "Acme Corporation",
                "part_number": "WIDGET-123",
                "quantity": 10,
                "priority": "high",
                "due_date": "2024-12-31T23:59:59Z",
                "notes": "Rush order for important customer",
                "created_by": "john.doe",
            }
        }


class UpdateJobRequest(BaseModel):
    """DTO for updating an existing job."""

    customer_name: str | None = Field(None, max_length=100)
    part_number: str | None = Field(None, max_length=50)
    quantity: int | None = Field(None, ge=1)
    priority: str | None = None
    due_date: datetime | None = None
    notes: str | None = Field(None, max_length=1000)
    change_reason: str | None = Field(
        None, max_length=200, description="Reason for the change"
    )

    @validator("priority")
    def validate_priority(cls, v):
        """Validate priority is a valid enum value."""
        if v is not None:
            valid_priorities = ["low", "normal", "high", "critical"]
            if v not in valid_priorities:
                raise ValueError(
                    f"Priority must be one of: {', '.join(valid_priorities)}"
                )
        return v

    @validator("due_date")
    def validate_due_date_future(cls, v):
        """Validate due date is in the future if provided."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Due date must be in the future")
        return v

    class Config:
        schema_extra = {
            "example": {
                "customer_name": "Acme Corporation Updated",
                "quantity": 15,
                "priority": "critical",
                "change_reason": "Customer requested priority increase",
            }
        }


class TaskSummaryResponse(BaseModel):
    """DTO for task summary in job responses."""

    id: UUID
    sequence_in_job: int
    status: str
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    assigned_machine_id: UUID | None = None
    is_critical_path: bool = False
    delay_minutes: int = 0


class JobResponse(BaseModel):
    """DTO for job response with full details."""

    id: UUID
    job_number: str
    customer_name: str | None
    part_number: str | None
    quantity: int
    priority: str
    status: str

    # Dates
    release_date: datetime | None
    due_date: datetime
    planned_start_date: datetime | None
    planned_end_date: datetime | None
    actual_start_date: datetime | None
    actual_end_date: datetime | None

    # Progress
    current_operation_sequence: int
    completion_percentage: float
    task_count: int
    completed_task_count: int

    # Status indicators
    is_active: bool
    is_complete: bool
    is_overdue: bool
    days_until_due: float

    # Metadata
    notes: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    # Related data
    tasks: list[TaskSummaryResponse] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "job_number": "JOB-2024-001",
                "customer_name": "Acme Corporation",
                "part_number": "WIDGET-123",
                "quantity": 10,
                "priority": "high",
                "status": "in_progress",
                "release_date": "2024-01-15T08:00:00Z",
                "due_date": "2024-12-31T23:59:59Z",
                "planned_start_date": "2024-01-15T08:00:00Z",
                "planned_end_date": "2024-12-30T17:00:00Z",
                "current_operation_sequence": 5,
                "completion_percentage": 50.0,
                "task_count": 10,
                "completed_task_count": 5,
                "is_active": True,
                "is_complete": False,
                "is_overdue": False,
                "days_until_due": 350.5,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T08:30:00Z",
            }
        }


class JobSummaryResponse(BaseModel):
    """DTO for job summary information."""

    id: UUID
    job_number: str
    customer_name: str | None
    status: str
    priority: str
    due_date: datetime
    completion_percentage: float
    is_overdue: bool
    days_until_due: float
    task_count: int
    completed_task_count: int

    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "job_number": "JOB-2024-001",
                "customer_name": "Acme Corporation",
                "status": "in_progress",
                "priority": "high",
                "due_date": "2024-12-31T23:59:59Z",
                "completion_percentage": 50.0,
                "is_overdue": False,
                "days_until_due": 350.5,
                "task_count": 10,
                "completed_task_count": 5,
            }
        }


class JobListRequest(BaseModel):
    """DTO for requesting lists of jobs with filters."""

    statuses: list[str] | None = None
    priorities: list[str] | None = None
    customer_name: str | None = None
    search_term: str | None = None
    overdue_only: bool = False
    due_within_days: int | None = None
    limit: int | None = Field(None, ge=1, le=1000)
    offset: int = Field(0, ge=0)

    @validator("statuses")
    def validate_statuses(cls, v):
        """Validate all statuses are valid."""
        if v:
            valid_statuses = [
                "planned",
                "released",
                "in_progress",
                "completed",
                "on_hold",
                "cancelled",
            ]
            for status in v:
                if status not in valid_statuses:
                    raise ValueError(f"Invalid status: {status}")
        return v

    @validator("priorities")
    def validate_priorities(cls, v):
        """Validate all priorities are valid."""
        if v:
            valid_priorities = ["low", "normal", "high", "critical"]
            for priority in v:
                if priority not in valid_priorities:
                    raise ValueError(f"Invalid priority: {priority}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "statuses": ["released", "in_progress"],
                "priorities": ["high", "critical"],
                "customer_name": "Acme",
                "due_within_days": 30,
                "limit": 50,
                "offset": 0,
            }
        }


class JobStatisticsResponse(BaseModel):
    """DTO for job statistics."""

    status_counts: dict = Field(description="Count of jobs by status")
    overdue_count: int = Field(description="Number of overdue jobs")
    due_soon_count: int = Field(description="Number of jobs due soon")
    total_jobs: int = Field(description="Total number of jobs")
    active_jobs: int = Field(description="Number of active jobs")
    completion_rate: float = Field(description="Overall completion rate percentage")

    class Config:
        schema_extra = {
            "example": {
                "status_counts": {
                    "planned": 10,
                    "released": 15,
                    "in_progress": 25,
                    "completed": 100,
                    "on_hold": 3,
                    "cancelled": 2,
                },
                "overdue_count": 5,
                "due_soon_count": 12,
                "total_jobs": 155,
                "active_jobs": 40,
                "completion_rate": 64.5,
            }
        }
