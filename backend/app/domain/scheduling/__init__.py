"""
Production Scheduling Domain

This module contains the complete domain model for production scheduling,
including entities, value objects, repositories, and domain services.

The domain follows Domain-Driven Design (DDD) principles with clear
separation between domain logic and infrastructure concerns.
"""

# Entities
from .entities import (
    Job,
    Machine,
    Operator,
    Task,
)

from .value_objects.enums import (
    MachineStatus,
    OperatorStatus,
    TaskStatus,
)

# Repository Interfaces
from .repositories import (
    JobRepository,
    MachineRepository,
    OperatorRepository,
    ScheduleRepository,
    TaskRepository,
)

# Domain Services
from .services import (
    ConstraintValidationService,
    OptimizationParameters,
    OptimizationResult,
    OptimizationService,
    ResourceAllocation,
    ResourceAllocationService,
    SchedulingRequest,
    SchedulingResult,
    SchedulingService,
    TaskTransition,
    WIPZone,
    WorkflowService,
    WorkflowState,
)

# Value Objects
from .value_objects import Duration, Money, Skill, TimeWindow

__all__ = [
    # Entities
    "Job",
    "Task",
    "TaskStatus",
    "Operator",
    "OperatorStatus",
    "Machine",
    "MachineStatus",
    # Value Objects
    "Duration",
    "TimeWindow",
    "Skill",
    "Money",
    # Repository Interfaces
    "JobRepository",
    "TaskRepository",
    "OperatorRepository",
    "MachineRepository",
    "ScheduleRepository",
    # Domain Services
    "ConstraintValidationService",
    "WIPZone",
    "ResourceAllocationService",
    "ResourceAllocation",
    "OptimizationService",
    "OptimizationParameters",
    "OptimizationResult",
    "WorkflowService",
    "WorkflowState",
    "TaskTransition",
    "SchedulingService",
    "SchedulingRequest",
    "SchedulingResult",
]
