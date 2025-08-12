"""
Skill Requirement Value Object

Represents a requirement for a specific skill type and minimum level to perform a task.
"""


class SkillRequirement:
    """
    A skill requirement value object representing the minimum skill needed for a task.

    Specifies the type of skill required and the minimum level needed.
    """

    def __init__(
        self,
        skill_type: str,
        minimum_level: int,
        preferred_level: int | None = None,
        years_experience_required: int = 0,
        required_certifications: list[str] | None = None,
    ) -> None:
        """
        Initialize a SkillRequirement.

        Args:
            skill_type: Type of skill required (e.g., 'welding', 'machining')
            minimum_level: Minimum skill level required (1-3)
            preferred_level: Preferred skill level (optional)
            years_experience_required: Minimum years of experience required
            required_certifications: List of required certification names

        Raises:
            ValueError: If skill levels are not 1-3 or other invalid parameters
        """
        if not (1 <= minimum_level <= 3):
            raise ValueError("Minimum skill level must be between 1 and 3")

        if preferred_level is not None and not (1 <= preferred_level <= 3):
            raise ValueError("Preferred skill level must be between 1 and 3")

        if preferred_level is not None and preferred_level < minimum_level:
            raise ValueError("Preferred level cannot be lower than minimum level")

        if years_experience_required < 0:
            raise ValueError("Years of experience required cannot be negative")

        if not skill_type.strip():
            raise ValueError("Skill type cannot be empty")

        self._skill_type = skill_type.strip().lower()
        self._minimum_level = minimum_level
        self._preferred_level = preferred_level
        self._years_experience_required = years_experience_required
        self._required_certifications = required_certifications or []

    @classmethod
    def basic_requirement(cls, skill_type: str) -> "SkillRequirement":
        """
        Create a basic skill requirement.

        Args:
            skill_type: Type of skill required

        Returns:
            Basic skill requirement (level 1)
        """
        return cls(skill_type=skill_type, minimum_level=1)

    @classmethod
    def intermediate_requirement(
        cls, skill_type: str, years_experience: int = 0
    ) -> "SkillRequirement":
        """
        Create an intermediate skill requirement.

        Args:
            skill_type: Type of skill required
            years_experience: Minimum years of experience

        Returns:
            Intermediate skill requirement (level 2)
        """
        return cls(
            skill_type=skill_type,
            minimum_level=2,
            years_experience_required=years_experience,
        )

    @classmethod
    def advanced_requirement(
        cls, skill_type: str, years_experience: int = 2
    ) -> "SkillRequirement":
        """
        Create an advanced skill requirement.

        Args:
            skill_type: Type of skill required
            years_experience: Minimum years of experience

        Returns:
            Advanced skill requirement (level 3)
        """
        return cls(
            skill_type=skill_type,
            minimum_level=3,
            years_experience_required=years_experience,
        )

    @property
    def skill_type(self) -> str:
        """Get required skill type."""
        return self._skill_type

    @property
    def minimum_level(self) -> int:
        """Get minimum required skill level."""
        return self._minimum_level

    @property
    def preferred_level(self) -> int | None:
        """Get preferred skill level."""
        return self._preferred_level

    @property
    def years_experience_required(self) -> int:
        """Get minimum years of experience required."""
        return self._years_experience_required

    @property
    def required_certifications(self) -> list[str]:
        """Get required certifications."""
        return self._required_certifications.copy()

    @property
    def minimum_level_name(self) -> str:
        """Get human-readable minimum level name."""
        level_names = {1: "Basic", 2: "Intermediate", 3: "Advanced"}
        return level_names[self._minimum_level]

    @property
    def preferred_level_name(self) -> str | None:
        """Get human-readable preferred level name."""
        if self._preferred_level is None:
            return None
        level_names = {1: "Basic", 2: "Intermediate", 3: "Advanced"}
        return level_names[self._preferred_level]

    def is_satisfied_by_skill(self, skill) -> bool:
        """
        Check if a skill satisfies this requirement.

        Args:
            skill: Skill object to check

        Returns:
            True if skill meets all requirements
        """
        # Import here to avoid circular imports
        from .skill import Skill

        if not isinstance(skill, Skill):
            return False

        # Must be same skill type
        if skill.skill_type != self._skill_type:
            return False

        # Must meet minimum level
        if skill.level < self._minimum_level:
            return False

        # Must meet experience requirement
        if skill.years_experience < self._years_experience_required:
            return False

        # Must have all required certifications
        for cert in self._required_certifications:
            if not skill.has_certification(cert):
                return False

        return True

    def is_preferred_by_skill(self, skill) -> bool:
        """
        Check if a skill meets the preferred level (if specified).

        Args:
            skill: Skill object to check

        Returns:
            True if skill meets preferred requirements
        """
        if not self.is_satisfied_by_skill(skill):
            return False

        if self._preferred_level is None:
            return True

        # Import here to avoid circular imports
        from .skill import Skill

        if not isinstance(skill, Skill):
            return False

        return skill.level >= self._preferred_level

    def calculate_skill_match_score(self, skill) -> float:
        """
        Calculate how well a skill matches this requirement (0.0 to 1.0).

        Args:
            skill: Skill object to evaluate

        Returns:
            Match score where 1.0 is perfect match, 0.0 is no match
        """
        # Import here to avoid circular imports
        from .skill import Skill

        if not isinstance(skill, Skill):
            return 0.0

        if not self.is_satisfied_by_skill(skill):
            return 0.0

        score = 0.5  # Base score for meeting minimum requirements

        # Bonus for skill level above minimum
        if self._preferred_level:
            level_bonus = min(
                0.3,
                (skill.level - self._minimum_level)
                / (self._preferred_level - self._minimum_level)
                * 0.3,
            )
        else:
            level_bonus = min(0.3, (skill.level - self._minimum_level) * 0.15)
        score += level_bonus

        # Bonus for experience above required
        if skill.years_experience > self._years_experience_required:
            experience_bonus = min(
                0.15, (skill.years_experience - self._years_experience_required) * 0.02
            )
            score += experience_bonus

        # Bonus for additional certifications
        extra_certs = len(skill.certifications) - len(self._required_certifications)
        cert_bonus = min(0.05, extra_certs * 0.01)
        score += cert_bonus

        return min(1.0, score)

    def with_certification_requirement(self, certification: str) -> "SkillRequirement":
        """
        Add a certification requirement.

        Args:
            certification: Name of required certification

        Returns:
            New SkillRequirement with added certification
        """
        new_certs = self._required_certifications.copy()
        if certification not in new_certs:
            new_certs.append(certification)

        return SkillRequirement(
            skill_type=self._skill_type,
            minimum_level=self._minimum_level,
            preferred_level=self._preferred_level,
            years_experience_required=self._years_experience_required,
            required_certifications=new_certs,
        )

    def with_experience_requirement(self, years: int) -> "SkillRequirement":
        """
        Set experience requirement.

        Args:
            years: Minimum years of experience required

        Returns:
            New SkillRequirement with experience requirement
        """
        return SkillRequirement(
            skill_type=self._skill_type,
            minimum_level=self._minimum_level,
            preferred_level=self._preferred_level,
            years_experience_required=years,
            required_certifications=self._required_certifications,
        )

    def with_preferred_level(self, level: int) -> "SkillRequirement":
        """
        Set preferred skill level.

        Args:
            level: Preferred skill level (1-3)

        Returns:
            New SkillRequirement with preferred level
        """
        return SkillRequirement(
            skill_type=self._skill_type,
            minimum_level=self._minimum_level,
            preferred_level=level,
            years_experience_required=self._years_experience_required,
            required_certifications=self._required_certifications,
        )

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, SkillRequirement):
            return False
        return (
            self._skill_type == other._skill_type
            and self._minimum_level == other._minimum_level
            and self._preferred_level == other._preferred_level
            and self._years_experience_required == other._years_experience_required
            and set(self._required_certifications)
            == set(other._required_certifications)
        )

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(
            (
                self._skill_type,
                self._minimum_level,
                self._preferred_level,
                self._years_experience_required,
                tuple(sorted(self._required_certifications)),
            )
        )

    def __str__(self) -> str:
        """String representation."""
        parts = [f"{self._skill_type.title()} (Min: Level {self._minimum_level})"]

        if self._preferred_level:
            parts.append(f"Preferred: Level {self._preferred_level}")

        if self._years_experience_required > 0:
            parts.append(f"{self._years_experience_required}+ years exp")

        if self._required_certifications:
            parts.append(f"Certs: {', '.join(self._required_certifications)}")

        return ", ".join(parts)

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"SkillRequirement(skill_type='{self._skill_type}', "
            f"minimum_level={self._minimum_level}, "
            f"preferred_level={self._preferred_level}, "
            f"years_experience_required={self._years_experience_required}, "
            f"required_certifications={self._required_certifications})"
        )
