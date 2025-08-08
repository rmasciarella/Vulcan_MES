"""Task SQLModel for individual work assignments and resource management."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, Column
from sqlalchemy import Text

from .base import AssignmentType, TaskStatus


class TaskBase(SQLModel):
    """Base task fields."""

    job_id: int = Field(foreign_key="jobs.id", index=True)
    operation_id: int = Field(foreign_key="operations.id", index=True)
    sequence_in_job: int = Field(
        ge=1, le=100, description="Task sequence within job (1-100)"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, description="Current task status"
    )

    department: str | None = Field(default="general", max_length=50, index=True)
    role_requirements_json: str | None = Field(default=None, sa_column=Column(Text))

    # Planning data
    planned_start_time: datetime | None = Field(default=None)
    planned_end_time: datetime | None = Field(default=None)
    planned_duration_minutes: int | None = Field(default=None, gt=0)
    planned_setup_minutes: int = Field(default=0, ge=0)

    # Execution data
    actual_start_time: datetime | None = Field(default=None)
    actual_end_time: datetime | None = Field(default=None)
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    actual_setup_minutes: int | None = Field(default=None, ge=0)

    # Resource assignment
    assigned_machine_id: int | None = Field(default=None, foreign_key="machines.id")

    # Tracking
    is_critical_path: bool = Field(
        default=False, description="Part of job's critical path"
    )
    delay_minutes: int = Field(default=0, ge=0, description="Total delay in minutes")
    rework_count: int = Field(default=0, ge=0, description="Number of rework cycles")
    notes: str | None = Field(default=None)


class Task(TaskBase, table=True):
    """
    Task table model.

    Represents individual work assignments within jobs.
    Tasks are instances of operations for specific jobs.
    """

    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    job: "Job" = Relationship(back_populates="tasks")
    assigned_machine: Optional["Machine"] = Relationship(back_populates="tasks")
    operator_assignments: list["TaskOperatorAssignment"] = Relationship(
        back_populates="task", cascade_delete=True
    )
    machine_options: list["TaskMachineOption"] = Relationship(
        back_populates="task", cascade_delete=True
    )

    # Note: Validation logic will be implemented in business layer


class TaskOperatorAssignmentBase(SQLModel):
    """Base task operator assignment fields."""

    task_id: int = Field(foreign_key="tasks.id")
    operator_id: int = Field(foreign_key="operators.id")
    assignment_type: AssignmentType = Field(description="Type of operator assignment")
    planned_start_time: datetime | None = Field(default=None)
    planned_end_time: datetime | None = Field(default=None)
    actual_start_time: datetime | None = Field(default=None)
    actual_end_time: datetime | None = Field(default=None)


class TaskOperatorAssignment(TaskOperatorAssignmentBase, table=True):
    """
    TaskOperatorAssignment table model.

    Represents operator assignments to tasks with timing information.
    """

    __tablename__ = "task_operator_assignments"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    task: "Task" = Relationship(back_populates="operator_assignments")
    operator: "Operator" = Relationship(back_populates="task_assignments")


class TaskMachineOptionBase(SQLModel):
    """Base task machine option fields."""

    task_id: int = Field(foreign_key="tasks.id")
    machine_id: int = Field(foreign_key="machines.id")
    is_preferred: bool = Field(
        default=False, description="Preferred machine for this task"
    )
    estimated_duration_minutes: int = Field(
        gt=0, description="Estimated processing duration"
    )
    estimated_setup_minutes: int = Field(
        default=0, ge=0, description="Estimated setup duration"
    )


class TaskMachineOption(TaskMachineOptionBase, table=True):
    """
    TaskMachineOption table model.

    Represents machine options available for a specific task.
    """

    __tablename__ = "task_machine_options"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    task: "Task" = Relationship(back_populates="machine_options")


class TaskCreate(TaskBase):
    """Task creation model."""

    pass


class TaskUpdate(SQLModel):
    """Task update model."""

    status: TaskStatus | None = Field(default=None)
    planned_start_time: datetime | None = Field(default=None)
    planned_end_time: datetime | None = Field(default=None)
    planned_duration_minutes: int | None = Field(default=None, gt=0)
    planned_setup_minutes: int | None = Field(default=None, ge=0)
    actual_start_time: datetime | None = Field(default=None)
    actual_end_time: datetime | None = Field(default=None)
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    actual_setup_minutes: int | None = Field(default=None, ge=0)
    assigned_machine_id: int | None = Field(default=None)
    is_critical_path: bool | None = Field(default=None)
    delay_minutes: int | None = Field(default=None, ge=0)
    rework_count: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None)


class TaskRead(TaskBase):
    """Task read model."""

    id: int
    created_at: datetime
    updated_at: datetime


class TaskReadWithAssignments(TaskRead):
    """Task read model with operator assignments and machine options."""

    operator_assignments: list["TaskOperatorAssignmentRead"] = []
    machine_options: list["TaskMachineOptionRead"] = []


class TaskOperatorAssignmentCreate(TaskOperatorAssignmentBase):
    """TaskOperatorAssignment creation model."""

    pass


class TaskOperatorAssignmentUpdate(SQLModel):
    """TaskOperatorAssignment update model."""

    assignment_type: AssignmentType | None = Field(default=None)
    planned_start_time: datetime | None = Field(default=None)
    planned_end_time: datetime | None = Field(default=None)
    actual_start_time: datetime | None = Field(default=None)
    actual_end_time: datetime | None = Field(default=None)


class TaskOperatorAssignmentRead(TaskOperatorAssignmentBase):
    """TaskOperatorAssignment read model."""

    id: int
    created_at: datetime
    updated_at: datetime


class TaskMachineOptionCreate(TaskMachineOptionBase):
    """TaskMachineOption creation model."""

    pass


class TaskMachineOptionRead(TaskMachineOptionBase):
    """TaskMachineOption read model."""

    id: int
    created_at: datetime


# Fix forward references - will be resolved by SQLModel
Job = "Job"
Machine = "Machine"
Operator = "Operator"
