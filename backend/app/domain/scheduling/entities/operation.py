"""Operation entity for manufacturing operations and sequencing."""

from uuid import UUID

from pydantic import Field, validator

from ...shared.base import BusinessRuleViolation, Entity
from ..value_objects.common import Duration


class InvalidOperationSequence(BusinessRuleViolation):
    """Raised when operation sequence is invalid."""

    def __init__(self, sequence_number: int):
        super().__init__(
            "INVALID_OPERATION_SEQUENCE",
            f"Operation sequence number must be between 1 and 100, got: {sequence_number}",
        )


class Operation(Entity):
    """
    Operation entity representing a standard manufacturing operation.

    Operations define the work that needs to be performed as part of a manufacturing
    process. They have a specific sequence within the 1-100 operation flow and
    define standard durations and requirements.
    """

    operation_code: str = Field(min_length=1, max_length=20)
    operation_name: str = Field(min_length=1, max_length=100)
    sequence_number: int = Field(ge=1, le=100, description="Position in 1-100 sequence")
    production_zone_id: UUID | None = None

    # Operation characteristics
    is_critical: bool = Field(default=False, description="Part of critical path")
    standard_duration: Duration = Field(description="Standard processing time")
    setup_duration: Duration = Field(
        default=Duration(minutes=0), description="Setup time"
    )
    description: str | None = None

    # Business configuration
    is_active: bool = Field(default=True)
    requires_quality_check: bool = Field(default=False)

    @validator("operation_code")
    def validate_operation_code(cls, v):
        """Operation code should be uppercase alphanumeric."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Operation code must be alphanumeric with underscores")
        return v.upper()

    @validator("sequence_number")
    def validate_sequence_number(cls, v):
        """Sequence number must be between 1 and 100."""
        if not (1 <= v <= 100):
            raise InvalidOperationSequence(v)
        return v

    def is_valid(self) -> bool:
        """Validate business rules."""
        return (
            bool(self.operation_code)
            and bool(self.operation_name)
            and 1 <= self.sequence_number <= 100
            and self.standard_duration.minutes > 0
            and self.setup_duration.minutes >= 0
        )

    @property
    def total_duration(self) -> Duration:
        """Get total duration including setup and processing."""
        return self.setup_duration.add(self.standard_duration)

    @property
    def is_first_operation(self) -> bool:
        """Check if this is the first operation in sequence."""
        return self.sequence_number == 1

    @property
    def is_last_operation(self) -> bool:
        """Check if this is the last operation in sequence."""
        return self.sequence_number == 100

    @property
    def next_sequence_number(self) -> int | None:
        """Get the next sequence number, if exists."""
        return self.sequence_number + 1 if self.sequence_number < 100 else None

    @property
    def previous_sequence_number(self) -> int | None:
        """Get the previous sequence number, if exists."""
        return self.sequence_number - 1 if self.sequence_number > 1 else None

    def can_be_performed_after(self, predecessor_operation: "Operation") -> bool:
        """
        Check if this operation can be performed after another operation.

        Args:
            predecessor_operation: The operation that would come before this one

        Returns:
            True if this operation can follow the predecessor
        """
        # Basic sequence check - this operation should come after predecessor
        if self.sequence_number <= predecessor_operation.sequence_number:
            return False

        # Both operations should be active
        if not (self.is_active and predecessor_operation.is_active):
            return False

        # Additional business rules can be added here
        return True

    def estimate_duration_for_quantity(self, quantity: int) -> Duration:
        """
        Estimate total duration for processing a specific quantity.

        Args:
            quantity: Number of items to process

        Returns:
            Estimated duration including setup and processing time per item
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        # Setup once + processing time per item
        total_minutes = self.setup_duration.minutes + (
            self.standard_duration.minutes * quantity
        )
        return Duration(minutes=total_minutes)

    def adjust_duration_for_efficiency(
        self, base_duration: Duration, efficiency_factor: float
    ) -> Duration:
        """
        Adjust operation duration based on efficiency factor.

        Args:
            base_duration: Base duration to adjust
            efficiency_factor: Efficiency factor (1.0 = standard, >1.0 = faster, <1.0 = slower)

        Returns:
            Adjusted duration
        """
        if efficiency_factor <= 0:
            raise ValueError("Efficiency factor must be positive")

        adjusted_minutes = int(base_duration.minutes / efficiency_factor)
        return Duration(minutes=max(1, adjusted_minutes))  # Minimum 1 minute

    def is_compatible_with_zone(self, zone: "ProductionZone") -> bool:
        """
        Check if this operation is compatible with a production zone.

        Args:
            zone: Production zone to check compatibility with

        Returns:
            True if operation can be performed in the zone
        """
        # If operation has no zone assignment, it can work anywhere
        if self.production_zone_id is None:
            return True

        # Otherwise, must match the assigned zone
        return self.production_zone_id == zone.id

    def mark_critical(self) -> None:
        """Mark this operation as critical to the manufacturing process."""
        if not self.is_critical:
            self.is_critical = True
            self.mark_updated()

    def remove_critical_marking(self) -> None:
        """Remove critical marking from this operation."""
        if self.is_critical:
            self.is_critical = False
            self.mark_updated()

    def update_duration(
        self,
        new_standard_duration: Duration,
        new_setup_duration: Duration | None = None,
    ) -> None:
        """
        Update operation durations.

        Args:
            new_standard_duration: New standard processing duration
            new_setup_duration: New setup duration (optional)
        """
        self.standard_duration = new_standard_duration
        if new_setup_duration is not None:
            self.setup_duration = new_setup_duration
        self.mark_updated()

    def assign_to_zone(self, zone_id: UUID) -> None:
        """
        Assign this operation to a production zone.

        Args:
            zone_id: ID of the production zone
        """
        self.production_zone_id = zone_id
        self.mark_updated()

    def remove_zone_assignment(self) -> None:
        """Remove zone assignment from this operation."""
        self.production_zone_id = None
        self.mark_updated()

    def deactivate(self) -> None:
        """
        Deactivate this operation.

        Raises:
            BusinessRuleViolation: If operation is critical and cannot be deactivated
        """
        if self.is_critical:
            raise BusinessRuleViolation(
                "CANNOT_DEACTIVATE_CRITICAL_OPERATION",
                f"Critical operation {self.operation_code} cannot be deactivated",
            )

        self.is_active = False
        self.mark_updated()

    def reactivate(self) -> None:
        """Reactivate this operation."""
        self.is_active = True
        self.mark_updated()

    def get_operation_info(self) -> dict:
        """Get operation information summary."""
        return {
            "operation_code": self.operation_code,
            "operation_name": self.operation_name,
            "sequence_number": self.sequence_number,
            "is_critical": self.is_critical,
            "standard_duration": str(self.standard_duration),
            "setup_duration": str(self.setup_duration),
            "total_duration": str(self.total_duration),
            "is_active": self.is_active,
            "requires_quality_check": self.requires_quality_check,
        }

    @staticmethod
    def create(
        operation_code: str,
        operation_name: str,
        sequence_number: int,
        standard_duration_minutes: int,
        setup_duration_minutes: int = 0,
        production_zone_id: UUID | None = None,
        is_critical: bool = False,
        description: str | None = None,
    ) -> "Operation":
        """
        Factory method to create a new Operation.

        Args:
            operation_code: Unique code for the operation
            operation_name: Human-readable name
            sequence_number: Position in 1-100 sequence
            standard_duration_minutes: Standard processing time in minutes
            setup_duration_minutes: Setup time in minutes
            production_zone_id: Optional zone assignment
            is_critical: Whether operation is on critical path
            description: Optional description

        Returns:
            New Operation instance
        """
        operation = Operation(
            operation_code=operation_code,
            operation_name=operation_name,
            sequence_number=sequence_number,
            production_zone_id=production_zone_id,
            is_critical=is_critical,
            standard_duration=Duration(minutes=standard_duration_minutes),
            setup_duration=Duration(minutes=setup_duration_minutes),
            description=description,
        )
        operation.validate()
        return operation
