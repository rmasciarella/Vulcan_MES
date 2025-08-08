"""Scheduling domain entities."""

from .job import (
    Job,
    JobDelayed,
    JobScheduleChanged,
    JobStatusChanged,
    TaskProgressUpdated,
)
from .machine import Machine, MachineCapability, MachineStatusChanged, RequiredSkill
from .operation import Operation
from .operator import (
    AvailabilityInfo,
    AvailabilityOverride,
    Operator,
    OperatorStatusChanged,
    SkillCertificationExpiring,
)
from .production_zone import ProductionZone, WipChanged, WipLimitExceeded
from .task import (
    OperatorAssignment,
    Task,
    TaskAssignmentChanged,
    TaskDelayed,
    TaskStatusChanged,
)

from .aliases import WorkOrder, Resource, WorkCell

__all__ = [
    # Entities
    "Job",
    "Task",
    "Operation",
    "Machine",
    "Operator",
    "ProductionZone",
    # Ubiquitous language aliases
    "WorkOrder",
    "Resource",
    "WorkCell",
    # Supporting entities
    "MachineCapability",
    "RequiredSkill",
    "OperatorAssignment",
    "AvailabilityOverride",
    "AvailabilityInfo",
    # Domain events
    "JobStatusChanged",
    "JobScheduleChanged",
    "JobDelayed",
    "TaskProgressUpdated",
    "TaskStatusChanged",
    "TaskAssignmentChanged",
    "TaskDelayed",
    "MachineStatusChanged",
    "OperatorStatusChanged",
    "SkillCertificationExpiring",
    "WipLimitExceeded",
    "WipChanged",
]
