"""
Comprehensive Unit Tests for Duration Value Object

Tests all functionality, validation, and business rules for the Duration value object.
Covers precision, arithmetic operations, conversions, and edge cases.
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from app.domain.scheduling.value_objects.duration import Duration


class TestDurationCreation:
    """Test Duration creation with various parameters."""

    def test_create_duration_from_minutes(self):
        """Test creating duration from minutes."""
        duration = Duration(minutes=90)
        assert duration.minutes == Decimal("90")
        assert duration.hours == Decimal("1.5")

    def test_create_duration_from_hours(self):
        """Test creating duration from hours."""
        duration = Duration(hours=2)
        assert duration.hours == Decimal("2")
        assert duration.minutes == Decimal("120")

    def test_create_duration_from_days(self):
        """Test creating duration from days."""
        duration = Duration(days=1)
        assert duration.days == Decimal("1")
        assert duration.hours == Decimal("24")
        assert duration.minutes == Decimal("1440")

    def test_create_duration_from_seconds(self):
        """Test creating duration from seconds."""
        duration = Duration(seconds=120)
        assert duration.seconds == Decimal("120")
        assert duration.minutes == Decimal("2")

    def test_create_duration_from_milliseconds(self):
        """Test creating duration from milliseconds."""
        duration = Duration(milliseconds=60000)
        assert duration.milliseconds == Decimal("60000")
        assert duration.minutes == Decimal("1")

    def test_create_duration_combined_units(self):
        """Test creating duration from multiple units."""
        duration = Duration(days=1, hours=2, minutes=30, seconds=45)
        
        expected_minutes = (
            Decimal("1440") +  # 1 day
            Decimal("120") +   # 2 hours
            Decimal("30") +    # 30 minutes
            Decimal("0.75")    # 45 seconds
        )
        assert duration.minutes == expected_minutes

    def test_create_zero_duration(self):
        """Test creating zero duration."""
        duration = Duration()
        assert duration.is_zero()
        assert duration.minutes == Decimal("0")

    def test_create_duration_with_decimal_precision(self):
        """Test creating duration with decimal precision."""
        duration = Duration(minutes=Decimal("30.5"))
        assert duration.minutes == Decimal("30.5")
        assert duration.seconds == Decimal("1830")

    def test_create_negative_duration_raises_error(self):
        """Test that negative duration raises ValueError."""
        with pytest.raises(ValueError, match="Duration cannot be negative"):
            Duration(minutes=-10)

        with pytest.raises(ValueError, match="Duration cannot be negative"):
            Duration(hours=-1)

    def test_create_duration_from_float(self):
        """Test creating duration from float values."""
        duration = Duration(minutes=90.5)
        assert duration.minutes == Decimal("90.5")


class TestDurationFactoryMethods:
    """Test Duration factory methods."""

    def test_from_minutes_factory(self):
        """Test from_minutes factory method."""
        duration = Duration.from_minutes(120)
        assert duration.minutes == Decimal("120")
        assert duration.hours == Decimal("2")

    def test_from_hours_factory(self):
        """Test from_hours factory method."""
        duration = Duration.from_hours(2.5)
        assert duration.hours == Decimal("2.5")
        assert duration.minutes == Decimal("150")

    def test_from_days_factory(self):
        """Test from_days factory method."""
        duration = Duration.from_days(0.5)
        assert duration.days == Decimal("0.5")
        assert duration.hours == Decimal("12")

    def test_from_timedelta_factory(self):
        """Test from_timedelta factory method."""
        td = timedelta(hours=3, minutes=30)
        duration = Duration.from_timedelta(td)
        assert duration.hours == Decimal("3.5")
        assert duration.minutes == Decimal("210")

    def test_from_minutes_with_decimal(self):
        """Test from_minutes with Decimal input."""
        duration = Duration.from_minutes(Decimal("30.333"))
        assert duration.minutes == Decimal("30.333")

    def test_from_negative_values_raises_error(self):
        """Test that factory methods reject negative values."""
        with pytest.raises(ValueError, match="Duration cannot be negative"):
            Duration.from_minutes(-30)

        with pytest.raises(ValueError, match="Duration cannot be negative"):
            Duration.from_hours(-2)


class TestDurationProperties:
    """Test Duration property accessors."""

    def test_minutes_property(self):
        """Test minutes property with various values."""
        duration = Duration(minutes=90)
        assert duration.minutes == Decimal("90")

    def test_hours_property(self):
        """Test hours property conversion."""
        duration = Duration(minutes=150)
        assert duration.hours == Decimal("2.5")

    def test_days_property(self):
        """Test days property conversion."""
        duration = Duration(minutes=2880)  # 48 hours = 2 days
        assert duration.days == Decimal("2")

    def test_seconds_property(self):
        """Test seconds property conversion."""
        duration = Duration(minutes=2)
        assert duration.seconds == Decimal("120")

    def test_milliseconds_property(self):
        """Test milliseconds property conversion."""
        duration = Duration(minutes=1)
        assert duration.milliseconds == Decimal("60000")

    def test_property_precision(self):
        """Test that properties maintain decimal precision."""
        duration = Duration(minutes=Decimal("90.333"))
        assert duration.hours == Decimal("1.50555")
        assert duration.seconds == Decimal("5419.98")


class TestDurationConversions:
    """Test Duration conversion methods."""

    def test_to_timedelta(self):
        """Test conversion to Python timedelta."""
        duration = Duration(hours=2, minutes=30)
        td = duration.to_timedelta()
        
        assert isinstance(td, timedelta)
        assert td.total_seconds() == 9000.0  # 2.5 hours in seconds

    def test_to_minutes_int(self):
        """Test conversion to integer minutes."""
        duration = Duration(minutes=Decimal("90.7"))
        int_minutes = duration.to_minutes_int()
        
        assert int_minutes == 91  # Rounded to nearest integer

    def test_to_minutes_int_rounding(self):
        """Test integer conversion rounding behavior."""
        # Test rounding up
        duration_up = Duration(minutes=Decimal("90.6"))
        assert duration_up.to_minutes_int() == 91

        # Test rounding down
        duration_down = Duration(minutes=Decimal("90.4"))
        assert duration_down.to_minutes_int() == 90

        # Test exact half (should round to even)
        duration_half = Duration(minutes=Decimal("90.5"))
        assert duration_half.to_minutes_int() == 90  # Banker's rounding


class TestDurationChecks:
    """Test Duration boolean check methods."""

    def test_is_zero(self):
        """Test is_zero method."""
        zero_duration = Duration()
        assert zero_duration.is_zero()

        non_zero = Duration(minutes=1)
        assert not non_zero.is_zero()

        # Test very small duration (within precision threshold)
        tiny_duration = Duration.from_minutes(Decimal("1e-10"))
        assert tiny_duration.is_zero()

    def test_is_positive(self):
        """Test is_positive method."""
        positive = Duration(minutes=10)
        assert positive.is_positive()

        zero = Duration()
        assert not zero.is_zero()

        # Test very small positive duration
        tiny_positive = Duration.from_minutes(Decimal("1e-8"))
        assert tiny_positive.is_positive()

    def test_is_negative(self):
        """Test is_negative method."""
        # Note: Duration constructor doesn't allow negative values
        # But arithmetic operations can produce negative durations
        duration1 = Duration(minutes=10)
        duration2 = Duration(minutes=20)
        negative = duration1 - duration2
        
        assert negative.is_negative()
        assert not negative.is_positive()
        assert not negative.is_zero()


class TestDurationArithmetic:
    """Test Duration arithmetic operations."""

    def test_addition(self):
        """Test duration addition."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        result = d1 + d2
        
        assert result.minutes == Decimal("75")
        assert isinstance(result, Duration)

    def test_subtraction(self):
        """Test duration subtraction."""
        d1 = Duration(minutes=60)
        d2 = Duration(minutes=30)
        result = d1 - d2
        
        assert result.minutes == Decimal("30")

    def test_subtraction_negative_result(self):
        """Test subtraction producing negative duration."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=60)
        result = d1 - d2
        
        assert result.minutes == Decimal("-30")
        assert result.is_negative()

    def test_multiplication_by_number(self):
        """Test duration multiplication by numbers."""
        duration = Duration(minutes=30)
        
        # Integer multiplication
        result_int = duration * 2
        assert result_int.minutes == Decimal("60")

        # Float multiplication
        result_float = duration * 2.5
        assert result_float.minutes == Decimal("75")

        # Decimal multiplication
        result_decimal = duration * Decimal("1.5")
        assert result_decimal.minutes == Decimal("45")

    def test_right_multiplication(self):
        """Test right multiplication (number * duration)."""
        duration = Duration(minutes=30)
        result = 2 * duration
        
        assert result.minutes == Decimal("60")

    def test_division_by_number(self):
        """Test duration division by numbers."""
        duration = Duration(minutes=60)
        
        # Division by integer
        result_int = duration / 2
        assert result_int.minutes == Decimal("30")

        # Division by float
        result_float = duration / 2.5
        assert result_float.minutes == Decimal("24")

        # Division by Decimal
        result_decimal = duration / Decimal("3")
        assert result_decimal.minutes == Decimal("20")

    def test_division_by_duration(self):
        """Test duration division by another duration."""
        d1 = Duration(minutes=60)
        d2 = Duration(minutes=20)
        
        ratio = d1 / d2
        assert ratio == Decimal("3")  # Returns Decimal, not Duration

    def test_floor_division(self):
        """Test floor division."""
        duration = Duration(minutes=75)
        result = duration // 2
        
        assert result.minutes == Decimal("37")  # Floor of 37.5

    def test_modulo_operation(self):
        """Test modulo operation."""
        duration = Duration(minutes=75)
        
        # Modulo by number
        remainder = duration % 30
        assert remainder.minutes == Decimal("15")

        # Modulo by duration
        divisor = Duration(minutes=30)
        remainder_duration = duration % divisor
        assert remainder_duration.minutes == Decimal("15")

    def test_negation(self):
        """Test duration negation."""
        duration = Duration(minutes=30)
        negated = -duration
        
        assert negated.minutes == Decimal("-30")
        assert negated.is_negative()

    def test_positive_unary_operator(self):
        """Test unary positive operator."""
        duration = Duration(minutes=30)
        positive = +duration
        
        assert positive.minutes == Decimal("30")
        assert positive == duration

    def test_absolute_value(self):
        """Test absolute value method."""
        positive = Duration(minutes=30)
        negative = -positive
        
        assert positive.abs().minutes == Decimal("30")
        assert negative.abs().minutes == Decimal("30")

    def test_arithmetic_type_errors(self):
        """Test arithmetic operations with invalid types."""
        duration = Duration(minutes=30)
        
        with pytest.raises(TypeError):
            duration + "invalid"

        with pytest.raises(TypeError):
            duration - "invalid"

        with pytest.raises(TypeError):
            duration * "invalid"

        with pytest.raises(TypeError):
            duration / "invalid"

    def test_division_by_zero(self):
        """Test division by zero raises error."""
        duration = Duration(minutes=30)
        
        with pytest.raises(ZeroDivisionError):
            duration / 0

        zero_duration = Duration()
        with pytest.raises(ZeroDivisionError):
            duration / zero_duration


class TestDurationComparisons:
    """Test Duration comparison operations."""

    def test_equality(self):
        """Test duration equality."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=30)
        d3 = Duration(hours=0.5)  # Same as 30 minutes
        
        assert d1 == d2
        assert d1 == d3
        assert d2 == d3

    def test_equality_with_precision(self):
        """Test equality with decimal precision."""
        d1 = Duration.from_minutes(Decimal("30.0000000001"))
        d2 = Duration(minutes=30)
        
        # Should be equal within precision threshold
        assert d1 == d2

    def test_inequality(self):
        """Test duration inequality."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        
        assert d1 != d2
        assert not (d1 == d2)

    def test_less_than(self):
        """Test less than comparison."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        
        assert d1 < d2
        assert not (d2 < d1)

    def test_less_than_or_equal(self):
        """Test less than or equal comparison."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        d3 = Duration(minutes=30)
        
        assert d1 <= d2
        assert d1 <= d3
        assert not (d2 <= d1)

    def test_greater_than(self):
        """Test greater than comparison."""
        d1 = Duration(minutes=45)
        d2 = Duration(minutes=30)
        
        assert d1 > d2
        assert not (d2 > d1)

    def test_greater_than_or_equal(self):
        """Test greater than or equal comparison."""
        d1 = Duration(minutes=45)
        d2 = Duration(minutes=30)
        d3 = Duration(minutes=45)
        
        assert d1 >= d2
        assert d1 >= d3
        assert not (d2 >= d1)

    def test_comparison_type_errors(self):
        """Test comparison with invalid types."""
        duration = Duration(minutes=30)
        
        with pytest.raises(TypeError):
            duration < "invalid"

        with pytest.raises(TypeError):
            duration <= 30

        with pytest.raises(TypeError):
            duration > timedelta(minutes=30)


class TestDurationHashing:
    """Test Duration hashing for use in sets and dicts."""

    def test_equal_durations_same_hash(self):
        """Test that equal durations have same hash."""
        d1 = Duration(minutes=30)
        d2 = Duration(hours=0.5)
        
        assert d1 == d2
        assert hash(d1) == hash(d2)

    def test_different_durations_different_hash(self):
        """Test that different durations have different hashes."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        
        assert d1 != d2
        assert hash(d1) != hash(d2)

    def test_duration_in_set(self):
        """Test using Duration in sets."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        d3 = Duration(hours=0.5)  # Same as d1
        
        duration_set = {d1, d2, d3}
        assert len(duration_set) == 2  # d1 and d3 are equal

    def test_duration_as_dict_key(self):
        """Test using Duration as dictionary key."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        
        duration_dict = {d1: "thirty", d2: "forty-five"}
        assert duration_dict[d1] == "thirty"
        assert duration_dict[Duration(hours=0.5)] == "thirty"  # Same as d1


class TestDurationStringRepresentation:
    """Test Duration string representation methods."""

    def test_str_representation_minutes(self):
        """Test string representation for durations under 1 hour."""
        duration = Duration(minutes=45)
        assert "45.0m" in str(duration)

    def test_str_representation_hours(self):
        """Test string representation for durations in hours."""
        duration = Duration(hours=2)
        assert "2.0h" in str(duration)

    def test_str_representation_days(self):
        """Test string representation for durations in days."""
        duration = Duration(days=1)
        assert "1.0d" in str(duration)

    def test_repr_representation(self):
        """Test detailed representation."""
        duration = Duration(minutes=30)
        repr_str = repr(duration)
        
        assert "Duration" in repr_str
        assert "30" in repr_str

    def test_format_detailed(self):
        """Test detailed formatting with multiple units."""
        # Test combined units
        duration = Duration(days=1, hours=2, minutes=30)
        formatted = duration.format_detailed()
        
        assert "1d" in formatted
        assert "2h" in formatted
        assert "30m" in formatted

    def test_format_detailed_single_unit(self):
        """Test detailed formatting with single unit."""
        duration = Duration(minutes=45)
        formatted = duration.format_detailed()
        
        assert formatted == "45m"

    def test_format_detailed_zero(self):
        """Test detailed formatting of zero duration."""
        duration = Duration()
        formatted = duration.format_detailed()
        
        assert formatted == "0m"

    def test_format_detailed_negative(self):
        """Test detailed formatting of negative duration."""
        duration = Duration(minutes=30) - Duration(minutes=60)
        formatted = duration.format_detailed()
        
        assert formatted.startswith("-")
        assert "30m" in formatted


class TestDurationImmutability:
    """Test that Duration is properly immutable."""

    def test_immutable_after_creation(self):
        """Test that Duration cannot be modified after creation."""
        duration = Duration(minutes=30)
        original_minutes = duration.minutes
        
        # Arithmetic operations should return new instances
        new_duration = duration + Duration(minutes=15)
        
        assert duration.minutes == original_minutes
        assert new_duration.minutes == Decimal("45")
        assert duration is not new_duration

    def test_no_attribute_modification(self):
        """Test that internal attributes cannot be modified."""
        duration = Duration(minutes=30)
        
        # Should not be able to modify internal state
        with pytest.raises(AttributeError):
            duration._minutes = Decimal("60")


class TestDurationEdgeCases:
    """Test Duration edge cases and boundary conditions."""

    def test_very_large_duration(self):
        """Test handling of very large durations."""
        large_duration = Duration.from_days(10000)  # ~27 years
        assert large_duration.days == Decimal("10000")
        assert large_duration.is_positive()

    def test_very_small_duration(self):
        """Test handling of very small durations."""
        small_duration = Duration.from_minutes(Decimal("0.001"))
        assert small_duration.minutes == Decimal("0.001")
        assert small_duration.is_positive()

    def test_precision_boundary(self):
        """Test precision boundary conditions."""
        # Test at precision threshold
        threshold_duration = Duration.from_minutes(Decimal("1e-9"))
        assert threshold_duration.is_zero()

        # Test just above threshold
        above_threshold = Duration.from_minutes(Decimal("1e-8"))
        assert above_threshold.is_positive()

    def test_arithmetic_precision_preservation(self):
        """Test that arithmetic operations preserve precision."""
        d1 = Duration.from_minutes(Decimal("10.123"))
        d2 = Duration.from_minutes(Decimal("5.456"))
        
        result = d1 + d2
        assert result.minutes == Decimal("15.579")

        result = d1 - d2
        assert result.minutes == Decimal("4.667")

    def test_division_precision(self):
        """Test division precision with recurring decimals."""
        duration = Duration(minutes=10)
        result = duration / 3
        
        # Should maintain high precision
        assert result.minutes == Decimal("10") / Decimal("3")

    def test_chained_operations(self):
        """Test chaining multiple operations."""
        base = Duration(minutes=60)
        result = base * 2 + Duration(minutes=30) - Duration(minutes=15)
        
        assert result.minutes == Decimal("135")  # 120 + 30 - 15


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])