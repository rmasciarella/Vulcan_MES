"""
Comprehensive Unit Tests for Skill-Related Value Objects

Tests SkillProficiency, SkillRequirement, and related enums.
Covers validation, business logic, and skill matching scenarios.
"""

import pytest
from datetime import date, timedelta

from app.domain.scheduling.value_objects.skill_proficiency import (
    SkillProficiency,
    SkillRequirement
)
from app.domain.scheduling.value_objects.enums import SkillType, SkillLevel


class TestSkillRequirement:
    """Test SkillRequirement value object."""

    def test_create_valid_skill_requirement(self):
        """Test creating valid skill requirement."""
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        assert requirement.skill_type == SkillType.WELDING
        assert requirement.minimum_level == 2

    def test_create_skill_requirement_level_1(self):
        """Test creating skill requirement with level 1."""
        requirement = SkillRequirement(
            skill_type=SkillType.MACHINING,
            minimum_level=1
        )
        
        assert requirement.skill_type == SkillType.MACHINING
        assert requirement.minimum_level == 1

    def test_create_skill_requirement_level_3(self):
        """Test creating skill requirement with level 3."""
        requirement = SkillRequirement(
            skill_type=SkillType.INSPECTION,
            minimum_level=3
        )
        
        assert requirement.skill_type == SkillType.INSPECTION
        assert requirement.minimum_level == 3

    def test_create_skill_requirement_invalid_level_zero(self):
        """Test creating skill requirement with invalid level 0."""
        with pytest.raises(ValueError, match="Minimum level must be 1-3"):
            SkillRequirement(
                skill_type=SkillType.WELDING,
                minimum_level=0
            )

    def test_create_skill_requirement_invalid_level_four(self):
        """Test creating skill requirement with invalid level 4."""
        with pytest.raises(ValueError, match="Minimum level must be 1-3"):
            SkillRequirement(
                skill_type=SkillType.WELDING,
                minimum_level=4
            )

    def test_create_skill_requirement_invalid_level_negative(self):
        """Test creating skill requirement with negative level."""
        with pytest.raises(ValueError, match="Minimum level must be 1-3"):
            SkillRequirement(
                skill_type=SkillType.WELDING,
                minimum_level=-1
            )

    def test_skill_requirement_string_representation(self):
        """Test string representation of skill requirement."""
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        str_repr = str(requirement)
        assert "Welding" in str_repr
        assert "Level 2+" in str_repr

    def test_skill_requirement_repr(self):
        """Test detailed representation of skill requirement."""
        requirement = SkillRequirement(
            skill_type=SkillType.ASSEMBLY,
            minimum_level=1
        )
        
        repr_str = repr(requirement)
        assert "SkillRequirement" in repr_str
        assert "ASSEMBLY" in repr_str
        assert "minimum_level=1" in repr_str

    def test_skill_requirement_equality(self):
        """Test skill requirement equality."""
        req1 = SkillRequirement(skill_type=SkillType.WELDING, minimum_level=2)
        req2 = SkillRequirement(skill_type=SkillType.WELDING, minimum_level=2)
        req3 = SkillRequirement(skill_type=SkillType.WELDING, minimum_level=3)
        req4 = SkillRequirement(skill_type=SkillType.MACHINING, minimum_level=2)
        
        assert req1 == req2
        assert req1 != req3  # Different level
        assert req1 != req4  # Different skill type

    def test_skill_requirement_hashable(self):
        """Test skill requirement can be used in sets and dicts."""
        req1 = SkillRequirement(skill_type=SkillType.WELDING, minimum_level=2)
        req2 = SkillRequirement(skill_type=SkillType.WELDING, minimum_level=2)
        req3 = SkillRequirement(skill_type=SkillType.MACHINING, minimum_level=2)
        
        requirements = {req1, req2, req3}
        assert len(requirements) == 2  # req1 and req2 are equal


class TestSkillProficiency:
    """Test SkillProficiency value object."""

    def test_create_valid_skill_proficiency(self):
        """Test creating valid skill proficiency."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        assert proficiency.skill_type == SkillType.WELDING
        assert proficiency.level == 2
        assert proficiency.certified_date == certified_date
        assert proficiency.expiry_date == expiry_date

    def test_create_skill_proficiency_without_expiry(self):
        """Test creating skill proficiency without expiry date."""
        certified_date = date(2023, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.MACHINING,
            level=3,
            certified_date=certified_date
        )
        
        assert proficiency.skill_type == SkillType.MACHINING
        assert proficiency.level == 3
        assert proficiency.certified_date == certified_date
        assert proficiency.expiry_date is None

    def test_create_skill_proficiency_all_levels(self):
        """Test creating skill proficiency with all valid levels."""
        certified_date = date(2023, 1, 1)
        
        for level in [1, 2, 3]:
            proficiency = SkillProficiency(
                skill_type=SkillType.PROGRAMMING,
                level=level,
                certified_date=certified_date
            )
            assert proficiency.level == level

    def test_create_skill_proficiency_invalid_level_zero(self):
        """Test creating skill proficiency with invalid level 0."""
        with pytest.raises(ValueError, match="Skill level must be 1-3"):
            SkillProficiency(
                skill_type=SkillType.WELDING,
                level=0,
                certified_date=date(2023, 1, 1)
            )

    def test_create_skill_proficiency_invalid_level_four(self):
        """Test creating skill proficiency with invalid level 4."""
        with pytest.raises(ValueError, match="Skill level must be 1-3"):
            SkillProficiency(
                skill_type=SkillType.WELDING,
                level=4,
                certified_date=date(2023, 1, 1)
            )

    def test_create_skill_proficiency_expiry_before_certified(self):
        """Test creating skill proficiency with expiry before certified date."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2022, 12, 31)  # Before certified
        
        with pytest.raises(ValueError, match="Expiry date must be after certification date"):
            SkillProficiency(
                skill_type=SkillType.WELDING,
                level=2,
                certified_date=certified_date,
                expiry_date=expiry_date
            )

    def test_create_skill_proficiency_expiry_same_as_certified(self):
        """Test creating skill proficiency with expiry same as certified date."""
        same_date = date(2023, 1, 1)
        
        with pytest.raises(ValueError, match="Expiry date must be after certification date"):
            SkillProficiency(
                skill_type=SkillType.WELDING,
                level=2,
                certified_date=same_date,
                expiry_date=same_date
            )


class TestSkillProficiencyValidation:
    """Test SkillProficiency validation methods."""

    def test_is_valid_on_within_validity_period(self):
        """Test skill validity within the validity period."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        # Check date within validity period
        check_date = date(2024, 6, 15)
        assert proficiency.is_valid_on(check_date)

    def test_is_valid_on_at_certified_date(self):
        """Test skill validity at certification date."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        assert proficiency.is_valid_on(certified_date)

    def test_is_valid_on_before_certified_date(self):
        """Test skill validity before certification date."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        # Check date before certification
        check_date = date(2022, 12, 31)
        assert not proficiency.is_valid_on(check_date)

    def test_is_valid_on_at_expiry_date(self):
        """Test skill validity at expiry date (should be invalid)."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        assert not proficiency.is_valid_on(expiry_date)

    def test_is_valid_on_after_expiry_date(self):
        """Test skill validity after expiry date."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        # Check date after expiry
        check_date = date(2025, 1, 2)
        assert not proficiency.is_valid_on(check_date)

    def test_is_valid_on_no_expiry_date(self):
        """Test skill validity when no expiry date is set."""
        certified_date = date(2023, 1, 1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date
            # No expiry date
        )
        
        # Should be valid for any date after certification
        far_future = date(2030, 1, 1)
        assert proficiency.is_valid_on(far_future)

    def test_meets_requirement_exact_match(self):
        """Test skill meets requirement with exact skill type and level."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        check_date = date(2024, 6, 15)
        assert proficiency.meets_requirement(requirement, check_date)

    def test_meets_requirement_higher_level(self):
        """Test skill meets requirement with higher level than required."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        check_date = date(2024, 6, 15)
        assert proficiency.meets_requirement(requirement, check_date)

    def test_meets_requirement_lower_level(self):
        """Test skill doesn't meet requirement with lower level."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=1,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        check_date = date(2024, 6, 15)
        assert not proficiency.meets_requirement(requirement, check_date)

    def test_meets_requirement_wrong_skill_type(self):
        """Test skill doesn't meet requirement with wrong skill type."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        requirement = SkillRequirement(
            skill_type=SkillType.MACHINING,  # Different skill
            minimum_level=2
        )
        
        check_date = date(2024, 6, 15)
        assert not proficiency.meets_requirement(requirement, check_date)

    def test_meets_requirement_expired_skill(self):
        """Test expired skill doesn't meet requirement."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2024, 1, 1)
        )
        
        requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        # Check after expiry
        check_date = date(2024, 6, 15)
        assert not proficiency.meets_requirement(requirement, check_date)


class TestSkillProficiencyProperties:
    """Test SkillProficiency computed properties."""

    def test_is_expired_property_not_expired(self):
        """Test is_expired property for non-expired skill."""
        future_date = date.today() + timedelta(days=30)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1),
            expiry_date=future_date
        )
        
        assert not proficiency.is_expired

    def test_is_expired_property_expired(self):
        """Test is_expired property for expired skill."""
        past_date = date.today() - timedelta(days=1)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=past_date
        )
        
        assert proficiency.is_expired

    def test_is_expired_property_no_expiry(self):
        """Test is_expired property when no expiry date set."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1)
            # No expiry date
        )
        
        assert not proficiency.is_expired

    def test_days_until_expiry_future(self):
        """Test days_until_expiry for future expiry."""
        days_ahead = 45
        future_date = date.today() + timedelta(days=days_ahead)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1),
            expiry_date=future_date
        )
        
        # Should be approximately the same (might vary by 1 day due to timing)
        days_until = proficiency.days_until_expiry
        assert abs(days_until - days_ahead) <= 1

    def test_days_until_expiry_past(self):
        """Test days_until_expiry for past expiry (should be 0)."""
        past_date = date.today() - timedelta(days=10)
        
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=past_date
        )
        
        assert proficiency.days_until_expiry == 0

    def test_days_until_expiry_no_expiry(self):
        """Test days_until_expiry when no expiry date set."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1)
        )
        
        assert proficiency.days_until_expiry is None

    def test_level_name_property(self):
        """Test level_name property for all levels."""
        certified_date = date(2023, 1, 1)
        
        level_1 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=1,
            certified_date=certified_date
        )
        assert level_1.level_name == "Beginner"
        
        level_2 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date
        )
        assert level_2.level_name == "Intermediate"
        
        level_3 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=certified_date
        )
        assert level_3.level_name == "Expert"


class TestSkillProficiencyFactoryMethods:
    """Test SkillProficiency factory and transformation methods."""

    def test_create_factory_method_with_defaults(self):
        """Test create factory method with default certified date."""
        proficiency = SkillProficiency.create(
            skill_type=SkillType.WELDING,
            level=2
        )
        
        assert proficiency.skill_type == SkillType.WELDING
        assert proficiency.level == 2
        assert proficiency.certified_date == date.today()
        assert proficiency.expiry_date is None

    def test_create_factory_method_with_all_parameters(self):
        """Test create factory method with all parameters."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        proficiency = SkillProficiency.create(
            skill_type=SkillType.MACHINING,
            level=3,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        assert proficiency.skill_type == SkillType.MACHINING
        assert proficiency.level == 3
        assert proficiency.certified_date == certified_date
        assert proficiency.expiry_date == expiry_date

    def test_renew_method(self):
        """Test renewing skill proficiency."""
        original = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2024, 1, 1)
        )
        
        new_certified = date(2024, 1, 1)
        new_expiry = date(2026, 1, 1)
        
        renewed = original.renew(new_certified, new_expiry)
        
        # Original unchanged
        assert original.certified_date == date(2022, 1, 1)
        
        # Renewed has new dates but same skill/level
        assert renewed.skill_type == SkillType.WELDING
        assert renewed.level == 2
        assert renewed.certified_date == new_certified
        assert renewed.expiry_date == new_expiry

    def test_upgrade_method(self):
        """Test upgrading skill proficiency level."""
        original = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=1,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        upgraded = original.upgrade(2)
        
        # Original unchanged
        assert original.level == 1
        
        # Upgraded has new level and certified date
        assert upgraded.skill_type == SkillType.WELDING
        assert upgraded.level == 2
        assert upgraded.certified_date == date.today()
        assert upgraded.expiry_date == original.expiry_date

    def test_upgrade_method_with_custom_date(self):
        """Test upgrading skill proficiency with custom certified date."""
        original = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=1,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        upgrade_date = date(2023, 6, 15)
        upgraded = original.upgrade(3, upgrade_date)
        
        assert upgraded.level == 3
        assert upgraded.certified_date == upgrade_date

    def test_upgrade_method_invalid_level(self):
        """Test upgrading to same or lower level fails."""
        original = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2022, 1, 1)
        )
        
        # Same level
        with pytest.raises(ValueError, match="must be higher than current level"):
            original.upgrade(2)
        
        # Lower level
        with pytest.raises(ValueError, match="must be higher than current level"):
            original.upgrade(1)


class TestSkillProficiencyStringRepresentation:
    """Test SkillProficiency string representation."""

    def test_str_with_expiry(self):
        """Test string representation with expiry date."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        str_repr = str(proficiency)
        assert "Welding" in str_repr
        assert "Level 2" in str_repr
        assert "expires 2025-01-01" in str_repr

    def test_str_without_expiry(self):
        """Test string representation without expiry date."""
        proficiency = SkillProficiency(
            skill_type=SkillType.MACHINING,
            level=3,
            certified_date=date(2023, 1, 1)
        )
        
        str_repr = str(proficiency)
        assert "Machining" in str_repr
        assert "Level 3" in str_repr
        assert "expires" not in str_repr

    def test_repr_representation(self):
        """Test detailed representation."""
        proficiency = SkillProficiency(
            skill_type=SkillType.ASSEMBLY,
            level=1,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        repr_str = repr(proficiency)
        assert "SkillProficiency" in repr_str
        assert "ASSEMBLY" in repr_str
        assert "level=1" in repr_str
        assert "certified_date=datetime.date(2023, 1, 1)" in repr_str
        assert "expiry_date=datetime.date(2025, 1, 1)" in repr_str


class TestSkillProficiencyEquality:
    """Test SkillProficiency equality and hashing."""

    def test_equality_identical(self):
        """Test equality of identical skill proficiencies."""
        certified_date = date(2023, 1, 1)
        expiry_date = date(2025, 1, 1)
        
        prof1 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        prof2 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date,
            expiry_date=expiry_date
        )
        
        assert prof1 == prof2
        assert hash(prof1) == hash(prof2)

    def test_equality_different_levels(self):
        """Test inequality with different levels."""
        certified_date = date(2023, 1, 1)
        
        prof1 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date
        )
        
        prof2 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=certified_date
        )
        
        assert prof1 != prof2

    def test_equality_different_skill_types(self):
        """Test inequality with different skill types."""
        certified_date = date(2023, 1, 1)
        
        prof1 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=certified_date
        )
        
        prof2 = SkillProficiency(
            skill_type=SkillType.MACHINING,
            level=2,
            certified_date=certified_date
        )
        
        assert prof1 != prof2

    def test_equality_different_dates(self):
        """Test inequality with different dates."""
        prof1 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1)
        )
        
        prof2 = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 2, 1)
        )
        
        assert prof1 != prof2


class TestSkillProficiencyImmutability:
    """Test that SkillProficiency is properly immutable."""

    def test_immutable_after_creation(self):
        """Test that SkillProficiency cannot be modified after creation."""
        proficiency = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1)
        )
        
        # Should not be able to modify attributes
        with pytest.raises(AttributeError):
            proficiency.level = 3

        with pytest.raises(AttributeError):
            proficiency.skill_type = SkillType.MACHINING

    def test_methods_return_new_instances(self):
        """Test that transformation methods return new instances."""
        original = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=1,
            certified_date=date(2022, 1, 1)
        )
        
        # Upgrade returns new instance
        upgraded = original.upgrade(2)
        assert original is not upgraded
        assert original.level == 1  # Original unchanged
        assert upgraded.level == 2
        
        # Renew returns new instance
        renewed = original.renew(date(2024, 1, 1))
        assert original is not renewed
        assert original.certified_date == date(2022, 1, 1)  # Original unchanged


class TestSkillBusinessScenarios:
    """Test skill-related business scenarios."""

    def test_operator_qualification_check(self):
        """Test checking if operator is qualified for a task."""
        # Operator has intermediate welding skill
        operator_skill = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2023, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        # Task requires basic welding
        basic_requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=1
        )
        
        # Task requires intermediate welding
        intermediate_requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=2
        )
        
        # Task requires expert welding
        expert_requirement = SkillRequirement(
            skill_type=SkillType.WELDING,
            minimum_level=3
        )
        
        check_date = date(2024, 6, 15)
        
        # Should qualify for basic and intermediate, not expert
        assert operator_skill.meets_requirement(basic_requirement, check_date)
        assert operator_skill.meets_requirement(intermediate_requirement, check_date)
        assert not operator_skill.meets_requirement(expert_requirement, check_date)

    def test_skill_expiry_warning_scenario(self):
        """Test scenario for warning about expiring skills."""
        # Skill expiring in 15 days
        near_expiry = date.today() + timedelta(days=15)
        expiring_skill = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=near_expiry
        )
        
        # Skill expiring in 60 days
        far_expiry = date.today() + timedelta(days=60)
        not_expiring_soon = SkillProficiency(
            skill_type=SkillType.MACHINING,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=far_expiry
        )
        
        # Check days until expiry for warnings
        assert expiring_skill.days_until_expiry <= 30  # Warning threshold
        assert not_expiring_soon.days_until_expiry > 30  # No warning needed

    def test_skill_renewal_scenario(self):
        """Test skill renewal business scenario."""
        # Original skill
        original_skill = SkillProficiency(
            skill_type=SkillType.INSPECTION,
            level=2,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2024, 1, 1)
        )
        
        # Check if expired
        check_date = date(2024, 6, 15)
        assert not original_skill.is_valid_on(check_date)
        
        # Renew the skill
        renewed_skill = original_skill.renew(
            new_certified_date=date(2024, 1, 1),
            new_expiry_date=date(2026, 1, 1)
        )
        
        # Renewed skill should be valid
        assert renewed_skill.is_valid_on(check_date)
        assert renewed_skill.skill_type == original_skill.skill_type
        assert renewed_skill.level == original_skill.level

    def test_skill_upgrade_scenario(self):
        """Test skill upgrade business scenario."""
        # Operator starts with basic skill
        basic_skill = SkillProficiency(
            skill_type=SkillType.PROGRAMMING,
            level=1,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        # Task requiring intermediate skill
        requirement = SkillRequirement(
            skill_type=SkillType.PROGRAMMING,
            minimum_level=2
        )
        
        check_date = date(2023, 6, 15)
        
        # Initially doesn't qualify
        assert not basic_skill.meets_requirement(requirement, check_date)
        
        # After training, upgrade skill
        upgraded_skill = basic_skill.upgrade(
            new_level=2,
            new_certified_date=date(2023, 5, 1)
        )
        
        # Now qualifies for the task
        assert upgraded_skill.meets_requirement(requirement, check_date)

    def test_multi_skill_operator_scenario(self):
        """Test operator with multiple skills."""
        # Operator skills
        welding_skill = SkillProficiency(
            skill_type=SkillType.WELDING,
            level=3,
            certified_date=date(2022, 1, 1),
            expiry_date=date(2025, 1, 1)
        )
        
        machining_skill = SkillProficiency(
            skill_type=SkillType.MACHINING,
            level=2,
            certified_date=date(2022, 6, 1),
            expiry_date=date(2025, 6, 1)
        )
        
        # Task requirements
        welding_req = SkillRequirement(SkillType.WELDING, minimum_level=2)
        machining_req = SkillRequirement(SkillType.MACHINING, minimum_level=1)
        assembly_req = SkillRequirement(SkillType.ASSEMBLY, minimum_level=1)
        
        check_date = date(2024, 1, 1)
        
        # Check which requirements the operator can meet
        assert welding_skill.meets_requirement(welding_req, check_date)
        assert machining_skill.meets_requirement(machining_req, check_date)
        # Doesn't have assembly skill
        assert not welding_skill.meets_requirement(assembly_req, check_date)
        assert not machining_skill.meets_requirement(assembly_req, check_date)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])