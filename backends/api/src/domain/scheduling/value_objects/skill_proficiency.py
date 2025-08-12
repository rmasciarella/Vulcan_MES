"""
Skill Proficiency and Skill Requirement Value Objects

Represents an operator's proficiency in a specific skill and skill requirements
for operations, matching DOMAIN.md specification exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .enums import SkillType


@dataclass(frozen=True)
class SkillRequirement:
    """
    Represents a skill requirement for operating a machine.
    Immutable value object matching DOMAIN.md specification.
    """

    skill_type: SkillType
    minimum_level: int

    def __post_init__(self):
        """Validate skill requirement constraints."""
        if not 1 <= self.minimum_level <= 3:
            raise ValueError(f"Minimum level must be 1-3, got {self.minimum_level}")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.skill_type} (Level {self.minimum_level}+)"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"SkillRequirement(skill_type={self.skill_type!r}, minimum_level={self.minimum_level})"


@dataclass(frozen=True)
class SkillProficiency:
    """
    Represents an operator's proficiency in a specific skill.
    Immutable value object matching DOMAIN.md specification exactly.
    """

    skill_type: SkillType
    level: int  # 1-3 scale
    certified_date: date
    expiry_date: date | None = None

    def __post_init__(self):
        """Validate skill proficiency constraints."""
        if not 1 <= self.level <= 3:
            raise ValueError(f"Skill level must be 1-3, got {self.level}")
        if self.expiry_date and self.expiry_date <= self.certified_date:
            raise ValueError("Expiry date must be after certification date")

    def is_valid_on(self, check_date: date) -> bool:
        """
        Check if skill is valid on given date.

        Args:
            check_date: Date to check validity

        Returns:
            True if skill is valid on the given date
        """
        if check_date < self.certified_date:
            return False
        if self.expiry_date and check_date >= self.expiry_date:
            return False
        return True

    def meets_requirement(
        self, requirement: SkillRequirement, check_date: date
    ) -> bool:
        """
        Check if this proficiency meets a skill requirement.

        Args:
            requirement: Skill requirement to check against
            check_date: Date to check validity

        Returns:
            True if this proficiency meets the requirement
        """
        return (
            self.skill_type == requirement.skill_type
            and self.level >= requirement.minimum_level
            and self.is_valid_on(check_date)
        )

    @property
    def is_expired(self) -> bool:
        """Check if skill proficiency is expired."""
        if not self.expiry_date:
            return False
        return date.today() >= self.expiry_date

    @property
    def days_until_expiry(self) -> int | None:
        """Get days until expiry, or None if no expiry date."""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - date.today()
        return max(0, delta.days)

    @property
    def level_name(self) -> str:
        """Get human-readable level name."""
        level_names = {1: "Beginner", 2: "Intermediate", 3: "Expert"}
        return level_names[self.level]

    @classmethod
    def create(
        cls,
        skill_type: SkillType,
        level: int,
        certified_date: date | None = None,
        expiry_date: date | None = None,
    ) -> SkillProficiency:
        """
        Factory method to create a SkillProficiency.

        Args:
            skill_type: Type of skill
            level: Skill level (1-3)
            certified_date: Date skill was certified (defaults to today)
            expiry_date: Optional expiry date

        Returns:
            New SkillProficiency instance
        """
        return cls(
            skill_type=skill_type,
            level=level,
            certified_date=certified_date or date.today(),
            expiry_date=expiry_date,
        )

    def renew(
        self, new_certified_date: date, new_expiry_date: date | None = None
    ) -> SkillProficiency:
        """
        Create a renewed version of this skill proficiency.

        Args:
            new_certified_date: New certification date
            new_expiry_date: Optional new expiry date

        Returns:
            New SkillProficiency instance with updated dates
        """
        return SkillProficiency(
            skill_type=self.skill_type,
            level=self.level,
            certified_date=new_certified_date,
            expiry_date=new_expiry_date,
        )

    def upgrade(
        self, new_level: int, new_certified_date: date | None = None
    ) -> SkillProficiency:
        """
        Create an upgraded version of this skill proficiency.

        Args:
            new_level: New skill level (must be higher)
            new_certified_date: New certification date (defaults to today)

        Returns:
            New SkillProficiency instance with upgraded level

        Raises:
            ValueError: If new level is not higher than current level
        """
        if new_level <= self.level:
            raise ValueError(
                f"New level {new_level} must be higher than current level {self.level}"
            )

        return SkillProficiency(
            skill_type=self.skill_type,
            level=new_level,
            certified_date=new_certified_date or date.today(),
            expiry_date=self.expiry_date,
        )

    def __str__(self) -> str:
        """String representation."""
        expiry_str = f" (expires {self.expiry_date})" if self.expiry_date else ""
        return f"{self.skill_type} Level {self.level}{expiry_str}"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"SkillProficiency(skill_type={self.skill_type!r}, level={self.level}, "
            f"certified_date={self.certified_date!r}, expiry_date={self.expiry_date!r})"
        )
