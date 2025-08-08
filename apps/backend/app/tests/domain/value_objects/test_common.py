"""
Comprehensive Unit Tests for Common Value Objects

Tests all value objects in the common module including Duration, TimeWindow,
WorkingHours, Skill, OperatorSkill, EfficiencyFactor, Address, ContactInfo,
Money, and Quantity.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest

from app.domain.scheduling.value_objects.common import (
    Address,
    ContactInfo,
    Duration,
    EfficiencyFactor,
    Money,
    OperatorSkill,
    Quantity,
    Skill,
    TimeWindow,
    WorkingHours,
)
from app.domain.scheduling.value_objects.enums import SkillLevel


class TestDuration:
    """Test Duration value object."""

    def test_create_valid_duration(self):
        """Test creating valid durations."""
        duration = Duration(minutes=120)
        assert duration.minutes == 120
        assert duration.hours == 2.0
        assert duration.timedelta == timedelta(minutes=120)

    def test_duration_zero_minutes(self):
        """Test duration with zero minutes."""
        duration = Duration(minutes=0)
        assert duration.minutes == 0
        assert duration.hours == 0.0

    def test_duration_negative_minutes_fails(self):
        """Test that negative minutes fail validation."""
        with pytest.raises(ValueError, match="cannot be negative"):
            Duration(minutes=-10)

    def test_duration_add(self):
        """Test adding durations together."""
        d1 = Duration(minutes=30)
        d2 = Duration(minutes=45)
        result = d1.add(d2)
        assert result.minutes == 75

    def test_duration_multiply(self):
        """Test multiplying duration by factor."""
        duration = Duration(minutes=60)
        result = duration.multiply(2.5)
        assert result.minutes == 150

    def test_duration_string_representation(self):
        """Test string representation of durations."""
        assert str(Duration(minutes=30)) == "30min"
        assert str(Duration(minutes=60)) == "1h"
        assert str(Duration(minutes=90)) == "1h 30min"
        assert str(Duration(minutes=120)) == "2h"

    def test_duration_immutability(self):
        """Test that duration is immutable."""
        d1 = Duration(minutes=60)
        d2 = d1.add(Duration(minutes=30))
        assert d1.minutes == 60  # Original unchanged
        assert d2.minutes == 90  # New instance


class TestTimeWindow:
    """Test TimeWindow value object."""

    def test_create_valid_time_window(self):
        """Test creating valid time window."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)

        assert window.start_time == start
        assert window.end_time == end
        assert window.duration.minutes == 480  # 8 hours

    def test_time_window_invalid_end_before_start(self):
        """Test that end time before start time fails."""
        start = datetime(2024, 1, 1, 17, 0)
        end = datetime(2024, 1, 1, 9, 0)  # End before start

        with pytest.raises(ValueError, match="End time must be after start time"):
            TimeWindow(start_time=start, end_time=end)

    def test_time_window_overlaps_with(self):
        """Test overlap detection between time windows."""
        # Non-overlapping windows
        w1 = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0), end_time=datetime(2024, 1, 1, 12, 0)
        )
        w2 = TimeWindow(
            start_time=datetime(2024, 1, 1, 13, 0), end_time=datetime(2024, 1, 1, 17, 0)
        )
        assert not w1.overlaps_with(w2)
        assert not w2.overlaps_with(w1)

        # Overlapping windows
        w3 = TimeWindow(
            start_time=datetime(2024, 1, 1, 11, 0), end_time=datetime(2024, 1, 1, 14, 0)
        )
        assert w1.overlaps_with(w3)
        assert w2.overlaps_with(w3)

    def test_time_window_contains(self):
        """Test if time window contains a point in time."""
        window = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0), end_time=datetime(2024, 1, 1, 17, 0)
        )

        assert window.contains(datetime(2024, 1, 1, 12, 0))  # Inside
        assert window.contains(datetime(2024, 1, 1, 9, 0))  # Start boundary
        assert window.contains(datetime(2024, 1, 1, 17, 0))  # End boundary
        assert not window.contains(datetime(2024, 1, 1, 8, 0))  # Before
        assert not window.contains(datetime(2024, 1, 1, 18, 0))  # After

    def test_time_window_is_adjacent_to(self):
        """Test adjacency detection between time windows."""
        w1 = TimeWindow(
            start_time=datetime(2024, 1, 1, 9, 0), end_time=datetime(2024, 1, 1, 12, 0)
        )
        w2 = TimeWindow(
            start_time=datetime(2024, 1, 1, 12, 0),  # Adjacent
            end_time=datetime(2024, 1, 1, 15, 0),
        )
        w3 = TimeWindow(
            start_time=datetime(2024, 1, 1, 13, 0),  # Not adjacent
            end_time=datetime(2024, 1, 1, 16, 0),
        )

        assert w1.is_adjacent_to(w2)
        assert w2.is_adjacent_to(w1)
        assert not w1.is_adjacent_to(w3)


class TestWorkingHours:
    """Test WorkingHours value object."""

    def test_create_default_working_hours(self):
        """Test creating working hours with defaults."""
        hours = WorkingHours()
        assert hours.start_time == time(7, 0)
        assert hours.end_time == time(16, 0)
        assert hours.lunch_start == time(12, 0)
        assert hours.lunch_duration.minutes == 30

    def test_create_custom_working_hours(self):
        """Test creating custom working hours."""
        hours = WorkingHours(
            start_time=time(8, 30),
            end_time=time(17, 30),
            lunch_start=time(12, 30),
            lunch_duration=Duration(minutes=60),
        )
        assert hours.start_time == time(8, 30)
        assert hours.end_time == time(17, 30)
        assert hours.lunch_start == time(12, 30)
        assert hours.lunch_duration.minutes == 60

    def test_working_hours_invalid_end_before_start(self):
        """Test that end time before start time fails."""
        with pytest.raises(ValueError, match="End time must be after start time"):
            WorkingHours(
                start_time=time(17, 0),
                end_time=time(8, 0),  # End before start
            )

    def test_working_hours_total_hours(self):
        """Test total working hours calculation."""
        hours = WorkingHours(
            start_time=time(8, 0),  # 8:00
            end_time=time(17, 0),  # 17:00 (9 hours)
            lunch_duration=Duration(minutes=60),  # 1 hour
        )
        # Total: 9 hours - 1 hour lunch = 8 hours = 480 minutes
        assert hours.total_hours.minutes == 480

    def test_is_within_working_hours(self):
        """Test checking if time is within working hours."""
        hours = WorkingHours(start_time=time(8, 0), end_time=time(17, 0))

        assert hours.is_within_working_hours(time(12, 0))  # During work
        assert hours.is_within_working_hours(time(8, 0))  # Start boundary
        assert hours.is_within_working_hours(time(17, 0))  # End boundary
        assert not hours.is_within_working_hours(time(7, 0))  # Before
        assert not hours.is_within_working_hours(time(18, 0))  # After

    def test_is_lunch_time(self):
        """Test checking if time is during lunch."""
        hours = WorkingHours(
            lunch_start=time(12, 0),
            lunch_duration=Duration(minutes=30),  # 12:00-12:30
        )

        assert hours.is_lunch_time(time(12, 15))  # During lunch
        assert hours.is_lunch_time(time(12, 0))  # Start boundary
        assert hours.is_lunch_time(time(12, 30))  # End boundary
        assert not hours.is_lunch_time(time(11, 59))  # Before
        assert not hours.is_lunch_time(time(12, 31))  # After


class TestSkill:
    """Test Skill value object."""

    def test_create_valid_skill(self):
        """Test creating valid skill."""
        skill = Skill(
            skill_code="WELD_001",
            skill_name="Basic Welding",
            skill_category="Welding",
            description="Basic welding operations",
        )
        assert skill.skill_code == "WELD_001"
        assert skill.skill_name == "Basic Welding"
        assert skill.skill_category == "Welding"
        assert skill.description == "Basic welding operations"

    def test_create_skill_minimal_fields(self):
        """Test creating skill with minimal fields."""
        skill = Skill(skill_code="MACH_001", skill_name="Machine Operation")
        assert skill.skill_code == "MACH_001"
        assert skill.skill_name == "Machine Operation"
        assert skill.skill_category is None
        assert skill.description is None

    def test_skill_code_validation(self):
        """Test skill code validation and normalization."""
        skill = Skill(
            skill_code="weld_basic",  # Lowercase
            skill_name="Welding",
        )
        assert skill.skill_code == "WELD_BASIC"  # Should be uppercase

    def test_skill_code_invalid_characters(self):
        """Test that invalid skill codes are rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            Skill(
                skill_code="WELD-001",  # Invalid hyphen
                skill_name="Welding",
            )

    def test_skill_empty_fields_validation(self):
        """Test that empty required fields are rejected."""
        with pytest.raises(ValueError):
            Skill(skill_code="", skill_name="Valid Name")

        with pytest.raises(ValueError):
            Skill(skill_code="VALID_CODE", skill_name="")

    def test_skill_field_length_validation(self):
        """Test field length validation."""
        # Too long skill code
        with pytest.raises(ValueError):
            Skill(
                skill_code="x" * 21,  # Too long
                skill_name="Valid Name",
            )

        # Too long skill name
        with pytest.raises(ValueError):
            Skill(
                skill_code="VALID",
                skill_name="x" * 101,  # Too long
            )


class TestOperatorSkill:
    """Test OperatorSkill value object."""

    def test_create_valid_operator_skill(self):
        """Test creating valid operator skill."""
        skill = Skill(skill_code="WELD_001", skill_name="Basic Welding")
        certified_date = datetime(2024, 1, 1)
        expiry_date = datetime(2025, 1, 1)

        operator_skill = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.PROFICIENT,
            certified_date=certified_date,
            expiry_date=expiry_date,
        )

        assert operator_skill.skill == skill
        assert operator_skill.proficiency_level == SkillLevel.PROFICIENT
        assert operator_skill.certified_date == certified_date
        assert operator_skill.expiry_date == expiry_date

    def test_operator_skill_no_expiry(self):
        """Test operator skill without expiry date."""
        skill = Skill(skill_code="MACH_001", skill_name="Machine Operation")

        operator_skill = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.EXPERT,
            certified_date=datetime(2024, 1, 1),
        )

        assert operator_skill.expiry_date is None
        assert operator_skill.is_valid  # No expiry = always valid

    def test_operator_skill_invalid_expiry_before_certified(self):
        """Test that expiry before certified date fails."""
        skill = Skill(skill_code="TEST", skill_name="Test Skill")

        with pytest.raises(
            ValueError, match="Expiry date must be after certified date"
        ):
            OperatorSkill(
                skill=skill,
                proficiency_level=SkillLevel.BASIC,
                certified_date=datetime(2024, 1, 1),
                expiry_date=datetime(2023, 12, 31),  # Before certified
            )

    def test_operator_skill_is_valid(self):
        """Test skill validity checking."""
        skill = Skill(skill_code="TEST", skill_name="Test Skill")

        # Valid skill (future expiry)
        valid_skill = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.PROFICIENT,
            expiry_date=datetime.utcnow() + timedelta(days=30),
        )
        assert valid_skill.is_valid

        # Expired skill
        expired_skill = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.PROFICIENT,
            expiry_date=datetime.utcnow() - timedelta(days=1),
        )
        assert not expired_skill.is_valid

    def test_operator_skill_is_expiring_soon(self):
        """Test expiring soon detection."""
        skill = Skill(skill_code="TEST", skill_name="Test Skill")

        # Expires in 15 days (soon)
        expiring_soon = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.PROFICIENT,
            expiry_date=datetime.utcnow() + timedelta(days=15),
        )
        assert expiring_soon.is_expiring_soon

        # Expires in 45 days (not soon)
        not_expiring_soon = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.PROFICIENT,
            expiry_date=datetime.utcnow() + timedelta(days=45),
        )
        assert not not_expiring_soon.is_expiring_soon

        # No expiry date
        no_expiry = OperatorSkill(skill=skill, proficiency_level=SkillLevel.PROFICIENT)
        assert not no_expiry.is_expiring_soon

    def test_operator_skill_meets_requirement(self):
        """Test if skill meets proficiency requirements."""
        skill = Skill(skill_code="TEST", skill_name="Test Skill")

        expert_skill = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.EXPERT,
            expiry_date=datetime.utcnow() + timedelta(days=365),
        )

        # Expert should meet all requirements
        assert expert_skill.meets_requirement(SkillLevel.BASIC)
        assert expert_skill.meets_requirement(SkillLevel.PROFICIENT)
        assert expert_skill.meets_requirement(SkillLevel.EXPERT)

        # Expired skill shouldn't meet requirements
        expired_expert = OperatorSkill(
            skill=skill,
            proficiency_level=SkillLevel.EXPERT,
            expiry_date=datetime.utcnow() - timedelta(days=1),
        )
        assert not expired_expert.meets_requirement(SkillLevel.BASIC)


class TestEfficiencyFactor:
    """Test EfficiencyFactor value object."""

    def test_create_valid_efficiency_factor(self):
        """Test creating valid efficiency factor."""
        factor = EfficiencyFactor(factor=Decimal("1.2"))
        assert factor.factor == Decimal("1.2")
        assert factor.percentage == 120.0
        assert factor.is_efficient
        assert not factor.is_below_standard

    def test_efficiency_factor_boundary_values(self):
        """Test efficiency factor boundary values."""
        # Minimum allowed
        min_factor = EfficiencyFactor(factor=Decimal("0.1"))
        assert min_factor.factor == Decimal("0.1")
        assert min_factor.percentage == 10.0
        assert min_factor.is_below_standard

        # Maximum allowed
        max_factor = EfficiencyFactor(factor=Decimal("2.0"))
        assert max_factor.factor == Decimal("2.0")
        assert max_factor.percentage == 200.0
        assert max_factor.is_efficient

    def test_efficiency_factor_invalid_values(self):
        """Test that invalid efficiency factors are rejected."""
        # Too low
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            EfficiencyFactor(factor=Decimal("0.05"))

        # Too high
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            EfficiencyFactor(factor=Decimal("2.5"))

    def test_efficiency_factor_apply_to_duration(self):
        """Test applying efficiency factor to duration."""
        factor = EfficiencyFactor(factor=Decimal("1.5"))  # 150% efficiency
        duration = Duration(minutes=120)  # 2 hours

        adjusted = factor.apply_to_duration(duration)
        assert adjusted.minutes == 80  # 120 / 1.5 = 80 minutes

    def test_efficiency_factor_standard_checks(self):
        """Test efficiency standard classification."""
        standard = EfficiencyFactor(factor=Decimal("1.0"))
        assert not standard.is_efficient
        assert not standard.is_below_standard

        efficient = EfficiencyFactor(factor=Decimal("1.1"))
        assert efficient.is_efficient
        assert not efficient.is_below_standard

        below_standard = EfficiencyFactor(factor=Decimal("0.8"))
        assert not below_standard.is_efficient
        assert below_standard.is_below_standard


class TestAddress:
    """Test Address value object."""

    def test_create_valid_address(self):
        """Test creating valid address."""
        address = Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            postal_code="12345",
            country="USA",
        )

        assert address.street == "123 Main St"
        assert address.city == "Anytown"
        assert address.state == "CA"
        assert address.postal_code == "12345"
        assert address.country == "USA"

    def test_create_address_default_country(self):
        """Test creating address with default country."""
        address = Address(
            street="456 Oak Ave", city="Springfield", state="IL", postal_code="62701"
        )

        assert address.country == "USA"  # Default value


class TestContactInfo:
    """Test ContactInfo value object."""

    def test_create_valid_contact_info(self):
        """Test creating valid contact info."""
        contact = ContactInfo(email="test@example.com", phone="555-123-4567")

        assert contact.email == "test@example.com"
        assert contact.phone == "555-123-4567"

    def test_create_contact_info_optional_fields(self):
        """Test creating contact info with optional fields."""
        contact_email_only = ContactInfo(email="test@example.com")
        assert contact_email_only.email == "test@example.com"
        assert contact_email_only.phone is None

        contact_phone_only = ContactInfo(phone="555-123-4567")
        assert contact_phone_only.email is None
        assert contact_phone_only.phone == "555-123-4567"

    def test_contact_info_invalid_email(self):
        """Test that invalid email is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            ContactInfo(email="not-an-email")


class TestMoney:
    """Test Money value object."""

    def test_create_valid_money(self):
        """Test creating valid money amount."""
        money = Money(amount=Decimal("150.75"), currency="USD")
        assert money.amount == Decimal("150.75")
        assert money.currency == "USD"

    def test_create_money_default_currency(self):
        """Test creating money with default currency."""
        money = Money(amount=Decimal("100.00"))
        assert money.currency == "USD"

    def test_money_negative_amount_fails(self):
        """Test that negative amounts are rejected."""
        with pytest.raises(ValueError):
            Money(amount=Decimal("-10.00"))

    def test_money_add_same_currency(self):
        """Test adding money with same currency."""
        m1 = Money(amount=Decimal("100.00"), currency="USD")
        m2 = Money(amount=Decimal("50.00"), currency="USD")
        result = m1.add(m2)

        assert result.amount == Decimal("150.00")
        assert result.currency == "USD"

    def test_money_add_different_currency_fails(self):
        """Test that adding different currencies fails."""
        m1 = Money(amount=Decimal("100.00"), currency="USD")
        m2 = Money(amount=Decimal("50.00"), currency="EUR")

        with pytest.raises(ValueError, match="Cannot add different currencies"):
            m1.add(m2)

    def test_money_multiply(self):
        """Test multiplying money by factor."""
        money = Money(amount=Decimal("100.00"), currency="USD")
        result = money.multiply(Decimal("2.5"))

        assert result.amount == Decimal("250.00")
        assert result.currency == "USD"

    def test_money_currency_validation(self):
        """Test currency code validation."""
        # Valid 3-letter currency
        money = Money(amount=Decimal("100.00"), currency="EUR")
        assert money.currency == "EUR"

        # Invalid length
        with pytest.raises(ValueError):
            Money(amount=Decimal("100.00"), currency="US")  # Too short

        with pytest.raises(ValueError):
            Money(amount=Decimal("100.00"), currency="USDX")  # Too long


class TestQuantity:
    """Test Quantity value object."""

    def test_create_valid_quantity(self):
        """Test creating valid quantity."""
        qty = Quantity(value=25, unit="pieces")
        assert qty.value == 25
        assert qty.unit == "pieces"

    def test_create_quantity_default_unit(self):
        """Test creating quantity with default unit."""
        qty = Quantity(value=10)
        assert qty.unit == "pieces"

    def test_quantity_zero_value_fails(self):
        """Test that zero quantity is rejected."""
        with pytest.raises(ValueError, match="must be positive"):
            Quantity(value=0)

    def test_quantity_negative_value_fails(self):
        """Test that negative quantity is rejected."""
        with pytest.raises(ValueError, match="must be positive"):
            Quantity(value=-5)

    def test_quantity_custom_units(self):
        """Test quantity with custom units."""
        units = ["kg", "liters", "meters", "hours"]

        for unit in units:
            qty = Quantity(value=100, unit=unit)
            assert qty.unit == unit
            assert qty.value == 100


class TestValueObjectImmutability:
    """Test that all value objects are properly immutable."""

    def test_duration_immutability(self):
        """Test Duration is immutable after creation."""
        duration = Duration(minutes=60)
        original_minutes = duration.minutes

        # Operations should return new instances
        new_duration = duration.add(Duration(minutes=30))
        assert duration.minutes == original_minutes
        assert new_duration.minutes != original_minutes

    def test_time_window_immutability(self):
        """Test TimeWindow is immutable after creation."""
        start = datetime(2024, 1, 1, 9, 0)
        end = datetime(2024, 1, 1, 17, 0)
        window = TimeWindow(start_time=start, end_time=end)

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            window.start_time = datetime(2024, 1, 1, 10, 0)

    def test_money_immutability(self):
        """Test Money is immutable after creation."""
        money = Money(amount=Decimal("100.00"))
        original_amount = money.amount

        # Operations should return new instances
        new_money = money.multiply(Decimal("2.0"))
        assert money.amount == original_amount
        assert new_money.amount != original_amount


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
