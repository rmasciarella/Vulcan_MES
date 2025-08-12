"""
Business Calendar Value Objects

Represents business calendar with working hours and holidays,
matching DOMAIN.md specification exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .time_window import TimeWindow


@dataclass(frozen=True)
class BusinessHours:
    """
    Represents daily business hours.
    Immutable value object matching DOMAIN.md specification.
    """

    start_time: time
    end_time: time

    def __post_init__(self):
        """Validate business hours constraints."""
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")

    def is_within_hours(self, check_time: time) -> bool:
        """
        Check if a time is within business hours.

        Args:
            check_time: Time to check

        Returns:
            True if time is within business hours
        """
        return self.start_time <= check_time <= self.end_time

    def duration_minutes(self) -> int:
        """
        Calculate duration of business hours in minutes.

        Returns:
            Duration in minutes
        """
        # Handle times that span midnight
        if self.end_time <= self.start_time:
            # This case should not happen due to validation, but handle it
            return 0

        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        return end_minutes - start_minutes

    def __str__(self) -> str:
        """String representation."""
        return (
            f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
        )

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"BusinessHours(start_time={self.start_time!r}, end_time={self.end_time!r})"
        )


@dataclass(frozen=True)
class BusinessCalendar:
    """
    Represents business calendar with working hours and holidays.
    Immutable value object matching DOMAIN.md specification exactly.
    """

    weekday_hours: dict[int, BusinessHours]  # 0=Monday, 6=Sunday
    holidays: set[date]
    lunch_break: TimeWindow | None = None

    def __post_init__(self):
        """Validate business calendar constraints."""
        # Validate weekday keys are 0-6
        for weekday in self.weekday_hours.keys():
            if not 0 <= weekday <= 6:
                raise ValueError(
                    f"Invalid weekday: {weekday}. Must be 0-6 (Monday=0, Sunday=6)"
                )

    @classmethod
    def standard_calendar(cls) -> BusinessCalendar:
        """
        Factory method for standard Mon-Fri 7am-4pm calendar.
        Matches DOMAIN.md specification exactly.

        Returns:
            Standard business calendar
        """
        weekday_hours = {
            0: BusinessHours(time(7, 0), time(16, 0)),  # Monday
            1: BusinessHours(time(7, 0), time(16, 0)),  # Tuesday
            2: BusinessHours(time(7, 0), time(16, 0)),  # Wednesday
            3: BusinessHours(time(7, 0), time(16, 0)),  # Thursday
            4: BusinessHours(time(7, 0), time(16, 0)),  # Friday
        }
        return cls(weekday_hours=weekday_hours, holidays=set())

    @classmethod
    def create_24_7(cls) -> BusinessCalendar:
        """
        Create a 24/7 business calendar with no holidays.

        Returns:
            24/7 business calendar
        """
        weekday_hours = {
            i: BusinessHours(time(0, 0), time(23, 59))
            for i in range(7)  # All days of week
        }
        return cls(weekday_hours=weekday_hours, holidays=set())

    @classmethod
    def create_custom(
        cls,
        working_days: dict[int, tuple[time, time]],
        holidays: set[date] = None,
        lunch_break: tuple[time, time] | None = None,
    ) -> BusinessCalendar:
        """
        Create a custom business calendar.

        Args:
            working_days: Dict mapping weekday (0-6) to (start_time, end_time) tuples
            holidays: Set of holiday dates
            lunch_break: Optional lunch break as (start_time, end_time) tuple

        Returns:
            Custom business calendar
        """
        weekday_hours = {
            weekday: BusinessHours(start, end)
            for weekday, (start, end) in working_days.items()
        }

        lunch_window = None
        if lunch_break:
            # Create a dummy lunch break TimeWindow (we'll need today's date)
            today = datetime.now().date()
            lunch_start = datetime.combine(today, lunch_break[0])
            lunch_end = datetime.combine(today, lunch_break[1])
            lunch_window = TimeWindow(lunch_start, lunch_end)

        return cls(
            weekday_hours=weekday_hours,
            holidays=holidays or set(),
            lunch_break=lunch_window,
        )

    def is_working_time(self, check_datetime: datetime) -> bool:
        """
        Check if datetime is during working hours.
        Matches DOMAIN.md specification exactly.

        Args:
            check_datetime: Datetime to check

        Returns:
            True if datetime is during working hours
        """
        check_date = check_datetime.date()
        if check_date in self.holidays:
            return False

        weekday = check_datetime.weekday()
        if weekday not in self.weekday_hours:
            return False

        hours = self.weekday_hours[weekday]
        check_time = check_datetime.time()

        if not hours.is_within_hours(check_time):
            return False

        # Check lunch break if defined
        if self.lunch_break:
            # Adjust lunch break to the check date
            lunch_start = datetime.combine(
                check_date, self.lunch_break.start_time.time()
            )
            lunch_end = datetime.combine(check_date, self.lunch_break.end_time.time())
            if lunch_start <= check_datetime <= lunch_end:
                return False

        return True

    def next_working_time(self, from_time: datetime) -> datetime:
        """
        Find next available working time.
        Matches DOMAIN.md specification exactly.

        Args:
            from_time: Starting datetime

        Returns:
            Next available working datetime
        """
        current = from_time
        max_iterations = 14  # Prevent infinite loop, check up to 2 weeks
        iterations = 0

        while not self.is_working_time(current) and iterations < max_iterations:
            current += timedelta(minutes=15)  # Check in 15-minute increments
            iterations += 1

        if iterations >= max_iterations:
            # Fallback: find next working day
            current = from_time.replace(hour=0, minute=0, second=0, microsecond=0)
            for _ in range(14):  # Check up to 2 weeks
                current += timedelta(days=1)
                weekday = current.weekday()
                if (
                    weekday in self.weekday_hours
                    and current.date() not in self.holidays
                ):
                    business_hours = self.weekday_hours[weekday]
                    return current.replace(
                        hour=business_hours.start_time.hour,
                        minute=business_hours.start_time.minute,
                        second=0,
                        microsecond=0,
                    )

        return current

    def get_working_hours_for_date(self, target_date: date) -> BusinessHours | None:
        """
        Get working hours for a specific date.

        Args:
            target_date: Date to check

        Returns:
            BusinessHours for the date, or None if not a working day
        """
        if target_date in self.holidays:
            return None

        weekday = target_date.weekday()
        return self.weekday_hours.get(weekday)

    def is_working_day(self, target_date: date) -> bool:
        """
        Check if a date is a working day.

        Args:
            target_date: Date to check

        Returns:
            True if date is a working day
        """
        if target_date in self.holidays:
            return False
        return target_date.weekday() in self.weekday_hours

    def add_holiday(self, holiday_date: date) -> BusinessCalendar:
        """
        Create a new calendar with an additional holiday.

        Args:
            holiday_date: Date to add as holiday

        Returns:
            New BusinessCalendar with added holiday
        """
        new_holidays = self.holidays.copy()
        new_holidays.add(holiday_date)
        return BusinessCalendar(
            weekday_hours=self.weekday_hours,
            holidays=new_holidays,
            lunch_break=self.lunch_break,
        )

    def remove_holiday(self, holiday_date: date) -> BusinessCalendar:
        """
        Create a new calendar with a holiday removed.

        Args:
            holiday_date: Date to remove from holidays

        Returns:
            New BusinessCalendar with removed holiday
        """
        new_holidays = self.holidays.copy()
        new_holidays.discard(holiday_date)
        return BusinessCalendar(
            weekday_hours=self.weekday_hours,
            holidays=new_holidays,
            lunch_break=self.lunch_break,
        )

    def working_minutes_in_day(self, target_date: date) -> int:
        """
        Calculate working minutes in a specific day.

        Args:
            target_date: Date to check

        Returns:
            Number of working minutes in the day
        """
        business_hours = self.get_working_hours_for_date(target_date)
        if not business_hours:
            return 0

        total_minutes = business_hours.duration_minutes()

        # Subtract lunch break if applicable
        if self.lunch_break:
            lunch_duration = self.lunch_break.end_time - self.lunch_break.start_time
            lunch_minutes = int(lunch_duration.total_seconds() / 60)
            total_minutes -= lunch_minutes

        return max(0, total_minutes)

    def __str__(self) -> str:
        """String representation."""
        working_days = sorted(self.weekday_hours.keys())
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        if not working_days:
            return "No working days"

        # Group consecutive days with same hours
        groups = []
        current_group = [working_days[0]]
        current_hours = self.weekday_hours[working_days[0]]

        for day in working_days[1:]:
            if self.weekday_hours[day] == current_hours:
                current_group.append(day)
            else:
                groups.append((current_group, current_hours))
                current_group = [day]
                current_hours = self.weekday_hours[day]

        groups.append((current_group, current_hours))

        # Format groups
        parts = []
        for days, hours in groups:
            if len(days) == 1:
                day_str = day_names[days[0]]
            elif len(days) >= 2 and days == list(range(days[0], days[-1] + 1)):
                day_str = f"{day_names[days[0]]}-{day_names[days[-1]]}"
            else:
                day_str = ",".join(day_names[d] for d in days)
            parts.append(f"{day_str}: {hours}")

        result = "; ".join(parts)

        if self.holidays:
            result += f" ({len(self.holidays)} holidays)"

        return result

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"BusinessCalendar(weekday_hours={self.weekday_hours!r}, "
            f"holidays={self.holidays!r}, lunch_break={self.lunch_break!r})"
        )
