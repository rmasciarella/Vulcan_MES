"""
Status Value Objects

Immutable value objects representing various status enums from the domain model.
These include job status, task status, machine status, and operator status with
proper validation and state transition rules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class StatusTransitionError(ValueError):
    """Raised when an invalid status transition is attempted."""

    pass


@dataclass(frozen=True)
class StatusValue(ABC):
    """Base class for all status value objects with transition validation."""

    @property
    @abstractmethod
    def allowed_transitions(self) -> frozenset[str]:
        """Return the set of statuses this status can transition to."""
        pass

    @abstractmethod
    def can_transition_to(self, new_status: "StatusValue") -> bool:
        """Check if transition to new status is allowed."""
        pass

    @abstractmethod
    def transition_to(self, new_status: "StatusValue") -> "StatusValue":
        """Validate and return new status or raise StatusTransitionError."""
        pass


class JobStatusType(Enum):
    """Job status enumeration matching database schema."""

    PLANNED = "planned"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobStatus(StatusValue):
    """
    Represents the status of a job in the production system.

    Valid transitions:
    - planned → released, on_hold, cancelled
    - released → in_progress, on_hold, cancelled
    - in_progress → completed, on_hold, cancelled
    - on_hold → released, cancelled
    - completed → (no transitions allowed - terminal state)
    - cancelled → (no transitions allowed - terminal state)
    """

    status: JobStatusType

    def __post_init__(self):
        if not isinstance(self.status, JobStatusType):
            raise ValueError(f"Invalid job status: {self.status}")

    @property
    def allowed_transitions(self) -> frozenset[str]:
        """Get allowed status transitions from current status."""
        transitions = {
            JobStatusType.PLANNED: frozenset(
                [
                    JobStatusType.RELEASED.value,
                    JobStatusType.ON_HOLD.value,
                    JobStatusType.CANCELLED.value,
                ]
            ),
            JobStatusType.RELEASED: frozenset(
                [
                    JobStatusType.IN_PROGRESS.value,
                    JobStatusType.ON_HOLD.value,
                    JobStatusType.CANCELLED.value,
                ]
            ),
            JobStatusType.IN_PROGRESS: frozenset(
                [
                    JobStatusType.COMPLETED.value,
                    JobStatusType.ON_HOLD.value,
                    JobStatusType.CANCELLED.value,
                ]
            ),
            JobStatusType.ON_HOLD: frozenset(
                [JobStatusType.RELEASED.value, JobStatusType.CANCELLED.value]
            ),
            JobStatusType.COMPLETED: frozenset(),  # Terminal state
            JobStatusType.CANCELLED: frozenset(),  # Terminal state
        }
        return transitions[self.status]

    def can_transition_to(self, new_status: "JobStatus") -> bool:
        """Check if transition to new status is valid."""
        if not isinstance(new_status, JobStatus):
            return False
        return new_status.status.value in self.allowed_transitions

    def transition_to(self, new_status: "JobStatus") -> "JobStatus":
        """Validate transition and return new status."""
        if not self.can_transition_to(new_status):
            raise StatusTransitionError(
                f"Invalid job status transition from {self.status.value} to {new_status.status.value}"
            )
        return new_status

    @property
    def is_active(self) -> bool:
        """Check if job is in an active (non-terminal) state."""
        return self.status not in {JobStatusType.COMPLETED, JobStatusType.CANCELLED}

    @property
    def is_schedulable(self) -> bool:
        """Check if job can be scheduled for work."""
        return self.status in {JobStatusType.RELEASED, JobStatusType.IN_PROGRESS}

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal (no further transitions allowed)."""
        return len(self.allowed_transitions) == 0

    @classmethod
    def planned(cls) -> "JobStatus":
        """Factory method for planned status."""
        return cls(JobStatusType.PLANNED)

    @classmethod
    def released(cls) -> "JobStatus":
        """Factory method for released status."""
        return cls(JobStatusType.RELEASED)

    @classmethod
    def in_progress(cls) -> "JobStatus":
        """Factory method for in-progress status."""
        return cls(JobStatusType.IN_PROGRESS)

    @classmethod
    def completed(cls) -> "JobStatus":
        """Factory method for completed status."""
        return cls(JobStatusType.COMPLETED)

    @classmethod
    def on_hold(cls) -> "JobStatus":
        """Factory method for on-hold status."""
        return cls(JobStatusType.ON_HOLD)

    @classmethod
    def cancelled(cls) -> "JobStatus":
        """Factory method for cancelled status."""
        return cls(JobStatusType.CANCELLED)


class TaskStatusType(Enum):
    """Task status enumeration matching database schema."""

    PENDING = "pending"  # Not yet ready (waiting on precedence)
    READY = "ready"  # All prerequisites met, awaiting resources
    SCHEDULED = "scheduled"  # Resources assigned, start time planned
    IN_PROGRESS = "in_progress"  # Currently being executed
    COMPLETED = "completed"  # Successfully finished
    CANCELLED = "cancelled"  # Cancelled before completion
    FAILED = "failed"  # Failed during execution


@dataclass(frozen=True)
class TaskStatus(StatusValue):
    """
    Represents the status of a task within a job.

    Valid transitions:
    - pending → ready, cancelled
    - ready → scheduled, cancelled
    - scheduled → in_progress, ready, cancelled
    - in_progress → completed, failed, cancelled
    - completed → (no transitions allowed - terminal state)
    - cancelled → (no transitions allowed - terminal state)
    - failed → ready (for rework), cancelled
    """

    status: TaskStatusType

    def __post_init__(self):
        if not isinstance(self.status, TaskStatusType):
            raise ValueError(f"Invalid task status: {self.status}")

    @property
    def allowed_transitions(self) -> frozenset[str]:
        """Get allowed status transitions from current status."""
        transitions = {
            TaskStatusType.PENDING: frozenset(
                [TaskStatusType.READY.value, TaskStatusType.CANCELLED.value]
            ),
            TaskStatusType.READY: frozenset(
                [TaskStatusType.SCHEDULED.value, TaskStatusType.CANCELLED.value]
            ),
            TaskStatusType.SCHEDULED: frozenset(
                [
                    TaskStatusType.IN_PROGRESS.value,
                    TaskStatusType.READY.value,
                    TaskStatusType.CANCELLED.value,
                ]
            ),
            TaskStatusType.IN_PROGRESS: frozenset(
                [
                    TaskStatusType.COMPLETED.value,
                    TaskStatusType.FAILED.value,
                    TaskStatusType.CANCELLED.value,
                ]
            ),
            TaskStatusType.COMPLETED: frozenset(),  # Terminal state
            TaskStatusType.CANCELLED: frozenset(),  # Terminal state
            TaskStatusType.FAILED: frozenset(
                [
                    TaskStatusType.READY.value,  # For rework
                    TaskStatusType.CANCELLED.value,
                ]
            ),
        }
        return transitions[self.status]

    def can_transition_to(self, new_status: "TaskStatus") -> bool:
        """Check if transition to new status is valid."""
        if not isinstance(new_status, TaskStatus):
            return False
        return new_status.status.value in self.allowed_transitions

    def transition_to(self, new_status: "TaskStatus") -> "TaskStatus":
        """Validate transition and return new status."""
        if not self.can_transition_to(new_status):
            raise StatusTransitionError(
                f"Invalid task status transition from {self.status.value} to {new_status.status.value}"
            )
        return new_status

    @property
    def is_active(self) -> bool:
        """Check if task is in an active (non-terminal) state."""
        return self.status not in {TaskStatusType.COMPLETED, TaskStatusType.CANCELLED}

    @property
    def is_schedulable(self) -> bool:
        """Check if task can be scheduled for resources."""
        return self.status == TaskStatusType.READY

    @property
    def is_executing(self) -> bool:
        """Check if task is currently being executed."""
        return self.status == TaskStatusType.IN_PROGRESS

    @property
    def is_waiting(self) -> bool:
        """Check if task is waiting for prerequisites or resources."""
        return self.status in {TaskStatusType.PENDING, TaskStatusType.READY}

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal (no further transitions allowed)."""
        return len(self.allowed_transitions) == 0

    @property
    def can_be_reworked(self) -> bool:
        """Check if task can be reworked (failed tasks only)."""
        return self.status == TaskStatusType.FAILED

    @classmethod
    def pending(cls) -> "TaskStatus":
        """Factory method for pending status."""
        return cls(TaskStatusType.PENDING)

    @classmethod
    def ready(cls) -> "TaskStatus":
        """Factory method for ready status."""
        return cls(TaskStatusType.READY)

    @classmethod
    def scheduled(cls) -> "TaskStatus":
        """Factory method for scheduled status."""
        return cls(TaskStatusType.SCHEDULED)

    @classmethod
    def in_progress(cls) -> "TaskStatus":
        """Factory method for in-progress status."""
        return cls(TaskStatusType.IN_PROGRESS)

    @classmethod
    def completed(cls) -> "TaskStatus":
        """Factory method for completed status."""
        return cls(TaskStatusType.COMPLETED)

    @classmethod
    def cancelled(cls) -> "TaskStatus":
        """Factory method for cancelled status."""
        return cls(TaskStatusType.CANCELLED)

    @classmethod
    def failed(cls) -> "TaskStatus":
        """Factory method for failed status."""
        return cls(TaskStatusType.FAILED)


class MachineStatusType(Enum):
    """Machine status enumeration matching database schema."""

    AVAILABLE = "available"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


@dataclass(frozen=True)
class MachineStatus(StatusValue):
    """
    Represents the status of a machine in the production system.

    Valid transitions:
    - available → busy, maintenance, offline
    - busy → available, maintenance, offline
    - maintenance → available, offline
    - offline → available, maintenance
    """

    status: MachineStatusType

    def __post_init__(self):
        if not isinstance(self.status, MachineStatusType):
            raise ValueError(f"Invalid machine status: {self.status}")

    @property
    def allowed_transitions(self) -> frozenset[str]:
        """Get allowed status transitions from current status."""
        transitions = {
            MachineStatusType.AVAILABLE: frozenset(
                [
                    MachineStatusType.BUSY.value,
                    MachineStatusType.MAINTENANCE.value,
                    MachineStatusType.OFFLINE.value,
                ]
            ),
            MachineStatusType.BUSY: frozenset(
                [
                    MachineStatusType.AVAILABLE.value,
                    MachineStatusType.MAINTENANCE.value,
                    MachineStatusType.OFFLINE.value,
                ]
            ),
            MachineStatusType.MAINTENANCE: frozenset(
                [MachineStatusType.AVAILABLE.value, MachineStatusType.OFFLINE.value]
            ),
            MachineStatusType.OFFLINE: frozenset(
                [MachineStatusType.AVAILABLE.value, MachineStatusType.MAINTENANCE.value]
            ),
        }
        return transitions[self.status]

    def can_transition_to(self, new_status: "MachineStatus") -> bool:
        """Check if transition to new status is valid."""
        if not isinstance(new_status, MachineStatus):
            return False
        return new_status.status.value in self.allowed_transitions

    def transition_to(self, new_status: "MachineStatus") -> "MachineStatus":
        """Validate transition and return new status."""
        if not self.can_transition_to(new_status):
            raise StatusTransitionError(
                f"Invalid machine status transition from {self.status.value} to {new_status.status.value}"
            )
        return new_status

    @property
    def is_available_for_work(self) -> bool:
        """Check if machine is available for scheduling work."""
        return self.status == MachineStatusType.AVAILABLE

    @property
    def is_operational(self) -> bool:
        """Check if machine is operational (available or busy)."""
        return self.status in {MachineStatusType.AVAILABLE, MachineStatusType.BUSY}

    @property
    def requires_intervention(self) -> bool:
        """Check if machine requires human intervention."""
        return self.status in {MachineStatusType.MAINTENANCE, MachineStatusType.OFFLINE}

    @classmethod
    def available(cls) -> "MachineStatus":
        """Factory method for available status."""
        return cls(MachineStatusType.AVAILABLE)

    @classmethod
    def busy(cls) -> "MachineStatus":
        """Factory method for busy status."""
        return cls(MachineStatusType.BUSY)

    @classmethod
    def maintenance(cls) -> "MachineStatus":
        """Factory method for maintenance status."""
        return cls(MachineStatusType.MAINTENANCE)

    @classmethod
    def offline(cls) -> "MachineStatus":
        """Factory method for offline status."""
        return cls(MachineStatusType.OFFLINE)


class OperatorStatusType(Enum):
    """Operator status enumeration matching database schema."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ON_BREAK = "on_break"
    OFF_SHIFT = "off_shift"
    ABSENT = "absent"


@dataclass(frozen=True)
class OperatorStatus(StatusValue):
    """
    Represents the status of an operator in the production system.

    Valid transitions:
    - available → assigned, on_break, off_shift, absent
    - assigned → available, on_break, off_shift, absent
    - on_break → available, assigned, off_shift, absent
    - off_shift → available, absent
    - absent → available, off_shift
    """

    status: OperatorStatusType

    def __post_init__(self):
        if not isinstance(self.status, OperatorStatusType):
            raise ValueError(f"Invalid operator status: {self.status}")

    @property
    def allowed_transitions(self) -> frozenset[str]:
        """Get allowed status transitions from current status."""
        transitions = {
            OperatorStatusType.AVAILABLE: frozenset(
                [
                    OperatorStatusType.ASSIGNED.value,
                    OperatorStatusType.ON_BREAK.value,
                    OperatorStatusType.OFF_SHIFT.value,
                    OperatorStatusType.ABSENT.value,
                ]
            ),
            OperatorStatusType.ASSIGNED: frozenset(
                [
                    OperatorStatusType.AVAILABLE.value,
                    OperatorStatusType.ON_BREAK.value,
                    OperatorStatusType.OFF_SHIFT.value,
                    OperatorStatusType.ABSENT.value,
                ]
            ),
            OperatorStatusType.ON_BREAK: frozenset(
                [
                    OperatorStatusType.AVAILABLE.value,
                    OperatorStatusType.ASSIGNED.value,
                    OperatorStatusType.OFF_SHIFT.value,
                    OperatorStatusType.ABSENT.value,
                ]
            ),
            OperatorStatusType.OFF_SHIFT: frozenset(
                [OperatorStatusType.AVAILABLE.value, OperatorStatusType.ABSENT.value]
            ),
            OperatorStatusType.ABSENT: frozenset(
                [OperatorStatusType.AVAILABLE.value, OperatorStatusType.OFF_SHIFT.value]
            ),
        }
        return transitions[self.status]

    def can_transition_to(self, new_status: "OperatorStatus") -> bool:
        """Check if transition to new status is valid."""
        if not isinstance(new_status, OperatorStatus):
            return False
        return new_status.status.value in self.allowed_transitions

    def transition_to(self, new_status: "OperatorStatus") -> "OperatorStatus":
        """Validate transition and return new status."""
        if not self.can_transition_to(new_status):
            raise StatusTransitionError(
                f"Invalid operator status transition from {self.status.value} to {new_status.status.value}"
            )
        return new_status

    @property
    def is_available_for_work(self) -> bool:
        """Check if operator is available for scheduling work."""
        return self.status == OperatorStatusType.AVAILABLE

    @property
    def is_working(self) -> bool:
        """Check if operator is currently working."""
        return self.status == OperatorStatusType.ASSIGNED

    @property
    def is_on_duty(self) -> bool:
        """Check if operator is on duty (available, assigned, or on break)."""
        return self.status in {
            OperatorStatusType.AVAILABLE,
            OperatorStatusType.ASSIGNED,
            OperatorStatusType.ON_BREAK,
        }

    @property
    def is_temporarily_unavailable(self) -> bool:
        """Check if operator is temporarily unavailable (on break)."""
        return self.status == OperatorStatusType.ON_BREAK

    @property
    def is_unavailable(self) -> bool:
        """Check if operator is unavailable for extended period."""
        return self.status in {OperatorStatusType.OFF_SHIFT, OperatorStatusType.ABSENT}

    @classmethod
    def available(cls) -> "OperatorStatus":
        """Factory method for available status."""
        return cls(OperatorStatusType.AVAILABLE)

    @classmethod
    def assigned(cls) -> "OperatorStatus":
        """Factory method for assigned status."""
        return cls(OperatorStatusType.ASSIGNED)

    @classmethod
    def on_break(cls) -> "OperatorStatus":
        """Factory method for on-break status."""
        return cls(OperatorStatusType.ON_BREAK)

    @classmethod
    def off_shift(cls) -> "OperatorStatus":
        """Factory method for off-shift status."""
        return cls(OperatorStatusType.OFF_SHIFT)

    @classmethod
    def absent(cls) -> "OperatorStatus":
        """Factory method for absent status."""
        return cls(OperatorStatusType.ABSENT)
