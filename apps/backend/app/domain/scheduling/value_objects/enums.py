"""Domain enums for scheduling."""

from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""

    PLANNED = "planned"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

    @property
    def is_active(self) -> bool:
        """Check if job status represents an active job."""
        return self in {JobStatus.RELEASED, JobStatus.IN_PROGRESS}

    @property
    def is_terminal(self) -> bool:
        """Check if job status is terminal (cannot transition further)."""
        return self in {JobStatus.COMPLETED, JobStatus.CANCELLED}

    def can_transition_to(self, target_status: "JobStatus") -> bool:
        """Check if job can transition from current status to target status."""
        valid_transitions = {
            JobStatus.PLANNED: {JobStatus.RELEASED, JobStatus.CANCELLED},
            JobStatus.RELEASED: {
                JobStatus.IN_PROGRESS,
                JobStatus.ON_HOLD,
                JobStatus.CANCELLED,
            },
            JobStatus.IN_PROGRESS: {
                JobStatus.COMPLETED,
                JobStatus.ON_HOLD,
                JobStatus.CANCELLED,
            },
            JobStatus.ON_HOLD: {JobStatus.RELEASED, JobStatus.CANCELLED},
            JobStatus.COMPLETED: set(),  # Terminal state
            JobStatus.CANCELLED: set(),  # Terminal state
        }
        return target_status in valid_transitions.get(self, set())


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"  # Not yet ready (waiting on precedence)
    READY = "ready"  # All prerequisites met, awaiting resources
    SCHEDULED = "scheduled"  # Resources assigned, start time planned
    IN_PROGRESS = "in_progress"  # Currently being executed
    COMPLETED = "completed"  # Successfully finished
    CANCELLED = "cancelled"  # Cancelled before completion
    FAILED = "failed"  # Failed during execution

    @property
    def is_active(self) -> bool:
        """Check if task status represents an active task."""
        return self in {TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS}

    @property
    def is_terminal(self) -> bool:
        """Check if task status is terminal."""
        return self in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED}

    @property
    def is_executable(self) -> bool:
        """Check if task is ready to be executed."""
        return self in {TaskStatus.READY, TaskStatus.SCHEDULED}

    def can_transition_to(self, target_status: "TaskStatus") -> bool:
        """Check if task can transition from current status to target status."""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.CANCELLED},
            TaskStatus.READY: {TaskStatus.SCHEDULED, TaskStatus.CANCELLED},
            TaskStatus.SCHEDULED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.COMPLETED: set(),  # Terminal state
            TaskStatus.CANCELLED: set(),  # Terminal state
            TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.CANCELLED},  # Can retry
        }
        return target_status in valid_transitions.get(self, set())


class MachineStatus(str, Enum):
    """Machine status enumeration."""

    AVAILABLE = "available"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

    @property
    def is_available_for_work(self) -> bool:
        """Check if machine is available for scheduling work."""
        return self == MachineStatus.AVAILABLE

    @property
    def is_operational(self) -> bool:
        """Check if machine is operational (not offline)."""
        return self != MachineStatus.OFFLINE


class OperatorStatus(str, Enum):
    """Operator status enumeration."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ON_BREAK = "on_break"
    OFF_SHIFT = "off_shift"
    ABSENT = "absent"

    @property
    def is_available_for_work(self) -> bool:
        """Check if operator is available for scheduling work."""
        return self == OperatorStatus.AVAILABLE

    @property
    def is_present(self) -> bool:
        """Check if operator is present at work."""
        return self not in {OperatorStatus.ABSENT, OperatorStatus.OFF_SHIFT}


class SkillLevel(str, Enum):
    """Skill proficiency level enumeration."""

    LEVEL_1 = "1"  # Beginner
    LEVEL_2 = "2"  # Intermediate
    LEVEL_3 = "3"  # Expert

    @property
    def numeric_value(self) -> int:
        """Get numeric value for comparison."""
        return int(self.value)

    def meets_minimum(self, minimum_level: "SkillLevel") -> bool:
        """Check if this skill level meets the minimum requirement."""
        return self.numeric_value >= minimum_level.numeric_value

    @classmethod
    def from_numeric(cls, level: int) -> "SkillLevel":
        """Create SkillLevel from numeric value."""
        if level == 1:
            return cls.LEVEL_1
        elif level == 2:
            return cls.LEVEL_2
        elif level == 3:
            return cls.LEVEL_3
        else:
            raise ValueError(f"Invalid skill level: {level}")


class MachineAutomationLevel(str, Enum):
    """Machine automation level enumeration."""

    ATTENDED = "attended"  # Requires operator for full duration
    UNATTENDED = "unattended"  # Requires operator for setup only

    @property
    def requires_full_operator_time(self) -> bool:
        """Check if machine requires operator for full duration."""
        return self == MachineAutomationLevel.ATTENDED


class PriorityLevel(str, Enum):
    """Priority level enumeration."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric_value(self) -> int:
        """Get numeric value for priority comparison."""
        priority_map = {
            PriorityLevel.LOW: 1,
            PriorityLevel.NORMAL: 2,
            PriorityLevel.HIGH: 3,
            PriorityLevel.CRITICAL: 4,
        }
        return priority_map[self]

    def is_higher_than(self, other: "PriorityLevel") -> bool:
        """Check if this priority is higher than another."""
        return self.numeric_value > other.numeric_value


class AssignmentType(str, Enum):
    """Task operator assignment type enumeration."""

    SETUP = "setup"  # Operator needed for setup only
    FULL_DURATION = "full_duration"  # Operator needed for entire task

    @property
    def requires_full_duration(self) -> bool:
        """Check if assignment requires operator for full task duration."""
        return self == AssignmentType.FULL_DURATION


class ConstraintType(str, Enum):
    """Task precedence constraint type enumeration."""

    FINISH_TO_START = (
        "finish_to_start"  # Predecessor must finish before successor starts
    )
    START_TO_START = "start_to_start"  # Predecessor must start before successor starts
    FINISH_TO_FINISH = (
        "finish_to_finish"  # Predecessor must finish before successor finishes
    )
    START_TO_FINISH = (
        "start_to_finish"  # Predecessor must start before successor finishes
    )


class ScheduleStatus(str, Enum):
    """Schedule status enumeration."""

    DRAFT = "draft"  # Under construction
    PUBLISHED = "published"  # Ready for activation but not yet active
    ACTIVE = "active"  # Currently active schedule
    COMPLETED = "completed"  # Schedule has finished executing
    CANCELLED = "cancelled"  # Schedule was cancelled

    @property
    def is_modifiable(self) -> bool:
        """Check if schedule can be modified."""
        return self == ScheduleStatus.DRAFT

    @property
    def is_active(self) -> bool:
        """Check if schedule is currently active."""
        return self == ScheduleStatus.ACTIVE

    @property
    def is_terminal(self) -> bool:
        """Check if schedule status is terminal."""
        return self in {ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED}

    def can_transition_to(self, target_status: "ScheduleStatus") -> bool:
        """Check if schedule can transition to target status."""
        valid_transitions = {
            ScheduleStatus.DRAFT: {
                ScheduleStatus.PUBLISHED,
                ScheduleStatus.CANCELLED,
            },
            ScheduleStatus.PUBLISHED: {
                ScheduleStatus.ACTIVE,
                ScheduleStatus.DRAFT,  # Can be sent back for revisions
                ScheduleStatus.CANCELLED,
            },
            ScheduleStatus.ACTIVE: {
                ScheduleStatus.COMPLETED,
                ScheduleStatus.CANCELLED,
            },
            ScheduleStatus.COMPLETED: set(),  # Terminal state
            ScheduleStatus.CANCELLED: set(),  # Terminal state
        }
        return target_status in valid_transitions.get(self, set())


class SkillType(str, Enum):
    """Types of skills in the manufacturing system - matches DOMAIN.md specification."""

    MACHINING = "machining"
    WELDING = "welding"
    INSPECTION = "inspection"
    ASSEMBLY = "assembly"
    PROGRAMMING = "programming"

    def __str__(self) -> str:
        """String representation."""
        return self.value.title()

    def __repr__(self) -> str:
        """Representation."""
        return f"SkillType.{self.name}"
