"""Value objects for the scheduling domain."""

from .common import (
    Address,
    ContactInfo,
    Duration,
    EfficiencyFactor,
    Money,
    OperatorSkill,
    Quantity,
    Skill,
    TimeWindow,
    WorkingHours,
)
from .enums import (
    AssignmentType,
    ConstraintType,
    JobStatus,
    MachineAutomationLevel,
    MachineStatus,
    OperatorStatus,
    PriorityLevel,
    SkillLevel,
    TaskStatus,
)
from .role_requirement import AttendanceRequirement, RoleRequirement

from .identifiers import WorkOrderId, TaskId, ResourceId, ScheduleId, WorkCellId
from .capability import ResourceCapability
from .timeslot import TimeSlot

__all__ = [
    # Common value objects
    "Address",
    "ContactInfo",
    "Duration",
    "EfficiencyFactor",
    "Money",
    "OperatorSkill",
    "Quantity",
    "Skill",
    "TimeWindow",
    "WorkingHours",
    # Role requirements
    "AttendanceRequirement",
    "RoleRequirement",
    # Enums
    "AssignmentType",
    "ConstraintType",
    "JobStatus",
    "MachineAutomationLevel",
    "MachineStatus",
    "OperatorStatus",
    "PriorityLevel",
    "SkillLevel",
    "TaskStatus",
    # Identifiers and capabilities
    "WorkOrderId",
    "TaskId",
    "ResourceId",
    "ScheduleId",
    "WorkCellId",
    "ResourceCapability",
    "TimeSlot",
]
