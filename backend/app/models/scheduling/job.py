"""Job SQLModel for work orders and job management."""

from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from .base import JobStatus, PriorityLevel


class JobBase(SQLModel):
    """Base job fields."""

    job_number: str = Field(max_length=50, unique=True, index=True)
    customer_name: str | None = Field(default=None, max_length=100)
    part_number: str | None = Field(default=None, max_length=50)
    quantity: int = Field(default=1, gt=0, description="Number of items to produce")
    priority: PriorityLevel = Field(
        default=PriorityLevel.NORMAL, description="Job priority level"
    )
    status: JobStatus = Field(
        default=JobStatus.PLANNED, description="Current job status"
    )

    # Scheduling dates
    release_date: datetime | None = Field(default=None)
    due_date: datetime = Field(description="Job due date")
    planned_start_date: datetime | None = Field(default=None)
    planned_end_date: datetime | None = Field(default=None)
    actual_start_date: datetime | None = Field(default=None)
    actual_end_date: datetime | None = Field(default=None)

    # Progress tracking
    current_operation_sequence: int = Field(
        default=0, ge=0, le=100, description="Current operation position"
    )
    notes: str | None = Field(default=None)
    created_by: str | None = Field(default=None, max_length=50)


class Job(JobBase, table=True):
    """
    Job table model.

    Represents manufacturing work orders containing multiple tasks.
    Jobs coordinate the execution of operations in sequence.
    """

    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    tasks: list["Task"] = Relationship(back_populates="job", cascade_delete=True)

    # Note: Validation logic will be implemented in business layer


class JobCreate(JobBase):
    """Job creation model."""

    pass


class JobUpdate(SQLModel):
    """Job update model."""

    customer_name: str | None = Field(default=None, max_length=100)
    part_number: str | None = Field(default=None, max_length=50)
    quantity: int | None = Field(default=None, gt=0)
    priority: PriorityLevel | None = Field(default=None)
    status: JobStatus | None = Field(default=None)
    release_date: datetime | None = Field(default=None)
    due_date: datetime | None = Field(default=None)
    planned_start_date: datetime | None = Field(default=None)
    planned_end_date: datetime | None = Field(default=None)
    actual_start_date: datetime | None = Field(default=None)
    actual_end_date: datetime | None = Field(default=None)
    current_operation_sequence: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None)


class JobRead(JobBase):
    """Job read model."""

    id: int
    created_at: datetime
    updated_at: datetime


class JobReadWithTasks(JobRead):
    """Job read model with related tasks."""

    tasks: list["TaskRead"] = []


# Fix forward references - will be resolved by SQLModel
TaskRead = "TaskRead"
