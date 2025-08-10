"""Common value objects for scheduling domain."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from pydantic import Field, validator

from ...shared.base import ValueObject
from .enums import SkillLevel


class Duration(ValueObject):
    """Represents a duration in minutes with validation."""

    minutes: int = Field(ge=0, description="Duration in minutes")

    @validator("minutes")
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Duration cannot be negative")
        return v

    @property
    def hours(self) -> float:
        """Get duration in hours."""
        return self.minutes / 60.0

    @property
    def timedelta(self) -> timedelta:
        """Convert to Python timedelta."""
        return timedelta(minutes=self.minutes)

    def add(self, other: "Duration") -> "Duration":
        """Add two durations together."""
        return Duration(minutes=self.minutes + other.minutes)

    def multiply(self, factor: float) -> "Duration":
        """Multiply duration by a factor."""
        return Duration(minutes=int(self.minutes * factor))

    def __str__(self) -> str:
        """String representation."""
        if self.minutes < 60:
            return f"{self.minutes}min"
        hours = self.minutes // 60
        mins = self.minutes % 60
        if mins == 0:
            return f"{hours}h"
        return f"{hours}h {mins}min"


class TimeWindow(ValueObject):
    """Represents a time window with start and end times."""

    start_time: datetime
    end_time: datetime

    @validator("end_time")
    def end_after_start(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    @property
    def duration(self) -> Duration:
        """Get the duration of this time window."""
        delta = self.end_time - self.start_time
        return Duration(minutes=int(delta.total_seconds() / 60))

    def overlaps_with(self, other: "TimeWindow") -> bool:
        """Check if this time window overlaps with another."""
        return self.start_time < other.end_time and self.end_time > other.start_time

    def contains(self, point: datetime) -> bool:
        """Check if a datetime point is within this time window."""
        return self.start_time <= point <= self.end_time

    def is_adjacent_to(self, other: "TimeWindow") -> bool:
        """Check if this time window is adjacent to another."""
        return self.end_time == other.start_time or other.end_time == self.start_time


class WorkingHours(ValueObject):
    """Represents daily working hours."""

    start_time: time = Field(default=time(7, 0))  # 07:00
    end_time: time = Field(default=time(16, 0))  # 16:00
    lunch_start: time = Field(default=time(12, 0))  # 12:00
    lunch_duration: Duration = Field(default=Duration(minutes=30))

    @validator("end_time")
    def end_after_start(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    @property
    def total_hours(self) -> Duration:
        """Get total working hours (excluding lunch)."""
        total_minutes = (
            (self.end_time.hour * 60 + self.end_time.minute)
            - (self.start_time.hour * 60 + self.start_time.minute)
            - self.lunch_duration.minutes
        )
        return Duration(minutes=total_minutes)

    def is_within_working_hours(self, time_point: time) -> bool:
        """Check if a time point is within working hours."""
        return self.start_time <= time_point <= self.end_time

    def is_lunch_time(self, time_point: time) -> bool:
        """Check if a time point is during lunch."""
        lunch_end_minutes = (
            self.lunch_start.hour * 60
            + self.lunch_start.minute
            + self.lunch_duration.minutes
        )
        lunch_end = time(lunch_end_minutes // 60, lunch_end_minutes % 60)
        return self.lunch_start <= time_point <= lunch_end


class Skill(ValueObject):
    """Represents a skill with code, name, and metadata."""

    skill_code: str = Field(min_length=1, max_length=20)
    skill_name: str = Field(min_length=1, max_length=100)
    skill_category: str | None = Field(None, max_length=50)
    description: str | None = None

    @validator("skill_code")
    def validate_code(cls, v):
        if not v.isalnum() and "_" not in v:
            raise ValueError("Skill code must be alphanumeric with underscores")
        return v.upper()


class OperatorSkill(ValueObject):
    """Represents an operator's proficiency in a specific skill."""

    skill: Skill
    proficiency_level: SkillLevel
    certified_date: datetime | None = None
    expiry_date: datetime | None = None

    @validator("expiry_date")
    def expiry_after_certified(cls, v, values):
        if v and "certified_date" in values and values["certified_date"]:
            if v <= values["certified_date"]:
                raise ValueError("Expiry date must be after certified date")
        return v

    @property
    def is_valid(self) -> bool:
        """Check if the skill certification is currently valid."""
        if self.expiry_date is None:
            return True  # No expiry
        return datetime.utcnow() < self.expiry_date

    @property
    def is_expiring_soon(self) -> bool:
        """Check if certification expires within 30 days."""
        if self.expiry_date is None:
            return False
        return datetime.utcnow() + timedelta(days=30) >= self.expiry_date

    def meets_requirement(self, required_level: SkillLevel) -> bool:
        """Check if this skill meets the required proficiency level."""
        return self.is_valid and self.proficiency_level.meets_minimum(required_level)


class EfficiencyFactor(ValueObject):
    """Represents machine or operator efficiency as a multiplier."""

    factor: Decimal = Field(ge=0.1, le=2.0)

    @validator("factor")
    def validate_range(cls, v):
        if v < Decimal("0.1") or v > Decimal("2.0"):
            raise ValueError("Efficiency factor must be between 0.1 and 2.0")
        return v

    @property
    def percentage(self) -> float:
        """Get efficiency as a percentage."""
        return float(self.factor) * 100

    def apply_to_duration(self, duration: Duration) -> Duration:
        """Apply efficiency factor to a duration."""
        adjusted_minutes = int(duration.minutes / self.factor)
        return Duration(minutes=adjusted_minutes)

    @property
    def is_efficient(self) -> bool:
        """Check if efficiency is above 100%."""
        return self.factor > Decimal("1.0")

    @property
    def is_below_standard(self) -> bool:
        """Check if efficiency is below 90%."""
        return self.factor < Decimal("0.9")


class Address(ValueObject):
    """Generic address value object."""

    street: str
    city: str
    state: str
    postal_code: str
    country: str = "USA"


class ContactInfo(ValueObject):
    """Contact information value object."""

    email: str | None = None
    phone: str | None = None

    @validator("email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class Money(ValueObject):
    """Represents monetary amounts."""

    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    def add(self, other: "Money") -> "Money":
        """Add two money amounts (must be same currency)."""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def multiply(self, factor: Decimal) -> "Money":
        """Multiply money by a factor."""
        return Money(amount=self.amount * factor, currency=self.currency)


class Quantity(ValueObject):
    """Represents quantities with units."""

    value: int = Field(ge=1)
    unit: str = Field(default="pieces")

    @validator("value")
    def validate_positive(cls, v):
        if v < 1:
            raise ValueError("Quantity must be positive")
        return v
