"""
Skill Value Object

Represents an operator's skill in a specific area with level and experience.
"""


class Skill:
    """
    A skill value object representing an operator's capability in a specific area.

    Skills have a type (e.g., 'welding', 'machining'), a level (1-3),
    and optional years of experience.
    """

    def __init__(
        self,
        skill_type: str,
        level: int,
        years_experience: int = 0,
        certifications: list[str] | None = None,
    ) -> None:
        """
        Initialize a Skill.

        Args:
            skill_type: Type of skill (e.g., 'welding', 'machining')
            level: Skill level (1=basic, 2=intermediate, 3=advanced)
            years_experience: Years of experience with this skill
            certifications: List of certification names

        Raises:
            ValueError: If skill level is not 1-3 or years_experience is negative
        """
        if not (1 <= level <= 3):
            raise ValueError("Skill level must be between 1 and 3")

        if years_experience < 0:
            raise ValueError("Years of experience cannot be negative")

        if not skill_type.strip():
            raise ValueError("Skill type cannot be empty")

        self._skill_type = skill_type.strip().lower()
        self._level = level
        self._years_experience = years_experience
        self._certifications = certifications or []

    @classmethod
    def basic_skill(cls, skill_type: str) -> "Skill":
        """
        Create a basic level skill.

        Args:
            skill_type: Type of skill

        Returns:
            Basic skill (level 1)
        """
        return cls(skill_type=skill_type, level=1)

    @classmethod
    def intermediate_skill(cls, skill_type: str, years_experience: int = 2) -> "Skill":
        """
        Create an intermediate level skill.

        Args:
            skill_type: Type of skill
            years_experience: Years of experience

        Returns:
            Intermediate skill (level 2)
        """
        return cls(skill_type=skill_type, level=2, years_experience=years_experience)

    @classmethod
    def advanced_skill(cls, skill_type: str, years_experience: int = 5) -> "Skill":
        """
        Create an advanced level skill.

        Args:
            skill_type: Type of skill
            years_experience: Years of experience

        Returns:
            Advanced skill (level 3)
        """
        return cls(skill_type=skill_type, level=3, years_experience=years_experience)

    @property
    def skill_type(self) -> str:
        """Get skill type."""
        return self._skill_type

    @property
    def level(self) -> int:
        """Get skill level (1-3)."""
        return self._level

    @property
    def years_experience(self) -> int:
        """Get years of experience."""
        return self._years_experience

    @property
    def certifications(self) -> list[str]:
        """Get certifications."""
        return self._certifications.copy()

    @property
    def is_basic(self) -> bool:
        """Check if this is a basic skill."""
        return self._level == 1

    @property
    def is_intermediate(self) -> bool:
        """Check if this is an intermediate skill."""
        return self._level == 2

    @property
    def is_advanced(self) -> bool:
        """Check if this is an advanced skill."""
        return self._level == 3

    @property
    def level_name(self) -> str:
        """Get human-readable level name."""
        level_names = {1: "Basic", 2: "Intermediate", 3: "Advanced"}
        return level_names[self._level]

    def meets_requirement(self, required_level: int) -> bool:
        """
        Check if this skill meets a required level.

        Args:
            required_level: Minimum required skill level

        Returns:
            True if skill level meets or exceeds requirement
        """
        return self._level >= required_level

    def has_certification(self, certification_name: str) -> bool:
        """
        Check if skill has a specific certification.

        Args:
            certification_name: Name of certification to check

        Returns:
            True if certification is present
        """
        return certification_name in self._certifications

    def add_certification(self, certification_name: str) -> "Skill":
        """
        Add a certification to this skill.

        Args:
            certification_name: Name of certification to add

        Returns:
            New Skill instance with added certification
        """
        new_certifications = self._certifications.copy()
        if certification_name not in new_certifications:
            new_certifications.append(certification_name)

        return Skill(
            skill_type=self._skill_type,
            level=self._level,
            years_experience=self._years_experience,
            certifications=new_certifications,
        )

    def upgrade_to_level(
        self, new_level: int, additional_experience: int = 0
    ) -> "Skill":
        """
        Upgrade skill to a higher level.

        Args:
            new_level: New skill level (must be higher than current)
            additional_experience: Additional years of experience to add

        Returns:
            New Skill instance with upgraded level

        Raises:
            ValueError: If new level is not higher than current level
        """
        if new_level <= self._level:
            raise ValueError(
                f"New level {new_level} must be higher than current level {self._level}"
            )

        if not (1 <= new_level <= 3):
            raise ValueError("New level must be between 1 and 3")

        return Skill(
            skill_type=self._skill_type,
            level=new_level,
            years_experience=self._years_experience + additional_experience,
            certifications=self._certifications,
        )

    def calculate_effectiveness(self) -> float:
        """
        Calculate overall skill effectiveness (0.0 to 1.0).

        Combines skill level and experience into a single effectiveness score.

        Returns:
            Effectiveness score between 0.0 and 1.0
        """
        # Base effectiveness from skill level
        base_effectiveness = self._level / 3.0

        # Bonus from experience (up to 20% bonus)
        experience_bonus = min(0.2, self._years_experience * 0.02)

        # Bonus from certifications (5% per certification, up to 15%)
        certification_bonus = min(0.15, len(self._certifications) * 0.05)

        return min(1.0, base_effectiveness + experience_bonus + certification_bonus)

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Skill):
            return False
        return (
            self._skill_type == other._skill_type
            and self._level == other._level
            and self._years_experience == other._years_experience
            and set(self._certifications) == set(other._certifications)
        )

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(
            (
                self._skill_type,
                self._level,
                self._years_experience,
                tuple(sorted(self._certifications)),
            )
        )

    def __str__(self) -> str:
        """String representation."""
        exp_str = (
            f", {self._years_experience} years" if self._years_experience > 0 else ""
        )
        cert_str = (
            f", {len(self._certifications)} certs" if self._certifications else ""
        )
        return f"{self._skill_type.title()} (Level {self._level}{exp_str}{cert_str})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"Skill(skill_type='{self._skill_type}', level={self._level}, "
            f"years_experience={self._years_experience}, "
            f"certifications={self._certifications})"
        )

    def __lt__(self, other: "Skill") -> bool:
        """Compare skills for sorting."""
        if not isinstance(other, Skill):
            raise TypeError(f"Cannot compare Skill with {type(other)}")

        # First compare by skill type
        if self._skill_type != other._skill_type:
            return self._skill_type < other._skill_type

        # Then by level (higher level comes first)
        if self._level != other._level:
            return self._level > other._level

        # Finally by experience (more experience comes first)
        return self._years_experience > other._years_experience
