"""
Comprehensive Unit Tests for TimeWindow Value Object

Tests all functionality, validation, and business rules for the TimeWindow value object.
Covers absolute and relative time windows, overlaps, intersections, and edge cases.
"""

import pytest
from datetime import datetime, time, timedelta

from app.domain.scheduling.value_objects.time_window import TimeWindow


class TestTimeWindowCreation:
    """Test TimeWindow creation with various parameters."""

    def test_create_absolute_time_window(self):
        """Test creating time window with absolute datetime."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        
        window = TimeWindow(start_time=start, end_time=end)
        
        assert window.start_time == start
        assert window.end_time == end
        assert window.is_absolute
        assert not window.is_relative
        assert window.start_minutes is None
        assert window.end_minutes is None

    def test_create_relative_time_window(self):
        """Test creating time window with relative minutes."""
        start_minutes = 9 * 60  # 9 AM
        end_minutes = 17 * 60   # 5 PM
        
        window = TimeWindow(start_minutes=start_minutes, end_minutes=end_minutes)
        
        assert window.start_minutes == start_minutes
        assert window.end_minutes == end_minutes
        assert window.is_relative
        assert not window.is_absolute
        assert window.start_time is None
        assert window.end_time is None

    def test_create_invalid_absolute_time_window(self):
        """Test creating absolute time window with end before start fails."""
        start = datetime(2024, 1, 1, 17, 0)
        end = datetime(2024, 1, 1, 9, 0)  # End before start
        
        with pytest.raises(ValueError, match="Start time must be before end time"):
            TimeWindow(start_time=start, end_time=end)

    def test_create_invalid_relative_time_window(self):
        """Test creating relative time window with end before start fails."""
        start_minutes = 17 * 60  # 5 PM
        end_minutes = 9 * 60     # 9 AM
        
        with pytest.raises(ValueError, match="Start minutes must be less than end minutes"):
            TimeWindow(start_minutes=start_minutes, end_minutes=end_minutes)

    def test_create_with_no_parameters_fails(self):
        """Test creating time window with no parameters fails."""
        with pytest.raises(ValueError, match="Must provide either absolute times or relative minutes"):
            TimeWindow()

    def test_create_with_mixed_parameters_fails(self):
        """Test creating time window with mixed absolute/relative parameters fails."""
        start = datetime(2024, 1, 1, 9, 0)
        end_minutes = 17 * 60
        
        with pytest.raises(ValueError, match="Must provide either absolute times or relative minutes"):
            TimeWindow(start_time=start, end_minutes=end_minutes)


class TestTimeWindowFactoryMethods:
    """Test TimeWindow factory methods."""

    def test_from_work_hours(self):
        """Test creating time window from work hours."""
        window = TimeWindow.from_work_hours(9, 17)  # 9 AM to 5 PM
        
        assert window.is_relative
        assert window.start_minutes == 9 * 60
        assert window.end_minutes == 17 * 60
        assert window.duration_minutes() == 8 * 60

    def test_from_time_objects(self):
        """Test creating time window from Python time objects."""
        start_time = time(9, 30)  # 9:30 AM
        end_time = time(17, 15)   # 5:15 PM
        
        window = TimeWindow.from_time_objects(start_time, end_time)
        
        assert window.is_relative
        assert window.start_minutes == 9 * 60 + 30
        assert window.end_minutes == 17 * 60 + 15

    def test_all_day(self):
        """Test creating all-day time window."""
        window = TimeWindow.all_day()
        
        assert window.is_relative
        assert window.start_minutes == 0
        assert window.end_minutes == 24 * 60 - 1  # 23:59
        assert window.duration_minutes() == 24 * 60 - 1

    def test_business_hours(self):
        """Test creating standard business hours window."""
        window = TimeWindow.business_hours()
        
        assert window.is_relative
        assert window.start_minutes == 9 * 60   # 9 AM
        assert window.end_minutes == 17 * 60    # 5 PM
        assert window.duration_minutes() == 8 * 60


class TestTimeWindowDuration:
    """Test TimeWindow duration calculations."""

    def test_duration_absolute_window(self):
        """Test duration calculation for absolute time window."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 30)  # 8.5 hours later
        
        window = TimeWindow(start_time=start, end_time=end)
        
        assert window.duration_minutes() == 8 * 60 + 30  # 8.5 hours

    def test_duration_relative_window(self):
        """Test duration calculation for relative time window."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60 + 30)
        
        assert window.duration_minutes() == 8 * 60 + 30  # 8.5 hours

    def test_duration_zero_window(self):
        """Test duration for zero-length window."""
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 0)
        
        window = TimeWindow(start_time=start, end_time=end)
        
        assert window.duration_minutes() == 0

    def test_duration_cross_midnight(self):
        """Test duration calculation crossing midnight."""
        # Note: This would require special handling in a real implementation
        # For now, testing within-day scenarios
        window = TimeWindow(start_minutes=22 * 60, end_minutes=23 * 60)  # 10-11 PM
        assert window.duration_minutes() == 60


class TestTimeWindowContainment:
    """Test TimeWindow containment methods."""

    def test_contains_absolute_time(self):
        """Test checking if absolute time is contained."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)
        
        # Time within window
        test_time = datetime(2024, 1, 1, 12, 0)
        assert window.contains_absolute_time(test_time)
        
        # Time at start boundary
        assert window.contains_absolute_time(start)
        
        # Time at end boundary
        assert window.contains_absolute_time(end)
        
        # Time before window
        before_time = datetime(2024, 1, 1, 8, 0)
        assert not window.contains_absolute_time(before_time)
        
        # Time after window
        after_time = datetime(2024, 1, 1, 18, 0)
        assert not window.contains_absolute_time(after_time)

    def test_contains_relative_time(self):
        """Test checking if relative time is contained."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        # Time within window
        assert window.contains_relative_time(12 * 60)  # Noon
        
        # Time at boundaries
        assert window.contains_relative_time(9 * 60)   # Start
        assert window.contains_relative_time(17 * 60)  # End
        
        # Time outside window
        assert not window.contains_relative_time(8 * 60)   # Before
        assert not window.contains_relative_time(18 * 60)  # After

    def test_contains_absolute_time_on_relative_window_fails(self):
        """Test checking absolute time on relative window fails."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        test_time = datetime(2024, 1, 1, 12, 0)
        
        with pytest.raises(ValueError, match="Cannot check absolute time against relative window"):
            window.contains_absolute_time(test_time)

    def test_contains_relative_time_on_absolute_window_fails(self):
        """Test checking relative time on absolute window fails."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)
        
        with pytest.raises(ValueError, match="Cannot check relative time against absolute window"):
            window.contains_relative_time(12 * 60)


class TestTimeWindowOverlaps:
    """Test TimeWindow overlap detection."""

    def test_overlaps_absolute_windows(self):
        """Test overlap detection for absolute windows."""
        # Non-overlapping windows
        w1 = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 12, 0)
        )
        w2 = TimeWindow(
            start_time=datetime(2024, 1, 1, 13, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        assert not w1.overlaps_with(w2)
        assert not w2.overlaps_with(w1)
        
        # Overlapping windows
        w3 = TimeWindow(
            start_time=datetime(2024, 1, 1, 11, 0),
            end_time=datetime(2024, 1, 1, 14, 0)
        )
        assert w1.overlaps_with(w3)
        assert w2.overlaps_with(w3)

    def test_overlaps_relative_windows(self):
        """Test overlap detection for relative windows."""
        # Non-overlapping windows
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=12 * 60)   # 9-12
        w2 = TimeWindow(start_minutes=13 * 60, end_minutes=17 * 60)  # 13-17
        
        assert not w1.overlaps_with(w2)
        
        # Overlapping windows
        w3 = TimeWindow(start_minutes=11 * 60, end_minutes=14 * 60)  # 11-14
        
        assert w1.overlaps_with(w3)
        assert w2.overlaps_with(w3)

    def test_overlaps_adjacent_windows(self):
        """Test that adjacent windows don't overlap."""
        # Adjacent absolute windows
        w1 = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 12, 0)
        )
        w2 = TimeWindow(
            start_time=datetime(2024, 1, 1, 12, 0),  # Starts exactly when w1 ends
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        
        # Should not overlap (start == end doesn't count as overlap)
        assert not w1.overlaps_with(w2)

    def test_overlaps_identical_windows(self):
        """Test that identical windows overlap."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        assert w1.overlaps_with(w2)

    def test_overlaps_different_types_fails(self):
        """Test overlap check between different window types fails."""
        absolute_window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        relative_window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        with pytest.raises(ValueError, match="Cannot compare absolute and relative time windows"):
            absolute_window.overlaps_with(relative_window)


class TestTimeWindowIntersection:
    """Test TimeWindow intersection operations."""

    def test_intersection_overlapping_absolute_windows(self):
        """Test intersection of overlapping absolute windows."""
        w1 = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 14, 0)
        )
        w2 = TimeWindow(
            start_time=datetime(2024, 1, 1, 12, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        
        intersection = w1.intersection_with(w2)
        
        assert intersection is not None
        assert intersection.start_time == datetime(2024, 1, 1, 12, 0)
        assert intersection.end_time == datetime(2024, 1, 1, 14, 0)

    def test_intersection_overlapping_relative_windows(self):
        """Test intersection of overlapping relative windows."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=14 * 60)   # 9-14
        w2 = TimeWindow(start_minutes=12 * 60, end_minutes=17 * 60)  # 12-17
        
        intersection = w1.intersection_with(w2)
        
        assert intersection is not None
        assert intersection.start_minutes == 12 * 60
        assert intersection.end_minutes == 14 * 60

    def test_intersection_non_overlapping_windows(self):
        """Test intersection of non-overlapping windows returns None."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=12 * 60)
        w2 = TimeWindow(start_minutes=13 * 60, end_minutes=17 * 60)
        
        intersection = w1.intersection_with(w2)
        
        assert intersection is None

    def test_intersection_identical_windows(self):
        """Test intersection of identical windows."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        intersection = w1.intersection_with(w2)
        
        assert intersection == w1
        assert intersection == w2

    def test_intersection_one_inside_other(self):
        """Test intersection when one window is inside another."""
        larger = TimeWindow(start_minutes=8 * 60, end_minutes=18 * 60)
        smaller = TimeWindow(start_minutes=10 * 60, end_minutes=16 * 60)
        
        intersection = larger.intersection_with(smaller)
        
        assert intersection == smaller


class TestTimeWindowUnion:
    """Test TimeWindow union operations."""

    def test_union_overlapping_relative_windows(self):
        """Test union of overlapping relative windows."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=14 * 60)
        w2 = TimeWindow(start_minutes=12 * 60, end_minutes=17 * 60)
        
        union = w1.union_with(w2)
        
        assert union.start_minutes == 9 * 60
        assert union.end_minutes == 17 * 60

    def test_union_non_overlapping_windows(self):
        """Test union of non-overlapping windows includes gaps."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=12 * 60)
        w2 = TimeWindow(start_minutes=14 * 60, end_minutes=17 * 60)
        
        union = w1.union_with(w2)
        
        assert union.start_minutes == 9 * 60
        assert union.end_minutes == 17 * 60
        # Note: Union includes the gap between 12-14

    def test_union_different_types_fails(self):
        """Test union of different window types fails."""
        absolute_window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        relative_window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        with pytest.raises(ValueError, match="Cannot union absolute and relative time windows"):
            absolute_window.union_with(relative_window)


class TestTimeWindowTransformations:
    """Test TimeWindow transformation methods."""

    def test_shift_absolute_window(self):
        """Test shifting absolute time window."""
        window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        
        # Shift by 2 hours (120 minutes)
        shifted = window.shift_by_minutes(120)
        
        assert shifted.start_time == datetime(2024, 1, 1, 11, 0)
        assert shifted.end_time == datetime(2024, 1, 1, 19, 0)
        assert shifted.duration_minutes() == window.duration_minutes()

    def test_shift_relative_window(self):
        """Test shifting relative time window."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        # Shift by 1 hour (60 minutes)
        shifted = window.shift_by_minutes(60)
        
        assert shifted.start_minutes == 10 * 60
        assert shifted.end_minutes == 18 * 60
        assert shifted.duration_minutes() == window.duration_minutes()

    def test_shift_negative_minutes(self):
        """Test shifting window backward in time."""
        window = TimeWindow(start_minutes=12 * 60, end_minutes=17 * 60)
        
        # Shift back 2 hours
        shifted = window.shift_by_minutes(-120)
        
        assert shifted.start_minutes == 10 * 60
        assert shifted.end_minutes == 15 * 60

    def test_extend_absolute_window(self):
        """Test extending absolute time window."""
        window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        
        # Extend by 2 hours
        extended = window.extend_by_minutes(120)
        
        assert extended.start_time == window.start_time  # Start unchanged
        assert extended.end_time == datetime(2024, 1, 1, 19, 0)
        assert extended.duration_minutes() == window.duration_minutes() + 120

    def test_extend_relative_window(self):
        """Test extending relative time window."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        # Extend by 1 hour
        extended = window.extend_by_minutes(60)
        
        assert extended.start_minutes == window.start_minutes  # Start unchanged
        assert extended.end_minutes == 18 * 60
        assert extended.duration_minutes() == window.duration_minutes() + 60

    def test_extend_negative_minutes(self):
        """Test shrinking window by extending with negative minutes."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        # Shrink by 2 hours
        shrunk = window.extend_by_minutes(-120)
        
        assert shrunk.start_minutes == window.start_minutes
        assert shrunk.end_minutes == 15 * 60
        assert shrunk.duration_minutes() == window.duration_minutes() - 120


class TestTimeWindowFormatting:
    """Test TimeWindow formatting methods."""

    def test_to_time_of_day_string(self):
        """Test converting relative window to time-of-day string."""
        window = TimeWindow(start_minutes=9 * 60 + 30, end_minutes=17 * 60 + 15)
        
        time_string = window.to_time_of_day_string()
        
        assert time_string == "09:30-17:15"

    def test_to_time_of_day_string_full_hours(self):
        """Test time-of-day string for full hour times."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        time_string = window.to_time_of_day_string()
        
        assert time_string == "09:00-17:00"

    def test_to_time_of_day_string_on_absolute_window_fails(self):
        """Test that time-of-day string fails on absolute window."""
        window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        
        with pytest.raises(ValueError, match="Cannot convert absolute time window to time-of-day"):
            window.to_time_of_day_string()


class TestTimeWindowEquality:
    """Test TimeWindow equality and hashing."""

    def test_equality_absolute_windows(self):
        """Test equality of absolute time windows."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        
        w1 = TimeWindow(start_time=start, end_time=end)
        w2 = TimeWindow(start_time=start, end_time=end)
        
        assert w1 == w2
        assert hash(w1) == hash(w2)

    def test_equality_relative_windows(self):
        """Test equality of relative time windows."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        assert w1 == w2
        assert hash(w1) == hash(w2)

    def test_inequality_different_times(self):
        """Test inequality of windows with different times."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=10 * 60, end_minutes=18 * 60)
        
        assert w1 != w2
        assert hash(w1) != hash(w2)

    def test_inequality_different_types(self):
        """Test inequality between absolute and relative windows."""
        absolute = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 17, 0)
        )
        relative = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        assert absolute != relative

    def test_equality_with_non_timewindow(self):
        """Test equality with non-TimeWindow objects."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        assert window != "not a window"
        assert window != 42
        assert window != None


class TestTimeWindowInSetsAndDicts:
    """Test TimeWindow usage in sets and dictionaries."""

    def test_timewindow_in_set(self):
        """Test using TimeWindow in sets."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=10 * 60, end_minutes=18 * 60)
        w3 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)  # Same as w1
        
        window_set = {w1, w2, w3}
        
        assert len(window_set) == 2  # w1 and w3 are equal

    def test_timewindow_as_dict_key(self):
        """Test using TimeWindow as dictionary key."""
        w1 = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        w2 = TimeWindow(start_minutes=10 * 60, end_minutes=18 * 60)
        
        window_dict = {w1: "morning shift", w2: "late shift"}
        
        assert window_dict[w1] == "morning shift"
        # Same window should access same value
        w1_copy = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        assert window_dict[w1_copy] == "morning shift"


class TestTimeWindowStringRepresentation:
    """Test TimeWindow string representation."""

    def test_str_absolute_window(self):
        """Test string representation of absolute window."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)
        
        str_repr = str(window)
        
        assert str(start) in str_repr
        assert str(end) in str_repr
        assert "to" in str_repr

    def test_str_relative_window(self):
        """Test string representation of relative window."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        str_repr = str(window)
        
        assert str_repr == "09:00-17:00"

    def test_repr_absolute_window(self):
        """Test repr of absolute window."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)
        
        repr_str = repr(window)
        
        assert "TimeWindow" in repr_str
        assert "start_time" in repr_str
        assert "end_time" in repr_str

    def test_repr_relative_window(self):
        """Test repr of relative window."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        repr_str = repr(window)
        
        assert "TimeWindow" in repr_str
        assert "start_minutes" in repr_str
        assert "end_minutes" in repr_str


class TestTimeWindowEdgeCases:
    """Test TimeWindow edge cases and boundary conditions."""

    def test_zero_duration_window(self):
        """Test window with zero duration."""
        window = TimeWindow(start_minutes=12 * 60, end_minutes=12 * 60)
        
        assert window.duration_minutes() == 0
        assert window.contains_relative_time(12 * 60)

    def test_midnight_crossing_relative_window(self):
        """Test relative window that would cross midnight."""
        # In current implementation, this is not handled specially
        # but should be valid for within-day scenarios
        window = TimeWindow(start_minutes=22 * 60, end_minutes=23 * 60 + 59)
        
        assert window.duration_minutes() == 119  # 1 hour 59 minutes

    def test_very_large_relative_window(self):
        """Test relative window with large minute values."""
        # Multi-day window represented in minutes
        start_minutes = 0
        end_minutes = 48 * 60  # 2 days
        
        window = TimeWindow(start_minutes=start_minutes, end_minutes=end_minutes)
        
        assert window.duration_minutes() == 48 * 60

    def test_shift_creates_negative_minutes(self):
        """Test shifting that creates negative minute values."""
        window = TimeWindow(start_minutes=2 * 60, end_minutes=4 * 60)  # 2-4 AM
        
        # Shift back 3 hours
        shifted = window.shift_by_minutes(-180)
        
        assert shifted.start_minutes == -60  # -1 hour (23:00 previous day conceptually)
        assert shifted.end_minutes == 60    # 1 AM

    def test_extend_creates_invalid_window(self):
        """Test extending that could create invalid window."""
        window = TimeWindow(start_minutes=10 * 60, end_minutes=12 * 60)
        
        # Extend by negative amount larger than duration
        extended = window.extend_by_minutes(-180)  # -3 hours
        
        # This creates an invalid window where end < start
        assert extended.start_minutes == 10 * 60
        assert extended.end_minutes == 9 * 60  # Invalid!
        
        # The implementation doesn't validate this - it's a known limitation


class TestTimeWindowImmutability:
    """Test that TimeWindow is properly immutable."""

    def test_immutable_after_creation(self):
        """Test that TimeWindow cannot be modified after creation."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        original_start = window.start_minutes
        
        # Operations should return new instances
        shifted = window.shift_by_minutes(60)
        
        assert window.start_minutes == original_start
        assert shifted.start_minutes != original_start
        assert window is not shifted

    def test_no_attribute_modification(self):
        """Test that internal attributes cannot be modified."""
        window = TimeWindow(start_minutes=9 * 60, end_minutes=17 * 60)
        
        # Should not be able to modify internal state
        with pytest.raises(AttributeError):
            window._start_minutes = 10 * 60


class TestTimeWindowBusinessScenarios:
    """Test TimeWindow in realistic business scenarios."""

    def test_work_shift_scenario(self):
        """Test modeling work shifts."""
        day_shift = TimeWindow.from_work_hours(7, 15)    # 7 AM - 3 PM
        night_shift = TimeWindow.from_work_hours(15, 23) # 3 PM - 11 PM
        
        assert not day_shift.overlaps_with(night_shift)  # Adjacent, not overlapping
        assert day_shift.duration_minutes() == 8 * 60
        assert night_shift.duration_minutes() == 8 * 60

    def test_break_time_scenario(self):
        """Test modeling break times within work periods."""
        work_day = TimeWindow.from_work_hours(9, 17)  # 9 AM - 5 PM
        lunch_break = TimeWindow(start_minutes=12 * 60, end_minutes=13 * 60)  # Noon - 1 PM
        
        # Lunch break should be within work day
        assert work_day.contains_relative_time(lunch_break.start_minutes)
        assert work_day.contains_relative_time(lunch_break.end_minutes)
        
        # Calculate working time (excluding lunch)
        total_work_minutes = work_day.duration_minutes() - lunch_break.duration_minutes()
        assert total_work_minutes == 7 * 60  # 7 hours

    def test_maintenance_window_scenario(self):
        """Test modeling maintenance windows."""
        production_window = TimeWindow.from_work_hours(8, 20)  # 8 AM - 8 PM
        maintenance_window = TimeWindow(start_minutes=20 * 60, end_minutes=22 * 60)  # 8 PM - 10 PM
        
        # Maintenance should not overlap with production
        assert not production_window.overlaps_with(maintenance_window)
        
        # Extended production window should overlap
        extended_production = production_window.extend_by_minutes(3 * 60)  # Until 11 PM
        assert extended_production.overlaps_with(maintenance_window)

    def test_scheduling_conflict_detection(self):
        """Test detecting scheduling conflicts."""
        task1_window = TimeWindow(start_minutes=9 * 60, end_minutes=11 * 60)    # 9-11 AM
        task2_window = TimeWindow(start_minutes=10 * 60, end_minutes=12 * 60)   # 10-12 PM
        task3_window = TimeWindow(start_minutes=11 * 60, end_minutes=13 * 60)   # 11-1 PM
        
        # Task 1 and 2 overlap (conflict)
        assert task1_window.overlaps_with(task2_window)
        
        # Task 2 and 3 overlap (conflict)
        assert task2_window.overlaps_with(task3_window)
        
        # Task 1 and 3 don't overlap (no conflict)
        assert not task1_window.overlaps_with(task3_window)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])