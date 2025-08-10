"""
RoleRequirement Value Object

Represents operator role requirements for a task, including the skill type,
minimum proficiency, headcount, and attendance type (setup-only vs full-duration).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AttendanceRequirement(str, Enum):
    """Specifies how long an operator presence is required for a role."""

    FULL_DURATION = "full_duration"
    SETUP_ONLY = "setup_only"


@dataclass(frozen=True)
class RoleRequirement:
    """
    Role requirement for operators assigned to a task.

    Attributes:
        skill_type: Domain skill identifier (e.g., "welding", "machining").
        minimum_level: Minimum proficiency required (1=basic, 2=intermediate, 3=advanced).
        count: Number of operators required for this role.
        attendance: Whether operators are needed for the full task duration or only setup.
    """

    skill_type: str
    minimum_level: int
    count: int
    attendance: AttendanceRequirement = AttendanceRequirement.FULL_DURATION

    def __post_init__(self) -> None:
        if not self.skill_type or not self.skill_type.strip():
            raise ValueError("RoleRequirement.skill_type cannot be empty")
        if not (1 <= self.minimum_level <= 3):
            raise ValueError("RoleRequirement.minimum_level must be between 1 and 3")
        if self.count <= 0:
            raise ValueError("RoleRequirement.count must be a positive integer")
