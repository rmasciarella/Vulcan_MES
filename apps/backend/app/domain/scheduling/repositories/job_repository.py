"""
Job Repository Interface

Defines the contract for job data access operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.job import Job


class JobRepository(ABC):
    """
    Abstract repository interface for Job entities.

    Defines the contract that infrastructure layer must implement
    for job data persistence and retrieval operations.
    """

    @abstractmethod
    async def save(self, job: Job) -> Job:
        """
        Save a job to the repository.

        Args:
            job: Job entity to save

        Returns:
            Saved job entity

        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> Job | None:
        """
        Retrieve a job by its ID.

        Args:
            job_id: Unique job identifier

        Returns:
            Job entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Job]:
        """
        Retrieve all jobs.

        Returns:
            List of all job entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_customer_id(self, customer_id: UUID) -> list[Job]:
        """
        Retrieve jobs for a specific customer.

        Args:
            customer_id: Customer identifier

        Returns:
            List of jobs for the customer

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_active_jobs(self) -> list[Job]:
        """
        Retrieve all active (not completed or cancelled) jobs.

        Returns:
            List of active job entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_jobs_due_before(self, due_date: datetime) -> list[Job]:
        """
        Retrieve jobs due before a specific date.

        Args:
            due_date: Due date threshold

        Returns:
            List of jobs due before the date

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_jobs_by_priority(self, priority: int) -> list[Job]:
        """
        Retrieve jobs with specific priority.

        Args:
            priority: Job priority level

        Returns:
            List of jobs with the priority

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def update(self, job: Job) -> Job:
        """
        Update an existing job.

        Args:
            job: Job entity with updated values

        Returns:
            Updated job entity

        Raises:
            RepositoryError: If update operation fails
            JobNotFoundError: If job doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, job_id: UUID) -> bool:
        """
        Delete a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted, False if not found

        Raises:
            RepositoryError: If delete operation fails
        """
        pass

    @abstractmethod
    async def exists(self, job_id: UUID) -> bool:
        """
        Check if a job exists.

        Args:
            job_id: Job identifier

        Returns:
            True if job exists

        Raises:
            RepositoryError: If check operation fails
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of jobs.

        Returns:
            Total job count

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_status(self, is_active: bool) -> int:
        """
        Count jobs by status.

        Args:
            is_active: True for active jobs, False for inactive

        Returns:
            Job count for the status

        Raises:
            RepositoryError: If count operation fails
        """
        pass
