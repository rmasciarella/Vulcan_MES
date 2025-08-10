"""
Business Calendar and Scheduling Value Objects

Value objects representing business calendar concepts, working days, holidays,
maintenance windows, and scheduling-specific calendar logic.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from .time import Duration, TimeOfDay, TimeWindow, WorkingHours


class DayType(Enum):
    """Types of days in the business calendar."""

    WORKING_DAY = "working_day"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    MAINTENANCE_DAY = "maintenance_day"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class BusinessDay:
    """
    Represents a single day in the business calendar with working hours and special attributes.

    Contains information about whether the day is working, holiday information,
    and specific working hours for the day.
    """

    calendar_date: date
    day_type: DayType
    is_working_day: bool
    holiday_name: str | None = None
    working_hours: WorkingHours | None = None
    notes: str | None = None

    def __post_init__(self):
        # Validate consistency
        if self.day_type == DayType.HOLIDAY and not self.holiday_name:
            raise ValueError("Holiday days must have a holiday name")

        if self.is_working_day and self.working_hours is None:
            # Set default working hours for working days
            object.__setattr__(self, "working_hours", WorkingHours.standard_day_shift())

        if not self.is_working_day and self.day_type == DayType.WORKING_DAY:
            raise ValueError("Working day type must have is_working_day=True")

    def __str__(self) -> str:
        """Return human-readable business day."""
        base = f"{self.calendar_date.strftime('%Y-%m-%d')} ({self.day_type.value})"
        if self.holiday_name:
            base += f" - {self.holiday_name}"
        if self.is_working_day and self.working_hours:
            base += f" {self.working_hours}"
        return base

    @property
    def weekday(self) -> int:
        """Get weekday (0=Monday, 6=Sunday)."""
        return self.calendar_date.weekday()

    @property
    def is_weekend(self) -> bool:
        """Check if day is weekend."""
        return self.weekday >= 5  # Saturday (5) or Sunday (6)

    @property
    def is_holiday(self) -> bool:
        """Check if day is a holiday."""
        return self.day_type == DayType.HOLIDAY

    @property
    def is_shutdown(self) -> bool:
        """Check if day is a shutdown day."""
        return self.day_type == DayType.SHUTDOWN

    @property
    def is_maintenance_day(self) -> bool:
        """Check if day is designated for maintenance."""
        return self.day_type == DayType.MAINTENANCE_DAY

    @property
    def available_work_duration(self) -> Duration:
        """Get available work duration for the day."""
        if not self.is_working_day or not self.working_hours:
            return Duration.zero()
        return self.working_hours.available_work_duration

    @property
    def day_name(self) -> str:
        """Get day name (Monday, Tuesday, etc.)."""
        return self.calendar_date.strftime("%A")

    def is_working_time(self, time_of_day: TimeOfDay) -> bool:
        """Check if specific time is within working hours."""
        if not self.is_working_day or not self.working_hours:
            return False
        return self.working_hours.is_working_time(time_of_day)

    def find_available_slot(
        self, duration_needed: Duration, start_from: TimeOfDay | None = None
    ) -> TimeOfDay | None:
        """Find available time slot of given duration on this day."""
        if not self.is_working_day or not self.working_hours:
            return None

        start_time = start_from or self.working_hours.start_time
        return self.working_hours.find_next_available_slot(start_time, duration_needed)

    @classmethod
    def working_day(
        cls, calendar_date: date, working_hours: WorkingHours | None = None
    ) -> "BusinessDay":
        """Factory method for working day."""
        return cls(
            calendar_date=calendar_date,
            day_type=DayType.WORKING_DAY,
            is_working_day=True,
            working_hours=working_hours or WorkingHours.standard_day_shift(),
        )

    @classmethod
    def weekend_day(cls, calendar_date: date) -> "BusinessDay":
        """Factory method for weekend day."""
        return cls(
            calendar_date=calendar_date, day_type=DayType.WEEKEND, is_working_day=False
        )

    @classmethod
    def holiday(cls, calendar_date: date, holiday_name: str) -> "BusinessDay":
        """Factory method for holiday."""
        return cls(
            calendar_date=calendar_date,
            day_type=DayType.HOLIDAY,
            is_working_day=False,
            holiday_name=holiday_name,
        )

    @classmethod
    def maintenance_day(
        cls,
        calendar_date: date,
        working_hours: WorkingHours | None = None,
        notes: str | None = None,
    ) -> "BusinessDay":
        """Factory method for maintenance day (may still be working)."""
        is_working = working_hours is not None
        return cls(
            calendar_date=calendar_date,
            day_type=DayType.MAINTENANCE_DAY,
            is_working_day=is_working,
            working_hours=working_hours,
            notes=notes,
        )

    @classmethod
    def shutdown_day(
        cls, calendar_date: date, notes: str | None = None
    ) -> "BusinessDay":
        """Factory method for shutdown day."""
        return cls(
            calendar_date=calendar_date,
            day_type=DayType.SHUTDOWN,
            is_working_day=False,
            notes=notes,
        )


@dataclass(frozen=True)
class BusinessCalendar:
    """
    Represents a business calendar with working days, holidays, and special events.

    Provides methods to query working days, calculate durations, and find
    available time slots across multiple days.
    """

    calendar_name: str
    start_date: date
    end_date: date
    business_days: dict[date, BusinessDay] = field(default_factory=dict)
    default_working_hours: WorkingHours = field(
        default_factory=WorkingHours.standard_day_shift
    )

    def __post_init__(self):
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date")
        if not self.calendar_name.strip():
            raise ValueError("Calendar name cannot be empty")

    def __str__(self) -> str:
        """Return human-readable business calendar."""
        return (
            f"{self.calendar_name} ({self.start_date} to {self.end_date}): "
            f"{len(self.business_days)} defined days"
        )

    def get_business_day(self, calendar_date: date) -> BusinessDay:
        """
        Get business day for given date, creating default if not defined.

        Args:
            calendar_date: Date to get business day for

        Returns:
            BusinessDay for the date
        """
        if calendar_date in self.business_days:
            return self.business_days[calendar_date]

        # Create default business day based on weekday
        weekday = calendar_date.weekday()
        if weekday < 5:  # Monday to Friday
            return BusinessDay.working_day(calendar_date, self.default_working_hours)
        else:  # Weekend
            return BusinessDay.weekend_day(calendar_date)

    def is_working_day(self, calendar_date: date) -> bool:
        """Check if given date is a working day."""
        return self.get_business_day(calendar_date).is_working_day

    def is_holiday(self, calendar_date: date) -> bool:
        """Check if given date is a holiday."""
        return self.get_business_day(calendar_date).is_holiday

    def get_working_hours(self, calendar_date: date) -> WorkingHours | None:
        """Get working hours for given date."""
        return self.get_business_day(calendar_date).working_hours

    def get_working_days_between(
        self, start_date: date, end_date: date
    ) -> list[BusinessDay]:
        """Get list of working days between two dates (inclusive)."""
        if end_date < start_date:
            return []

        working_days = []
        current_date = start_date
        while current_date <= end_date:
            business_day = self.get_business_day(current_date)
            if business_day.is_working_day:
                working_days.append(business_day)
            current_date += timedelta(days=1)

        return working_days

    def count_working_days_between(self, start_date: date, end_date: date) -> int:
        """Count number of working days between two dates."""
        return len(self.get_working_days_between(start_date, end_date))

    def get_next_working_day(self, from_date: date) -> BusinessDay | None:
        """Get next working day after given date."""
        current_date = from_date + timedelta(days=1)
        while current_date <= self.end_date:
            business_day = self.get_business_day(current_date)
            if business_day.is_working_day:
                return business_day
            current_date += timedelta(days=1)
        return None

    def get_previous_working_day(self, from_date: date) -> BusinessDay | None:
        """Get previous working day before given date."""
        current_date = from_date - timedelta(days=1)
        while current_date >= self.start_date:
            business_day = self.get_business_day(current_date)
            if business_day.is_working_day:
                return business_day
            current_date -= timedelta(days=1)
        return None

    def calculate_working_duration_between(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> Duration:
        """
        Calculate total working duration between two datetimes.

        Args:
            start_datetime: Start datetime
            end_datetime: End datetime

        Returns:
            Total working duration between the times
        """
        if end_datetime <= start_datetime:
            return Duration.zero()

        total_minutes = 0
        current_date = start_datetime.date()
        end_date = end_datetime.date()

        while current_date <= end_date:
            business_day = self.get_business_day(current_date)
            if not business_day.is_working_day or not business_day.working_hours:
                current_date += timedelta(days=1)
                continue

            # Determine effective start and end times for this day
            if current_date == start_datetime.date():
                day_start = TimeOfDay(start_datetime.hour, start_datetime.minute)
            else:
                day_start = business_day.working_hours.start_time

            if current_date == end_datetime.date():
                day_end = TimeOfDay(end_datetime.hour, end_datetime.minute)
            else:
                day_end = business_day.working_hours.end_time

            # Calculate working minutes for this day
            for work_start, work_end in business_day.working_hours.get_work_periods():
                period_start = max(day_start, work_start)
                period_end = min(day_end, work_end)

                if period_start < period_end:
                    period_minutes = (
                        period_end.total_minutes_from_midnight
                        - period_start.total_minutes_from_midnight
                    )
                    total_minutes += period_minutes

            current_date += timedelta(days=1)

        return Duration(total_minutes)

    def find_next_available_datetime(
        self, from_datetime: datetime, duration_needed: Duration
    ) -> datetime | None:
        """
        Find next available datetime slot for given duration.

        Args:
            from_datetime: Earliest datetime to start looking
            duration_needed: Required duration

        Returns:
            Start datetime of available slot, or None if not found
        """
        current_date = from_datetime.date()
        current_time = TimeOfDay(from_datetime.hour, from_datetime.minute)

        while current_date <= self.end_date:
            business_day = self.get_business_day(current_date)

            if business_day.is_working_day and business_day.working_hours:
                # Try to find slot on this day
                slot_time = business_day.find_available_slot(
                    duration_needed, current_time
                )

                if slot_time is not None:
                    return datetime.combine(current_date, slot_time.to_time())

            # Move to next day, start from beginning of working hours
            current_date += timedelta(days=1)
            current_time = self.default_working_hours.start_time

        return None

    def add_holiday(self, holiday_date: date, holiday_name: str) -> "BusinessCalendar":
        """Create new calendar with added holiday."""
        new_days = dict(self.business_days)
        new_days[holiday_date] = BusinessDay.holiday(holiday_date, holiday_name)

        return BusinessCalendar(
            calendar_name=self.calendar_name,
            start_date=self.start_date,
            end_date=self.end_date,
            business_days=new_days,
            default_working_hours=self.default_working_hours,
        )

    def add_shutdown_period(
        self, start_date: date, end_date: date, reason: str | None = None
    ) -> "BusinessCalendar":
        """Create new calendar with shutdown period."""
        new_days = dict(self.business_days)

        current_date = start_date
        while current_date <= end_date:
            new_days[current_date] = BusinessDay.shutdown_day(current_date, reason)
            current_date += timedelta(days=1)

        return BusinessCalendar(
            calendar_name=self.calendar_name,
            start_date=self.start_date,
            end_date=self.end_date,
            business_days=new_days,
            default_working_hours=self.default_working_hours,
        )

    def get_holidays_in_period(
        self, start_date: date, end_date: date
    ) -> list[BusinessDay]:
        """Get list of holidays in given period."""
        holidays = []
        current_date = start_date
        while current_date <= end_date:
            business_day = self.get_business_day(current_date)
            if business_day.is_holiday:
                holidays.append(business_day)
            current_date += timedelta(days=1)
        return holidays

    @classmethod
    def create_standard_calendar(
        cls, calendar_name: str, year: int, working_hours: WorkingHours | None = None
    ) -> "BusinessCalendar":
        """
        Create standard business calendar for a year with weekends as non-working days.

        Args:
            calendar_name: Name of the calendar
            year: Year to create calendar for
            working_hours: Default working hours (uses standard if not provided)

        Returns:
            BusinessCalendar for the year
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        default_hours = working_hours or WorkingHours.standard_day_shift()

        return cls(
            calendar_name=calendar_name,
            start_date=start_date,
            end_date=end_date,
            business_days={},
            default_working_hours=default_hours,
        )


@dataclass(frozen=True)
class MaintenanceWindow:
    """
    Represents a maintenance window when resources are unavailable.

    Maintenance windows block resource availability and must be considered
    during scheduling to avoid conflicts.
    """

    maintenance_id: int
    resource_id: int
    resource_type: str  # "machine", "operator", "zone"
    maintenance_type: str  # "preventive", "corrective", "calibration"
    time_window: TimeWindow
    technician_name: str | None = None
    description: str | None = None
    is_emergency: bool = False

    def __post_init__(self):
        if self.maintenance_id <= 0:
            raise ValueError("Maintenance ID must be positive")
        if self.resource_id <= 0:
            raise ValueError("Resource ID must be positive")
        if not self.resource_type.strip():
            raise ValueError("Resource type cannot be empty")
        if not self.maintenance_type.strip():
            raise ValueError("Maintenance type cannot be empty")

    def __str__(self) -> str:
        """Return human-readable maintenance window."""
        return (
            f"{self.maintenance_type.title()} maintenance for "
            f"{self.resource_type} {self.resource_id}: {self.time_window}"
        )

    @property
    def duration(self) -> Duration:
        """Get maintenance duration."""
        return self.time_window.duration

    @property
    def start_time(self) -> datetime:
        """Get maintenance start time."""
        return self.time_window.earliest

    @property
    def end_time(self) -> datetime:
        """Get maintenance end time."""
        return self.time_window.latest

    @property
    def is_preventive(self) -> bool:
        """Check if this is preventive maintenance."""
        return self.maintenance_type.lower() == "preventive"

    @property
    def is_corrective(self) -> bool:
        """Check if this is corrective maintenance."""
        return self.maintenance_type.lower() == "corrective"

    @property
    def affects_machine(self) -> bool:
        """Check if maintenance affects a machine."""
        return self.resource_type.lower() == "machine"

    @property
    def affects_operator(self) -> bool:
        """Check if maintenance affects an operator."""
        return self.resource_type.lower() == "operator"

    def conflicts_with_schedule(
        self, schedule_start: datetime, schedule_end: datetime
    ) -> bool:
        """Check if maintenance window conflicts with given schedule."""
        return schedule_start < self.end_time and schedule_end > self.start_time

    def blocks_resource_at(self, check_time: datetime) -> bool:
        """Check if maintenance blocks resource at given time."""
        return self.time_window.contains_time(check_time)

    @classmethod
    def preventive_maintenance(
        cls,
        maintenance_id: int,
        resource_id: int,
        resource_type: str,
        start_time: datetime,
        duration: Duration,
        technician_name: str | None = None,
    ) -> "MaintenanceWindow":
        """Factory method for preventive maintenance."""
        time_window = TimeWindow(start_time, start_time + duration.to_timedelta())
        return cls(
            maintenance_id=maintenance_id,
            resource_id=resource_id,
            resource_type=resource_type,
            maintenance_type="preventive",
            time_window=time_window,
            technician_name=technician_name,
            is_emergency=False,
        )

    @classmethod
    def emergency_maintenance(
        cls,
        maintenance_id: int,
        resource_id: int,
        resource_type: str,
        start_time: datetime,
        duration: Duration,
        description: str | None = None,
    ) -> "MaintenanceWindow":
        """Factory method for emergency maintenance."""
        time_window = TimeWindow(start_time, start_time + duration.to_timedelta())
        return cls(
            maintenance_id=maintenance_id,
            resource_id=resource_id,
            resource_type=resource_type,
            maintenance_type="corrective",
            time_window=time_window,
            description=description,
            is_emergency=True,
        )
