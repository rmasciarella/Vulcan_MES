"""
Level and Skill Value Objects

Immutable value objects representing skill levels, automation levels, priority levels,
and related domain concepts from the production scheduling system.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum


class SkillLevelType(IntEnum):
    """
    Skill level enumeration with ordinal values for comparison.
    Higher numbers indicate higher skill levels.
    """

    LEVEL_1 = 1  # Basic/Beginner
    LEVEL_2 = 2  # Intermediate
    LEVEL_3 = 3  # Advanced/Expert


@dataclass(frozen=True)
class SkillLevel:
    """
    Represents a skill proficiency level with comparison capabilities.

    Skill levels are ordinal values where higher numbers indicate
    greater proficiency. Level 1 is basic, Level 2 is intermediate,
    and Level 3 is expert level.
    """

    level: SkillLevelType

    def __post_init__(self):
        if not isinstance(self.level, SkillLevelType):
            if isinstance(self.level, int | str):
                try:
                    # Convert string or int to SkillLevelType
                    level_value = int(self.level)
                    if level_value not in {1, 2, 3}:
                        raise ValueError(
                            f"Skill level must be 1, 2, or 3, got {level_value}"
                        )
                    object.__setattr__(self, "level", SkillLevelType(level_value))
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid skill level: {self.level}")
            else:
                raise ValueError(f"Invalid skill level type: {type(self.level)}")

    def __str__(self) -> str:
        """Return human-readable skill level."""
        level_names = {
            SkillLevelType.LEVEL_1: "Basic",
            SkillLevelType.LEVEL_2: "Intermediate",
            SkillLevelType.LEVEL_3: "Expert",
        }
        return level_names[self.level]

    def __int__(self) -> int:
        """Return numeric value for database storage."""
        return self.level.value

    def __lt__(self, other: "SkillLevel") -> bool:
        """Compare skill levels - lower levels are 'less than' higher levels."""
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.level < other.level

    def __le__(self, other: "SkillLevel") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.level <= other.level

    def __gt__(self, other: "SkillLevel") -> bool:
        """Greater than comparison."""
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.level > other.level

    def __ge__(self, other: "SkillLevel") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.level >= other.level

    def meets_requirement(self, required_level: "SkillLevel") -> bool:
        """Check if this skill level meets or exceeds the required level."""
        return self >= required_level

    def can_mentor(self, other_level: "SkillLevel") -> bool:
        """Check if this level can mentor another level (must be higher)."""
        return self > other_level

    @property
    def is_basic(self) -> bool:
        """Check if this is basic level (Level 1)."""
        return self.level == SkillLevelType.LEVEL_1

    @property
    def is_intermediate(self) -> bool:
        """Check if this is intermediate level (Level 2)."""
        return self.level == SkillLevelType.LEVEL_2

    @property
    def is_expert(self) -> bool:
        """Check if this is expert level (Level 3)."""
        return self.level == SkillLevelType.LEVEL_3

    @property
    def numeric_value(self) -> int:
        """Get numeric representation of skill level."""
        return self.level.value

    @classmethod
    def basic(cls) -> "SkillLevel":
        """Factory method for basic skill level."""
        return cls(SkillLevelType.LEVEL_1)

    @classmethod
    def intermediate(cls) -> "SkillLevel":
        """Factory method for intermediate skill level."""
        return cls(SkillLevelType.LEVEL_2)

    @classmethod
    def expert(cls) -> "SkillLevel":
        """Factory method for expert skill level."""
        return cls(SkillLevelType.LEVEL_3)

    @classmethod
    def from_string(cls, level_str: str) -> "SkillLevel":
        """Create skill level from string representation."""
        level_map = {
            "1": SkillLevelType.LEVEL_1,
            "2": SkillLevelType.LEVEL_2,
            "3": SkillLevelType.LEVEL_3,
            "basic": SkillLevelType.LEVEL_1,
            "intermediate": SkillLevelType.LEVEL_2,
            "expert": SkillLevelType.LEVEL_3,
            "beginner": SkillLevelType.LEVEL_1,
            "advanced": SkillLevelType.LEVEL_3,
        }

        normalized = level_str.lower().strip()
        if normalized not in level_map:
            raise ValueError(f"Unknown skill level: {level_str}")

        return cls(level_map[normalized])

    @classmethod
    def from_int(cls, level_int: int) -> "SkillLevel":
        """Create skill level from integer value."""
        if level_int not in {1, 2, 3}:
            raise ValueError(f"Skill level must be 1, 2, or 3, got {level_int}")
        return cls(SkillLevelType(level_int))


class AutomationLevelType(Enum):
    """Machine automation level enumeration matching database schema."""

    ATTENDED = "attended"  # Requires operator for full duration
    UNATTENDED = "unattended"  # Requires operator for setup only


@dataclass(frozen=True)
class AutomationLevel:
    """
    Represents the automation level of a machine.

    Attended machines require an operator for the full duration of operation.
    Unattended machines only require an operator for initial setup.
    """

    level: AutomationLevelType

    def __post_init__(self):
        if not isinstance(self.level, AutomationLevelType):
            if isinstance(self.level, str):
                try:
                    object.__setattr__(
                        self, "level", AutomationLevelType(self.level.lower())
                    )
                except ValueError:
                    raise ValueError(f"Invalid automation level: {self.level}")
            else:
                raise ValueError(f"Invalid automation level type: {type(self.level)}")

    def __str__(self) -> str:
        """Return human-readable automation level."""
        return self.level.value.title()

    @property
    def requires_full_operator_attention(self) -> bool:
        """Check if machine requires operator for full duration."""
        return self.level == AutomationLevelType.ATTENDED

    @property
    def requires_setup_only(self) -> bool:
        """Check if machine only requires operator for setup."""
        return self.level == AutomationLevelType.UNATTENDED

    @property
    def operator_utilization_factor(self) -> Decimal:
        """
        Get operator utilization factor for scheduling calculations.
        Attended machines use 1.0 (full operator time).
        Unattended machines use setup time ratio (estimated 0.1-0.3).
        """
        if self.level == AutomationLevelType.ATTENDED:
            return Decimal("1.0")
        else:
            # Unattended machines typically need ~10-20% operator time for setup
            return Decimal("0.15")

    @classmethod
    def attended(cls) -> "AutomationLevel":
        """Factory method for attended automation level."""
        return cls(AutomationLevelType.ATTENDED)

    @classmethod
    def unattended(cls) -> "AutomationLevel":
        """Factory method for unattended automation level."""
        return cls(AutomationLevelType.UNATTENDED)

    @classmethod
    def from_string(cls, level_str: str) -> "AutomationLevel":
        """Create automation level from string."""
        try:
            return cls(AutomationLevelType(level_str.lower().strip()))
        except ValueError:
            raise ValueError(f"Invalid automation level: {level_str}")


class PriorityLevelType(IntEnum):
    """
    Priority level enumeration with ordinal values for comparison.
    Higher numbers indicate higher priority.
    """

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class PriorityLevel:
    """
    Represents priority level with comparison capabilities.

    Priority levels are ordinal where higher values indicate higher priority.
    Critical > High > Normal > Low
    """

    level: PriorityLevelType

    def __post_init__(self):
        if not isinstance(self.level, PriorityLevelType):
            if isinstance(self.level, str):
                level_map = {
                    "low": PriorityLevelType.LOW,
                    "normal": PriorityLevelType.NORMAL,
                    "high": PriorityLevelType.HIGH,
                    "critical": PriorityLevelType.CRITICAL,
                }
                normalized = self.level.lower().strip()
                if normalized not in level_map:
                    raise ValueError(f"Invalid priority level: {self.level}")
                object.__setattr__(self, "level", level_map[normalized])
            elif isinstance(self.level, int):
                if self.level not in {1, 2, 3, 4}:
                    raise ValueError(f"Priority level must be 1-4, got {self.level}")
                object.__setattr__(self, "level", PriorityLevelType(self.level))
            else:
                raise ValueError(f"Invalid priority level type: {type(self.level)}")

    def __str__(self) -> str:
        """Return human-readable priority level."""
        level_names = {
            PriorityLevelType.LOW: "Low",
            PriorityLevelType.NORMAL: "Normal",
            PriorityLevelType.HIGH: "High",
            PriorityLevelType.CRITICAL: "Critical",
        }
        return level_names[self.level]

    def __int__(self) -> int:
        """Return numeric value for calculations."""
        return self.level.value

    def __lt__(self, other: "PriorityLevel") -> bool:
        """Compare priority levels."""
        if not isinstance(other, PriorityLevel):
            return NotImplemented
        return self.level < other.level

    def __le__(self, other: "PriorityLevel") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, PriorityLevel):
            return NotImplemented
        return self.level <= other.level

    def __gt__(self, other: "PriorityLevel") -> bool:
        """Greater than comparison."""
        if not isinstance(other, PriorityLevel):
            return NotImplemented
        return self.level > other.level

    def __ge__(self, other: "PriorityLevel") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, PriorityLevel):
            return NotImplemented
        return self.level >= other.level

    @property
    def weight_factor(self) -> Decimal:
        """Get weight factor for scheduling algorithms."""
        weights = {
            PriorityLevelType.LOW: Decimal("0.5"),
            PriorityLevelType.NORMAL: Decimal("1.0"),
            PriorityLevelType.HIGH: Decimal("2.0"),
            PriorityLevelType.CRITICAL: Decimal("5.0"),
        }
        return weights[self.level]

    @property
    def is_urgent(self) -> bool:
        """Check if priority is urgent (high or critical)."""
        return self.level in {PriorityLevelType.HIGH, PriorityLevelType.CRITICAL}

    @property
    def is_critical(self) -> bool:
        """Check if priority is critical."""
        return self.level == PriorityLevelType.CRITICAL

    @property
    def requires_expedited_handling(self) -> bool:
        """Check if priority requires expedited handling."""
        return self.is_urgent

    @property
    def numeric_value(self) -> int:
        """Get numeric representation of priority level."""
        return self.level.value

    def boost_priority(self, boost_factor: int = 1) -> "PriorityLevel":
        """
        Boost priority level by given factor, capped at critical.

        Args:
            boost_factor: Number of levels to boost (default 1)

        Returns:
            New PriorityLevel with boosted priority
        """
        new_level = min(
            self.level.value + boost_factor, PriorityLevelType.CRITICAL.value
        )
        return PriorityLevel(PriorityLevelType(new_level))

    @classmethod
    def low(cls) -> "PriorityLevel":
        """Factory method for low priority."""
        return cls(PriorityLevelType.LOW)

    @classmethod
    def normal(cls) -> "PriorityLevel":
        """Factory method for normal priority."""
        return cls(PriorityLevelType.NORMAL)

    @classmethod
    def high(cls) -> "PriorityLevel":
        """Factory method for high priority."""
        return cls(PriorityLevelType.HIGH)

    @classmethod
    def critical(cls) -> "PriorityLevel":
        """Factory method for critical priority."""
        return cls(PriorityLevelType.CRITICAL)

    @classmethod
    def from_string(cls, level_str: str) -> "PriorityLevel":
        """Create priority level from string representation."""
        return cls(level_str)

    @classmethod
    def from_int(cls, level_int: int) -> "PriorityLevel":
        """Create priority level from integer value."""
        return cls(level_int)


@dataclass(frozen=True)
class EfficiencyFactor:
    """
    Represents machine or operator efficiency as a percentage factor.

    Efficiency factors are typically between 0.1 (10%) and 2.0 (200%).
    A factor of 1.0 represents 100% efficiency (standard performance).
    """

    factor: Decimal

    def __post_init__(self):
        if isinstance(self.factor, int | float):
            object.__setattr__(self, "factor", Decimal(str(self.factor)))
        elif not isinstance(self.factor, Decimal):
            raise ValueError(
                f"Efficiency factor must be numeric, got {type(self.factor)}"
            )

        if not (Decimal("0.1") <= self.factor <= Decimal("2.0")):
            raise ValueError(
                f"Efficiency factor must be between 0.1 and 2.0, got {self.factor}"
            )

    def __str__(self) -> str:
        """Return percentage representation."""
        return f"{self.factor * 100:.1f}%"

    def __float__(self) -> float:
        """Return float value for calculations."""
        return float(self.factor)

    def apply_to_duration(self, duration_minutes: int) -> int:
        """
        Apply efficiency factor to duration in minutes.

        Higher efficiency factors result in shorter durations.
        Lower efficiency factors result in longer durations.

        Args:
            duration_minutes: Base duration in minutes

        Returns:
            Adjusted duration in minutes
        """
        if duration_minutes < 0:
            raise ValueError("Duration cannot be negative")

        adjusted = Decimal(duration_minutes) / self.factor
        return max(1, int(adjusted.quantize(Decimal("1"))))

    @property
    def as_percentage(self) -> int:
        """Get efficiency as percentage (e.g., 95 for 95%)."""
        return int(self.factor * 100)

    @property
    def is_optimal(self) -> bool:
        """Check if efficiency is at or above optimal level (100%)."""
        return self.factor >= Decimal("1.0")

    @property
    def is_below_standard(self) -> bool:
        """Check if efficiency is below standard (less than 100%)."""
        return self.factor < Decimal("1.0")

    @property
    def is_high_performance(self) -> bool:
        """Check if efficiency indicates high performance (above 120%)."""
        return self.factor > Decimal("1.2")

    @classmethod
    def standard(cls) -> "EfficiencyFactor":
        """Factory method for standard efficiency (100%)."""
        return cls(Decimal("1.0"))

    @classmethod
    def from_percentage(cls, percentage: int | float | Decimal) -> "EfficiencyFactor":
        """
        Create efficiency factor from percentage value.

        Args:
            percentage: Efficiency as percentage (e.g., 95 for 95%)

        Returns:
            EfficiencyFactor instance
        """
        if isinstance(percentage, int | float):
            percentage = Decimal(str(percentage))
        elif not isinstance(percentage, Decimal):
            raise ValueError(f"Percentage must be numeric, got {type(percentage)}")

        if percentage <= 0 or percentage > 200:
            raise ValueError(f"Percentage must be between 1 and 200, got {percentage}")

        return cls(percentage / 100)

    @classmethod
    def from_ratio(
        cls, actual_time: int | float, standard_time: int | float
    ) -> "EfficiencyFactor":
        """
        Calculate efficiency factor from actual vs standard times.

        Args:
            actual_time: Actual time taken
            standard_time: Standard/expected time

        Returns:
            EfficiencyFactor based on performance ratio
        """
        if actual_time <= 0 or standard_time <= 0:
            raise ValueError("Times must be positive values")

        # Efficiency = standard_time / actual_time
        # If actual < standard, efficiency > 1.0 (good performance)
        # If actual > standard, efficiency < 1.0 (poor performance)
        factor = Decimal(str(standard_time)) / Decimal(str(actual_time))
        return cls(factor)
