"""Machine entity for production resources and capabilities."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, validator

from ...shared.base import BusinessRuleViolation, DomainEvent, Entity
from ...shared.validation import (
    DataSanitizer,
    ValidationError,
)
from ..value_objects.common import (
    Duration,
    EfficiencyFactor,
    OperatorSkill,
    Skill,
    TimeWindow,
)
from ..value_objects.enums import MachineAutomationLevel, MachineStatus, SkillLevel


class MachineStatusChanged(DomainEvent):
    """Event raised when machine status changes."""

    machine_id: UUID
    machine_code: str
    old_status: MachineStatus
    new_status: MachineStatus
    reason: str | None = None


class MachineCapability(Entity):
    """Represents a machine's capability to perform a specific operation."""

    machine_id: UUID
    operation_id: UUID
    is_primary: bool = Field(
        default=False, description="Primary vs alternative machine"
    )
    processing_time: Duration = Field(description="Time to process one unit")
    setup_time: Duration = Field(default=Duration(minutes=0), description="Setup time")

    def is_valid(self) -> bool:
        """Validate business rules."""
        return self.processing_time.minutes > 0 and self.setup_time.minutes >= 0

    @property
    def total_time_per_unit(self) -> Duration:
        """Get total time per unit including amortized setup."""
        # For single unit, full setup + processing
        return self.setup_time.add(self.processing_time)

    def estimate_total_time(self, quantity: int) -> Duration:
        """
        Estimate total time for a given quantity.

        Args:
            quantity: Number of units to process

        Returns:
            Total estimated time
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        total_minutes = self.setup_time.minutes + (
            self.processing_time.minutes * quantity
        )
        return Duration(minutes=total_minutes)

    @staticmethod
    def create(
        machine_id: UUID,
        operation_id: UUID,
        processing_time_minutes: int,
        setup_time_minutes: int = 0,
        is_primary: bool = False,
    ) -> "MachineCapability":
        """Factory method to create a machine capability."""
        capability = MachineCapability(
            machine_id=machine_id,
            operation_id=operation_id,
            processing_time=Duration(minutes=processing_time_minutes),
            setup_time=Duration(minutes=setup_time_minutes),
            is_primary=is_primary,
        )
        capability.validate()
        return capability


class RequiredSkill(Entity):
    """Represents a skill required to operate a machine."""

    machine_id: UUID
    skill: Skill
    minimum_level: SkillLevel

    def is_valid(self) -> bool:
        """Validate business rules."""
        return bool(self.skill.skill_code)

    def is_satisfied_by(self, operator_skill: OperatorSkill) -> bool:
        """
        Check if an operator's skill satisfies this requirement.

        Args:
            operator_skill: Operator's skill to check

        Returns:
            True if requirement is satisfied
        """
        return operator_skill.skill == self.skill and operator_skill.meets_requirement(
            self.minimum_level
        )


class Machine(Entity):
    """
    Machine entity representing production equipment.

    Machines have capabilities (what operations they can perform), requirements
    (what skills are needed), and availability constraints. They can be in
    different states and have different automation levels.
    """

    machine_code: str = Field(min_length=1, max_length=20)
    machine_name: str = Field(min_length=1, max_length=100)

    @validator("machine_name")
    def sanitize_machine_name(cls, v):
        """Sanitize machine name input."""
        try:
            return DataSanitizer.sanitize_string(v, max_length=100, allow_empty=False)
        except ValidationError as e:
            raise ValueError(e.message)

    automation_level: MachineAutomationLevel
    production_zone_id: UUID | None = None
    status: MachineStatus = Field(default=MachineStatus.AVAILABLE)
    efficiency_factor: EfficiencyFactor = Field(default=EfficiencyFactor(factor=1.0))
    is_bottleneck: bool = Field(
        default=False, description="Identified as a bottleneck resource"
    )

    # Capabilities and requirements (managed as collections)
    _capabilities: dict[UUID, MachineCapability] = Field(default_factory=dict)
    _required_skills: dict[UUID, RequiredSkill] = Field(default_factory=dict)

    # Maintenance and availability
    _maintenance_windows: list[TimeWindow] = Field(default_factory=list)

    @validator("machine_code")
    def validate_machine_code(cls, v):
        """Machine code should be uppercase alphanumeric."""
        try:
            return DataSanitizer.sanitize_code(v, r"^[A-Z0-9_-]+$")
        except ValidationError as e:
            raise ValueError(e.message)

    def is_valid(self) -> bool:
        """Validate business rules."""
        return (
            bool(self.machine_code)
            and bool(self.machine_name)
            and 0.1 <= self.efficiency_factor.factor <= 2.0
        )

    @property
    def is_available_for_work(self) -> bool:
        """Check if machine is available for scheduling work."""
        return self.status.is_available_for_work and not self.is_in_maintenance()

    @property
    def requires_operator_throughout(self) -> bool:
        """Check if machine requires operator for full duration."""
        return self.automation_level.requires_full_operator_time

    @property
    def requires_operator_setup_only(self) -> bool:
        """Check if machine only requires operator for setup."""
        return not self.automation_level.requires_full_operator_time

    def is_in_maintenance(self, at_time: datetime | None = None) -> bool:
        """
        Check if machine is in maintenance at a specific time.

        Args:
            at_time: Time to check (defaults to now)

        Returns:
            True if machine is in maintenance
        """
        check_time = at_time or datetime.utcnow()
        return any(window.contains(check_time) for window in self._maintenance_windows)

    def can_perform_operation(self, operation_id: UUID) -> bool:
        """
        Check if machine can perform a specific operation.

        Args:
            operation_id: ID of the operation

        Returns:
            True if machine has capability for this operation
        """
        return operation_id in self._capabilities

    def get_capability_for_operation(
        self, operation_id: UUID
    ) -> MachineCapability | None:
        """Get machine capability for a specific operation."""
        return self._capabilities.get(operation_id)

    def add_capability(self, capability: MachineCapability) -> None:
        """
        Add a new capability to the machine.

        Args:
            capability: Machine capability to add

        Raises:
            BusinessRuleViolation: If capability already exists
        """
        if capability.machine_id != self.id:
            raise BusinessRuleViolation(
                "CAPABILITY_MACHINE_MISMATCH",
                "Capability machine_id must match machine ID",
            )

        if capability.operation_id in self._capabilities:
            raise BusinessRuleViolation(
                "DUPLICATE_CAPABILITY",
                f"Machine {self.machine_code} already has capability for operation {capability.operation_id}",
            )

        self._capabilities[capability.operation_id] = capability
        self.mark_updated()

    def remove_capability(self, operation_id: UUID) -> None:
        """
        Remove a capability from the machine.

        Args:
            operation_id: ID of the operation capability to remove
        """
        if operation_id in self._capabilities:
            del self._capabilities[operation_id]
            self.mark_updated()

    def add_required_skill(self, required_skill: RequiredSkill) -> None:
        """
        Add a skill requirement for operating this machine.

        Args:
            required_skill: Skill requirement to add

        Raises:
            BusinessRuleViolation: If skill requirement already exists
        """
        if required_skill.machine_id != self.id:
            raise BusinessRuleViolation(
                "SKILL_MACHINE_MISMATCH",
                "Required skill machine_id must match machine ID",
            )

        skill_id = UUID(str(required_skill.skill.skill_code))  # Use skill code as UUID
        if skill_id in self._required_skills:
            raise BusinessRuleViolation(
                "DUPLICATE_SKILL_REQUIREMENT",
                f"Machine {self.machine_code} already requires skill {required_skill.skill.skill_code}",
            )

        self._required_skills[skill_id] = required_skill
        self.mark_updated()

    def remove_required_skill(self, skill_code: str) -> None:
        """
        Remove a skill requirement from the machine.

        Args:
            skill_code: Code of the skill requirement to remove
        """
        skill_id = UUID(str(skill_code))
        if skill_id in self._required_skills:
            del self._required_skills[skill_id]
            self.mark_updated()

    def operator_can_operate(self, operator_skills: list[OperatorSkill]) -> bool:
        """
        Check if an operator with given skills can operate this machine.

        Args:
            operator_skills: List of operator's skills

        Returns:
            True if operator meets all skill requirements
        """
        # If no skills required, anyone can operate
        if not self._required_skills:
            return True

        # Check each required skill
        for required_skill in self._required_skills.values():
            skill_satisfied = any(
                required_skill.is_satisfied_by(operator_skill)
                for operator_skill in operator_skills
            )
            if not skill_satisfied:
                return False

        return True

    def estimate_processing_time(
        self, operation_id: UUID, quantity: int = 1
    ) -> Duration | None:
        """
        Estimate processing time for an operation with given quantity.

        Args:
            operation_id: ID of the operation
            quantity: Number of items to process

        Returns:
            Estimated duration including efficiency factor, or None if incapable
        """
        capability = self.get_capability_for_operation(operation_id)
        if not capability:
            return None

        base_time = capability.estimate_total_time(quantity)
        return self.efficiency_factor.apply_to_duration(base_time)

    def change_status(
        self, new_status: MachineStatus, reason: str | None = None
    ) -> None:
        """
        Change machine status with domain event.

        Args:
            new_status: New machine status
            reason: Optional reason for status change
        """
        if new_status == self.status:
            return  # No change needed

        old_status = self.status
        self.status = new_status
        self.mark_updated()

        # Raise domain event
        self.add_domain_event(
            MachineStatusChanged(
                aggregate_id=self.id,
                machine_id=self.id,
                machine_code=self.machine_code,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
            )
        )

    def schedule_maintenance(self, maintenance_window: TimeWindow) -> None:
        """
        Schedule maintenance for the machine.

        Args:
            maintenance_window: Time window for maintenance

        Raises:
            BusinessRuleViolation: If maintenance window conflicts
        """
        # Check for conflicts with existing maintenance
        for existing_window in self._maintenance_windows:
            if maintenance_window.overlaps_with(existing_window):
                raise BusinessRuleViolation(
                    "MAINTENANCE_CONFLICT",
                    "Maintenance window conflicts with existing maintenance",
                )

        self._maintenance_windows.append(maintenance_window)
        self.mark_updated()

    def cancel_maintenance(self, maintenance_start: datetime) -> None:
        """
        Cancel a scheduled maintenance window.

        Args:
            maintenance_start: Start time of maintenance to cancel
        """
        self._maintenance_windows = [
            window
            for window in self._maintenance_windows
            if window.start_time != maintenance_start
        ]
        self.mark_updated()

    def get_next_available_time(self, after: datetime) -> datetime:
        """
        Get the next time this machine becomes available after a given time.

        Args:
            after: Time to search from

        Returns:
            Next available datetime
        """
        if not self.is_available_for_work:
            # If not available, return far future (should be handled by scheduler)
            return datetime(2099, 12, 31)

        # Check maintenance windows
        for window in self._maintenance_windows:
            if window.start_time > after and after < window.end_time:
                after = window.end_time

        return after

    def mark_as_bottleneck(self) -> None:
        """Mark this machine as a bottleneck resource."""
        if not self.is_bottleneck:
            self.is_bottleneck = True
            self.mark_updated()

    def remove_bottleneck_marking(self) -> None:
        """Remove bottleneck marking from this machine."""
        if self.is_bottleneck:
            self.is_bottleneck = False
            self.mark_updated()

    def get_machine_summary(self) -> dict:
        """Get machine information summary."""
        return {
            "machine_code": self.machine_code,
            "machine_name": self.machine_name,
            "status": self.status.value,
            "automation_level": self.automation_level.value,
            "efficiency_percentage": self.efficiency_factor.percentage,
            "is_bottleneck": self.is_bottleneck,
            "capabilities_count": len(self._capabilities),
            "required_skills_count": len(self._required_skills),
            "is_available_for_work": self.is_available_for_work,
            "maintenance_windows": len(self._maintenance_windows),
        }

    @staticmethod
    def create(
        machine_code: str,
        machine_name: str,
        automation_level: MachineAutomationLevel,
        production_zone_id: UUID | None = None,
        efficiency_factor: float = 1.0,
    ) -> "Machine":
        """
        Factory method to create a new Machine.

        Args:
            machine_code: Unique code for the machine
            machine_name: Human-readable name
            automation_level: Level of automation
            production_zone_id: Optional zone assignment
            efficiency_factor: Efficiency factor (1.0 = standard)

        Returns:
            New Machine instance
        """
        machine = Machine(
            machine_code=machine_code,
            machine_name=machine_name,
            automation_level=automation_level,
            production_zone_id=production_zone_id,
            efficiency_factor=EfficiencyFactor(factor=efficiency_factor),
        )
        machine.validate()
        return machine
