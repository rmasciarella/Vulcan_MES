"""Resource capability value objects.

Represents the capabilities of resources (machines and operators) in a common
structure to support matching and allocation logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .skill_proficiency import SkillRequirement, SkillType


@dataclass(frozen=True)
class ResourceCapability:
    """Common capability description for resources.

    - For machines: represent supported operations, capacity, and required skill
      types to operate.
    - For operators: represent possessed skills and proficiency levels.
    """

    skills: Mapping[SkillType, int] = field(default_factory=dict)
    max_parallel_tasks: int = 1
    notes: str | None = None

    def meets(self, requirement: SkillRequirement) -> bool:
        level = self.skills.get(requirement.skill_type, 0)
        return level >= requirement.minimum_level
