"""Scheduling SQLModel classes exports (explicit, no star imports)."""

from .base import (
    AssignmentType,
    JobStatus,
    MachineAutomationLevel,
    MachineStatus,
    OperatorStatus,
    PriorityLevel,
    SkillLevel,
)
from .job import Job
from .machine import Machine, MachineCapability, MachineRequiredSkill
from .operation import Operation
from .operator import Operator, OperatorSkill
from .production_zone import ProductionZone
from .skill import Skill
from .solve_request import (
    BusinessConstraints,
    JobSolution,
    OptimizationParameters,
    SolutionMetrics,
    SolveErrorResponse,
    SolveJobRequest,
    SolveRequest,
    SolveResponse,
    TaskAssignment,
)
from .task import Task, TaskMachineOption, TaskOperatorAssignment

__all__ = [
    # Base enums
    "JobStatus",
    "TaskStatus",
    "MachineStatus",
    "OperatorStatus",
    "MachineAutomationLevel",
    "PriorityLevel",
    "SkillLevel",
    "AssignmentType",
    # Core models
    "Job",
    "Task",
    "Machine",
    "Operator",
    "Operation",
    "Skill",
    "ProductionZone",
    # Supporting models
    "MachineCapability",
    "MachineRequiredSkill",
    "OperatorSkill",
    "TaskOperatorAssignment",
    "TaskMachineOption",
    # API models
    "SolveRequest",
    "SolveJobRequest",
    "SolveResponse",
    "SolveErrorResponse",
    "OptimizationParameters",
    "BusinessConstraints",
    "TaskAssignment",
    "JobSolution",
    "SolutionMetrics",
]
