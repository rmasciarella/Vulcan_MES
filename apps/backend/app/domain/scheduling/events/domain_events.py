"""
Domain Events

Complete domain event system matching DOMAIN.md specification exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from ..value_objects.duration import Duration


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events - matches DOMAIN.md specification exactly."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.now)
    aggregate_id: UUID = None


@dataclass(frozen=True)
class TaskScheduled(DomainEvent):
    """Raised when a task is scheduled to a machine with operators."""

    task_id: UUID
    job_id: UUID
    machine_id: UUID
    operator_ids: list[UUID]
    planned_start: datetime
    planned_end: datetime


@dataclass(frozen=True)
class TaskStarted(DomainEvent):
    """Raised when task production begins."""

    task_id: UUID
    job_id: UUID
    actual_start: datetime
    machine_id: UUID
    operator_ids: list[UUID]


@dataclass(frozen=True)
class TaskCompleted(DomainEvent):
    """Raised when task production ends."""

    task_id: UUID
    job_id: UUID
    actual_end: datetime
    actual_duration: Duration


@dataclass(frozen=True)
class OperatorAssigned(DomainEvent):
    """Raised when operator is assigned to a task."""

    operator_id: UUID
    task_id: UUID
    assignment_type: str  # 'full_duration' or 'setup_only'


@dataclass(frozen=True)
class OperatorReleased(DomainEvent):
    """Raised when operator is released from a task."""

    operator_id: UUID
    task_id: UUID


@dataclass(frozen=True)
class JobDelayed(DomainEvent):
    """Raised when job due date is at risk."""

    job_id: UUID
    original_due_date: datetime
    expected_completion: datetime
    delay_hours: Decimal


@dataclass(frozen=True)
class TaskStatusChanged(DomainEvent):
    """Raised when task status changes."""

    task_id: UUID
    job_id: UUID
    operation_sequence: int
    old_status: str
    new_status: str
    reason: str | None = None


@dataclass(frozen=True)
class TaskAssignmentChanged(DomainEvent):
    """Raised when task resource assignments change."""

    task_id: UUID
    job_id: UUID
    operation_sequence: int
    old_machine_id: UUID | None
    new_machine_id: UUID | None
    operator_assignments: list[UUID]  # List of assigned operator IDs
    reason: str


@dataclass(frozen=True)
class TaskDelayed(DomainEvent):
    """Raised when task is delayed."""

    task_id: UUID
    job_id: UUID
    operation_sequence: int
    original_planned_start: datetime
    new_planned_start: datetime
    delay_minutes: int
    reason: str


@dataclass(frozen=True)
class JobCreated(DomainEvent):
    """Raised when a new job is created."""

    job_id: UUID
    job_number: str
    priority: int
    due_date: datetime | None
    release_date: datetime
    task_count: int


@dataclass(frozen=True)
class JobStatusChanged(DomainEvent):
    """Raised when job status changes."""

    job_id: UUID
    job_number: str
    old_status: str
    new_status: str
    reason: str | None = None


@dataclass(frozen=True)
class JobCompleted(DomainEvent):
    """Raised when all tasks in a job are completed."""

    job_id: UUID
    job_number: str
    completion_time: datetime
    planned_completion: datetime | None
    actual_duration: Duration
    delay_hours: Decimal


@dataclass(frozen=True)
class SchedulePublished(DomainEvent):
    """Raised when a schedule is published."""

    schedule_id: UUID
    version: int
    effective_date: datetime
    task_count: int
    makespan_hours: Decimal


@dataclass(frozen=True)
class ScheduleUpdated(DomainEvent):
    """Raised when a schedule is updated."""

    schedule_id: UUID
    old_version: int
    new_version: int
    changes_description: str
    affected_tasks: list[UUID]


@dataclass(frozen=True)
class MachineAllocated(DomainEvent):
    """Raised when machine is allocated to a task."""

    machine_id: UUID
    task_id: UUID
    job_id: UUID
    allocation_start: datetime
    allocation_end: datetime


@dataclass(frozen=True)
class MachineReleased(DomainEvent):
    """Raised when machine is released from a task."""

    machine_id: UUID
    task_id: UUID
    job_id: UUID
    release_time: datetime
    utilization_hours: Decimal


@dataclass(frozen=True)
class MachineStatusChanged(DomainEvent):
    """Raised when machine status changes."""

    machine_id: UUID
    machine_name: str
    old_status: str
    new_status: str
    reason: str | None = None


@dataclass(frozen=True)
class OperatorStatusChanged(DomainEvent):
    """Raised when operator status changes."""

    operator_id: UUID
    operator_name: str
    old_status: str
    new_status: str
    reason: str | None = None


@dataclass(frozen=True)
class ConstraintViolated(DomainEvent):
    """Raised when a scheduling constraint is violated."""

    constraint_type: str
    constraint_description: str
    violated_by: UUID  # Task, Job, or Resource ID
    violation_details: str


@dataclass(frozen=True)
class ResourceConflictDetected(DomainEvent):
    """Raised when resource conflicts are detected."""

    resource_type: str  # 'machine' or 'operator'
    resource_id: UUID
    conflicting_tasks: list[UUID]
    conflict_time_start: datetime
    conflict_time_end: datetime


@dataclass(frozen=True)
class CriticalPathChanged(DomainEvent):
    """Raised when the critical path changes."""

    job_id: UUID
    old_critical_tasks: list[UUID]
    new_critical_tasks: list[UUID]
    new_makespan_hours: Decimal


@dataclass(frozen=True)
class PriorityChanged(DomainEvent):
    """Raised when job or task priority changes."""

    entity_type: str  # 'job' or 'task'
    entity_id: UUID
    old_priority: int
    new_priority: int
    reason: str | None = None


@dataclass(frozen=True)
class MaintenanceScheduled(DomainEvent):
    """Raised when machine maintenance is scheduled."""

    machine_id: UUID
    machine_name: str
    maintenance_start: datetime
    maintenance_end: datetime
    maintenance_type: str
    affected_tasks: list[UUID]


@dataclass(frozen=True)
class SkillRequirementNotMet(DomainEvent):
    """Raised when operator skill requirement is not met."""

    operator_id: UUID
    task_id: UUID
    required_skill: str
    required_level: int
    operator_level: int | None = None


@dataclass(frozen=True)
class DeadlineMissed(DomainEvent):
    """Raised when a job misses its deadline."""

    job_id: UUID
    job_number: str
    original_due_date: datetime
    actual_completion: datetime
    delay_hours: Decimal
    contributing_factors: list[str]


# Event Handler Interface
class DomainEventHandler:
    """Base interface for domain event handlers."""

    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can handle the given event."""
        raise NotImplementedError

    def handle(self, event: DomainEvent) -> None:
        """Handle the domain event."""
        raise NotImplementedError


# Event Publisher/Dispatcher
class DomainEventDispatcher:
    """Dispatches domain events to registered handlers."""

    def __init__(self):
        self._handlers: list[DomainEventHandler] = []

    def register_handler(self, handler: DomainEventHandler) -> None:
        """Register an event handler."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unregister_handler(self, handler: DomainEventHandler) -> None:
        """Unregister an event handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all capable handlers."""
        for handler in self._handlers:
            if handler.can_handle(event):
                try:
                    handler.handle(event)
                except Exception as e:
                    # Log error but continue with other handlers
                    print(f"Error handling event {event.event_id}: {e}")

    def dispatch_all(self, events: list[DomainEvent]) -> None:
        """Dispatch multiple events."""
        for event in events:
            self.dispatch(event)


# Global event dispatcher instance
_global_dispatcher = DomainEventDispatcher()


def get_event_dispatcher() -> DomainEventDispatcher:
    """Get the global event dispatcher."""
    return _global_dispatcher


def publish_event(event: DomainEvent) -> None:
    """Publish a domain event using the global dispatcher."""
    _global_dispatcher.dispatch(event)


def publish_events(events: list[DomainEvent]) -> None:
    """Publish multiple domain events using the global dispatcher."""
    _global_dispatcher.dispatch_all(events)
