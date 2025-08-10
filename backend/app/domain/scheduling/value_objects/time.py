"""
Time-based Value Objects

Immutable value objects representing time concepts in the production scheduling domain.
This includes durations, working hours, schedules, and time-related constraints.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional


class TimeValidationError(ValueError):
    """Raised when time-related validation fails."""

    pass


@dataclass(frozen=True)
class Duration:
    """
    Represents a duration of time with validation and arithmetic operations.

    Durations are measured in minutes for precision in scheduling calculations.
    Supports conversion to/from various time units and arithmetic operations.
    """

    minutes: int

    def __post_init__(self):
        if not isinstance(self.minutes, int):
            raise ValueError(
                f"Duration minutes must be integer, got {type(self.minutes)}"
            )
        if self.minutes < 0:
            raise ValueError(f"Duration cannot be negative, got {self.minutes}")

    def __str__(self) -> str:
        """Return human-readable duration string."""
        if self.minutes < 60:
            return f"{self.minutes}min"
        elif self.minutes < 1440:  # Less than 24 hours
            hours = self.minutes // 60
            mins = self.minutes % 60
            if mins == 0:
                return f"{hours}h"
            else:
                return f"{hours}h {mins}min"
        else:  # 24 hours or more
            days = self.minutes // 1440
            remaining_minutes = self.minutes % 1440
            hours = remaining_minutes // 60
            mins = remaining_minutes % 60

            parts = [f"{days}d"]
            if hours > 0:
                parts.append(f"{hours}h")
            if mins > 0:
                parts.append(f"{mins}min")
            return " ".join(parts)

    def __add__(self, other: "Duration") -> "Duration":
        """Add two durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.minutes + other.minutes)

    def __sub__(self, other: "Duration") -> "Duration":
        """Subtract two durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        result = self.minutes - other.minutes
        if result < 0:
            raise ValueError("Duration subtraction cannot result in negative duration")
        return Duration(result)

    def __mul__(self, factor: int | float | Decimal) -> "Duration":
        """Multiply duration by a factor."""
        if isinstance(factor, Decimal):
            result = int(Decimal(self.minutes) * factor)
        else:
            result = int(self.minutes * factor)
        return Duration(max(0, result))

    def __truediv__(self, divisor: int | float | Decimal) -> "Duration":
        """Divide duration by a divisor."""
        if divisor == 0:
            raise ZeroDivisionError("Cannot divide duration by zero")

        if isinstance(divisor, Decimal):
            result = int(Decimal(self.minutes) / divisor)
        else:
            result = int(self.minutes / divisor)
        return Duration(max(0, result))

    def __lt__(self, other: "Duration") -> bool:
        """Compare durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.minutes < other.minutes

    def __le__(self, other: "Duration") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.minutes <= other.minutes

    def __gt__(self, other: "Duration") -> bool:
        """Greater than comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.minutes > other.minutes

    def __ge__(self, other: "Duration") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.minutes >= other.minutes

    @property
    def total_minutes(self) -> int:
        """Get total duration in minutes."""
        return self.minutes

    @property
    def total_hours(self) -> Decimal:
        """Get total duration in hours (with decimal precision)."""
        return Decimal(self.minutes) / Decimal("60")

    @property
    def total_days(self) -> Decimal:
        """Get total duration in days (with decimal precision)."""
        return Decimal(self.minutes) / Decimal("1440")

    @property
    def hours_and_minutes(self) -> tuple[int, int]:
        """Get duration as (hours, minutes) tuple."""
        hours = self.minutes // 60
        mins = self.minutes % 60
        return (hours, mins)

    @property
    def is_zero(self) -> bool:
        """Check if duration is zero."""
        return self.minutes == 0

    @property
    def is_short_duration(self) -> bool:
        """Check if duration is less than 1 hour."""
        return self.minutes < 60

    @property
    def is_long_duration(self) -> bool:
        """Check if duration is more than 8 hours."""
        return self.minutes > 480

    def to_timedelta(self) -> timedelta:
        """Convert to Python timedelta object."""
        return timedelta(minutes=self.minutes)

    @classmethod
    def zero(cls) -> "Duration":
        """Factory method for zero duration."""
        return cls(0)

    @classmethod
    def from_hours(cls, hours: int | float | Decimal) -> "Duration":
        """Create duration from hours."""
        if isinstance(hours, Decimal):
            minutes = int(hours * 60)
        else:
            minutes = int(hours * 60)
        return cls(minutes)

    @classmethod
    def from_days(cls, days: int | float | Decimal) -> "Duration":
        """Create duration from days."""
        if isinstance(days, Decimal):
            minutes = int(days * 1440)
        else:
            minutes = int(days * 1440)
        return cls(minutes)

    @classmethod
    def from_timedelta(cls, td: timedelta) -> "Duration":
        """Create duration from timedelta object."""
        total_minutes = int(td.total_seconds() / 60)
        return cls(total_minutes)

    @classmethod
    def from_minutes(cls, minutes: int) -> "Duration":
        """Create duration from minutes."""
        return cls(minutes)

    @classmethod
    def from_hours_minutes(cls, hours: int, minutes: int) -> "Duration":
        """Create duration from hours and minutes."""
        if hours < 0 or minutes < 0:
            raise ValueError("Hours and minutes must be non-negative")
        if minutes >= 60:
            raise ValueError("Minutes must be less than 60")

        total_minutes = hours * 60 + minutes
        return cls(total_minutes)


@dataclass(frozen=True)
class TimeOfDay:
    """
    Represents a specific time of day (hours and minutes).

    Used for shift times, lunch breaks, and other recurring daily events.
    """

    hour: int
    minute: int

    def __post_init__(self):
        if not (0 <= self.hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"Minute must be between 0 and 59, got {self.minute}")

    def __str__(self) -> str:
        """Return time in HH:MM format."""
        return f"{self.hour:02d}:{self.minute:02d}"

    def __lt__(self, other: "TimeOfDay") -> bool:
        """Compare times of day."""
        if not isinstance(other, TimeOfDay):
            return NotImplemented
        return (self.hour, self.minute) < (other.hour, other.minute)

    def __le__(self, other: "TimeOfDay") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, TimeOfDay):
            return NotImplemented
        return (self.hour, self.minute) <= (other.hour, other.minute)

    def __gt__(self, other: "TimeOfDay") -> bool:
        """Greater than comparison."""
        if not isinstance(other, TimeOfDay):
            return NotImplemented
        return (self.hour, self.minute) > (other.hour, other.minute)

    def __ge__(self, other: "TimeOfDay") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, TimeOfDay):
            return NotImplemented
        return (self.hour, self.minute) >= (other.hour, other.minute)

    @property
    def total_minutes_from_midnight(self) -> int:
        """Get total minutes from midnight."""
        return self.hour * 60 + self.minute

    @property
    def is_morning(self) -> bool:
        """Check if time is in morning (before 12:00)."""
        return self.hour < 12

    @property
    def is_afternoon(self) -> bool:
        """Check if time is in afternoon (12:00-17:59)."""
        return 12 <= self.hour < 18

    @property
    def is_evening(self) -> bool:
        """Check if time is in evening (18:00 or later)."""
        return self.hour >= 18

    def add_minutes(self, minutes: int) -> "TimeOfDay":
        """Add minutes to time of day, wrapping to next day if needed."""
        total_minutes = self.total_minutes_from_midnight + minutes
        # Handle day wrap-around
        total_minutes = total_minutes % (24 * 60)

        new_hour = total_minutes // 60
        new_minute = total_minutes % 60
        return TimeOfDay(new_hour, new_minute)

    def subtract_minutes(self, minutes: int) -> "TimeOfDay":
        """Subtract minutes from time of day, wrapping to previous day if needed."""
        total_minutes = self.total_minutes_from_midnight - minutes
        # Handle day wrap-around (negative values)
        if total_minutes < 0:
            total_minutes += 24 * 60

        new_hour = total_minutes // 60
        new_minute = total_minutes % 60
        return TimeOfDay(new_hour, new_minute)

    def time_until(self, other: "TimeOfDay") -> Duration:
        """Calculate duration until another time of day (same day)."""
        if other < self:
            # Time is tomorrow, add 24 hours
            other_minutes = other.total_minutes_from_midnight + (24 * 60)
        else:
            other_minutes = other.total_minutes_from_midnight

        minutes_diff = other_minutes - self.total_minutes_from_midnight
        return Duration(minutes_diff)

    def to_time(self) -> time:
        """Convert to Python time object."""
        return time(self.hour, self.minute)

    @classmethod
    def from_time(cls, time_obj: time) -> "TimeOfDay":
        """Create from Python time object."""
        return cls(time_obj.hour, time_obj.minute)

    @classmethod
    def from_string(cls, time_str: str) -> "TimeOfDay":
        """
        Create from string in HH:MM or H:MM format.

        Examples: "09:30", "9:30", "14:15"
        """
        try:
            parts = time_str.strip().split(":")
            if len(parts) != 2:
                raise ValueError("Time must be in HH:MM format")

            hour = int(parts[0])
            minute = int(parts[1])
            return cls(hour, minute)
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid time format '{time_str}': {e}")

    @classmethod
    def midnight(cls) -> "TimeOfDay":
        """Factory method for midnight (00:00)."""
        return cls(0, 0)

    @classmethod
    def noon(cls) -> "TimeOfDay":
        """Factory method for noon (12:00)."""
        return cls(12, 0)


@dataclass(frozen=True)
class WorkingHours:
    """
    Represents working hours for a day with start time, end time, and lunch break.

    Handles validation that start < end and lunch is within working hours.
    Provides methods to calculate available working time.
    """

    start_time: TimeOfDay
    end_time: TimeOfDay
    lunch_start: TimeOfDay
    lunch_duration: Duration

    def __post_init__(self):
        # Validate start < end
        if self.start_time >= self.end_time:
            raise TimeValidationError("Start time must be before end time")

        # Validate lunch is within working hours
        lunch_end = self.lunch_start.add_minutes(self.lunch_duration.minutes)
        if self.lunch_start < self.start_time or lunch_end > self.end_time:
            raise TimeValidationError("Lunch break must be within working hours")

    def __str__(self) -> str:
        """Return human-readable working hours."""
        return (
            f"{self.start_time}-{self.end_time} "
            f"(lunch: {self.lunch_start} for {self.lunch_duration})"
        )

    @property
    def total_shift_duration(self) -> Duration:
        """Get total shift duration including lunch."""
        return Duration(
            self.end_time.total_minutes_from_midnight
            - self.start_time.total_minutes_from_midnight
        )

    @property
    def available_work_duration(self) -> Duration:
        """Get available work duration excluding lunch."""
        return self.total_shift_duration - self.lunch_duration

    @property
    def lunch_end_time(self) -> TimeOfDay:
        """Get lunch end time."""
        return self.lunch_start.add_minutes(self.lunch_duration.minutes)

    @property
    def morning_work_duration(self) -> Duration:
        """Get work duration before lunch."""
        return Duration(
            self.lunch_start.total_minutes_from_midnight
            - self.start_time.total_minutes_from_midnight
        )

    @property
    def afternoon_work_duration(self) -> Duration:
        """Get work duration after lunch."""
        return Duration(
            self.end_time.total_minutes_from_midnight
            - self.lunch_end_time.total_minutes_from_midnight
        )

    def is_working_time(self, time_of_day: TimeOfDay) -> bool:
        """Check if given time is within working hours (excluding lunch)."""
        if time_of_day < self.start_time or time_of_day > self.end_time:
            return False

        # Check if during lunch
        lunch_end = self.lunch_start.add_minutes(self.lunch_duration.minutes)
        if self.lunch_start <= time_of_day <= lunch_end:
            return False

        return True

    def is_lunch_time(self, time_of_day: TimeOfDay) -> bool:
        """Check if given time is during lunch break."""
        lunch_end = self.lunch_start.add_minutes(self.lunch_duration.minutes)
        return self.lunch_start <= time_of_day <= lunch_end

    def get_work_periods(self) -> list[tuple[TimeOfDay, TimeOfDay]]:
        """Get list of work periods as (start, end) tuples, excluding lunch."""
        periods = []

        # Morning period (start to lunch)
        if self.morning_work_duration.minutes > 0:
            periods.append((self.start_time, self.lunch_start))

        # Afternoon period (lunch end to end)
        if self.afternoon_work_duration.minutes > 0:
            periods.append((self.lunch_end_time, self.end_time))

        return periods

    def find_next_available_slot(
        self, start_from: TimeOfDay, duration_needed: Duration
    ) -> TimeOfDay | None:
        """
        Find next available time slot of given duration within working hours.

        Args:
            start_from: Earliest time to start looking
            duration_needed: Required duration for the slot

        Returns:
            Start time of available slot, or None if no slot available
        """
        for period_start, period_end in self.get_work_periods():
            # Find effective start time for this period
            effective_start = max(start_from, period_start)

            if effective_start >= period_end:
                continue  # This period is before our start time

            # Check if duration fits in this period
            period_duration = Duration(
                period_end.total_minutes_from_midnight
                - effective_start.total_minutes_from_midnight
            )

            if period_duration >= duration_needed:
                return effective_start

        return None

    @classmethod
    def standard_day_shift(cls) -> "WorkingHours":
        """Factory method for standard day shift (7:00-16:00, lunch 12:00-12:30)."""
        return cls(
            start_time=TimeOfDay(7, 0),
            end_time=TimeOfDay(16, 0),
            lunch_start=TimeOfDay(12, 0),
            lunch_duration=Duration(30),
        )

    @classmethod
    def standard_night_shift(cls) -> "WorkingHours":
        """Factory method for standard night shift (22:00-06:00, lunch 01:00-01:30)."""
        return cls(
            start_time=TimeOfDay(22, 0),
            end_time=TimeOfDay(6, 0),  # Next day
            lunch_start=TimeOfDay(1, 0),
            lunch_duration=Duration(30),
        )


@dataclass(frozen=True)
class Schedule:
    """
    Represents a complete schedule with start time, duration, and resource assignments.

    Combines absolute timing (datetime) with duration and provides methods for
    schedule manipulation and conflict detection.
    """

    start_time: datetime
    duration: Duration

    def __post_init__(self):
        if not isinstance(self.start_time, datetime):
            raise ValueError(
                f"Start time must be datetime, got {type(self.start_time)}"
            )
        if not isinstance(self.duration, Duration):
            raise ValueError(f"Duration must be Duration, got {type(self.duration)}")

    def __str__(self) -> str:
        """Return human-readable schedule."""
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M')} for {self.duration}"

    @property
    def end_time(self) -> datetime:
        """Get calculated end time."""
        return self.start_time + self.duration.to_timedelta()

    @property
    def date(self) -> date:
        """Get date of schedule."""
        return self.start_time.date()

    @property
    def start_time_of_day(self) -> TimeOfDay:
        """Get start time as TimeOfDay."""
        return TimeOfDay(self.start_time.hour, self.start_time.minute)

    @property
    def end_time_of_day(self) -> TimeOfDay:
        """Get end time as TimeOfDay."""
        end_dt = self.end_time
        return TimeOfDay(end_dt.hour, end_dt.minute)

    @property
    def spans_multiple_days(self) -> bool:
        """Check if schedule spans multiple days."""
        return self.start_time.date() != self.end_time.date()

    def overlaps_with(self, other: "Schedule") -> bool:
        """Check if this schedule overlaps with another schedule."""
        if not isinstance(other, Schedule):
            return False

        return self.start_time < other.end_time and self.end_time > other.start_time

    def contains_time(self, check_time: datetime) -> bool:
        """Check if given time is within this schedule."""
        return self.start_time <= check_time < self.end_time

    def time_until_start(self, from_time: datetime) -> Duration | None:
        """
        Get duration until schedule starts from given time.

        Returns None if schedule has already started.
        """
        if from_time >= self.start_time:
            return None

        diff_seconds = (self.start_time - from_time).total_seconds()
        return Duration(int(diff_seconds / 60))

    def time_since_start(self, current_time: datetime) -> Duration:
        """Get duration since schedule started."""
        if current_time < self.start_time:
            return Duration.zero()

        diff_seconds = (current_time - self.start_time).total_seconds()
        return Duration(int(diff_seconds / 60))

    def remaining_duration(self, current_time: datetime) -> Duration:
        """Get remaining duration from current time."""
        if current_time >= self.end_time:
            return Duration.zero()
        if current_time <= self.start_time:
            return self.duration

        remaining_seconds = (self.end_time - current_time).total_seconds()
        return Duration(int(remaining_seconds / 60))

    def shift_by(self, time_delta: timedelta | Duration) -> "Schedule":
        """Create new schedule shifted by given time delta."""
        if isinstance(time_delta, Duration):
            time_delta = time_delta.to_timedelta()

        new_start = self.start_time + time_delta
        return Schedule(new_start, self.duration)

    def extend_duration(self, additional_duration: Duration) -> "Schedule":
        """Create new schedule with extended duration."""
        new_duration = self.duration + additional_duration
        return Schedule(self.start_time, new_duration)

    def truncate_to(self, new_end_time: datetime) -> "Schedule":
        """Create new schedule truncated to given end time."""
        if new_end_time <= self.start_time:
            raise ValueError("New end time must be after start time")

        new_duration_seconds = (new_end_time - self.start_time).total_seconds()
        new_duration = Duration(int(new_duration_seconds / 60))
        return Schedule(self.start_time, new_duration)

    @classmethod
    def from_start_end(cls, start_time: datetime, end_time: datetime) -> "Schedule":
        """Create schedule from start and end times."""
        if end_time <= start_time:
            raise ValueError("End time must be after start time")

        duration_seconds = (end_time - start_time).total_seconds()
        duration = Duration(int(duration_seconds / 60))
        return cls(start_time, duration)


@dataclass(frozen=True)
class TimeWindow:
    """
    Represents a time window constraint with earliest and latest allowed times.

    Used for due dates, availability windows, and scheduling constraints.
    """

    earliest: datetime
    latest: datetime

    def __post_init__(self):
        if self.latest <= self.earliest:
            raise TimeValidationError("Latest time must be after earliest time")

    def __str__(self) -> str:
        """Return human-readable time window."""
        return (
            f"{self.earliest.strftime('%Y-%m-%d %H:%M')} - "
            f"{self.latest.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def duration(self) -> Duration:
        """Get duration of the time window."""
        duration_seconds = (self.latest - self.earliest).total_seconds()
        return Duration(int(duration_seconds / 60))

    def contains_time(self, check_time: datetime) -> bool:
        """Check if given time is within the time window."""
        return self.earliest <= check_time <= self.latest

    def contains_schedule(self, schedule: Schedule) -> bool:
        """Check if entire schedule fits within the time window."""
        return self.earliest <= schedule.start_time and schedule.end_time <= self.latest

    def overlaps_with(self, other: "TimeWindow") -> bool:
        """Check if this time window overlaps with another."""
        return self.earliest < other.latest and self.latest > other.earliest

    def intersection_with(self, other: "TimeWindow") -> Optional["TimeWindow"]:
        """Get intersection with another time window, if any."""
        if not self.overlaps_with(other):
            return None

        intersection_start = max(self.earliest, other.earliest)
        intersection_end = min(self.latest, other.latest)

        return TimeWindow(intersection_start, intersection_end)

    def can_fit_duration(self, duration: Duration) -> bool:
        """Check if given duration can fit within the time window."""
        return self.duration >= duration

    def find_earliest_slot(
        self, duration: Duration, not_before: datetime | None = None
    ) -> datetime | None:
        """
        Find earliest possible start time for given duration within window.

        Args:
            duration: Required duration
            not_before: Earliest allowed start time (optional)

        Returns:
            Earliest start time, or None if duration doesn't fit
        """
        effective_start = self.earliest
        if not_before:
            effective_start = max(effective_start, not_before)

        if effective_start >= self.latest:
            return None

        # Check if duration fits from effective start
        end_time = effective_start + duration.to_timedelta()
        if end_time <= self.latest:
            return effective_start

        return None

    @classmethod
    def from_date(cls, target_date: date) -> "TimeWindow":
        """Create time window for entire day."""
        start = datetime.combine(target_date, time.min)
        end = datetime.combine(target_date, time.max)
        return cls(start, end)
