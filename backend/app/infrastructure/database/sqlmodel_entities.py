"""
SQLModel database models for the scheduling system.

These models provide the ORM mapping between domain entities and the SQL schema.
They use SQLModel to bridge Pydantic models with SQLAlchemy ORM functionality.
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, String
from sqlmodel import Column, Field, Relationship, SQLModel, Text
from sqlmodel import Enum as SQLEnum


# Enums matching the database schema
# Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# # Commented out - duplicate in models/
# class JobStatusEnum(str, Enum):
# # # # # # # # # # #     PLANNED = "planned"
# # # # # # # # # # #     RELEASED = "released"
# # # # # # # # # # #     IN_PROGRESS = "in_progress"
# # # # # # # # # # #     COMPLETED = "completed"
# # # # # # # # # # #     ON_HOLD = "on_hold"
# # # # # # # # # # #     CANCELLED = "cancelled"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class TaskStatusEnum(str, Enum):
# # # # # # # # # # #     PENDING = "pending"
# # # # # # # # # # #     READY = "ready"
# # # # # # # # # # #     SCHEDULED = "scheduled"
# # # # # # # # # # #     IN_PROGRESS = "in_progress"
# # # # # # # # # # #     COMPLETED = "completed"
# # # # # # # # # # #     CANCELLED = "cancelled"
# # # # # # # # # # #     FAILED = "failed"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class MachineStatusEnum(str, Enum):
# # # # # # # # # # #     AVAILABLE = "available"
# # # # # # # # # # #     BUSY = "busy"
# # # # # # # # # # #     MAINTENANCE = "maintenance"
# # # # # # # # # # #     OFFLINE = "offline"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class OperatorStatusEnum(str, Enum):
# # # # # # # # # # #     AVAILABLE = "available"
# # # # # # # # # # #     ASSIGNED = "assigned"
# # # # # # # # # # #     ON_BREAK = "on_break"
# # # # # # # # # # #     OFF_SHIFT = "off_shift"
# # # # # # # # # # #     ABSENT = "absent"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class SkillLevelEnum(str, Enum):
# # # # # # # # # # #     LEVEL_1 = "1"
# # # # # # # # # # #     LEVEL_2 = "2"
# # # # # # # # # # #     LEVEL_3 = "3"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class AutomationLevelEnum(str, Enum):
# # # # # # # # # # #     ATTENDED = "attended"
# # # # # # # # # # #     UNATTENDED = "unattended"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class PriorityLevelEnum(str, Enum):
# # # # # # # # # # #     LOW = "low"
# # # # # # # # # # #     NORMAL = "normal"
# # # # # # # # # # #     HIGH = "high"
# # # # # # # # # # #     CRITICAL = "critical"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class AssignmentTypeEnum(str, Enum):
# # # # # # # # # # #     SETUP = "setup"
# # # # # # # # # # #     FULL_DURATION = "full_duration"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # class ConstraintTypeEnum(str, Enum):
# # # # # # # # # # #     FINISH_TO_START = "finish_to_start"
# # # # # # # # # # #     START_TO_START = "start_to_start"
# # # # # # # # # # #     FINISH_TO_FINISH = "finish_to_finish"
# # # # # # # # # # #     START_TO_FINISH = "start_to_finish"
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Base model with common fields
# # # # # # # # # # # class BaseModel(SQLModel):
# # # # # # # # # # #     """Base model with common timestamps and UUID."""
# # # # # # # # # # #
# # # # # # # # # # #     id: int | None = Field(default=None, primary_key=True)
# # # # # # # # # # #     created_at: datetime = Field(default_factory=datetime.utcnow)
# # # # # # # # # # #     updated_at: datetime = Field(default_factory=datetime.utcnow)
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Production Zones - Commented out due to duplicate definition in models/scheduling/production_zone.py
# # # # # # # # # # # # class ProductionZone(BaseModel, table=True):
# # # # # # # # # # # #     __tablename__ = "production_zones"
# # # # # # # # # # # #
# # # # # # # # # # # #     zone_code: str = Field(max_length=20, unique=True, index=True)
# # # # # # # # # # # #     zone_name: str = Field(max_length=100)
# # # # # # # # # # # #     wip_limit: int = Field(gt=0)
# # # # # # # # # # # #     current_wip: int = Field(default=0, ge=0)
# # # # # # # # # # # #     description: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # # #
# # # # # # # # # # # #     # Relationships
# # # # # # # # # # # #     operations: list["Operation"] = Relationship(back_populates="production_zone")
# # # # # # # # # # # #     machines: list["Machine"] = Relationship(back_populates="production_zone")
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Skills
# # # # # # # # # # # class Skill(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "skills"
# # # # # # # # # # #
# # # # # # # # # # #     skill_code: str = Field(max_length=20, unique=True, index=True)
# # # # # # # # # # #     skill_name: str = Field(max_length=100)
# # # # # # # # # # #     skill_category: str | None = Field(default=None, max_length=50)
# # # # # # # # # # #     description: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     operator_skills: list["OperatorSkill"] = Relationship(back_populates="skill")
# # # # # # # # # # #     machine_required_skills: list["MachineRequiredSkill"] = Relationship(
# # # # # # # # # # #         back_populates="skill"
# # # # # # # # # # #     )
# # # # # # # # # # #     task_skill_requirements: list["TaskSkillRequirement"] = Relationship(
# # # # # # # # # # #         back_populates="skill"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Operations
# # # # # # # # # # # class Operation(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "operations"
# # # # # # # # # # #
# # # # # # # # # # #     operation_code: str = Field(max_length=20, unique=True, index=True)
# # # # # # # # # # #     operation_name: str = Field(max_length=100)
# # # # # # # # # # #     sequence_number: int = Field(ge=1, le=100, unique=True)
# # # # # # # # # # #     production_zone_id: int | None = Field(
# # # # # # # # # # #         default=None, foreign_key="production_zones.id"
# # # # # # # # # # #     )
# # # # # # # # # # #     is_critical: bool = Field(default=False)
# # # # # # # # # # #     standard_duration_minutes: int = Field(gt=0)
# # # # # # # # # # #     setup_duration_minutes: int = Field(default=0, ge=0)
# # # # # # # # # # #     description: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     production_zone: ProductionZone | None = Relationship(back_populates="operations")
# # # # # # # # # # #     tasks: list["Task"] = Relationship(back_populates="operation")
# # # # # # # # # # #     machine_capabilities: list["MachineCapability"] = Relationship(
# # # # # # # # # # #         back_populates="operation"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Machines
# # # # # # # # # # # class Machine(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "machines"
# # # # # # # # # # #
# # # # # # # # # # #     machine_code: str = Field(max_length=20, unique=True, index=True)
# # # # # # # # # # #     machine_name: str = Field(max_length=100)
# # # # # # # # # # #     automation_level: AutomationLevelEnum = Field(
# # # # # # # # # # #         sa_column=Column(SQLEnum(AutomationLevelEnum))
# # # # # # # # # # #     )
# # # # # # # # # # #     production_zone_id: int | None = Field(
# # # # # # # # # # #         default=None, foreign_key="production_zones.id"
# # # # # # # # # # #     )
# # # # # # # # # # #     status: MachineStatusEnum = Field(
# # # # # # # # # # #         default=MachineStatusEnum.AVAILABLE,
# # # # # # # # # # #         sa_column=Column(SQLEnum(MachineStatusEnum)),
# # # # # # # # # # #     )
# # # # # # # # # # #     efficiency_factor: Decimal = Field(
# # # # # # # # # # #         default=Decimal("1.00"), ge=Decimal("0.1"), le=Decimal("2.0")
# # # # # # # # # # #     )
# # # # # # # # # # #     is_bottleneck: bool = Field(default=False)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     production_zone: ProductionZone | None = Relationship(back_populates="machines")
# # # # # # # # # # #     capabilities: list["MachineCapability"] = Relationship(back_populates="machine")
# # # # # # # # # # #     required_skills: list["MachineRequiredSkill"] = Relationship(
# # # # # # # # # # #         back_populates="machine"
# # # # # # # # # # #     )
# # # # # # # # # # #     tasks: list["Task"] = Relationship(back_populates="assigned_machine")
# # # # # # # # # # #     task_options: list["TaskMachineOption"] = Relationship(back_populates="machine")
# # # # # # # # # # #     maintenance_records: list["MachineMaintenance"] = Relationship(
# # # # # # # # # # #         back_populates="machine"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Machine Capabilities
# # # # # # # # # # # class MachineCapability(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "machine_capabilities"
# # # # # # # # # # #
# # # # # # # # # # #     machine_id: int = Field(foreign_key="machines.id")
# # # # # # # # # # #     operation_id: int = Field(foreign_key="operations.id")
# # # # # # # # # # #     is_primary: bool = Field(default=False)
# # # # # # # # # # #     processing_time_minutes: int = Field(gt=0)
# # # # # # # # # # #     setup_time_minutes: int = Field(default=0, ge=0)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     machine: Machine = Relationship(back_populates="capabilities")
# # # # # # # # # # #     operation: Operation = Relationship(back_populates="machine_capabilities")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (UniqueConstraint("machine_id", "operation_id"),)
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Machine Required Skills
# # # # # # # # # # # class MachineRequiredSkill(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "machine_required_skills"
# # # # # # # # # # #
# # # # # # # # # # #     machine_id: int = Field(foreign_key="machines.id")
# # # # # # # # # # #     skill_id: int = Field(foreign_key="skills.id")
# # # # # # # # # # #     minimum_level: SkillLevelEnum = Field(sa_column=Column(SQLEnum(SkillLevelEnum)))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     machine: Machine = Relationship(back_populates="required_skills")
# # # # # # # # # # #     skill: Skill = Relationship(back_populates="machine_required_skills")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (UniqueConstraint("machine_id", "skill_id"),)
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Operators
# # # # # # # # # # # class Operator(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "operators"
# # # # # # # # # # #
# # # # # # # # # # #     employee_id: str = Field(max_length=20, unique=True, index=True)
# # # # # # # # # # #     first_name: str = Field(max_length=50)
# # # # # # # # # # #     last_name: str = Field(max_length=50)
# # # # # # # # # # #     email: str | None = Field(default=None, max_length=100, unique=True)
# # # # # # # # # # #     status: OperatorStatusEnum = Field(
# # # # # # # # # # #         default=OperatorStatusEnum.AVAILABLE,
# # # # # # # # # # #         sa_column=Column(SQLEnum(OperatorStatusEnum)),
# # # # # # # # # # #     )
# # # # # # # # # # #     default_shift_start: time = Field(default=time(7, 0))
# # # # # # # # # # #     default_shift_end: time = Field(default=time(16, 0))
# # # # # # # # # # #     lunch_start: time = Field(default=time(12, 0))
# # # # # # # # # # #     lunch_duration_minutes: int = Field(default=30)
# # # # # # # # # # #     is_active: bool = Field(default=True)
# # # # # # # # # # #     department: str = Field(default="general", max_length=50, index=True)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     skills: list["OperatorSkill"] = Relationship(back_populates="operator")
# # # # # # # # # # #     task_assignments: list["TaskOperatorAssignment"] = Relationship(
# # # # # # # # # # #         back_populates="operator"
# # # # # # # # # # #     )
# # # # # # # # # # #     availability_records: list["OperatorAvailability"] = Relationship(
# # # # # # # # # # #         back_populates="operator"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Operator Skills
# # # # # # # # # # # class OperatorSkill(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "operator_skills"
# # # # # # # # # # #
# # # # # # # # # # #     operator_id: int = Field(foreign_key="operators.id")
# # # # # # # # # # #     skill_id: int = Field(foreign_key="skills.id")
# # # # # # # # # # #     proficiency_level: SkillLevelEnum = Field(sa_column=Column(SQLEnum(SkillLevelEnum)))
# # # # # # # # # # #     certified_date: date | None = None
# # # # # # # # # # #     expiry_date: date | None = None
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     operator: Operator = Relationship(back_populates="skills")
# # # # # # # # # # #     skill: Skill = Relationship(back_populates="operator_skills")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("operator_id", "skill_id"),
# # # # # # # # # # #         CheckConstraint("expiry_date IS NULL OR expiry_date > certified_date"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Jobs
# # # # # # # # # # # class Job(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "jobs"
# # # # # # # # # # #
# # # # # # # # # # #     job_number: str = Field(max_length=50, unique=True, index=True)
# # # # # # # # # # #     customer_name: str | None = Field(default=None, max_length=100)
# # # # # # # # # # #     part_number: str | None = Field(default=None, max_length=50)
# # # # # # # # # # #     quantity: int = Field(default=1, gt=0)
# # # # # # # # # # #     priority: PriorityLevelEnum = Field(
# # # # # # # # # # #         default=PriorityLevelEnum.NORMAL, sa_column=Column(SQLEnum(PriorityLevelEnum))
# # # # # # # # # # #     )
# # # # # # # # # # #     status: JobStatusEnum = Field(
# # # # # # # # # # #         default=JobStatusEnum.PLANNED, sa_column=Column(SQLEnum(JobStatusEnum))
# # # # # # # # # # #     )
# # # # # # # # # # #     release_date: datetime | None = None
# # # # # # # # # # #     due_date: datetime
# # # # # # # # # # #     planned_start_date: datetime | None = None
# # # # # # # # # # #     planned_end_date: datetime | None = None
# # # # # # # # # # #     actual_start_date: datetime | None = None
# # # # # # # # # # #     actual_end_date: datetime | None = None
# # # # # # # # # # #     current_operation_sequence: int | None = Field(default=None, ge=0, le=100)
# # # # # # # # # # #     notes: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #     created_by: str | None = Field(default=None, max_length=50)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     tasks: list["Task"] = Relationship(back_populates="job", cascade_delete=True)
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         CheckConstraint(
# # # # # # # # # # #             "actual_end_date IS NULL OR actual_end_date >= actual_start_date"
# # # # # # # # # # #         ),
# # # # # # # # # # #         CheckConstraint(
# # # # # # # # # # #             "planned_end_date IS NULL OR planned_end_date >= planned_start_date"
# # # # # # # # # # #         ),
# # # # # # # # # # #         Index("idx_jobs_status", "status"),
# # # # # # # # # # #         Index("idx_jobs_due_date", "due_date"),
# # # # # # # # # # #         Index("idx_jobs_priority", "priority", "due_date"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Tasks
# # # # # # # # # # # class Task(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "tasks"
# # # # # # # # # # #
# # # # # # # # # # #     job_id: int = Field(foreign_key="jobs.id")
# # # # # # # # # # #     operation_id: int = Field(foreign_key="operations.id")
# # # # # # # # # # #     sequence_in_job: int = Field(gt=0)
# # # # # # # # # # #     status: TaskStatusEnum = Field(
# # # # # # # # # # #         default=TaskStatusEnum.PENDING, sa_column=Column(SQLEnum(TaskStatusEnum))
# # # # # # # # # # #     )
# # # # # # # # # # #     department: str = Field(default="general", max_length=50, index=True)
# # # # # # # # # # #     role_requirements_json: str | None = Field(
# # # # # # # # # # #         default=None,
# # # # # # # # # # #         sa_column=Column(Text),
# # # # # # # # # # #         description="JSON-serialized list of role requirements",
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #     # Planning data
# # # # # # # # # # #     planned_start_time: datetime | None = None
# # # # # # # # # # #     planned_end_time: datetime | None = None
# # # # # # # # # # #     planned_duration_minutes: int | None = Field(default=None, gt=0)
# # # # # # # # # # #     planned_setup_minutes: int = Field(default=0, ge=0)
# # # # # # # # # # #
# # # # # # # # # # #     # Execution data
# # # # # # # # # # #     actual_start_time: datetime | None = None
# # # # # # # # # # #     actual_end_time: datetime | None = None
# # # # # # # # # # #     actual_duration_minutes: int | None = Field(default=None, gt=0)
# # # # # # # # # # #     actual_setup_minutes: int | None = Field(default=None, ge=0)
# # # # # # # # # # #
# # # # # # # # # # #     # Resource assignments
# # # # # # # # # # #     assigned_machine_id: int | None = Field(default=None, foreign_key="machines.id")
# # # # # # # # # # #
# # # # # # # # # # #     # Tracking
# # # # # # # # # # #     is_critical_path: bool = Field(default=False)
# # # # # # # # # # #     delay_minutes: int = Field(default=0, ge=0)
# # # # # # # # # # #     rework_count: int = Field(default=0, ge=0)
# # # # # # # # # # #     notes: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     job: Job = Relationship(back_populates="tasks")
# # # # # # # # # # #     operation: Operation = Relationship(back_populates="tasks")
# # # # # # # # # # #     assigned_machine: Machine | None = Relationship(back_populates="tasks")
# # # # # # # # # # #     machine_options: list["TaskMachineOption"] = Relationship(
# # # # # # # # # # #         back_populates="task", cascade_delete=True
# # # # # # # # # # #     )
# # # # # # # # # # #     operator_assignments: list["TaskOperatorAssignment"] = Relationship(
# # # # # # # # # # #         back_populates="task", cascade_delete=True
# # # # # # # # # # #     )
# # # # # # # # # # #     predecessor_constraints: list["TaskPrecedenceConstraint"] = Relationship(
# # # # # # # # # # #         back_populates="successor_task",
# # # # # # # # # # #         sa_relationship_kwargs={
# # # # # # # # # # #             "foreign_keys": "[TaskPrecedenceConstraint.successor_task_id]"
# # # # # # # # # # #         },
# # # # # # # # # # #     )
# # # # # # # # # # #     successor_constraints: list["TaskPrecedenceConstraint"] = Relationship(
# # # # # # # # # # #         back_populates="predecessor_task",
# # # # # # # # # # #         sa_relationship_kwargs={
# # # # # # # # # # #             "foreign_keys": "[TaskPrecedenceConstraint.predecessor_task_id]"
# # # # # # # # # # #         },
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("job_id", "sequence_in_job"),
# # # # # # # # # # #         CheckConstraint(
# # # # # # # # # # #             "planned_end_time IS NULL OR planned_end_time > planned_start_time"
# # # # # # # # # # #         ),
# # # # # # # # # # #         CheckConstraint(
# # # # # # # # # # #             "actual_end_time IS NULL OR actual_end_time > actual_start_time"
# # # # # # # # # # #         ),
# # # # # # # # # # #         Index("idx_tasks_job_id", "job_id"),
# # # # # # # # # # #         Index("idx_tasks_status", "status"),
# # # # # # # # # # #         Index("idx_tasks_operation_id", "operation_id"),
# # # # # # # # # # #         Index("idx_tasks_machine", "assigned_machine_id"),
# # # # # # # # # # #         Index("idx_tasks_critical_path", "is_critical_path"),
# # # # # # # # # # #         Index("idx_tasks_planned_start", "planned_start_time"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Machine Options
# # # # # # # # # # # class TaskMachineOption(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_machine_options"
# # # # # # # # # # #
# # # # # # # # # # #     task_id: int = Field(foreign_key="tasks.id")
# # # # # # # # # # #     machine_id: int = Field(foreign_key="machines.id")
# # # # # # # # # # #     is_preferred: bool = Field(default=False)
# # # # # # # # # # #     estimated_duration_minutes: int = Field(gt=0)
# # # # # # # # # # #     estimated_setup_minutes: int = Field(default=0, ge=0)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     task: Task = Relationship(back_populates="machine_options")
# # # # # # # # # # #     machine: Machine = Relationship(back_populates="task_options")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (UniqueConstraint("task_id", "machine_id"),)
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Skill Requirements
# # # # # # # # # # # class TaskSkillRequirement(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_skill_requirements"
# # # # # # # # # # #
# # # # # # # # # # #     task_uuid: UUID = Field(description="UUID reference to task (foreign key to be added when tasks use UUIDs)")
# # # # # # # # # # #     skill_id: int = Field(foreign_key="skills.id")
# # # # # # # # # # #     minimum_level: int = Field(ge=1, le=5, description="Minimum skill level required (1-5)")
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     skill: Skill = Relationship(back_populates="task_skill_requirements")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("task_uuid", "skill_id"),
# # # # # # # # # # #         Index("idx_task_skill_requirements_task_uuid", "task_uuid"),
# # # # # # # # # # #         Index("idx_task_skill_requirements_skill_id", "skill_id"),
# # # # # # # # # # #         Index("idx_task_skill_requirements_minimum_level", "minimum_level"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Operator Assignments
# # # # # # # # # # # class TaskOperatorAssignment(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_operator_assignments"
# # # # # # # # # # #
# # # # # # # # # # #     task_id: int = Field(foreign_key="tasks.id")
# # # # # # # # # # #     operator_id: int = Field(foreign_key="operators.id")
# # # # # # # # # # #     assignment_type: AssignmentTypeEnum = Field(
# # # # # # # # # # #         sa_column=Column(SQLEnum(AssignmentTypeEnum))
# # # # # # # # # # #     )
# # # # # # # # # # #     planned_start_time: datetime | None = None
# # # # # # # # # # #     planned_end_time: datetime | None = None
# # # # # # # # # # #     actual_start_time: datetime | None = None
# # # # # # # # # # #     actual_end_time: datetime | None = None
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     task: Task = Relationship(back_populates="operator_assignments")
# # # # # # # # # # #     operator: Operator = Relationship(back_populates="task_assignments")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("task_id", "operator_id", "assignment_type"),
# # # # # # # # # # #         Index(
# # # # # # # # # # #             "idx_task_operator_assignments_operator",
# # # # # # # # # # #             "operator_id",
# # # # # # # # # # #             "planned_start_time",
# # # # # # # # # # #         ),
# # # # # # # # # # #         Index("idx_task_operator_assignments_task", "task_id"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Business Calendar
# # # # # # # # # # # class BusinessCalendar(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "business_calendar"
# # # # # # # # # # #
# # # # # # # # # # #     calendar_date: date = Field(unique=True, index=True)
# # # # # # # # # # #     is_working_day: bool = Field(default=True)
# # # # # # # # # # #     holiday_name: str | None = Field(default=None, max_length=100)
# # # # # # # # # # #     working_hours_start: time | None = None
# # # # # # # # # # #     working_hours_end: time | None = None
# # # # # # # # # # #     notes: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Operator Availability
# # # # # # # # # # # class OperatorAvailability(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "operator_availability"
# # # # # # # # # # #
# # # # # # # # # # #     operator_id: int = Field(foreign_key="operators.id")
# # # # # # # # # # #     availability_date: date
# # # # # # # # # # #     is_available: bool = Field(default=True)
# # # # # # # # # # #     shift_start: time | None = None
# # # # # # # # # # #     shift_end: time | None = None
# # # # # # # # # # #     lunch_start: time | None = None
# # # # # # # # # # #     lunch_duration_minutes: int | None = None
# # # # # # # # # # #     reason: str | None = Field(default=None, max_length=100)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     operator: Operator = Relationship(back_populates="availability_records")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("operator_id", "availability_date"),
# # # # # # # # # # #         Index("idx_operator_availability_date", "availability_date", "operator_id"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Machine Maintenance
# # # # # # # # # # # class MachineMaintenance(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "machine_maintenance"
# # # # # # # # # # #
# # # # # # # # # # #     machine_id: int = Field(foreign_key="machines.id")
# # # # # # # # # # #     maintenance_type: str = Field(max_length=50)
# # # # # # # # # # #     planned_start_time: datetime
# # # # # # # # # # #     planned_end_time: datetime
# # # # # # # # # # #     actual_start_time: datetime | None = None
# # # # # # # # # # #     actual_end_time: datetime | None = None
# # # # # # # # # # #     technician_name: str | None = Field(default=None, max_length=100)
# # # # # # # # # # #     notes: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     machine: Machine = Relationship(back_populates="maintenance_records")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         CheckConstraint("planned_end_time > planned_start_time"),
# # # # # # # # # # #         CheckConstraint(
# # # # # # # # # # #             "actual_end_time IS NULL OR actual_end_time > actual_start_time"
# # # # # # # # # # #         ),
# # # # # # # # # # #         Index(
# # # # # # # # # # #             "idx_machine_maintenance_planned",
# # # # # # # # # # #             "machine_id",
# # # # # # # # # # #             "planned_start_time",
# # # # # # # # # # #             "planned_end_time",
# # # # # # # # # # #         ),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Precedence Constraints
# # # # # # # # # # # class TaskPrecedenceConstraint(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_precedence_constraints"
# # # # # # # # # # #
# # # # # # # # # # #     predecessor_task_id: int = Field(foreign_key="tasks.id")
# # # # # # # # # # #     successor_task_id: int = Field(foreign_key="tasks.id")
# # # # # # # # # # #     lag_time_minutes: int = Field(default=0)
# # # # # # # # # # #     constraint_type: ConstraintTypeEnum = Field(
# # # # # # # # # # #         default=ConstraintTypeEnum.FINISH_TO_START,
# # # # # # # # # # #         sa_column=Column(SQLEnum(ConstraintTypeEnum)),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     predecessor_task: Task = Relationship(
# # # # # # # # # # #         back_populates="successor_constraints",
# # # # # # # # # # #         sa_relationship_kwargs={
# # # # # # # # # # #             "foreign_keys": "[TaskPrecedenceConstraint.predecessor_task_id]"
# # # # # # # # # # #         },
# # # # # # # # # # #     )
# # # # # # # # # # #     successor_task: Task = Relationship(
# # # # # # # # # # #         back_populates="predecessor_constraints",
# # # # # # # # # # #         sa_relationship_kwargs={
# # # # # # # # # # #             "foreign_keys": "[TaskPrecedenceConstraint.successor_task_id]"
# # # # # # # # # # #         },
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         UniqueConstraint("predecessor_task_id", "successor_task_id"),
# # # # # # # # # # #         CheckConstraint("predecessor_task_id != successor_task_id"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Templates (from imported CSV data)
# # # # # # # # # # # class TaskTemplate(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_templates"
# # # # # # # # # # #
# # # # # # # # # # #     task_id: str = Field(unique=True, index=True, description="UUID from CSV")
# # # # # # # # # # #     sequence_id: str | None = Field(default=None, description="Optional sequence UUID")
# # # # # # # # # # #     department_id: str = Field(max_length=10, index=True, description="Department code (MS, FH, OB)")
# # # # # # # # # # #     name: str = Field(max_length=255, description="Task name")
# # # # # # # # # # #     is_unattended: bool = Field(default=False, description="Can run without operator attention")
# # # # # # # # # # #     is_setup: bool = Field(default=False, description="Is a setup task")
# # # # # # # # # # #     wip_limit: int = Field(default=10, gt=0, description="Work-in-progress limit")
# # # # # # # # # # #     max_batch_size: int = Field(default=1, gt=0, description="Maximum batch processing size")
# # # # # # # # # # #     setup_for_task_id: str | None = Field(default=None, index=True, description="Task this setup is for")
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         Index("idx_task_templates_task_id", "task_id"),
# # # # # # # # # # #         Index("idx_task_templates_department", "department_id"),
# # # # # # # # # # #         Index("idx_task_templates_setup_for", "setup_for_task_id"),
# # # # # # # # # # #         Index("idx_task_templates_sequence", "sequence_id"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Critical Sequences
# # # # # # # # # # # class CriticalSequence(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "critical_sequences"
# # # # # # # # # # #
# # # # # # # # # # #     sequence_name: str = Field(max_length=100)
# # # # # # # # # # #     from_operation_sequence: int = Field(ge=1, le=100)
# # # # # # # # # # #     to_operation_sequence: int = Field(ge=1, le=100)
# # # # # # # # # # #     priority_boost: int = Field(default=1)
# # # # # # # # # # #     description: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #     is_active: bool = Field(default=True)
# # # # # # # # # # #
# # # # # # # # # # #     __table_args__ = (
# # # # # # # # # # #         CheckConstraint("to_operation_sequence > from_operation_sequence"),
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Schedule Versions
# # # # # # # # # # # class ScheduleVersion(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "schedule_versions"
# # # # # # # # # # #
# # # # # # # # # # #     version_number: int = Field(unique=True)
# # # # # # # # # # #     schedule_name: str | None = Field(default=None, max_length=100)
# # # # # # # # # # #     is_baseline: bool = Field(default=False)
# # # # # # # # # # #     created_by: str = Field(max_length=50)
# # # # # # # # # # #     approved_by: str | None = Field(default=None, max_length=50)
# # # # # # # # # # #     approved_at: datetime | None = None
# # # # # # # # # # #     notes: str | None = Field(default=None, sa_column=Column(Text))
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     history_records: list["TaskScheduleHistory"] = Relationship(
# # # # # # # # # # #         back_populates="schedule_version"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Task Schedule History
# # # # # # # # # # # class TaskScheduleHistory(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "task_schedule_history"
# # # # # # # # # # #
# # # # # # # # # # #     task_id: int = Field(foreign_key="tasks.id")
# # # # # # # # # # #     schedule_version_id: int | None = Field(
# # # # # # # # # # #         default=None, foreign_key="schedule_versions.id"
# # # # # # # # # # #     )
# # # # # # # # # # #     old_planned_start: datetime | None = None
# # # # # # # # # # #     new_planned_start: datetime | None = None
# # # # # # # # # # #     old_planned_end: datetime | None = None
# # # # # # # # # # #     new_planned_end: datetime | None = None
# # # # # # # # # # #     old_machine_id: int | None = Field(default=None, foreign_key="machines.id")
# # # # # # # # # # #     new_machine_id: int | None = Field(default=None, foreign_key="machines.id")
# # # # # # # # # # #     change_reason: str | None = Field(default=None, max_length=200)
# # # # # # # # # # #     changed_by: str | None = Field(default=None, max_length=50)
# # # # # # # # # # #     changed_at: datetime = Field(default_factory=datetime.utcnow)
# # # # # # # # # # #
# # # # # # # # # # #     # Relationships
# # # # # # # # # # #     schedule_version: ScheduleVersion | None = Relationship(
# # # # # # # # # # #         back_populates="history_records"
# # # # # # # # # # #     )
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Holiday Calendar
# # # # # # # # # # # class HolidayCalendar(SQLModel, table=True):
# # # # # # # # # # #     __tablename__ = "holiday_calendar"
# # # # # # # # # # #
# # # # # # # # # # #     holiday_id: str = Field(primary_key=True, max_length=36)
# # # # # # # # # # #     holiday_date: date = Field(index=True)
# # # # # # # # # # #     name: str = Field(max_length=100)
# # # # # # # # # # #     created_at: datetime = Field(default_factory=datetime.utcnow)
# # # # # # # # # # #     updated_at: datetime = Field(default_factory=datetime.utcnow)
# # # # # # # # # # #
# # # # # # # # # # #
# # # # # # # # # # # # Work Cells
# # # # # # # # # # # class WorkCell(BaseModel, table=True):
# # # # # # # # # # #     __tablename__ = "work_cells"
# # # # # # # # # # #
# # # # # # # # # # #     cell_id: str = Field(max_length=36, unique=True, index=True)
# # # # # # # # # # #     name: str = Field(max_length=100, unique=True, index=True)
# # # # # # # # # # #     capacity: int = Field(gt=0)
# # # # # # # # # # #     is_active: bool = Field(default=True)
# # # # # # # # # # #