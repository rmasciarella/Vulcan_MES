"""
Machine Repository Interface

Defines the contract for machine data access operations.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.machine import Machine
from ..value_objects.enums import MachineStatus


class MachineRepository(ABC):
    """
    Abstract repository interface for Machine entities.

    Defines the contract that infrastructure layer must implement
    for machine data persistence and retrieval operations.
    """

    @abstractmethod
    async def save(self, machine: Machine) -> Machine:
        """
        Save a machine to the repository.

        Args:
            machine: Machine entity to save

        Returns:
            Saved machine entity

        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, machine_id: UUID) -> Machine | None:
        """
        Retrieve a machine by its ID.

        Args:
            machine_id: Unique machine identifier

        Returns:
            Machine entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Machine]:
        """
        Retrieve all machines.

        Returns:
            List of all machine entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_status(self, status: MachineStatus) -> list[Machine]:
        """
        Retrieve machines with specific status.

        Args:
            status: Machine status to filter by

        Returns:
            List of machines with the status

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    # Method removed: MachineType is not defined in the domain model

    @abstractmethod
    async def get_available_machines(self) -> list[Machine]:
        """
        Retrieve all available machines.

        Returns:
            List of available machine entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_machines_for_task_type(self, task_type: str) -> list[Machine]:
        """
        Retrieve machines that can perform a specific task type.

        Args:
            task_type: Type of task the machine must support

        Returns:
            List of machines capable of the task type

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_attended_machines(self) -> list[Machine]:
        """
        Retrieve machines that require operator attendance.

        Returns:
            List of attended machines

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_unattended_machines(self) -> list[Machine]:
        """
        Retrieve machines that can operate without constant operator presence.

        Returns:
            List of unattended machines

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_machines_with_current_task(self) -> list[Machine]:
        """
        Retrieve machines currently processing a task.

        Returns:
            List of busy machines

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_machines_needing_maintenance(self) -> list[Machine]:
        """
        Retrieve machines that need maintenance.

        Returns:
            List of machines needing maintenance

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_machines_by_utilization_threshold(
        self, threshold: float
    ) -> list[Machine]:
        """
        Retrieve machines with utilization above threshold.

        Args:
            threshold: Utilization threshold (0.0 to 1.0)

        Returns:
            List of highly utilized machines

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def find_best_machine_for_task(
        self,
        task_type: str,
        required_capabilities: list[str] | None = None,
        exclude_machine_ids: list[UUID] | None = None,
    ) -> Machine | None:
        """
        Find the best available machine for a specific task.

        Args:
            task_type: Type of task to perform
            required_capabilities: Additional capabilities needed
            exclude_machine_ids: Machine IDs to exclude from search

        Returns:
            Best matching available machine or None if none found

        Raises:
            RepositoryError: If search operation fails
        """
        pass

    @abstractmethod
    async def get_machines_with_scheduled_tasks(self) -> list[Machine]:
        """
        Retrieve machines that have tasks scheduled.

        Returns:
            List of machines with scheduled tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_machine_utilization_stats(self, machine_id: UUID) -> dict | None:
        """
        Get utilization statistics for a specific machine.

        Args:
            machine_id: Machine identifier

        Returns:
            Dictionary with utilization stats or None if machine not found

        Raises:
            RepositoryError: If stats retrieval fails
        """
        pass

    @abstractmethod
    async def update(self, machine: Machine) -> Machine:
        """
        Update an existing machine.

        Args:
            machine: Machine entity with updated values

        Returns:
            Updated machine entity

        Raises:
            RepositoryError: If update operation fails
            MachineNotFoundError: If machine doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, machine_id: UUID) -> bool:
        """
        Delete a machine by ID.

        Args:
            machine_id: Machine identifier

        Returns:
            True if machine was deleted, False if not found

        Raises:
            RepositoryError: If delete operation fails
        """
        pass

    @abstractmethod
    async def exists(self, machine_id: UUID) -> bool:
        """
        Check if a machine exists.

        Args:
            machine_id: Machine identifier

        Returns:
            True if machine exists

        Raises:
            RepositoryError: If check operation fails
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of machines.

        Returns:
            Total machine count

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: MachineStatus) -> int:
        """
        Count machines by status.

        Args:
            status: Machine status to count

        Returns:
            Machine count for the status

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    # Method removed: MachineType is not defined in the domain model
