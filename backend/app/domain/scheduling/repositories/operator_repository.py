"""
Operator Repository Interface

Defines the contract for operator data access operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.operator import Operator


class OperatorRepository(ABC):
    """
    Abstract repository interface for Operator entities.

    Defines the contract that infrastructure layer must implement
    for operator data persistence and retrieval operations.
    """

    @abstractmethod
    async def save(self, operator: Operator) -> Operator:
        """
        Save an operator to the repository.

        Args:
            operator: Operator entity to save

        Returns:
            Saved operator entity

        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, operator_id: UUID) -> Operator | None:
        """
        Retrieve an operator by its ID.

        Args:
            operator_id: Unique operator identifier

        Returns:
            Operator entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Operator]:
        """
        Retrieve all operators.

        Returns:
            List of all operator entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_employee_number(self, employee_number: str) -> Operator | None:
        """
        Retrieve an operator by employee number.

        Args:
            employee_number: Employee number to search for

        Returns:
            Operator entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_status(self, status: str) -> list[Operator]:
        """
        Retrieve operators with specific status.

        Args:
            status: Operator status to filter by

        Returns:
            List of operators with the status

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_available_operators(self) -> list[Operator]:
        """
        Retrieve all available operators.

        Returns:
            List of available operator entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_with_skill(
        self, skill_type: str, minimum_level: int = 1
    ) -> list[Operator]:
        """
        Retrieve operators who have a specific skill at minimum level.

        Args:
            skill_type: Type of skill required
            minimum_level: Minimum skill level required

        Returns:
            List of operators with the skill

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_available_on_date(self, date: datetime) -> list[Operator]:
        """
        Retrieve operators available on a specific date.

        Args:
            date: Date to check availability

        Returns:
            List of operators available on the date

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_by_skill_level(
        self, skill_type: str, skill_level: int
    ) -> list[Operator]:
        """
        Retrieve operators with specific skill level.

        Args:
            skill_type: Type of skill
            skill_level: Exact skill level to match

        Returns:
            List of operators with the skill level

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_by_cost_range(
        self, min_cost: float, max_cost: float
    ) -> list[Operator]:
        """
        Retrieve operators within a cost range.

        Args:
            min_cost: Minimum hourly cost
            max_cost: Maximum hourly cost

        Returns:
            List of operators within the cost range

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_assigned_to_task(self, task_id: UUID) -> list[Operator]:
        """
        Retrieve operators currently assigned to a specific task.

        Args:
            task_id: Task identifier

        Returns:
            List of operators assigned to the task

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_operators_by_highest_skill_level(
        self, minimum_level: int
    ) -> list[Operator]:
        """
        Retrieve operators whose highest skill level meets minimum.

        Args:
            minimum_level: Minimum highest skill level required

        Returns:
            List of operators meeting the criteria

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def find_best_operators_for_task(
        self,
        skill_requirements: list[dict],
        exclude_operator_ids: list[UUID] | None = None,
        limit: int = 10,
    ) -> list[Operator]:
        """
        Find the best operators for a task based on skill requirements.

        Args:
            skill_requirements: List of skill requirement dicts
            exclude_operator_ids: Operator IDs to exclude from search
            limit: Maximum number of operators to return

        Returns:
            List of best matching operators, sorted by match quality

        Raises:
            RepositoryError: If search operation fails
        """
        pass

    @abstractmethod
    async def update(self, operator: Operator) -> Operator:
        """
        Update an existing operator.

        Args:
            operator: Operator entity with updated values

        Returns:
            Updated operator entity

        Raises:
            RepositoryError: If update operation fails
            OperatorNotFoundError: If operator doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, operator_id: UUID) -> bool:
        """
        Delete an operator by ID.

        Args:
            operator_id: Operator identifier

        Returns:
            True if operator was deleted, False if not found

        Raises:
            RepositoryError: If delete operation fails
        """
        pass

    @abstractmethod
    async def exists(self, operator_id: UUID) -> bool:
        """
        Check if an operator exists.

        Args:
            operator_id: Operator identifier

        Returns:
            True if operator exists

        Raises:
            RepositoryError: If check operation fails
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of operators.

        Returns:
            Total operator count

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: str) -> int:
        """
        Count operators by status.

        Args:
            status: Operator status to count

        Returns:
            Operator count for the status

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_with_skill(self, skill_type: str, minimum_level: int = 1) -> int:
        """
        Count operators with a specific skill.

        Args:
            skill_type: Type of skill
            minimum_level: Minimum skill level

        Returns:
            Count of operators with the skill

        Raises:
            RepositoryError: If count operation fails
        """
        pass
