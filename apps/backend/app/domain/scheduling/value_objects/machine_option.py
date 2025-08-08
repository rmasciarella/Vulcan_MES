"""
MachineOption Value Object

Represents a machine option for a task with associated durations and requirements.
This is a critical component for flexible scheduling routing logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .duration import Duration


@dataclass(frozen=True)
class MachineOption:
    """
    Represents a machine option for a task with associated durations.
    Immutable value object that defines routing flexibility for tasks.

    This allows tasks to have multiple machine alternatives with different
    processing characteristics, enabling the scheduler to choose the best
    option based on availability and optimization criteria.
    """

    machine_id: UUID
    setup_duration: Duration
    processing_duration: Duration
    requires_operator_full_duration: bool = True

    def __post_init__(self):
        """Validate machine option constraints."""
        if self.setup_duration.minutes < Decimal("0"):
            raise ValueError(
                f"Setup duration cannot be negative: {self.setup_duration.minutes}"
            )
        if self.processing_duration.minutes < Decimal("0"):
            raise ValueError(
                f"Processing duration cannot be negative: {self.processing_duration.minutes}"
            )

    def total_duration(self) -> Duration:
        """Calculate total duration (setup + processing)."""
        return self.setup_duration + self.processing_duration

    @classmethod
    def from_minutes(
        cls,
        machine_id: UUID,
        setup_minutes: int | float | Decimal,
        processing_minutes: int | float | Decimal,
        requires_operator_full_duration: bool = True,
    ) -> MachineOption:
        """
        Factory method to create MachineOption from minute values.

        Args:
            machine_id: ID of the machine
            setup_minutes: Setup time in minutes
            processing_minutes: Processing time in minutes
            requires_operator_full_duration: Whether operator needed for full duration

        Returns:
            New MachineOption instance
        """
        return cls(
            machine_id=machine_id,
            setup_duration=Duration.from_minutes(Decimal(str(setup_minutes))),
            processing_duration=Duration.from_minutes(Decimal(str(processing_minutes))),
            requires_operator_full_duration=requires_operator_full_duration,
        )

    def get_operator_duration(self) -> Duration:
        """
        Get the duration that operators are required.

        Returns:
            Duration for operator requirement (setup only or full duration)
        """
        if self.requires_operator_full_duration:
            return self.total_duration()
        else:
            return self.setup_duration

    def is_unattended_capable(self) -> bool:
        """
        Check if this machine option can run unattended after setup.

        Returns:
            True if machine can run unattended after setup
        """
        return not self.requires_operator_full_duration

    def __str__(self) -> str:
        """String representation."""
        operator_req = "Full" if self.requires_operator_full_duration else "Setup Only"
        return (
            f"MachineOption(machine={self.machine_id}, "
            f"setup={self.setup_duration}, "
            f"processing={self.processing_duration}, "
            f"operator={operator_req})"
        )

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"MachineOption(machine_id={self.machine_id!r}, "
            f"setup_duration={self.setup_duration!r}, "
            f"processing_duration={self.processing_duration!r}, "
            f"requires_operator_full_duration={self.requires_operator_full_duration!r})"
        )
