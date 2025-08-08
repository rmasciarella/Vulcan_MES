"""
Constraint and Utilization Value Objects

Value objects representing scheduling constraints, precedence relationships,
resource utilization metrics, and optimization objectives.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .time import Duration, Schedule


class ConstraintType(Enum):
    """Types of scheduling constraints."""

    PRECEDENCE = "precedence"  # Task A must complete before Task B
    RESOURCE = "resource"  # Resource capacity constraints
    TEMPORAL = "temporal"  # Time window constraints
    SKILL = "skill"  # Skill requirement constraints
    WIP = "wip"  # Work-in-progress limits
    SETUP = "setup"  # Setup sequence constraints
    CAMPAIGN = "campaign"  # Batch/campaign constraints


class PrecedenceType(Enum):
    """Types of precedence relationships between tasks."""

    FINISH_TO_START = "finish_to_start"  # A finishes, then B starts
    START_TO_START = "start_to_start"  # A starts, then B can start
    FINISH_TO_FINISH = "finish_to_finish"  # A finishes, then B can finish
    START_TO_FINISH = "start_to_finish"  # A starts, then B can finish


@dataclass(frozen=True)
class PrecedenceConstraint:
    """
    Represents a precedence relationship between two tasks.

    Defines that one task (predecessor) must complete some relationship
    with another task (successor) before the successor can proceed.
    """

    constraint_id: int
    predecessor_task_id: int
    successor_task_id: int
    precedence_type: PrecedenceType
    lag_time: Duration = Duration.zero()  # Minimum time between tasks
    is_mandatory: bool = True

    def __post_init__(self):
        if self.constraint_id <= 0:
            raise ValueError("Constraint ID must be positive")
        if self.predecessor_task_id <= 0:
            raise ValueError("Predecessor task ID must be positive")
        if self.successor_task_id <= 0:
            raise ValueError("Successor task ID must be positive")
        if self.predecessor_task_id == self.successor_task_id:
            raise ValueError("Predecessor and successor cannot be the same task")

    def __str__(self) -> str:
        """Return human-readable precedence constraint."""
        relationship = self.precedence_type.value.replace("_", " ")
        base = f"Task {self.predecessor_task_id} --({relationship})--> Task {self.successor_task_id}"
        if not self.lag_time.is_zero:
            base += f" with {self.lag_time} lag"
        if not self.is_mandatory:
            base += " (optional)"
        return base

    def calculate_successor_earliest_time(
        self, predecessor_schedule: Schedule
    ) -> datetime:
        """
        Calculate earliest time successor can start/finish based on predecessor.

        Args:
            predecessor_schedule: Schedule of the predecessor task

        Returns:
            Earliest datetime for successor based on precedence type
        """
        if self.precedence_type == PrecedenceType.FINISH_TO_START:
            return predecessor_schedule.end_time + self.lag_time.to_timedelta()

        elif self.precedence_type == PrecedenceType.START_TO_START:
            return predecessor_schedule.start_time + self.lag_time.to_timedelta()

        elif self.precedence_type == PrecedenceType.FINISH_TO_FINISH:
            return predecessor_schedule.end_time + self.lag_time.to_timedelta()

        elif self.precedence_type == PrecedenceType.START_TO_FINISH:
            return predecessor_schedule.start_time + self.lag_time.to_timedelta()

        else:
            raise ValueError(f"Unknown precedence type: {self.precedence_type}")

    def is_satisfied_by_schedules(
        self, predecessor_schedule: Schedule, successor_schedule: Schedule
    ) -> bool:
        """
        Check if the constraint is satisfied by given schedules.

        Args:
            predecessor_schedule: Schedule of predecessor task
            successor_schedule: Schedule of successor task

        Returns:
            True if constraint is satisfied, False otherwise
        """
        required_time = self.calculate_successor_earliest_time(predecessor_schedule)

        if self.precedence_type in {
            PrecedenceType.FINISH_TO_START,
            PrecedenceType.START_TO_START,
        }:
            return successor_schedule.start_time >= required_time

        else:  # FINISH_TO_FINISH, START_TO_FINISH
            return successor_schedule.end_time >= required_time

    def calculate_violation_time(
        self, predecessor_schedule: Schedule, successor_schedule: Schedule
    ) -> Duration:
        """
        Calculate how much the constraint is violated by given schedules.

        Returns:
            Duration of violation (zero if satisfied)
        """
        if self.is_satisfied_by_schedules(predecessor_schedule, successor_schedule):
            return Duration.zero()

        required_time = self.calculate_successor_earliest_time(predecessor_schedule)

        if self.precedence_type in {
            PrecedenceType.FINISH_TO_START,
            PrecedenceType.START_TO_START,
        }:
            actual_time = successor_schedule.start_time
        else:
            actual_time = successor_schedule.end_time

        if actual_time < required_time:
            violation_seconds = (required_time - actual_time).total_seconds()
            return Duration(int(violation_seconds / 60))

        return Duration.zero()

    @classmethod
    def finish_to_start(
        cls,
        constraint_id: int,
        predecessor_id: int,
        successor_id: int,
        lag_time: Duration = Duration.zero(),
    ) -> "PrecedenceConstraint":
        """Factory method for finish-to-start precedence."""
        return cls(
            constraint_id,
            predecessor_id,
            successor_id,
            PrecedenceType.FINISH_TO_START,
            lag_time,
        )

    @classmethod
    def start_to_start(
        cls,
        constraint_id: int,
        predecessor_id: int,
        successor_id: int,
        lag_time: Duration = Duration.zero(),
    ) -> "PrecedenceConstraint":
        """Factory method for start-to-start precedence."""
        return cls(
            constraint_id,
            predecessor_id,
            successor_id,
            PrecedenceType.START_TO_START,
            lag_time,
        )


@dataclass(frozen=True)
class ResourceConstraint:
    """
    Represents a resource capacity constraint.

    Defines limits on how many tasks a resource can handle simultaneously
    and time-based availability restrictions.
    """

    constraint_id: int
    resource_id: int
    resource_type: str  # "machine", "operator", "zone"
    max_concurrent_tasks: int
    time_restrictions: frozenset[tuple[datetime, datetime]] | None = None
    efficiency_degradation_factor: Decimal = Decimal(
        "1.0"
    )  # Performance impact when near capacity

    def __post_init__(self):
        if self.constraint_id <= 0:
            raise ValueError("Constraint ID must be positive")
        if self.resource_id <= 0:
            raise ValueError("Resource ID must be positive")
        if not self.resource_type.strip():
            raise ValueError("Resource type cannot be empty")
        if self.max_concurrent_tasks <= 0:
            raise ValueError("Max concurrent tasks must be positive")
        if self.efficiency_degradation_factor <= 0:
            raise ValueError("Efficiency degradation factor must be positive")

    def __str__(self) -> str:
        """Return human-readable resource constraint."""
        return (
            f"{self.resource_type.title()} {self.resource_id}: "
            f"max {self.max_concurrent_tasks} concurrent tasks"
        )

    def is_available_during(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if resource is available during given time period."""
        if self.time_restrictions is None:
            return True

        # Check if period conflicts with any restriction
        for restriction_start, restriction_end in self.time_restrictions:
            if start_time < restriction_end and end_time > restriction_start:
                return False  # Conflicts with restriction

        return True

    def can_accept_task(self, current_task_count: int) -> bool:
        """Check if resource can accept another task."""
        return current_task_count < self.max_concurrent_tasks

    def get_efficiency_factor(self, current_task_count: int) -> Decimal:
        """Get efficiency factor based on current load."""
        if current_task_count == 0:
            return Decimal("1.0")

        utilization_rate = Decimal(current_task_count) / Decimal(
            self.max_concurrent_tasks
        )

        # Apply degradation factor as utilization increases
        if utilization_rate >= Decimal("0.8"):  # High utilization
            return self.efficiency_degradation_factor

        return Decimal("1.0")


@dataclass(frozen=True)
class SetupConstraint:
    """
    Represents setup time and sequence constraints between tasks.

    Defines setup requirements when switching between different operations
    or product types on the same resource.
    """

    constraint_id: int
    resource_id: int
    from_operation_id: int | None  # None means from any operation
    to_operation_id: int
    setup_duration: Duration
    setup_cost: Decimal = Decimal("0.0")
    requires_specialist: bool = False
    setup_materials: frozenset[str] = frozenset()

    def __post_init__(self):
        if self.constraint_id <= 0:
            raise ValueError("Constraint ID must be positive")
        if self.resource_id <= 0:
            raise ValueError("Resource ID must be positive")
        if self.to_operation_id <= 0:
            raise ValueError("To operation ID must be positive")
        if self.setup_cost < 0:
            raise ValueError("Setup cost cannot be negative")

    def __str__(self) -> str:
        """Return human-readable setup constraint."""
        from_op = (
            f"Op {self.from_operation_id}"
            if self.from_operation_id
            else "Any operation"
        )
        return (
            f"Setup from {from_op} to Op {self.to_operation_id}: "
            f"{self.setup_duration}"
        )

    def applies_to_transition(
        self, from_operation_id: int | None, to_operation_id: int
    ) -> bool:
        """Check if constraint applies to given operation transition."""
        return to_operation_id == self.to_operation_id and (
            self.from_operation_id is None
            or self.from_operation_id == from_operation_id
        )

    def calculate_total_setup_time(
        self, include_specialist_delay: bool = False
    ) -> Duration:
        """Calculate total setup time including any specialist requirements."""
        base_time = self.setup_duration

        if self.requires_specialist and include_specialist_delay:
            # Add time to find and assign specialist
            specialist_delay = Duration.from_hours(1)  # Assume 1 hour to get specialist
            return base_time + specialist_delay

        return base_time


@dataclass(frozen=True)
class UtilizationMetrics:
    """
    Represents resource utilization metrics and performance indicators.

    Tracks actual vs planned utilization, efficiency metrics,
    and performance trends for scheduling optimization.
    """

    resource_id: int
    resource_type: str
    measurement_period_start: datetime
    measurement_period_end: datetime
    total_available_time: Duration
    total_scheduled_time: Duration
    total_actual_time: Duration
    total_idle_time: Duration
    setup_time: Duration = Duration.zero()
    maintenance_time: Duration = Duration.zero()

    def __post_init__(self):
        if self.resource_id <= 0:
            raise ValueError("Resource ID must be positive")
        if not self.resource_type.strip():
            raise ValueError("Resource type cannot be empty")
        if self.measurement_period_end <= self.measurement_period_start:
            raise ValueError("End time must be after start time")

        # Validate time relationships
        if self.total_scheduled_time > self.total_available_time:
            raise ValueError("Scheduled time cannot exceed available time")
        if self.total_actual_time > self.total_available_time:
            raise ValueError("Actual time cannot exceed available time")

    def __str__(self) -> str:
        """Return human-readable utilization metrics."""
        return (
            f"{self.resource_type.title()} {self.resource_id}: "
            f"{self.utilization_percentage:.1f}% utilized, "
            f"{self.efficiency_percentage:.1f}% efficient"
        )

    @property
    def measurement_duration(self) -> Duration:
        """Get total duration of measurement period."""
        period_seconds = (
            self.measurement_period_end - self.measurement_period_start
        ).total_seconds()
        return Duration(int(period_seconds / 60))

    @property
    def utilization_rate(self) -> Decimal:
        """Get utilization rate (actual time / available time)."""
        if self.total_available_time.is_zero:
            return Decimal("0.0")

        return Decimal(self.total_actual_time.minutes) / Decimal(
            self.total_available_time.minutes
        )

    @property
    def utilization_percentage(self) -> Decimal:
        """Get utilization as percentage."""
        return self.utilization_rate * 100

    @property
    def scheduled_utilization_rate(self) -> Decimal:
        """Get scheduled utilization rate (scheduled time / available time)."""
        if self.total_available_time.is_zero:
            return Decimal("0.0")

        return Decimal(self.total_scheduled_time.minutes) / Decimal(
            self.total_available_time.minutes
        )

    @property
    def efficiency_rate(self) -> Decimal:
        """Get efficiency rate (actual time / scheduled time)."""
        if self.total_scheduled_time.is_zero:
            return Decimal("1.0")  # Assume 100% if no schedule

        return Decimal(self.total_actual_time.minutes) / Decimal(
            self.total_scheduled_time.minutes
        )

    @property
    def efficiency_percentage(self) -> Decimal:
        """Get efficiency as percentage."""
        return self.efficiency_rate * 100

    @property
    def idle_rate(self) -> Decimal:
        """Get idle time rate (idle time / available time)."""
        if self.total_available_time.is_zero:
            return Decimal("0.0")

        return Decimal(self.total_idle_time.minutes) / Decimal(
            self.total_available_time.minutes
        )

    @property
    def setup_overhead_rate(self) -> Decimal:
        """Get setup overhead rate (setup time / total actual time)."""
        total_time = self.total_actual_time + self.setup_time
        if total_time.is_zero:
            return Decimal("0.0")

        return Decimal(self.setup_time.minutes) / Decimal(total_time.minutes)

    @property
    def is_underutilized(self, threshold: Decimal = Decimal("0.7")) -> bool:
        """Check if resource is underutilized."""
        return self.utilization_rate < threshold

    @property
    def is_overutilized(self, threshold: Decimal = Decimal("0.95")) -> bool:
        """Check if resource is overutilized."""
        return self.utilization_rate > threshold

    @property
    def is_inefficient(self, threshold: Decimal = Decimal("0.8")) -> bool:
        """Check if resource is operating inefficiently."""
        return self.efficiency_rate < threshold

    @property
    def has_high_setup_overhead(self, threshold: Decimal = Decimal("0.2")) -> bool:
        """Check if resource has high setup overhead."""
        return self.setup_overhead_rate > threshold

    def compare_with_target(
        self, target_utilization: Decimal, target_efficiency: Decimal
    ) -> dict[str, Decimal]:
        """Compare metrics with target values."""
        return {
            "utilization_variance": self.utilization_rate - target_utilization,
            "efficiency_variance": self.efficiency_rate - target_efficiency,
            "utilization_achievement": self.utilization_rate / target_utilization
            if target_utilization > 0
            else Decimal("1.0"),
            "efficiency_achievement": self.efficiency_rate / target_efficiency
            if target_efficiency > 0
            else Decimal("1.0"),
        }


@dataclass(frozen=True)
class OptimizationObjective:
    """
    Represents an optimization objective for scheduling algorithms.

    Defines what to optimize for (minimize makespan, maximize utilization, etc.)
    with weights and constraints for multi-objective optimization.
    """

    objective_id: int
    objective_name: str
    objective_type: str  # "minimize", "maximize"
    metric_name: str  # "makespan", "utilization", "tardiness", etc.
    weight: Decimal = Decimal("1.0")
    target_value: Decimal | None = None
    is_primary_objective: bool = False

    def __post_init__(self):
        if self.objective_id <= 0:
            raise ValueError("Objective ID must be positive")
        if not self.objective_name.strip():
            raise ValueError("Objective name cannot be empty")
        if self.objective_type.lower() not in {"minimize", "maximize"}:
            raise ValueError("Objective type must be 'minimize' or 'maximize'")
        if not self.metric_name.strip():
            raise ValueError("Metric name cannot be empty")
        if self.weight <= 0:
            raise ValueError("Weight must be positive")

    def __str__(self) -> str:
        """Return human-readable optimization objective."""
        base = f"{self.objective_type.title()} {self.metric_name}"
        if self.target_value is not None:
            base += f" (target: {self.target_value})"
        if self.weight != Decimal("1.0"):
            base += f" weight: {self.weight}"
        if self.is_primary_objective:
            base += " [PRIMARY]"
        return base

    @property
    def is_minimization(self) -> bool:
        """Check if objective is minimization."""
        return self.objective_type.lower() == "minimize"

    @property
    def is_maximization(self) -> bool:
        """Check if objective is maximization."""
        return self.objective_type.lower() == "maximize"

    def calculate_weighted_score(self, actual_value: Decimal) -> Decimal:
        """
        Calculate weighted score for given actual value.

        For minimization: lower values get higher scores
        For maximization: higher values get higher scores
        """
        if self.target_value is not None:
            # Score based on deviation from target
            deviation = abs(actual_value - self.target_value)
            base_score = max(Decimal("0.0"), Decimal("100.0") - deviation)
        else:
            # Score based on value magnitude
            if self.is_minimization:
                # Lower is better - invert the value
                base_score = Decimal("100.0") / (actual_value + Decimal("1.0"))
            else:
                # Higher is better
                base_score = actual_value

        return base_score * self.weight

    @classmethod
    def minimize_makespan(
        cls, objective_id: int, weight: Decimal = Decimal("1.0")
    ) -> "OptimizationObjective":
        """Factory method for minimizing makespan."""
        return cls(
            objective_id,
            "Minimize Makespan",
            "minimize",
            "makespan",
            weight,
            is_primary_objective=True,
        )

    @classmethod
    def maximize_utilization(
        cls, objective_id: int, weight: Decimal = Decimal("1.0")
    ) -> "OptimizationObjective":
        """Factory method for maximizing utilization."""
        return cls(
            objective_id, "Maximize Utilization", "maximize", "utilization", weight
        )

    @classmethod
    def minimize_tardiness(
        cls, objective_id: int, weight: Decimal = Decimal("1.0")
    ) -> "OptimizationObjective":
        """Factory method for minimizing tardiness."""
        return cls(objective_id, "Minimize Tardiness", "minimize", "tardiness", weight)
