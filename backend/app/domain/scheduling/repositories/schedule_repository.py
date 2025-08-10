"""
Schedule Repository Interface

Defines the contract for schedule data access operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.schedule import Schedule, ScheduleStatus


class ScheduleRepository(ABC):
    """
    Abstract repository interface for Schedule entities.

    Defines the contract that infrastructure layer must implement
    for schedule data persistence and retrieval operations.
    """

    @abstractmethod
    async def save(self, schedule: Schedule) -> Schedule:
        """
        Save a schedule to the repository.

        Args:
            schedule: Schedule entity to save

        Returns:
            Saved schedule entity

        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        """
        Retrieve a schedule by its ID.

        Args:
            schedule_id: Unique schedule identifier

        Returns:
            Schedule entity or None if not found

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Schedule]:
        """
        Retrieve all schedules.

        Returns:
            List of all schedule entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_by_status(self, status: ScheduleStatus) -> list[Schedule]:
        """
        Retrieve schedules with specific status.

        Args:
            status: Schedule status to filter by

        Returns:
            List of schedules with the status

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_active_schedule(self) -> Schedule | None:
        """
        Retrieve the currently active schedule.

        Returns:
            Active schedule entity or None if no active schedule

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_published_schedules(self) -> list[Schedule]:
        """
        Retrieve all published schedules.

        Returns:
            List of published schedule entities

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_schedules_by_creator(self, created_by: UUID) -> list[Schedule]:
        """
        Retrieve schedules created by a specific user.

        Args:
            created_by: User ID who created the schedules

        Returns:
            List of schedules created by the user

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_schedules_containing_job(self, job_id: UUID) -> list[Schedule]:
        """
        Retrieve schedules that contain a specific job.

        Args:
            job_id: Job identifier to search for

        Returns:
            List of schedules containing the job

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_schedules_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Schedule]:
        """
        Retrieve schedules within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of schedules in the date range

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_recent_schedules(self, limit: int = 10) -> list[Schedule]:
        """
        Retrieve most recently created schedules.

        Args:
            limit: Maximum number of schedules to return

        Returns:
            List of recent schedules, ordered by creation time

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_schedules_with_violations(self) -> list[Schedule]:
        """
        Retrieve schedules that have constraint violations.

        Returns:
            List of schedules with violations

        Raises:
            RepositoryError: If retrieval operation fails
        """
        pass

    @abstractmethod
    async def get_schedule_performance_metrics(self, schedule_id: UUID) -> dict | None:
        """
        Get performance metrics for a specific schedule.

        Args:
            schedule_id: Schedule identifier

        Returns:
            Dictionary with performance metrics or None if not found

        Raises:
            RepositoryError: If metrics retrieval fails
        """
        pass

    @abstractmethod
    async def find_conflicting_schedules(
        self,
        machine_ids: list[UUID],
        operator_ids: list[UUID],
        start_time: datetime,
        end_time: datetime,
        exclude_schedule_id: UUID | None = None,
    ) -> list[Schedule]:
        """
        Find schedules that would conflict with given resource assignments.

        Args:
            machine_ids: Machine IDs to check for conflicts
            operator_ids: Operator IDs to check for conflicts
            start_time: Start time of potential conflict
            end_time: End time of potential conflict
            exclude_schedule_id: Schedule ID to exclude from conflict check

        Returns:
            List of schedules that would conflict

        Raises:
            RepositoryError: If conflict check fails
        """
        pass

    @abstractmethod
    async def update(self, schedule: Schedule) -> Schedule:
        """
        Update an existing schedule.

        Args:
            schedule: Schedule entity with updated values

        Returns:
            Updated schedule entity

        Raises:
            RepositoryError: If update operation fails
            ScheduleNotFoundError: If schedule doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, schedule_id: UUID) -> bool:
        """
        Delete a schedule by ID.

        Args:
            schedule_id: Schedule identifier

        Returns:
            True if schedule was deleted, False if not found

        Raises:
            RepositoryError: If delete operation fails
        """
        pass

    @abstractmethod
    async def exists(self, schedule_id: UUID) -> bool:
        """
        Check if a schedule exists.

        Args:
            schedule_id: Schedule identifier

        Returns:
            True if schedule exists

        Raises:
            RepositoryError: If check operation fails
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Count total number of schedules.

        Returns:
            Total schedule count

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: ScheduleStatus) -> int:
        """
        Count schedules by status.

        Args:
            status: Schedule status to count

        Returns:
            Schedule count for the status

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
    async def archive_old_schedules(self, cutoff_date: datetime) -> int:
        """
        Archive old completed schedules.

        Args:
            cutoff_date: Archive schedules completed before this date

        Returns:
            Number of schedules archived

        Raises:
            RepositoryError: If archive operation fails
        """
        pass
