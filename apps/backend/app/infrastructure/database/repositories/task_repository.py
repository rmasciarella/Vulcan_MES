"""
Task repository implementation providing CRUD and domain-specific operations.

This module implements the TaskRepository interface, providing concrete
database operations for Task entities and their operator assignments.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import and_, or_, select

from app.domain.scheduling.value_objects.enums import TaskStatus
from app.infrastructure.database.models import Task, TaskCreate, TaskUpdate

from .base import BaseRepository, DatabaseError, EntityNotFoundError


class TaskRepository(BaseRepository[Task, TaskCreate, TaskUpdate]):
    """
    Repository implementation for Task entities.

    Provides CRUD operations plus domain-specific queries for tasks,
    including job relationships, status filtering, and resource assignments.
    """

    @property
    def entity_class(self):
        """Return the Task entity class."""
        return Task

    def find_by_job_id(self, job_id: UUID) -> list[Task]:
        """
        Find all tasks for a specific job.

        Args:
            job_id: UUID of the job

        Returns:
            List of tasks for the job, ordered by sequence

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Task).where(Task.job_id == job_id).order_by(Task.sequence_in_job)
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding tasks by job_id {job_id}: {str(e)}"
            ) from e

    def find_by_status(self, status: TaskStatus) -> list[Task]:
        """
        Find all tasks with given status.

        Args:
            status: Task status to filter by

        Returns:
            List of tasks with the specified status

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(Task.status == status)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding tasks by status {status}: {str(e)}"
            ) from e

    def find_ready_tasks(self) -> list[Task]:
        """
        Find all tasks that are ready to be scheduled.

        Returns:
            List of tasks with READY status

        Raises:
            DatabaseError: If database operation fails
        """
        return self.find_by_status(TaskStatus.READY)

    def find_scheduled_tasks(self) -> list[Task]:
        """
        Find all tasks that are scheduled.

        Returns:
            List of tasks with SCHEDULED status

        Raises:
            DatabaseError: If database operation fails
        """
        return self.find_by_status(TaskStatus.SCHEDULED)

    def find_active_tasks(self) -> list[Task]:
        """
        Find all currently active tasks (scheduled or in progress).

        Returns:
            List of active tasks

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(
                or_(
                    Task.status == TaskStatus.SCHEDULED,
                    Task.status == TaskStatus.IN_PROGRESS,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding active tasks: {str(e)}") from e

    def find_by_machine(self, machine_id: UUID) -> list[Task]:
        """
        Find all tasks assigned to a specific machine.

        Args:
            machine_id: UUID of the machine

        Returns:
            List of tasks assigned to the machine

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(Task.assigned_machine_id == machine_id)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding tasks by machine {machine_id}: {str(e)}"
            ) from e

    def find_critical_path_tasks(self) -> list[Task]:
        """
        Find all tasks that are on the critical path.

        Returns:
            List of critical path tasks

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(Task.is_critical_path)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding critical path tasks: {str(e)}") from e

    def find_delayed_tasks(self, min_delay_minutes: int = 0) -> list[Task]:
        """
        Find all tasks that are delayed.

        Args:
            min_delay_minutes: Minimum delay in minutes to consider

        Returns:
            List of delayed tasks

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(Task.delay_minutes > min_delay_minutes)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding delayed tasks: {str(e)}") from e

    def find_tasks_with_rework(self) -> list[Task]:
        """
        Find all tasks that required rework.

        Returns:
            List of tasks with rework

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(Task.rework_count > 0)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding tasks with rework: {str(e)}") from e

    def find_with_operator_assignments(self, task_id: UUID) -> Task | None:
        """
        Find task with all operator assignments eagerly loaded.

        Args:
            task_id: UUID of the task

        Returns:
            Task with operator assignments loaded, None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Task)
                .options(selectinload(Task.operator_assignments))
                .where(Task.id == task_id)
            )
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding task with assignments {task_id}: {str(e)}"
            ) from e

    def find_scheduled_between(
        self, start_time: datetime, end_time: datetime
    ) -> list[Task]:
        """
        Find tasks scheduled between specified times.

        Args:
            start_time: Start of time window
            end_time: End of time window

        Returns:
            List of tasks scheduled in the time window

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(Task).where(
                and_(
                    Task.planned_start_time >= start_time,
                    Task.planned_end_time <= end_time,
                    Task.status == TaskStatus.SCHEDULED,
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding tasks scheduled between {start_time} and {end_time}: {str(e)}"
            ) from e

    def find_by_sequence_range(
        self, job_id: UUID, min_sequence: int, max_sequence: int
    ) -> list[Task]:
        """
        Find tasks within a sequence range for a specific job.

        Args:
            job_id: UUID of the job
            min_sequence: Minimum sequence number (inclusive)
            max_sequence: Maximum sequence number (inclusive)

        Returns:
            List of tasks in the sequence range

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Task)
                .where(
                    and_(
                        Task.job_id == job_id,
                        Task.sequence_in_job >= min_sequence,
                        Task.sequence_in_job <= max_sequence,
                    )
                )
                .order_by(Task.sequence_in_job)
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding tasks in sequence range for job {job_id}: {str(e)}"
            ) from e

    def find_next_tasks_in_job(
        self, job_id: UUID, current_sequence: int, limit: int = 10
    ) -> list[Task]:
        """
        Find next tasks in job sequence after current operation.

        Args:
            job_id: UUID of the job
            current_sequence: Current operation sequence number
            limit: Maximum number of tasks to return

        Returns:
            List of next tasks in sequence

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = (
                select(Task)
                .where(
                    and_(Task.job_id == job_id, Task.sequence_in_job > current_sequence)
                )
                .order_by(Task.sequence_in_job)
                .limit(limit)
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding next tasks for job {job_id}: {str(e)}"
            ) from e

    def find_overdue_scheduled_tasks(self, as_of: datetime | None = None) -> list[Task]:
        """
        Find scheduled tasks that are overdue.

        Args:
            as_of: Date to check against (defaults to now)

        Returns:
            List of overdue scheduled tasks

        Raises:
            DatabaseError: If database operation fails
        """
        if as_of is None:
            as_of = datetime.utcnow()

        try:
            statement = select(Task).where(
                and_(
                    Task.status == TaskStatus.SCHEDULED, Task.planned_start_time < as_of
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding overdue scheduled tasks: {str(e)}"
            ) from e

    def get_task_statistics(self, job_id: UUID | None = None) -> dict:
        """
        Get statistics about tasks in the system or for a specific job.

        Args:
            job_id: Optional job ID to filter statistics

        Returns:
            Dictionary with task statistics

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from sqlalchemy import func

            # Base query
            base_query = select(func.count(Task.id))
            if job_id:
                base_query = base_query.where(Task.job_id == job_id)

            # Count by status
            status_counts = {}
            for status in TaskStatus:
                status_query = base_query.where(Task.status == status)
                count = self.session.exec(status_query).one()
                status_counts[status.value] = count

            # Critical path tasks
            critical_query = base_query.where(Task.is_critical_path)
            critical_count = self.session.exec(critical_query).one()

            # Delayed tasks
            delayed_query = base_query.where(Task.delay_minutes > 0)
            delayed_count = self.session.exec(delayed_query).one()

            # Tasks with rework
            rework_query = base_query.where(Task.rework_count > 0)
            rework_count = self.session.exec(rework_query).one()

            # Average delay
            avg_delay_query = select(func.avg(Task.delay_minutes))
            if job_id:
                avg_delay_query = avg_delay_query.where(Task.job_id == job_id)
            avg_delay = self.session.exec(avg_delay_query).one() or 0

            return {
                "by_status": status_counts,
                "critical_path_count": critical_count,
                "delayed_count": delayed_count,
                "rework_count": rework_count,
                "average_delay_minutes": float(avg_delay),
                "total_active": (
                    status_counts.get(TaskStatus.SCHEDULED.value, 0)
                    + status_counts.get(TaskStatus.IN_PROGRESS.value, 0)
                ),
            }
        except Exception as e:
            raise DatabaseError(f"Error getting task statistics: {str(e)}") from e

    def mark_task_ready(self, task_id: UUID) -> Task:
        """
        Mark a task as ready for scheduling.

        Args:
            task_id: UUID of the task to mark ready

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task not found
            DatabaseError: If database operation fails
        """
        try:
            task = self.get_by_id_required(task_id)
            if task.status != TaskStatus.PENDING:
                raise ValueError(
                    f"Task {task_id} is not in PENDING status, cannot mark as ready"
                )

            task.status = TaskStatus.READY
            task.updated_at = datetime.utcnow()
            return self.save(task)
        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Error marking task ready: {str(e)}") from e

    def schedule_task(
        self,
        task_id: UUID,
        machine_id: UUID | None,
        start_time: datetime,
        end_time: datetime,
    ) -> Task:
        """
        Schedule a task with machine and timing.

        Args:
            task_id: UUID of the task to schedule
            machine_id: UUID of assigned machine (optional)
            start_time: Planned start time
            end_time: Planned end time

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task not found
            DatabaseError: If database operation fails
        """
        try:
            task = self.get_by_id_required(task_id)
            if task.status not in [TaskStatus.READY, TaskStatus.SCHEDULED]:
                raise ValueError(
                    f"Task {task_id} cannot be scheduled from status {task.status}"
                )

            task.assigned_machine_id = machine_id
            task.planned_start_time = start_time
            task.planned_end_time = end_time
            task.planned_duration_minutes = int(
                (end_time - start_time).total_seconds() / 60
            )
            task.status = TaskStatus.SCHEDULED
            task.updated_at = datetime.utcnow()

            return self.save(task)
        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Error scheduling task: {str(e)}") from e

    def start_task(
        self, task_id: UUID, actual_start_time: datetime | None = None
    ) -> Task:
        """
        Start task execution.

        Args:
            task_id: UUID of the task to start
            actual_start_time: Actual start time (defaults to now)

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task not found
            DatabaseError: If database operation fails
        """
        try:
            task = self.get_by_id_required(task_id)
            if task.status != TaskStatus.SCHEDULED:
                raise ValueError(f"Task {task_id} is not scheduled, cannot start")

            task.actual_start_time = actual_start_time or datetime.utcnow()
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.utcnow()

            return self.save(task)
        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Error starting task: {str(e)}") from e

    def complete_task(
        self, task_id: UUID, actual_end_time: datetime | None = None
    ) -> Task:
        """
        Complete task execution.

        Args:
            task_id: UUID of the task to complete
            actual_end_time: Actual end time (defaults to now)

        Returns:
            Updated task

        Raises:
            EntityNotFoundError: If task not found
            DatabaseError: If database operation fails
        """
        try:
            task = self.get_by_id_required(task_id)
            if task.status != TaskStatus.IN_PROGRESS:
                raise ValueError(f"Task {task_id} is not in progress, cannot complete")

            end_time = actual_end_time or datetime.utcnow()
            task.actual_end_time = end_time
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.utcnow()

            if task.actual_start_time:
                duration = end_time - task.actual_start_time
                task.actual_duration_minutes = int(duration.total_seconds() / 60)

            return self.save(task)
        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Error completing task: {str(e)}") from e
