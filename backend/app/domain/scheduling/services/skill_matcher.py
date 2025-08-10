"""
SkillMatcher Domain Service

Domain service for matching operators to machines based on skills.
Matches DOMAIN.md specification exactly.
"""

from datetime import date

from ..entities.machine import Machine
from ..entities.operator import Operator
from ..value_objects.skill_proficiency import SkillRequirement


class SkillMatcher:
    """
    Domain service for matching operators to machines based on skills.
    Matches DOMAIN.md specification exactly.
    """

    @staticmethod
    def find_qualified_operators(
        machine: Machine, operators: list[Operator], check_date: date | None = None
    ) -> list[Operator]:
        """
        Find all operators qualified to operate a machine.
        Matches DOMAIN.md specification exactly.

        Args:
            machine: Machine that needs operation
            operators: List of available operators
            check_date: Date to check skill validity (defaults to today)

        Returns:
            List of operators qualified to operate the machine
        """
        check_date = check_date or date.today()
        qualified = []

        for operator in operators:
            if operator.can_operate_machine(machine, check_date):
                qualified.append(operator)

        return qualified

    @staticmethod
    def find_best_operator(
        machine: Machine,
        operators: list[Operator],
        check_date: date | None = None,
        prefer_available: bool = True,
    ) -> Operator | None:
        """
        Find best operator for machine based on skill level and availability.
        Returns operator with highest skill level, preferring available operators.
        Matches DOMAIN.md specification exactly.

        Args:
            machine: Machine that needs operation
            operators: List of available operators
            check_date: Date to check skill validity (defaults to today)
            prefer_available: Whether to prefer available operators

        Returns:
            Best qualified operator, or None if none qualified
        """
        qualified = SkillMatcher.find_qualified_operators(
            machine, operators, check_date
        )

        if not qualified:
            return None

        # Sort by availability and skill level
        def score_operator(op: Operator) -> tuple[int, int]:
            availability_score = 1 if op.is_available else 0

            # Calculate max skill level for required skills
            max_level = 0
            for req in machine.skill_requirements:
                for skill in op.skills:
                    if skill.skill_type == req.skill_type and skill.is_valid_on(
                        check_date or date.today()
                    ):
                        max_level = max(max_level, skill.level)

            return (availability_score if prefer_available else 0, max_level)

        qualified.sort(key=score_operator, reverse=True)
        return qualified[0]

    @staticmethod
    def find_operators_by_skill(
        skill_requirement: SkillRequirement,
        operators: list[Operator],
        check_date: date | None = None,
    ) -> list[Operator]:
        """
        Find operators that meet a specific skill requirement.

        Args:
            skill_requirement: Skill requirement to match
            operators: List of available operators
            check_date: Date to check skill validity (defaults to today)

        Returns:
            List of operators that meet the skill requirement
        """
        check_date = check_date or date.today()
        matching_operators = []

        for operator in operators:
            if operator.has_skill(skill_requirement, check_date):
                matching_operators.append(operator)

        return matching_operators

    @staticmethod
    def rank_operators_by_skills(
        operators: list[Operator],
        skill_requirements: list[SkillRequirement],
        check_date: date | None = None,
    ) -> list[tuple[Operator, float]]:
        """
        Rank operators by their skill match score for multiple requirements.

        Args:
            operators: List of operators to rank
            skill_requirements: List of skill requirements to match
            check_date: Date to check skill validity (defaults to today)

        Returns:
            List of (operator, score) tuples sorted by score (highest first)
        """
        check_date = check_date or date.today()
        operator_scores = []

        for operator in operators:
            score = SkillMatcher._calculate_skill_match_score(
                operator, skill_requirements, check_date
            )
            operator_scores.append((operator, score))

        # Sort by score (highest first)
        operator_scores.sort(key=lambda x: x[1], reverse=True)
        return operator_scores

    @staticmethod
    def _calculate_skill_match_score(
        operator: Operator, skill_requirements: list[SkillRequirement], check_date: date
    ) -> float:
        """
        Calculate skill match score for an operator against requirements.

        Args:
            operator: Operator to evaluate
            skill_requirements: List of skill requirements
            check_date: Date to check skill validity

        Returns:
            Skill match score (0.0 to 1.0)
        """
        if not skill_requirements:
            return 1.0

        total_score = 0.0
        met_requirements = 0

        for requirement in skill_requirements:
            best_skill_level = 0

            for skill in operator.skills:
                if skill.skill_type == requirement.skill_type and skill.is_valid_on(
                    check_date
                ):
                    best_skill_level = max(best_skill_level, skill.level)

            if best_skill_level >= requirement.minimum_level:
                met_requirements += 1
                # Score based on how much the skill level exceeds requirement
                excess_level = best_skill_level - requirement.minimum_level
                requirement_score = 0.5 + (excess_level * 0.25)  # 0.5-1.0 range
                total_score += min(1.0, requirement_score)

        if met_requirements == 0:
            return 0.0

        # Average score across all requirements, with penalty for unmet requirements
        coverage_ratio = met_requirements / len(skill_requirements)
        average_score = total_score / len(skill_requirements)

        return average_score * coverage_ratio

    @staticmethod
    def get_skill_gap_analysis(
        operator: Operator,
        skill_requirements: list[SkillRequirement],
        check_date: date | None = None,
    ) -> list[tuple[SkillRequirement, int | None]]:
        """
        Analyze skill gaps for an operator against requirements.

        Args:
            operator: Operator to analyze
            skill_requirements: List of skill requirements
            check_date: Date to check skill validity (defaults to today)

        Returns:
            List of (requirement, current_level) tuples where current_level is None if missing
        """
        check_date = check_date or date.today()
        gaps = []

        for requirement in skill_requirements:
            current_level = None

            for skill in operator.skills:
                if skill.skill_type == requirement.skill_type and skill.is_valid_on(
                    check_date
                ):
                    current_level = max(current_level or 0, skill.level)

            if current_level is None or current_level < requirement.minimum_level:
                gaps.append((requirement, current_level))

        return gaps

    @staticmethod
    def suggest_training_priorities(
        operators: list[Operator],
        skill_requirements: list[SkillRequirement],
        check_date: date | None = None,
    ) -> list[tuple[SkillRequirement, int]]:
        """
        Suggest training priorities based on operator skill gaps.

        Args:
            operators: List of operators to analyze
            skill_requirements: List of skill requirements
            check_date: Date to check skill validity (defaults to today)

        Returns:
            List of (skill_requirement, gap_count) tuples sorted by priority
        """
        check_date = check_date or date.today()
        requirement_gaps = {}

        for requirement in skill_requirements:
            gap_count = 0

            for operator in operators:
                operator_gaps = SkillMatcher.get_skill_gap_analysis(
                    operator, [requirement], check_date
                )
                if operator_gaps:  # Has gap for this requirement
                    gap_count += 1

            requirement_gaps[requirement] = gap_count

        # Sort by gap count (highest first - most urgent training need)
        sorted_priorities = sorted(
            requirement_gaps.items(), key=lambda x: x[1], reverse=True
        )

        return sorted_priorities
