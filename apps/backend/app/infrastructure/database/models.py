"""
SQLModel table definitions for scheduling domain entities.

This module defines the database table structures for scheduling domain
entities using SQLModel. These models serve as both Pydantic models for
API serialization and SQLAlchemy ORM models for database operations.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    MachineAutomationLevel,
    MachineStatus,
    OperatorStatus,
    PriorityLevel,
    SkillLevel,
    TaskStatus,
)


# Base classes for shared fields
class TimestampedModel(SQLModel):
    """Base model with timestamp fields."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


class IdentifiedModel(TimestampedModel):
    """Base model with UUID primary key and timestamps."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)


# Job tables
class JobBase(SQLModel):
    """Base Job model with shared fields."""

    job_number: str = Field(min_length=1, max_length=50, unique=True, index=True)
    customer_name: str | None = Field(None, max_length=100)
    part_number: str | None = Field(None, max_length=50)
    quantity: int = Field(default=1, ge=1)
    priority: PriorityLevel = Field(default=PriorityLevel.NORMAL)
    status: JobStatus = Field(default=JobStatus.PLANNED)

    # Scheduling dates
    release_date: datetime | None = None
    due_date: datetime
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None
    actual_start_date: datetime | None = None
    actual_end_date: datetime | None = None

    # Progress tracking
    current_operation_sequence: int = Field(default=0, ge=0, le=100)
    notes: str | None = None
    created_by: str | None = None


class Job(JobBase, IdentifiedModel, table=True):
    """Job table definition."""

    __tablename__ = "jobs"

    # Relationships
    tasks: list["Task"] = Relationship(back_populates="job", cascade_delete=True)


class JobCreate(JobBase):
    """Job creation model."""

    pass


class JobUpdate(SQLModel):
    """Job update model."""

    customer_name: str | None = None
    part_number: str | None = None
    quantity: int | None = None
    priority: PriorityLevel | None = None
    status: JobStatus | None = None
    release_date: datetime | None = None
    due_date: datetime | None = None
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None
    actual_start_date: datetime | None = None
    actual_end_date: datetime | None = None
    current_operation_sequence: int | None = None
    notes: str | None = None


class JobPublic(JobBase, IdentifiedModel):
    """Job public model for API responses."""

    task_count: int = 0
    completed_task_count: int = 0
    completion_percentage: float = 0.0


# Task tables
class TaskBase(SQLModel):
    """Base Task model with shared fields."""

    job_id: UUID = Field(foreign_key="jobs.id", index=True)
    operation_id: UUID = Field(index=True)
    sequence_in_job: int = Field(ge=1, le=100)
    status: TaskStatus = Field(default=TaskStatus.PENDING)

    # Planning data
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    planned_duration_minutes: int | None = Field(None, ge=0)
    planned_setup_duration_minutes: int = Field(default=0, ge=0)

    # Execution data
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    actual_duration_minutes: int | None = Field(None, ge=0)
    actual_setup_duration_minutes: int | None = Field(None, ge=0)

    # Resource assignments
    assigned_machine_id: UUID | None = Field(None, foreign_key="machines.id")

    # Tracking and quality
    is_critical_path: bool = Field(default=False)
    delay_minutes: int = Field(default=0, ge=0)
    rework_count: int = Field(default=0, ge=0)
    quality_notes: str | None = None
    notes: str | None = None


class Task(TaskBase, IdentifiedModel, table=True):
    """Task table definition."""

    __tablename__ = "tasks"

    # Relationships
    job: Job | None = Relationship(back_populates="tasks")
    assigned_machine: Optional["Machine"] = Relationship(
        back_populates="assigned_tasks"
    )
    operator_assignments: list["OperatorAssignment"] = Relationship(
        back_populates="task", cascade_delete=True
    )


class TaskCreate(TaskBase):
    """Task creation model."""

    pass


class TaskUpdate(SQLModel):
    """Task update model."""

    status: TaskStatus | None = None
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    planned_duration_minutes: int | None = None
    planned_setup_duration_minutes: int | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    actual_duration_minutes: int | None = None
    actual_setup_duration_minutes: int | None = None
    assigned_machine_id: UUID | None = None
    is_critical_path: bool | None = None
    delay_minutes: int | None = None
    rework_count: int | None = None
    quality_notes: str | None = None
    notes: str | None = None


class TaskPublic(TaskBase, IdentifiedModel):
    """Task public model for API responses."""

    pass


# Machine/Resource tables
class MachineBase(SQLModel):
    """Base Machine model with shared fields."""

    name: str = Field(min_length=1, max_length=100, unique=True)
    machine_type: str = Field(max_length=50)
    zone: str = Field(max_length=50, index=True)
    automation_level: MachineAutomationLevel = Field(
        default=MachineAutomationLevel.ATTENDED
    )
    status: MachineStatus = Field(default=MachineStatus.AVAILABLE)

    # Capabilities
    max_setup_duration_minutes: int = Field(default=60, ge=0)
    min_processing_duration_minutes: int = Field(default=1, ge=1)

    # Maintenance
    last_maintenance_date: datetime | None = None
    next_maintenance_date: datetime | None = None

    notes: str | None = None


class Machine(MachineBase, IdentifiedModel, table=True):
    """Machine table definition."""

    __tablename__ = "machines"

    # Relationships
    assigned_tasks: list[Task] = Relationship(back_populates="assigned_machine")
    skill_requirements: list["MachineSkillRequirement"] = Relationship(
        back_populates="machine", cascade_delete=True
    )


class MachineCreate(MachineBase):
    """Machine creation model."""

    pass


class MachineUpdate(SQLModel):
    """Machine update model."""

    name: str | None = None
    machine_type: str | None = None
    zone: str | None = None
    automation_level: MachineAutomationLevel | None = None
    status: MachineStatus | None = None
    max_setup_duration_minutes: int | None = None
    min_processing_duration_minutes: int | None = None
    last_maintenance_date: datetime | None = None
    next_maintenance_date: datetime | None = None
    notes: str | None = None


class MachinePublic(MachineBase, IdentifiedModel):
    """Machine public model for API responses."""

    is_available: bool = False
    current_task_count: int = 0


# Operator tables
class OperatorBase(SQLModel):
    """Base Operator model with shared fields."""

    name: str = Field(min_length=1, max_length=100)
    employee_id: str = Field(min_length=1, max_length=50, unique=True, index=True)
    status: OperatorStatus = Field(default=OperatorStatus.AVAILABLE)
    shift_pattern: str = Field(default="day", max_length=20)
    zone: str | None = Field(None, max_length=50, index=True)

    # Contact and scheduling
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)

    notes: str | None = None


class Operator(OperatorBase, IdentifiedModel, table=True):
    """Operator table definition."""

    __tablename__ = "operators"

    # Relationships
    skills: list["OperatorSkill"] = Relationship(
        back_populates="operator", cascade_delete=True
    )
    assignments: list["OperatorAssignment"] = Relationship(back_populates="operator")


class OperatorCreate(OperatorBase):
    """Operator creation model."""

    pass


class OperatorUpdate(SQLModel):
    """Operator update model."""

    name: str | None = None
    status: OperatorStatus | None = None
    shift_pattern: str | None = None
    zone: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class OperatorPublic(OperatorBase, IdentifiedModel):
    """Operator public model for API responses."""

    is_available: bool = False
    current_assignments_count: int = 0
    skill_count: int = 0


# Skill and assignment tables
class SkillTypeBase(SQLModel):
    """Base SkillType model."""

    name: str = Field(min_length=1, max_length=50, unique=True)
    description: str | None = None
    category: str | None = Field(None, max_length=50)


class SkillType(SkillTypeBase, IdentifiedModel, table=True):
    """Skill type table definition."""

    __tablename__ = "skill_types"


class OperatorSkillBase(SQLModel):
    """Base OperatorSkill model."""

    operator_id: UUID = Field(foreign_key="operators.id", primary_key=True)
    skill_type_id: UUID = Field(foreign_key="skill_types.id", primary_key=True)
    level: SkillLevel = Field(default=SkillLevel.LEVEL_1)
    certified_date: datetime = Field(default_factory=datetime.utcnow)
    expiry_date: datetime | None = None
    notes: str | None = None


class OperatorSkill(OperatorSkillBase, TimestampedModel, table=True):
    """Operator skill table definition."""

    __tablename__ = "operator_skills"

    # Relationships
    operator: Operator | None = Relationship(back_populates="skills")
    skill_type: SkillType | None = Relationship()


class MachineSkillRequirementBase(SQLModel):
    """Base MachineSkillRequirement model."""

    machine_id: UUID = Field(foreign_key="machines.id", primary_key=True)
    skill_type_id: UUID = Field(foreign_key="skill_types.id", primary_key=True)
    minimum_level: SkillLevel = Field(default=SkillLevel.LEVEL_1)
    is_required: bool = Field(default=True)


class MachineSkillRequirement(
    MachineSkillRequirementBase, TimestampedModel, table=True
):
    """Machine skill requirement table definition."""

    __tablename__ = "machine_skill_requirements"

    # Relationships
    machine: Machine | None = Relationship(back_populates="skill_requirements")
    skill_type: SkillType | None = Relationship()


class OperatorAssignmentBase(SQLModel):
    """Base OperatorAssignment model."""

    task_id: UUID = Field(foreign_key="tasks.id")
    operator_id: UUID = Field(foreign_key="operators.id")
    assignment_type: AssignmentType = Field(default=AssignmentType.FULL_DURATION)

    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None

    notes: str | None = None


class OperatorAssignment(OperatorAssignmentBase, IdentifiedModel, table=True):
    """Operator assignment table definition."""

    __tablename__ = "operator_assignments"

    # Relationships
    task: Task | None = Relationship(back_populates="operator_assignments")
    operator: Operator | None = Relationship(back_populates="assignments")


class OperatorAssignmentCreate(OperatorAssignmentBase):
    """Operator assignment creation model."""

    pass


class OperatorAssignmentUpdate(SQLModel):
    """Operator assignment update model."""

    assignment_type: AssignmentType | None = None
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    notes: str | None = None


class OperatorAssignmentPublic(OperatorAssignmentBase, IdentifiedModel):
    """Operator assignment public model for API responses."""

    is_active: bool = False


# Summary models for API responses
class JobSummary(SQLModel):
    """Job summary for dashboard views."""

    id: UUID
    job_number: str
    customer_name: str | None
    status: JobStatus
    priority: PriorityLevel
    due_date: datetime
    completion_percentage: float
    is_overdue: bool
    days_until_due: float


class TaskSummary(SQLModel):
    """Task summary for scheduling views."""

    id: UUID
    job_id: UUID
    job_number: str
    sequence_in_job: int
    status: TaskStatus
    planned_start_time: datetime | None
    planned_end_time: datetime | None
    assigned_machine_id: UUID | None
    is_critical_path: bool
    delay_minutes: int


class ResourceSummary(SQLModel):
    """Resource summary for capacity planning."""

    id: UUID
    name: str
    type: str  # 'machine' or 'operator'
    status: str
    zone: str | None
    current_utilization_percentage: float
    available_capacity_hours: float


# Import ScheduleStatus enum
from app.domain.scheduling.value_objects.enums import ScheduleStatus


# Schedule tables
class ScheduleBase(SQLModel):
    """Base Schedule model with shared fields."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    version: int = Field(default=1, ge=1)
    status: ScheduleStatus = Field(default=ScheduleStatus.DRAFT)

    start_date: datetime
    end_date: datetime
    job_ids: list[UUID] | None = Field(default_factory=list, sa_column_kwargs={"type_": "JSON"})
    
    # Optimization results
    makespan_minutes: int | None = None
    total_cost: float | None = None
    utilization_percentage: float | None = None
    
    # Metadata
    created_by: str | None = None
    published_at: datetime | None = None
    activated_at: datetime | None = None


class Schedule(ScheduleBase, IdentifiedModel, table=True):
    """Schedule table definition."""

    __tablename__ = "schedules"

    # Relationships
    assignments: list["ScheduleAssignment"] = Relationship(
        back_populates="schedule", cascade_delete=True
    )


class ScheduleCreate(ScheduleBase):
    """Schedule creation model."""

    pass


class ScheduleUpdate(SQLModel):
    """Schedule update model."""

    name: str | None = None
    description: str | None = None
    status: ScheduleStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    job_ids: list[UUID] | None = None
    makespan_minutes: int | None = None
    total_cost: float | None = None
    utilization_percentage: float | None = None
    published_at: datetime | None = None
    activated_at: datetime | None = None


class SchedulePublic(ScheduleBase, IdentifiedModel):
    """Schedule public model for API responses."""

    is_valid: bool = True
    constraint_violations: list[str] = Field(default_factory=list)
    assignment_count: int = 0


# Schedule Assignment tables
class ScheduleAssignmentBase(SQLModel):
    """Base ScheduleAssignment model."""

    schedule_id: UUID = Field(foreign_key="schedules.id")
    task_id: UUID = Field(foreign_key="tasks.id")
    job_id: UUID = Field(foreign_key="jobs.id")
    machine_id: UUID = Field(foreign_key="machines.id")
    
    # Time windows
    start_time: datetime
    end_time: datetime
    setup_start_time: datetime | None = None
    setup_end_time: datetime | None = None
    processing_start_time: datetime | None = None
    processing_end_time: datetime | None = None
    
    # Operator assignments
    operator_ids: list[UUID] | None = Field(default_factory=list, sa_column_kwargs={"type_": "JSON"})
    
    # Duration tracking
    setup_duration_minutes: int = 0
    processing_duration_minutes: int = 0
    total_duration_minutes: int = 0
    
    # Sequence and constraints
    sequence_in_job: int = 0
    is_critical_path: bool = False
    
    notes: str | None = None


class ScheduleAssignment(ScheduleAssignmentBase, IdentifiedModel, table=True):
    """Schedule assignment table definition."""

    __tablename__ = "schedule_assignments"

    # Relationships
    schedule: Schedule | None = Relationship(back_populates="assignments")
    task: Task | None = Relationship()
    job: Job | None = Relationship()
    machine: Machine | None = Relationship()


class ScheduleAssignmentCreate(ScheduleAssignmentBase):
    """Schedule assignment creation model."""

    pass


class ScheduleAssignmentUpdate(SQLModel):
    """Schedule assignment update model."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    setup_start_time: datetime | None = None
    setup_end_time: datetime | None = None
    processing_start_time: datetime | None = None
    processing_end_time: datetime | None = None
    operator_ids: list[UUID] | None = None
    setup_duration_minutes: int | None = None
    processing_duration_minutes: int | None = None
    total_duration_minutes: int | None = None
    sequence_in_job: int | None = None
    is_critical_path: bool | None = None
    notes: str | None = None


class ScheduleAssignmentPublic(ScheduleAssignmentBase, IdentifiedModel):
    """Schedule assignment public model for API responses."""

    job_number: str | None = None
    machine_name: str | None = None
    operator_names: list[str] = Field(default_factory=list)
