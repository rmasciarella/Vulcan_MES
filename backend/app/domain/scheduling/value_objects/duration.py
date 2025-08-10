"""
Duration Value Object

Represents a time duration with various unit conversions and arithmetic operations.
Uses Decimal precision for accurate time calculations as required by DOMAIN.md.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Union


class Duration:
    """
    A time duration value object with Decimal precision.

    Provides a rich interface for working with time durations
    while maintaining immutability and accurate calculations.
    """

    def __init__(
        self,
        *,
        days: int = 0,
        hours: int = 0,
        minutes: int | float | Decimal = 0,
        seconds: int | float | Decimal = 0,
        milliseconds: int | float | Decimal = 0,
    ) -> None:
        """
        Initialize a Duration with Decimal precision.

        Args:
            days: Number of days
            hours: Number of hours
            minutes: Number of minutes (supports Decimal for precision)
            seconds: Number of seconds (supports Decimal for precision)
            milliseconds: Number of milliseconds (supports Decimal for precision)
        """
        # Store total duration in minutes using Decimal for precision
        total_minutes = (
            Decimal(days) * Decimal("24") * Decimal("60")
            + Decimal(hours) * Decimal("60")
            + Decimal(str(minutes))
            + Decimal(str(seconds)) / Decimal("60")
            + Decimal(str(milliseconds)) / Decimal("60000")
        )
        self._minutes = total_minutes

        # Validate non-negative duration
        if self._minutes < 0:
            raise ValueError(f"Duration cannot be negative: {self._minutes} minutes")

    @classmethod
    def from_minutes(cls, minutes: int | float | Decimal) -> "Duration":
        """
        Create Duration from minutes with Decimal precision.

        Args:
            minutes: Number of minutes

        Returns:
            New Duration instance
        """
        instance = cls.__new__(cls)
        instance._minutes = Decimal(str(minutes))
        if instance._minutes < 0:
            raise ValueError(
                f"Duration cannot be negative: {instance._minutes} minutes"
            )
        return instance

    @classmethod
    def from_hours(cls, hours: int | float | Decimal) -> "Duration":
        """
        Create Duration from hours with Decimal precision.

        Args:
            hours: Number of hours

        Returns:
            New Duration instance
        """
        return cls.from_minutes(Decimal(str(hours)) * Decimal("60"))

    @classmethod
    def from_days(cls, days: int | float | Decimal) -> "Duration":
        """
        Create Duration from days with Decimal precision.

        Args:
            days: Number of days

        Returns:
            New Duration instance
        """
        return cls.from_minutes(Decimal(str(days)) * Decimal("24") * Decimal("60"))

    @classmethod
    def from_timedelta(cls, td: timedelta) -> "Duration":
        """
        Create Duration from Python timedelta with Decimal precision.

        Args:
            td: timedelta object

        Returns:
            New Duration instance
        """
        total_seconds = Decimal(str(td.total_seconds()))
        return cls.from_minutes(total_seconds / Decimal("60"))

    @property
    def minutes(self) -> Decimal:
        """Get duration in minutes with Decimal precision."""
        return self._minutes

    @property
    def hours(self) -> Decimal:
        """Get duration in hours with Decimal precision."""
        return self._minutes / Decimal("60")

    @property
    def days(self) -> Decimal:
        """Get duration in days with Decimal precision."""
        return self._minutes / (Decimal("24") * Decimal("60"))

    @property
    def seconds(self) -> Decimal:
        """Get duration in seconds with Decimal precision."""
        return self._minutes * Decimal("60")

    @property
    def milliseconds(self) -> Decimal:
        """Get duration in milliseconds with Decimal precision."""
        return self._minutes * Decimal("60") * Decimal("1000")

    def to_timedelta(self) -> timedelta:
        """
        Convert to Python timedelta.

        Returns:
            Equivalent timedelta object
        """
        return timedelta(minutes=float(self._minutes))

    def to_minutes_int(self) -> int:
        """
        Get duration as integer minutes (for OR-Tools compatibility).

        Returns:
            Duration in minutes, rounded to nearest integer
        """
        return int(round(float(self._minutes)))

    def is_zero(self) -> bool:
        """Check if duration is zero with Decimal precision."""
        return abs(self._minutes) < Decimal("1e-9")

    def is_positive(self) -> bool:
        """Check if duration is positive with Decimal precision."""
        return self._minutes > Decimal("1e-9")

    def is_negative(self) -> bool:
        """Check if duration is negative with Decimal precision."""
        return self._minutes < Decimal("-1e-9")

    def abs(self) -> "Duration":
        """
        Get absolute value of duration.

        Returns:
            New Duration with absolute value
        """
        return Duration.from_minutes(abs(self._minutes))

    def __add__(self, other: "Duration") -> "Duration":
        """Add two durations."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot add Duration and {type(other)}")
        return Duration.from_minutes(self._minutes + other._minutes)

    def __sub__(self, other: "Duration") -> "Duration":
        """Subtract two durations."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot subtract {type(other)} from Duration")
        return Duration.from_minutes(self._minutes - other._minutes)

    def __mul__(self, factor: int | float | Decimal) -> "Duration":
        """Multiply duration by a factor with Decimal precision."""
        if not isinstance(factor, int | float | Decimal):
            raise TypeError(f"Cannot multiply Duration by {type(factor)}")
        return Duration.from_minutes(self._minutes * Decimal(str(factor)))

    def __rmul__(self, factor: int | float | Decimal) -> "Duration":
        """Right multiplication (factor * duration) with Decimal precision."""
        return self.__mul__(factor)

    def __truediv__(
        self, divisor: Union[int, float, Decimal, "Duration"]
    ) -> Union["Duration", Decimal]:
        """Divide duration with Decimal precision."""
        if isinstance(divisor, int | float | Decimal):
            divisor_decimal = Decimal(str(divisor))
            if divisor_decimal == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            return Duration.from_minutes(self._minutes / divisor_decimal)
        elif isinstance(divisor, Duration):
            if divisor._minutes == 0:
                raise ZeroDivisionError("Cannot divide by zero duration")
            return self._minutes / divisor._minutes
        else:
            raise TypeError(f"Cannot divide Duration by {type(divisor)}")

    def __floordiv__(self, divisor: int | float | Decimal) -> "Duration":
        """Floor division of duration with Decimal precision."""
        if not isinstance(divisor, int | float | Decimal):
            raise TypeError(f"Cannot floor divide Duration by {type(divisor)}")
        divisor_decimal = Decimal(str(divisor))
        if divisor_decimal == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return Duration.from_minutes(self._minutes // divisor_decimal)

    def __mod__(self, divisor: Union[int, float, Decimal, "Duration"]) -> "Duration":
        """Modulo operation on duration with Decimal precision."""
        if isinstance(divisor, int | float | Decimal):
            divisor_decimal = Decimal(str(divisor))
            if divisor_decimal == 0:
                raise ZeroDivisionError("Cannot modulo by zero")
            return Duration.from_minutes(self._minutes % divisor_decimal)
        elif isinstance(divisor, Duration):
            if divisor._minutes == 0:
                raise ZeroDivisionError("Cannot modulo by zero duration")
            return Duration.from_minutes(self._minutes % divisor._minutes)
        else:
            raise TypeError(f"Cannot modulo Duration by {type(divisor)}")

    def __neg__(self) -> "Duration":
        """Negate duration."""
        return Duration.from_minutes(-self._minutes)

    def __pos__(self) -> "Duration":
        """Positive duration (no-op)."""
        return Duration.from_minutes(self._minutes)

    def __eq__(self, other: object) -> bool:
        """Check equality with Decimal precision."""
        if not isinstance(other, Duration):
            return False
        return abs(self._minutes - other._minutes) < Decimal("1e-9")

    def __ne__(self, other: object) -> bool:
        """Check inequality."""
        return not self.__eq__(other)

    def __lt__(self, other: "Duration") -> bool:
        """Check if less than."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot compare Duration and {type(other)}")
        return self._minutes < other._minutes

    def __le__(self, other: "Duration") -> bool:
        """Check if less than or equal."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot compare Duration and {type(other)}")
        return self._minutes <= other._minutes

    def __gt__(self, other: "Duration") -> bool:
        """Check if greater than."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot compare Duration and {type(other)}")
        return self._minutes > other._minutes

    def __ge__(self, other: "Duration") -> bool:
        """Check if greater than or equal."""
        if not isinstance(other, Duration):
            raise TypeError(f"Cannot compare Duration and {type(other)}")
        return self._minutes >= other._minutes

    def __hash__(self) -> int:
        """Hash for use in sets and dicts with Decimal precision."""
        return hash(
            self._minutes.quantize(Decimal("0.000000001"))
        )  # Round to 9 decimal places

    def __str__(self) -> str:
        """String representation with Decimal precision."""
        if self._minutes < Decimal("60"):
            return f"{float(self._minutes):.1f}m"
        elif self._minutes < Decimal("24") * Decimal("60"):
            hours = self._minutes / Decimal("60")
            return f"{float(hours):.1f}h"
        else:
            days = self._minutes / (Decimal("24") * Decimal("60"))
            return f"{float(days):.1f}d"

    def __repr__(self) -> str:
        """Detailed string representation with Decimal precision."""
        return f"Duration(minutes={self._minutes})"  # Decimal handles its own precision

    def format_detailed(self) -> str:
        """
        Format as detailed string with multiple units using Decimal precision.

        Returns:
            Formatted string like "1d 2h 30m"
        """
        total_minutes = abs(self._minutes)
        sign = "-" if self._minutes < 0 else ""

        day_minutes = Decimal("24") * Decimal("60")
        days = int(total_minutes // day_minutes)
        remaining_minutes = total_minutes % day_minutes

        hours = int(remaining_minutes // Decimal("60"))
        minutes = int(remaining_minutes % Decimal("60"))

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:  # Show minutes if it's the only unit
            parts.append(f"{minutes}m")

        return sign + " ".join(parts)
