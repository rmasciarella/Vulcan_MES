"""
Job repository implementation providing CRUD and domain-specific operations.

This module implements the JobRepository interface defined in the domain layer,
providing concrete database operations for Job entities using SQLModel.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import and_, or_, select

from app.domain.scheduling.value_objects.enums import JobStatus, TaskStatus
from app.infrastructure.database.models import Job, JobCreate, JobUpdate, Task

from .base import BaseRepository, DatabaseError, EntityNotFoundError


class JobRepository(BaseRepository[Job, JobCreate, JobUpdate]):
    """
    Repository implementation for Job entities.

    Provides CRUD operations plus domain-specific queries for jobs,
    including task relationship management and status-based filtering.
    """

    @property
    def entity_class(self):
        """Return the Job entity class."""
        return Job

    def find_by_job_number(self, job_number: str) -> Job | None:
        """
        Find job by job number.

        Args:
            job_number: Unique job number to search for

        Returns:
            Job if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(Job.job_number == job_number.upper())
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding job by number {job_number}: {str(e)}"
            ) from e

    def find_by_job_number_required(self, job_number: str) -> Job:
        """
        Find job by job number, raising exception if not found.

        Args:
            job_number: Unique job number to search for

        Returns:
            Job entity

        Raises:
            EntityNotFoundError: If job not found
            DatabaseError: If database operation fails
        """
        job = self.find_by_job_number(job_number)
        if not job:
            raise EntityNotFoundError(f"Job with number {job_number} not found")
        return job

    def find_with_tasks(self, job_id: UUID) -> Job | None:
        """
        Find job with all tasks eagerly loaded.

        Args:
            job_id: UUID of the job

        Returns:
            Job with tasks loaded, None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Job).options(selectinload(Job.tasks)).where(Job.id == job_id)
            )
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding job with tasks {job_id}: {str(e)}"
            ) from e

    def find_by_status(self, status: JobStatus) -> list[Job]:
        """
        Find all jobs with given status.

        Args:
            status: Job status to filter by

        Returns:
            List of jobs with the specified status

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(Job.status == status)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs by status {status}: {str(e)}"
            ) from e

    def find_active_jobs(self) -> list[Job]:
        """
        Find all active jobs (released or in progress).

        Returns:
            List of active jobs

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(
                or_(
                    Job.status == JobStatus.RELEASED,
                    Job.status == JobStatus.IN_PROGRESS,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding active jobs: {str(e)}") from e

    def find_overdue(self, as_of: datetime | None = None) -> list[Job]:
        """
        Find jobs that are overdue as of a specific date.

        Args:
            as_of: Date to check against (defaults to now)

        Returns:
            List of overdue jobs

        Raises:
            DatabaseError: If database operation fails
        """
        if as_of is None:
            as_of = datetime.utcnow()

        try:
            statement = select(Job).where(
                and_(
                    Job.due_date < as_of,
                    Job.status != JobStatus.COMPLETED,
                    Job.status != JobStatus.CANCELLED,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding overdue jobs: {str(e)}") from e

    def find_by_customer(self, customer_name: str) -> list[Job]:
        """
        Find jobs for a specific customer.

        Args:
            customer_name: Customer name to search for

        Returns:
            List of jobs for the customer

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(Job.customer_name.ilike(f"%{customer_name}%"))
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs by customer {customer_name}: {str(e)}"
            ) from e

    def find_by_part_number(self, part_number: str) -> list[Job]:
        """
        Find jobs for a specific part number.

        Args:
            part_number: Part number to search for

        Returns:
            List of jobs for the part number

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(Job.part_number == part_number)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs by part number {part_number}: {str(e)}"
            ) from e

    def find_due_within_days(self, days: int) -> list[Job]:
        """
        Find jobs due within specified number of days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of jobs due within the specified days

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.utcnow() + timedelta(days=days)

            statement = select(Job).where(
                and_(
                    Job.due_date <= cutoff_date,
                    Job.due_date >= datetime.utcnow(),
                    Job.status != JobStatus.COMPLETED,
                    Job.status != JobStatus.CANCELLED,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs due within {days} days: {str(e)}"
            ) from e

    def find_by_priority(self, priority: str) -> list[Job]:
        """
        Find jobs with specified priority level.

        Args:
            priority: Priority level to filter by

        Returns:
            List of jobs with the specified priority

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Job).where(Job.priority == priority)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs by priority {priority}: {str(e)}"
            ) from e

    def find_with_incomplete_tasks(self) -> list[Job]:
        """
        Find jobs that have incomplete tasks.

        Returns:
            List of jobs with incomplete tasks

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Job)
                .join(Task)
                .where(
                    and_(
                        Task.status != TaskStatus.COMPLETED,
                        Task.status != TaskStatus.CANCELLED,
                    )
                )
                .distinct()
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs with incomplete tasks: {str(e)}"
            ) from e

    def find_ready_for_release(self) -> list[Job]:
        """
        Find jobs that are ready to be released (planned status with release date reached).

        Returns:
            List of jobs ready for release

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            now = datetime.utcnow()
            statement = select(Job).where(
                and_(
                    Job.status == JobStatus.PLANNED,
                    or_(Job.release_date <= now, Job.release_date.is_(None)),
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding jobs ready for release: {str(e)}"
            ) from e

    def get_job_statistics(self) -> dict:
        """
        Get statistics about jobs in the system.

        Returns:
            Dictionary with job statistics

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from sqlalchemy import func

            # Count by status
            status_counts = {}
            for status in JobStatus:
                count_statement = select(func.count(Job.id)).where(Job.status == status)
                count = self.session.exec(count_statement).one()
                status_counts[status.value] = count

            # Overdue count
            overdue_statement = select(func.count(Job.id)).where(
                and_(
                    Job.due_date < datetime.utcnow(),
                    Job.status != JobStatus.COMPLETED,
                    Job.status != JobStatus.CANCELLED,
                )
            )
            overdue_count = self.session.exec(overdue_statement).one()

            # Due this week
            from datetime import timedelta

            week_end = datetime.utcnow() + timedelta(days=7)
            due_this_week_statement = select(func.count(Job.id)).where(
                and_(
                    Job.due_date <= week_end,
                    Job.due_date >= datetime.utcnow(),
                    Job.status != JobStatus.COMPLETED,
                    Job.status != JobStatus.CANCELLED,
                )
            )
            due_this_week_count = self.session.exec(due_this_week_statement).one()

            return {
                "by_status": status_counts,
                "overdue_count": overdue_count,
                "due_this_week_count": due_this_week_count,
                "total_active": status_counts.get(JobStatus.RELEASED.value, 0)
                + status_counts.get(JobStatus.IN_PROGRESS.value, 0),
            }
        except Exception as e:
            raise DatabaseError(f"Error getting job statistics: {str(e)}") from e

    def update_progress(self, job_id: UUID, current_operation: int) -> Job:
        """
        Update job progress to current operation.

        Args:
            job_id: UUID of the job to update
            current_operation: Current operation sequence number

        Returns:
            Updated job

        Raises:
            EntityNotFoundError: If job not found
            DatabaseError: If database operation fails
        """
        try:
            job = self.get_by_id_required(job_id)
            job.current_operation_sequence = max(
                job.current_operation_sequence, current_operation
            )
            job.updated_at = datetime.utcnow()

            if current_operation >= 100:
                job.status = JobStatus.COMPLETED
                job.actual_end_date = datetime.utcnow()
            elif job.status == JobStatus.PLANNED:
                job.status = JobStatus.IN_PROGRESS
                if not job.actual_start_date:
                    job.actual_start_date = datetime.utcnow()

            return self.save(job)
        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Error updating job progress: {str(e)}") from e
