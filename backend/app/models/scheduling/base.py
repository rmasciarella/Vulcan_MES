"""Base enums and types for scheduling SQLModel classes."""

from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration matching SQL schema."""

    PLANNED = "planned"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Task status enumeration matching SQL schema."""

    PENDING = "pending"
    READY = "ready"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MachineStatus(str, Enum):
    """Machine status enumeration matching SQL schema."""

    AVAILABLE = "available"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class OperatorStatus(str, Enum):
    """Operator status enumeration matching SQL schema."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ON_BREAK = "on_break"
    OFF_SHIFT = "off_shift"
    ABSENT = "absent"


class SkillLevel(str, Enum):
    """Skill level enumeration matching SQL schema."""

    LEVEL_1 = "1"
    LEVEL_2 = "2"
    LEVEL_3 = "3"


class MachineAutomationLevel(str, Enum):
    """Machine automation level matching SQL schema."""

    ATTENDED = "attended"
    UNATTENDED = "unattended"


class PriorityLevel(str, Enum):
    """Priority level enumeration matching SQL schema."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AssignmentType(str, Enum):
    """Operator assignment type enumeration."""

    SETUP = "setup"
    FULL_DURATION = "full_duration"
