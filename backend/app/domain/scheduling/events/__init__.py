"""
Domain Events Module

Exports all domain events and event handling infrastructure.
"""

from .domain_events import (
    # Constraint and conflict events
    ConstraintViolated,
    CriticalPathChanged,
    DeadlineMissed,
    # Base classes
    DomainEvent,
    DomainEventDispatcher,
    DomainEventHandler,
    JobCompleted,
    # Job events
    JobCreated,
    JobDelayed,
    JobStatusChanged,
    # Machine events
    MachineAllocated,
    MachineReleased,
    MachineStatusChanged,
    MaintenanceScheduled,
    # Operator events
    OperatorAssigned,
    OperatorReleased,
    OperatorStatusChanged,
    # Priority and maintenance events
    PriorityChanged,
    ResourceConflictDetected,
    # Schedule events
    SchedulePublished,
    ScheduleUpdated,
    SkillRequirementNotMet,
    TaskAssignmentChanged,
    TaskCompleted,
    TaskDelayed,
    # Task events
    TaskScheduled,
    TaskStarted,
    TaskStatusChanged,
    # Utility functions
    get_event_dispatcher,
    publish_event,
    publish_events,
)
from .aliases import WorkOrderCreated, ResourceAssigned

__all__ = [
    # Base classes
    "DomainEvent",
    "DomainEventHandler",
    "DomainEventDispatcher",
    # Task events
    "TaskScheduled",
    "TaskStarted",
    "TaskCompleted",
    "TaskStatusChanged",
    "TaskAssignmentChanged",
    "TaskDelayed",
    # Job events
    "JobCreated",
    "JobStatusChanged",
    "JobCompleted",
    "JobDelayed",
    # Ubiquitous-language job event alias
    "WorkOrderCreated",
    # Operator/Machine events
    "OperatorAssigned",
    "OperatorReleased",
    "OperatorStatusChanged",
    "MachineAllocated",
    "MachineReleased",
    "MachineStatusChanged",
    # Unified resource event
    "ResourceAssigned",
    # Schedule events
    "SchedulePublished",
    "ScheduleUpdated",
    # Constraint and conflict events
    "ConstraintViolated",
    "ResourceConflictDetected",
    "CriticalPathChanged",
    "SkillRequirementNotMet",
    # Priority and maintenance events
    "PriorityChanged",
    "MaintenanceScheduled",
    "DeadlineMissed",
    # Utility functions
    "get_event_dispatcher",
    "publish_event",
    "publish_events",
]
