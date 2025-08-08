"""
Time Window Value Object

Represents a time period with start and end boundaries.
Used for work hours, availability windows, and scheduling constraints.
"""

from datetime import datetime, time
from typing import Optional


class TimeWindow:
    """
    A time window value object representing a period between two points in time.

    Can represent absolute time windows (with datetime) or relative time windows
    (with minutes from a reference point).
    """

    def __init__(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        start_minutes: int | None = None,
        end_minutes: int | None = None,
    ) -> None:
        """
        Initialize a TimeWindow.

        Must provide either absolute times (start_time/end_time) or
        relative minutes (start_minutes/end_minutes).

        Args:
            start_time: Absolute start time
            end_time: Absolute end time
            start_minutes: Start time in minutes from reference (e.g., midnight)
            end_minutes: End time in minutes from reference

        Raises:
            ValueError: If invalid parameters provided
        """
        if start_time is not None and end_time is not None:
            # Absolute time window
            if start_time > end_time:
                raise ValueError("Start time must be before end time")
            self._start_time = start_time
            self._end_time = end_time
            self._start_minutes = None
            self._end_minutes = None

        elif start_minutes is not None and end_minutes is not None:
            # Relative time window (minutes from reference point)
            if start_minutes > end_minutes:
                raise ValueError("Start minutes must be less than end minutes")
            self._start_time = None
            self._end_time = None
            self._start_minutes = start_minutes
            self._end_minutes = end_minutes

        else:
            raise ValueError("Must provide either absolute times or relative minutes")

    @classmethod
    def from_work_hours(cls, start_hour: int, end_hour: int) -> "TimeWindow":
        """
        Create TimeWindow from work hours (24-hour format).

        Args:
            start_hour: Start hour (0-23)
            end_hour: End hour (0-23)

        Returns:
            TimeWindow representing the work hours
        """
        start_minutes = start_hour * 60
        end_minutes = end_hour * 60
        return cls(start_minutes=start_minutes, end_minutes=end_minutes)

    @classmethod
    def from_time_objects(cls, start: time, end: time) -> "TimeWindow":
        """
        Create TimeWindow from Python time objects.

        Args:
            start: Start time
            end: End time

        Returns:
            TimeWindow representing the time period
        """
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        return cls(start_minutes=start_minutes, end_minutes=end_minutes)

    @classmethod
    def all_day(cls) -> "TimeWindow":
        """
        Create a 24-hour TimeWindow.

        Returns:
            TimeWindow covering entire day (0:00 to 23:59)
        """
        return cls(start_minutes=0, end_minutes=24 * 60 - 1)

    @classmethod
    def business_hours(cls) -> "TimeWindow":
        """
        Create standard business hours TimeWindow (9 AM to 5 PM).

        Returns:
            TimeWindow for business hours
        """
        return cls.from_work_hours(9, 17)

    @property
    def start_time(self) -> datetime | None:
        """Get absolute start time."""
        return self._start_time

    @property
    def end_time(self) -> datetime | None:
        """Get absolute end time."""
        return self._end_time

    @property
    def start_minutes(self) -> int | None:
        """Get start time in minutes from reference."""
        return self._start_minutes

    @property
    def end_minutes(self) -> int | None:
        """Get end time in minutes from reference."""
        return self._end_minutes

    @property
    def is_absolute(self) -> bool:
        """Check if this is an absolute time window."""
        return self._start_time is not None

    @property
    def is_relative(self) -> bool:
        """Check if this is a relative time window."""
        return self._start_minutes is not None

    def duration_minutes(self) -> int:
        """
        Get duration of the time window in minutes.

        Returns:
            Duration in minutes
        """
        if self.is_absolute:
            delta = self._end_time - self._start_time  # type: ignore
            return int(delta.total_seconds() / 60)
        else:
            return self._end_minutes - self._start_minutes  # type: ignore

    def contains_absolute_time(self, time_point: datetime) -> bool:
        """
        Check if an absolute time point is within this window.

        Args:
            time_point: Time to check

        Returns:
            True if time point is within window

        Raises:
            ValueError: If this is not an absolute time window
        """
        if not self.is_absolute:
            raise ValueError("Cannot check absolute time against relative window")

        return self._start_time <= time_point <= self._end_time  # type: ignore

    def contains_relative_time(self, minutes: int) -> bool:
        """
        Check if a relative time (in minutes) is within this window.

        Args:
            minutes: Time in minutes from reference point

        Returns:
            True if time is within window

        Raises:
            ValueError: If this is not a relative time window
        """
        if not self.is_relative:
            raise ValueError("Cannot check relative time against absolute window")

        return self._start_minutes <= minutes <= self._end_minutes  # type: ignore

    def overlaps_with(self, other: "TimeWindow") -> bool:
        """
        Check if this window overlaps with another window.

        Args:
            other: Other time window to check

        Returns:
            True if windows overlap

        Raises:
            ValueError: If windows have different reference systems
        """
        if self.is_absolute != other.is_absolute:
            raise ValueError("Cannot compare absolute and relative time windows")

        if self.is_absolute:
            return (
                self._start_time < other._end_time  # type: ignore
                and other._start_time < self._end_time
            )  # type: ignore
        else:
            return (
                self._start_minutes < other._end_minutes  # type: ignore
                and other._start_minutes < self._end_minutes
            )  # type: ignore

    def intersection_with(self, other: "TimeWindow") -> Optional["TimeWindow"]:
        """
        Get intersection with another time window.

        Args:
            other: Other time window

        Returns:
            Intersection time window or None if no overlap

        Raises:
            ValueError: If windows have different reference systems
        """
        if not self.overlaps_with(other):
            return None

        if self.is_absolute:
            start = max(self._start_time, other._start_time)  # type: ignore
            end = min(self._end_time, other._end_time)  # type: ignore
            return TimeWindow(start_time=start, end_time=end)
        else:
            start = max(self._start_minutes, other._start_minutes)  # type: ignore
            end = min(self._end_minutes, other._end_minutes)  # type: ignore
            return TimeWindow(start_minutes=start, end_minutes=end)

    def union_with(self, other: "TimeWindow") -> "TimeWindow":
        """
        Get union with another time window.

        Args:
            other: Other time window

        Returns:
            Union time window (may include gaps)

        Raises:
            ValueError: If windows have different reference systems
        """
        if self.is_absolute != other.is_absolute:
            raise ValueError("Cannot union absolute and relative time windows")

        if self.is_absolute:
            start = min(self._start_time, other._start_time)  # type: ignore
            end = max(self._end_time, other._end_time)  # type: ignore
            return TimeWindow(start_time=start, end_time=end)
        else:
            start = min(self._start_minutes, other._start_minutes)  # type: ignore
            end = max(self._end_minutes, other._end_minutes)  # type: ignore
            return TimeWindow(start_minutes=start, end_minutes=end)

    def shift_by_minutes(self, minutes: int) -> "TimeWindow":
        """
        Shift the time window by a number of minutes.

        Args:
            minutes: Minutes to shift (positive = later, negative = earlier)

        Returns:
            New shifted time window
        """
        if self.is_absolute:
            from datetime import timedelta

            delta = timedelta(minutes=minutes)
            return TimeWindow(
                start_time=self._start_time + delta,  # type: ignore
                end_time=self._end_time + delta,  # type: ignore
            )
        else:
            return TimeWindow(
                start_minutes=self._start_minutes + minutes,  # type: ignore
                end_minutes=self._end_minutes + minutes,  # type: ignore
            )

    def extend_by_minutes(self, minutes: int) -> "TimeWindow":
        """
        Extend the end of the time window by a number of minutes.

        Args:
            minutes: Minutes to extend (can be negative to shrink)

        Returns:
            New extended time window
        """
        if self.is_absolute:
            from datetime import timedelta

            delta = timedelta(minutes=minutes)
            return TimeWindow(
                start_time=self._start_time,  # type: ignore
                end_time=self._end_time + delta,  # type: ignore
            )
        else:
            return TimeWindow(
                start_minutes=self._start_minutes,  # type: ignore
                end_minutes=self._end_minutes + minutes,  # type: ignore
            )

    def to_time_of_day_string(self) -> str:
        """
        Convert to time-of-day string format.

        Returns:
            String like "09:00-17:00"

        Raises:
            ValueError: If this is an absolute time window
        """
        if not self.is_relative:
            raise ValueError("Cannot convert absolute time window to time-of-day")

        start_hours = self._start_minutes // 60  # type: ignore
        start_mins = self._start_minutes % 60  # type: ignore
        end_hours = self._end_minutes // 60  # type: ignore
        end_mins = self._end_minutes % 60  # type: ignore

        return f"{start_hours:02d}:{start_mins:02d}-{end_hours:02d}:{end_mins:02d}"

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, TimeWindow):
            return False

        if self.is_absolute != other.is_absolute:
            return False

        if self.is_absolute:
            return (
                self._start_time == other._start_time
                and self._end_time == other._end_time
            )
        else:
            return (
                self._start_minutes == other._start_minutes
                and self._end_minutes == other._end_minutes
            )

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        if self.is_absolute:
            return hash((self._start_time, self._end_time))
        else:
            return hash((self._start_minutes, self._end_minutes))

    def __str__(self) -> str:
        """String representation."""
        if self.is_absolute:
            return f"{self._start_time} to {self._end_time}"
        else:
            return self.to_time_of_day_string()

    def __repr__(self) -> str:
        """Detailed string representation."""
        if self.is_absolute:
            return (
                f"TimeWindow(start_time={self._start_time}, end_time={self._end_time})"
            )
        else:
            return f"TimeWindow(start_minutes={self._start_minutes}, end_minutes={self._end_minutes})"
