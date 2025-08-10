"""
Task Repository Interface

Defines the contract for task data access operations.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.task import Task
from ..value_objects.enums import TaskStatus


class TaskRepository(ABC):
    """
    Abstract repository interface for Task entities.

    Defines the contract that infrastructure layer must implement
    for task data persistence and retrieval operations.
    """

    @abstractmethod
    async def save(self, task: Task) -> Task:
        """
        Save a task to the repository.

        Args:
            task: Task entity to save

        Returns:
            Saved task entity

        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Task | None:
        """
        Retrieve a task by its ID.

        Args:
            task_id: Unique task identifier

        Returns:
            Task entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Task]:
        """
        Retrieve all tasks.

        Returns:
            List of all task entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_job_id(self, job_id: UUID) -> list[Task]:
        """
        Retrieve all tasks for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            List of tasks for the job, ordered by position

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_status(self, status: TaskStatus) -> list[Task]:
        """
        Retrieve tasks with specific status.

        Args:
            status: Task status to filter by

        Returns:
            List of tasks with the status

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    # Method removed: TaskType is not defined in the domain model

    @abstractmethod
    async def get_by_machine_id(self, machine_id: UUID) -> list[Task]:
        """
        Retrieve tasks assigned to a specific machine.

        Args:
            machine_id: Machine identifier

        Returns:
            List of tasks assigned to the machine

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_operator_id(self, operator_id: UUID) -> list[Task]:
        """
        Retrieve tasks assigned to a specific operator.

        Args:
            operator_id: Operator identifier

        Returns:
            List of tasks assigned to the operator

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_scheduled_tasks(self) -> list[Task]:
        """
        Retrieve all scheduled tasks (status = SCHEDULED, IN_PROGRESS, or COMPLETED).

        Returns:
            List of scheduled tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_pending_tasks(self) -> list[Task]:
        """
        Retrieve all pending tasks (status = PENDING).

        Returns:
            List of pending tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_in_progress_tasks(self) -> list[Task]:
        """
        Retrieve all tasks currently in progress.

        Returns:
            List of in-progress tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_tasks_for_skill_type(self, skill_type: str) -> list[Task]:
        """
        Retrieve tasks that require a specific skill type.

        Args:
            skill_type: Skill type required (e.g., 'welding', 'machining')

        Returns:
            List of tasks requiring the skill

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_tasks_requiring_multiple_operators(self) -> list[Task]:
        """
        Retrieve tasks that require multiple operators.

        Returns:
            List of tasks needing multiple operators

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_attended_tasks(self) -> list[Task]:
        """
        Retrieve tasks that require operator attendance during processing.

        Returns:
            List of attended tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_unattended_tasks(self) -> list[Task]:
        """
        Retrieve tasks that don't require operator attendance during processing.

        Returns:
            List of unattended tasks

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def update(self, task: Task) -> Task:
        """
        Update an existing task.

        Args:
            task: Task entity with updated values

        Returns:
            Updated task entity

        Raises:
            RepositoryError: If update operation fails
            TaskNotFoundError: If task doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, task_id: UUID) -> bool:
        """
        Delete a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            True if task was deleted, False if not found

        Raises:
            RepositoryError: If delete operation fails
        """
        pass

    @abstractmethod
    async def exists(self, task_id: UUID) -> bool:
        """
        Check if a task exists.

        Args:
            task_id: Task identifier

        Returns:
            True if task exists

        Raises:
            RepositoryError: If check operation fails
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of tasks.

        Returns:
            Total task count

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: TaskStatus) -> int:
        """
        Count tasks by status.

        Args:
            status: Task status to count

        Returns:
            Task count for the status

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_job_id(self, job_id: UUID) -> int:
        """
        Count tasks for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            Task count for the job

        Raises:
            RepositoryError: If count operation fails
        """
        pass
