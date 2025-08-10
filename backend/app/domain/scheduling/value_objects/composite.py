"""
Composite Value Objects

Complex value objects that combine multiple domain concepts like skill requirements,
resource capacities, and task assignments. These represent business concepts that
require multiple pieces of information to be meaningful.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .levels import EfficiencyFactor, SkillLevel
from .time import Duration, Schedule


@dataclass(frozen=True)
class SkillRequirement:
    """
    Represents a skill requirement with skill ID, minimum level, and optionally
    preferred level and certification requirements.

    Used to define what skills are needed for machines, operations, or tasks.
    """

    skill_id: int
    skill_code: str
    skill_name: str
    minimum_level: SkillLevel
    preferred_level: SkillLevel | None = None
    certification_required: bool = False
    certification_must_be_current: bool = True

    def __post_init__(self):
        if self.skill_id <= 0:
            raise ValueError("Skill ID must be positive")
        if not self.skill_code.strip():
            raise ValueError("Skill code cannot be empty")
        if not self.skill_name.strip():
            raise ValueError("Skill name cannot be empty")

        # Validate preferred level is not lower than minimum
        if (
            self.preferred_level is not None
            and self.preferred_level < self.minimum_level
        ):
            raise ValueError("Preferred level cannot be lower than minimum level")

    def __str__(self) -> str:
        """Return human-readable skill requirement."""
        base = f"{self.skill_name} (min: {self.minimum_level})"
        if self.preferred_level:
            base += f", preferred: {self.preferred_level}"
        if self.certification_required:
            base += ", cert required"
        return base

    def is_satisfied_by(self, operator_skill: "OperatorSkill") -> bool:
        """
        Check if an operator's skill satisfies this requirement.

        Args:
            operator_skill: The operator's skill to check

        Returns:
            True if requirement is satisfied, False otherwise
        """
        # Check skill ID matches
        if operator_skill.skill_id != self.skill_id:
            return False

        # Check minimum level
        if not operator_skill.proficiency_level.meets_requirement(self.minimum_level):
            return False

        # Check certification if required
        if self.certification_required:
            if not operator_skill.is_certified:
                return False

            if self.certification_must_be_current and not operator_skill.is_current:
                return False

        return True

    def meets_preferred_level(self, operator_skill: "OperatorSkill") -> bool:
        """Check if operator skill meets preferred level (if specified)."""
        if self.preferred_level is None:
            return True  # No preference specified

        return (
            operator_skill.skill_id == self.skill_id
            and operator_skill.proficiency_level.meets_requirement(self.preferred_level)
        )

    @property
    def requires_expert_level(self) -> bool:
        """Check if requirement needs expert-level skill."""
        return self.minimum_level.is_expert

    @property
    def has_preference(self) -> bool:
        """Check if there's a preferred level above minimum."""
        return self.preferred_level is not None


@dataclass(frozen=True)
class OperatorSkill:
    """
    Represents an operator's skill with proficiency level and certification info.

    Used to track what skills operators have and their proficiency levels.
    """

    skill_id: int
    skill_code: str
    skill_name: str
    proficiency_level: SkillLevel
    certified_date: date | None = None
    expiry_date: date | None = None

    def __post_init__(self):
        if self.skill_id <= 0:
            raise ValueError("Skill ID must be positive")
        if not self.skill_code.strip():
            raise ValueError("Skill code cannot be empty")
        if not self.skill_name.strip():
            raise ValueError("Skill name cannot be empty")

        # Validate date logic
        if (
            self.certified_date is not None
            and self.expiry_date is not None
            and self.expiry_date <= self.certified_date
        ):
            raise ValueError("Expiry date must be after certified date")

    def __str__(self) -> str:
        """Return human-readable operator skill."""
        base = f"{self.skill_name}: {self.proficiency_level}"
        if self.is_certified:
            if self.is_current:
                base += " (certified)"
            else:
                base += " (cert expired)"
        return base

    @property
    def is_certified(self) -> bool:
        """Check if operator has certification for this skill."""
        return self.certified_date is not None

    @property
    def is_current(self) -> bool:
        """Check if certification is current (not expired)."""
        if not self.is_certified:
            return False
        if self.expiry_date is None:
            return True  # No expiry date means permanent certification
        return datetime.now().date() <= self.expiry_date

    @property
    def days_until_expiry(self) -> int | None:
        """Get number of days until certification expires."""
        if not self.is_certified or self.expiry_date is None:
            return None

        days = (self.expiry_date - datetime.now().date()).days
        return max(0, days)

    @property
    def is_expiring_soon(self, threshold_days: int = 30) -> bool:
        """Check if certification is expiring within threshold days."""
        days = self.days_until_expiry
        return days is not None and days <= threshold_days

    def can_satisfy_requirement(self, requirement: SkillRequirement) -> bool:
        """Check if this skill can satisfy a requirement."""
        return requirement.is_satisfied_by(self)


@dataclass(frozen=True)
class ResourceCapacity:
    """
    Represents resource capacity constraints and utilization for machines or operators.

    Tracks current capacity, maximum capacity, utilization rates, and availability.
    """

    resource_id: int
    resource_code: str
    resource_name: str
    max_concurrent_tasks: int
    current_tasks: int = 0
    efficiency_factor: EfficiencyFactor = field(
        default_factory=EfficiencyFactor.standard
    )
    is_bottleneck: bool = False

    def __post_init__(self):
        if self.resource_id <= 0:
            raise ValueError("Resource ID must be positive")
        if not self.resource_code.strip():
            raise ValueError("Resource code cannot be empty")
        if not self.resource_name.strip():
            raise ValueError("Resource name cannot be empty")
        if self.max_concurrent_tasks <= 0:
            raise ValueError("Max concurrent tasks must be positive")
        if self.current_tasks < 0:
            raise ValueError("Current tasks cannot be negative")
        if self.current_tasks > self.max_concurrent_tasks:
            raise ValueError("Current tasks cannot exceed maximum capacity")

    def __str__(self) -> str:
        """Return human-readable resource capacity."""
        return (
            f"{self.resource_name}: {self.current_tasks}/{self.max_concurrent_tasks} "
            f"({self.utilization_percentage:.1f}%)"
        )

    @property
    def available_capacity(self) -> int:
        """Get number of additional tasks this resource can handle."""
        return self.max_concurrent_tasks - self.current_tasks

    @property
    def is_at_capacity(self) -> bool:
        """Check if resource is at full capacity."""
        return self.current_tasks >= self.max_concurrent_tasks

    @property
    def is_available(self) -> bool:
        """Check if resource has available capacity."""
        return self.current_tasks < self.max_concurrent_tasks

    @property
    def utilization_rate(self) -> Decimal:
        """Get utilization rate as decimal (0.0 to 1.0)."""
        if self.max_concurrent_tasks == 0:
            return Decimal("0")
        return Decimal(self.current_tasks) / Decimal(self.max_concurrent_tasks)

    @property
    def utilization_percentage(self) -> Decimal:
        """Get utilization rate as percentage (0 to 100)."""
        return self.utilization_rate * 100

    @property
    def is_underutilized(self, threshold: Decimal = Decimal("0.7")) -> bool:
        """Check if resource is underutilized (below threshold)."""
        return self.utilization_rate < threshold

    @property
    def is_overutilized(self, threshold: Decimal = Decimal("0.9")) -> bool:
        """Check if resource is overutilized (above threshold)."""
        return self.utilization_rate > threshold

    @property
    def effective_capacity_with_efficiency(self) -> Decimal:
        """Get effective capacity adjusted for efficiency factor."""
        base_capacity = Decimal(self.max_concurrent_tasks)
        return base_capacity * Decimal(str(self.efficiency_factor.factor))

    def can_accept_tasks(self, num_tasks: int) -> bool:
        """Check if resource can accept additional tasks."""
        return (self.current_tasks + num_tasks) <= self.max_concurrent_tasks

    def with_additional_tasks(self, num_tasks: int) -> "ResourceCapacity":
        """Create new capacity object with additional tasks assigned."""
        if not self.can_accept_tasks(num_tasks):
            raise ValueError(f"Cannot accept {num_tasks} additional tasks")

        return ResourceCapacity(
            resource_id=self.resource_id,
            resource_code=self.resource_code,
            resource_name=self.resource_name,
            max_concurrent_tasks=self.max_concurrent_tasks,
            current_tasks=self.current_tasks + num_tasks,
            efficiency_factor=self.efficiency_factor,
            is_bottleneck=self.is_bottleneck,
        )

    def with_completed_tasks(self, num_tasks: int) -> "ResourceCapacity":
        """Create new capacity object with tasks completed (removed)."""
        new_current = max(0, self.current_tasks - num_tasks)

        return ResourceCapacity(
            resource_id=self.resource_id,
            resource_code=self.resource_code,
            resource_name=self.resource_name,
            max_concurrent_tasks=self.max_concurrent_tasks,
            current_tasks=new_current,
            efficiency_factor=self.efficiency_factor,
            is_bottleneck=self.is_bottleneck,
        )


@dataclass(frozen=True)
class TaskAssignment:
    """
    Represents a complete task assignment with resource, schedule, and requirements.

    Combines task, resource, timing, and constraint information into a single
    cohesive assignment that can be validated and manipulated.
    """

    task_id: int
    job_id: int
    operation_id: int
    sequence_in_job: int
    assigned_machine_id: int | None
    assigned_operators: frozenset[int]
    schedule: Schedule | None
    estimated_duration: Duration
    setup_duration: Duration
    skill_requirements: frozenset[SkillRequirement]
    is_critical_path: bool = False

    def __post_init__(self):
        if self.task_id <= 0:
            raise ValueError("Task ID must be positive")
        if self.job_id <= 0:
            raise ValueError("Job ID must be positive")
        if self.operation_id <= 0:
            raise ValueError("Operation ID must be positive")
        if self.sequence_in_job <= 0:
            raise ValueError("Sequence in job must be positive")

        # Validate that if scheduled, we have resource assignments
        if self.schedule is not None:
            if self.assigned_machine_id is None and not self.assigned_operators:
                raise ValueError("Scheduled task must have resource assignments")

    def __str__(self) -> str:
        """Return human-readable task assignment."""
        base = f"Task {self.task_id} (Job {self.job_id}, Op {self.sequence_in_job})"
        if self.schedule:
            base += f" scheduled {self.schedule}"
        if self.assigned_machine_id:
            base += f" on machine {self.assigned_machine_id}"
        if self.assigned_operators:
            base += f" with operators {list(self.assigned_operators)}"
        return base

    @property
    def is_scheduled(self) -> bool:
        """Check if task has been scheduled."""
        return self.schedule is not None

    @property
    def is_machine_assigned(self) -> bool:
        """Check if machine has been assigned."""
        return self.assigned_machine_id is not None

    @property
    def is_operators_assigned(self) -> bool:
        """Check if operators have been assigned."""
        return len(self.assigned_operators) > 0

    @property
    def is_fully_assigned(self) -> bool:
        """Check if task is fully assigned (has all required resources)."""
        return (
            self.is_scheduled
            and self.is_machine_assigned
            and self.is_operators_assigned
        )

    @property
    def total_duration(self) -> Duration:
        """Get total duration including setup."""
        return self.setup_duration + self.estimated_duration

    @property
    def requires_skills(self) -> bool:
        """Check if task requires specific skills."""
        return len(self.skill_requirements) > 0

    @property
    def required_skill_codes(self) -> set[str]:
        """Get set of required skill codes."""
        return {req.skill_code for req in self.skill_requirements}

    @property
    def operator_count(self) -> int:
        """Get number of assigned operators."""
        return len(self.assigned_operators)

    def conflicts_with(self, other: "TaskAssignment") -> bool:
        """
        Check if this assignment conflicts with another assignment.

        Conflicts occur when:
        1. Same machine assigned with overlapping schedules
        2. Same operator assigned with overlapping schedules
        """
        if not self.is_scheduled or not other.is_scheduled:
            return False  # Can't conflict if not scheduled

        if not self.schedule.overlaps_with(other.schedule):
            return False  # No time overlap

        # Check machine conflict
        if (
            self.assigned_machine_id is not None
            and self.assigned_machine_id == other.assigned_machine_id
        ):
            return True

        # Check operator conflicts
        if self.assigned_operators & other.assigned_operators:
            return True  # Shared operators

        return False

    def can_be_assigned_operator(
        self, operator_id: int, operator_skills: list[OperatorSkill]
    ) -> bool:
        """
        Check if operator can be assigned to this task.

        Args:
            operator_id: ID of operator to check
            operator_skills: List of operator's skills

        Returns:
            True if operator can be assigned, False otherwise
        """
        # Create skill lookup for efficiency
        skill_lookup = {skill.skill_id: skill for skill in operator_skills}

        # Check all skill requirements
        for requirement in self.skill_requirements:
            if requirement.skill_id not in skill_lookup:
                return False  # Operator doesn't have required skill

            operator_skill = skill_lookup[requirement.skill_id]
            if not requirement.is_satisfied_by(operator_skill):
                return False

        return True

    def with_schedule(self, new_schedule: Schedule) -> "TaskAssignment":
        """Create new assignment with different schedule."""
        return TaskAssignment(
            task_id=self.task_id,
            job_id=self.job_id,
            operation_id=self.operation_id,
            sequence_in_job=self.sequence_in_job,
            assigned_machine_id=self.assigned_machine_id,
            assigned_operators=self.assigned_operators,
            schedule=new_schedule,
            estimated_duration=self.estimated_duration,
            setup_duration=self.setup_duration,
            skill_requirements=self.skill_requirements,
            is_critical_path=self.is_critical_path,
        )

    def with_machine(self, machine_id: int) -> "TaskAssignment":
        """Create new assignment with different machine."""
        return TaskAssignment(
            task_id=self.task_id,
            job_id=self.job_id,
            operation_id=self.operation_id,
            sequence_in_job=self.sequence_in_job,
            assigned_machine_id=machine_id,
            assigned_operators=self.assigned_operators,
            schedule=self.schedule,
            estimated_duration=self.estimated_duration,
            setup_duration=self.setup_duration,
            skill_requirements=self.skill_requirements,
            is_critical_path=self.is_critical_path,
        )

    def with_operators(self, operator_ids: set[int]) -> "TaskAssignment":
        """Create new assignment with different operators."""
        return TaskAssignment(
            task_id=self.task_id,
            job_id=self.job_id,
            operation_id=self.operation_id,
            sequence_in_job=self.sequence_in_job,
            assigned_machine_id=self.assigned_machine_id,
            assigned_operators=frozenset(operator_ids),
            schedule=self.schedule,
            estimated_duration=self.estimated_duration,
            setup_duration=self.setup_duration,
            skill_requirements=self.skill_requirements,
            is_critical_path=self.is_critical_path,
        )


@dataclass(frozen=True)
class ProductionConstraint:
    """
    Represents a production constraint that limits scheduling options.

    Constraints can be temporal (time windows), resource-based (capacity limits),
    or precedence-based (task dependencies).
    """

    constraint_id: int
    constraint_type: str  # "temporal", "resource", "precedence", "skill"
    description: str
    is_hard_constraint: bool = True  # Hard vs soft constraint
    weight: Decimal = Decimal("1.0")  # Weight for soft constraints

    def __post_init__(self):
        if self.constraint_id <= 0:
            raise ValueError("Constraint ID must be positive")
        if not self.constraint_type.strip():
            raise ValueError("Constraint type cannot be empty")
        if not self.description.strip():
            raise ValueError("Description cannot be empty")
        if self.weight < 0:
            raise ValueError("Weight cannot be negative")

    def __str__(self) -> str:
        """Return human-readable constraint."""
        constraint_level = (
            "HARD" if self.is_hard_constraint else f"SOFT(w={self.weight})"
        )
        return (
            f"[{constraint_level}] {self.constraint_type.upper()}: {self.description}"
        )

    @property
    def is_soft_constraint(self) -> bool:
        """Check if this is a soft constraint."""
        return not self.is_hard_constraint

    @property
    def violation_penalty(self) -> Decimal:
        """Get penalty for violating this constraint."""
        if self.is_hard_constraint:
            return Decimal("1000000")  # Very high penalty for hard constraints
        return self.weight * 100  # Scaled penalty for soft constraints


@dataclass(frozen=True)
class WIPConstraint:
    """
    Work-In-Progress constraint for production zones.

    Limits the number of active jobs in a production zone to control flow
    and prevent overloading of resources.
    """

    zone_id: int
    zone_code: str
    zone_name: str
    wip_limit: int
    current_wip: int = 0

    def __post_init__(self):
        if self.zone_id <= 0:
            raise ValueError("Zone ID must be positive")
        if not self.zone_code.strip():
            raise ValueError("Zone code cannot be empty")
        if not self.zone_name.strip():
            raise ValueError("Zone name cannot be empty")
        if self.wip_limit <= 0:
            raise ValueError("WIP limit must be positive")
        if self.current_wip < 0:
            raise ValueError("Current WIP cannot be negative")
        if self.current_wip > self.wip_limit:
            raise ValueError("Current WIP cannot exceed limit")

    def __str__(self) -> str:
        """Return human-readable WIP constraint."""
        return f"{self.zone_name}: {self.current_wip}/{self.wip_limit} WIP"

    @property
    def available_capacity(self) -> int:
        """Get number of additional jobs this zone can accept."""
        return self.wip_limit - self.current_wip

    @property
    def is_at_limit(self) -> bool:
        """Check if zone is at WIP limit."""
        return self.current_wip >= self.wip_limit

    @property
    def is_near_limit(self, threshold: Decimal = Decimal("0.9")) -> bool:
        """Check if zone is near WIP limit."""
        if self.wip_limit == 0:
            return True
        utilization = Decimal(self.current_wip) / Decimal(self.wip_limit)
        return utilization >= threshold

    @property
    def utilization_rate(self) -> Decimal:
        """Get WIP utilization rate as decimal (0.0 to 1.0)."""
        if self.wip_limit == 0:
            return Decimal("1.0")  # Treat as fully utilized
        return Decimal(self.current_wip) / Decimal(self.wip_limit)

    @property
    def utilization_percentage(self) -> Decimal:
        """Get WIP utilization as percentage."""
        return self.utilization_rate * 100

    def can_accept_jobs(self, num_jobs: int) -> bool:
        """Check if zone can accept additional jobs."""
        return (self.current_wip + num_jobs) <= self.wip_limit

    def with_additional_jobs(self, num_jobs: int) -> "WIPConstraint":
        """Create new constraint with additional jobs."""
        if not self.can_accept_jobs(num_jobs):
            raise ValueError(f"Cannot accept {num_jobs} additional jobs")

        return WIPConstraint(
            zone_id=self.zone_id,
            zone_code=self.zone_code,
            zone_name=self.zone_name,
            wip_limit=self.wip_limit,
            current_wip=self.current_wip + num_jobs,
        )

    def with_completed_jobs(self, num_jobs: int) -> "WIPConstraint":
        """Create new constraint with jobs completed (removed)."""
        new_current = max(0, self.current_wip - num_jobs)

        return WIPConstraint(
            zone_id=self.zone_id,
            zone_code=self.zone_code,
            zone_name=self.zone_name,
            wip_limit=self.wip_limit,
            current_wip=new_current,
        )
