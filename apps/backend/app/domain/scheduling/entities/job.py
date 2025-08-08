"""Job aggregate root for coordinating production tasks."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, validator

from ...shared.base import AggregateRoot, BusinessRuleViolation, DomainEvent
from ...shared.validation import (
    BusinessRuleValidators,
    DataSanitizer,
    SchedulingValidators,
    ValidationError,
)
from ..value_objects.common import Duration, Quantity
from ..value_objects.enums import JobStatus, PriorityLevel, TaskStatus


class JobStatusChanged(DomainEvent):
    """Event raised when job status changes."""

    job_id: UUID
    job_number: str
    old_status: JobStatus
    new_status: JobStatus
    reason: str | None = None


class JobScheduleChanged(DomainEvent):
    """Event raised when job schedule changes."""

    job_id: UUID
    job_number: str
    old_planned_start: datetime | None
    new_planned_start: datetime | None
    old_planned_end: datetime | None
    new_planned_end: datetime | None
    reason: str


class JobDelayed(DomainEvent):
    """Event raised when job is delayed beyond due date."""

    job_id: UUID
    job_number: str
    due_date: datetime
    estimated_completion: datetime
    delay_hours: float
    customer_name: str | None


class TaskProgressUpdated(DomainEvent):
    """Event raised when task progression updates job progress."""

    job_id: UUID
    job_number: str
    completed_tasks: int
    total_tasks: int
    current_operation_sequence: int
    completion_percentage: float


class Job(AggregateRoot):
    """
    Job aggregate root representing a manufacturing work order.

    Jobs coordinate the execution of multiple tasks in sequence to produce
    a finished product. They manage priority, scheduling, and progress tracking
    while enforcing business rules about task progression and resource allocation.
    """

    job_number: str = Field(min_length=1, max_length=50)
    customer_name: str | None = Field(None, max_length=100)
    part_number: str | None = Field(None, max_length=50)
    quantity: Quantity = Field(default=Quantity(value=1))
    priority: PriorityLevel = Field(default=PriorityLevel.NORMAL)
    status: JobStatus = Field(default=JobStatus.PLANNED)

    @validator("customer_name")
    def sanitize_customer_name(cls, v):
        """Sanitize customer name input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=100)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    @validator("part_number")
    def sanitize_part_number(cls, v):
        """Sanitize part number input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=50)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    # Scheduling dates
    release_date: datetime | None = None
    due_date: datetime
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None
    actual_start_date: datetime | None = None
    actual_end_date: datetime | None = None

    # Progress tracking
    current_operation_sequence: int = Field(default=0, ge=0, le=100)
    notes: str | None = None
    created_by: str | None = None

    @validator("current_operation_sequence")
    def validate_sequence_range(cls, v):
        """Current operation sequence must be between 0 and 100."""
        try:
            BusinessRuleValidators.validate_range(
                "current_operation_sequence", v, 0, 100
            )
            return v
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("notes")
    def sanitize_notes(cls, v):
        """Sanitize notes input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=1000)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    @validator("created_by")
    def sanitize_created_by(cls, v):
        """Sanitize created by input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=100)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    # Task coordination (managed internally)
    _tasks: dict[int, "Task"] = Field(default_factory=dict)  # sequence -> Task
    _task_dependencies: dict[UUID, list[UUID]] = Field(
        default_factory=dict
    )  # task_id -> [prerequisite_ids]

    @validator("job_number")
    def validate_job_number(cls, v):
        """Job number should be non-empty and well-formed."""
        try:
            return SchedulingValidators.validate_job_number_format(v)
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("due_date")
    def due_date_in_future(cls, v):
        """Due date should be in the future."""
        try:
            BusinessRuleValidators.validate_future_date("due_date", v)
            return v
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("actual_end_date")
    def end_after_start(cls, v, values):
        """Actual end date must be after actual start date."""
        if v and "actual_start_date" in values and values["actual_start_date"]:
            try:
                BusinessRuleValidators.validate_date_range(
                    "actual_start_date",
                    values["actual_start_date"],
                    "actual_end_date",
                    v,
                )
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    def is_valid(self) -> bool:
        """Validate business rules."""
        return (
            bool(self.job_number)
            and self.due_date > datetime.utcnow()
            and self.quantity.value > 0
            and 0 <= self.current_operation_sequence <= 100
        )

    @property
    def is_active(self) -> bool:
        """Check if job is in an active state."""
        return self.status.is_active

    @property
    def is_complete(self) -> bool:
        """Check if job is completed."""
        return self.status == JobStatus.COMPLETED

    @property
    def is_overdue(self) -> bool:
        """Check if job is past its due date."""
        return datetime.utcnow() > self.due_date and not self.is_complete

    @property
    def days_until_due(self) -> float:
        """Get days until due date (negative if overdue)."""
        delta = self.due_date - datetime.utcnow()
        return delta.total_seconds() / (24 * 3600)  # Convert to days

    @property
    def task_count(self) -> int:
        """Get total number of tasks."""
        return len(self._tasks)

    @property
    def completed_task_count(self) -> int:
        """Get number of completed tasks."""
        return len(
            [
                task
                for task in self._tasks.values()
                if task.status == TaskStatus.COMPLETED
            ]
        )

    @property
    def completion_percentage(self) -> float:
        """Get job completion percentage."""
        if self.task_count == 0:
            return 0.0
        return (self.completed_task_count / self.task_count) * 100

    @property
    def estimated_duration(self) -> Duration | None:
        """Get estimated total duration based on tasks."""
        if not self._tasks:
            return None

        total_minutes = sum(
            (task.planned_duration or Duration(minutes=0)).minutes
            + (task.planned_setup_duration or Duration(minutes=0)).minutes
            for task in self._tasks.values()
        )
        return Duration(minutes=total_minutes)

    @property
    def critical_path_tasks(self) -> list["Task"]:
        """Get tasks that are on the critical path."""
        return [task for task in self._tasks.values() if task.is_critical_path]

    def get_task_by_sequence(self, sequence: int) -> Optional["Task"]:
        """Get task by sequence number."""
        return self._tasks.get(sequence)

    def get_all_tasks(self) -> list["Task"]:
        """Get all tasks sorted by sequence."""
        return sorted(self._tasks.values(), key=lambda t: t.sequence_in_job)

    def get_ready_tasks(self) -> list["Task"]:
        """Get tasks that are ready to be scheduled."""
        return [
            task for task in self._tasks.values() if task.status == TaskStatus.READY
        ]

    def get_active_tasks(self) -> list["Task"]:
        """Get tasks that are currently active."""
        return [
            task
            for task in self._tasks.values()
            if task.status in {TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS}
        ]

    def add_task(self, task: "Task") -> None:
        """
        Add a task to the job.

        Args:
            task: Task to add

        Raises:
            BusinessRuleViolation: If task sequence conflicts or job is complete
        """
        if self.is_complete:
            raise BusinessRuleViolation(
                "JOB_COMPLETE", f"Cannot add tasks to completed job {self.job_number}"
            )

        if task.job_id != self.id:
            raise BusinessRuleViolation(
                "TASK_JOB_MISMATCH", "Task job_id must match this job's ID"
            )

        if task.sequence_in_job in self._tasks:
            raise BusinessRuleViolation(
                "DUPLICATE_TASK_SEQUENCE",
                f"Task sequence {task.sequence_in_job} already exists in job {self.job_number}",
            )

        self._tasks[task.sequence_in_job] = task

        # First task can be ready immediately
        if task.sequence_in_job == 1 and task.status == TaskStatus.PENDING:
            task.mark_ready()

        self.mark_updated()

    def remove_task(self, sequence: int) -> None:
        """
        Remove a task from the job.

        Args:
            sequence: Sequence number of task to remove

        Raises:
            BusinessRuleViolation: If task is in progress or doesn't exist
        """
        task = self._tasks.get(sequence)
        if not task:
            raise BusinessRuleViolation(
                "TASK_NOT_FOUND",
                f"No task with sequence {sequence} in job {self.job_number}",
            )

        if task.status == TaskStatus.IN_PROGRESS:
            raise BusinessRuleViolation(
                "CANNOT_REMOVE_ACTIVE_TASK",
                f"Cannot remove task {sequence} while it's in progress",
            )

        del self._tasks[sequence]
        self.mark_updated()

    def complete_task(self, sequence: int, actual_end_time: datetime) -> None:
        """
        Mark a task as completed and update job progress.

        Args:
            sequence: Sequence number of task to complete
            actual_end_time: When the task was completed

        Raises:
            BusinessRuleViolation: If task is not in progress
        """
        task = self._tasks.get(sequence)
        if not task:
            raise BusinessRuleViolation(
                "TASK_NOT_FOUND",
                f"No task with sequence {sequence} in job {self.job_number}",
            )

        if task.status != TaskStatus.IN_PROGRESS:
            raise BusinessRuleViolation(
                "TASK_NOT_IN_PROGRESS", f"Task {sequence} is not in progress"
            )

        # Complete the task
        task.complete(actual_end_time)

        # Update job progress
        self.current_operation_sequence = max(self.current_operation_sequence, sequence)

        # Set job start date if this is first task completion
        if self.actual_start_date is None:
            self.actual_start_date = task.actual_start_time

        # Check if job is complete (all tasks done or reached operation 100)
        if sequence == 100 or all(
            task.status == TaskStatus.COMPLETED for task in self._tasks.values()
        ):
            self._complete_job(actual_end_time)
        else:
            # Mark next task as ready if it exists
            next_task = self._tasks.get(sequence + 1)
            if next_task and next_task.status == TaskStatus.PENDING:
                next_task.mark_ready()

        self.mark_updated()

        # Raise progress event
        self.add_domain_event(
            TaskProgressUpdated(
                aggregate_id=self.id,
                job_id=self.id,
                job_number=self.job_number,
                completed_tasks=self.completed_task_count,
                total_tasks=self.task_count,
                current_operation_sequence=self.current_operation_sequence,
                completion_percentage=self.completion_percentage,
            )
        )

    def _complete_job(self, completion_time: datetime) -> None:
        """Complete the job."""
        old_status = self.status
        self.status = JobStatus.COMPLETED
        self.actual_end_date = completion_time

        self.add_domain_event(
            JobStatusChanged(
                aggregate_id=self.id,
                job_id=self.id,
                job_number=self.job_number,
                old_status=old_status,
                new_status=self.status,
                reason="all_tasks_completed",
            )
        )

    def change_status(self, new_status: JobStatus, reason: str | None = None) -> None:
        """
        Change job status with validation and events.

        Args:
            new_status: New job status
            reason: Optional reason for change

        Raises:
            BusinessRuleViolation: If status transition is invalid
        """
        if not self.status.can_transition_to(new_status):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition job from {self.status} to {new_status}",
            )

        if new_status == self.status:
            return  # No change needed

        old_status = self.status
        self.status = new_status

        # Set release date when job is released
        if new_status == JobStatus.RELEASED and self.release_date is None:
            self.release_date = datetime.utcnow()

        self.mark_updated()

        self.add_domain_event(
            JobStatusChanged(
                aggregate_id=self.id,
                job_id=self.id,
                job_number=self.job_number,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
            )
        )

    def update_schedule(
        self,
        planned_start: datetime | None,
        planned_end: datetime | None,
        reason: str = "schedule_update",
    ) -> None:
        """
        Update job schedule.

        Args:
            planned_start: New planned start date
            planned_end: New planned end date
            reason: Reason for schedule change
        """
        if planned_start and planned_end and planned_start >= planned_end:
            raise BusinessRuleViolation(
                "INVALID_SCHEDULE", "Planned start date must be before planned end date"
            )

        old_start = self.planned_start_date
        old_end = self.planned_end_date

        self.planned_start_date = planned_start
        self.planned_end_date = planned_end
        self.mark_updated()

        # Check for delays
        if planned_end and planned_end > self.due_date:
            delay_hours = (planned_end - self.due_date).total_seconds() / 3600
            self.add_domain_event(
                JobDelayed(
                    aggregate_id=self.id,
                    job_id=self.id,
                    job_number=self.job_number,
                    due_date=self.due_date,
                    estimated_completion=planned_end,
                    delay_hours=delay_hours,
                    customer_name=self.customer_name,
                )
            )

        self.add_domain_event(
            JobScheduleChanged(
                aggregate_id=self.id,
                job_id=self.id,
                job_number=self.job_number,
                old_planned_start=old_start,
                new_planned_start=planned_start,
                old_planned_end=old_end,
                new_planned_end=planned_end,
                reason=reason,
            )
        )

    def adjust_priority(self, new_priority: PriorityLevel, reason: str) -> None:
        """
        Adjust job priority.

        Args:
            new_priority: New priority level
            reason: Reason for priority change
        """
        if new_priority == self.priority:
            return

        self.priority = new_priority
        self.mark_updated()

        # Priority changes may affect scheduling
        self.add_domain_event(
            JobScheduleChanged(
                aggregate_id=self.id,
                job_id=self.id,
                job_number=self.job_number,
                old_planned_start=self.planned_start_date,
                new_planned_start=self.planned_start_date,
                old_planned_end=self.planned_end_date,
                new_planned_end=self.planned_end_date,
                reason=f"priority_changed_to_{new_priority.value}_{reason}",
            )
        )

    def extend_due_date(self, new_due_date: datetime, reason: str) -> None:
        """
        Extend the job due date.

        Args:
            new_due_date: New due date
            reason: Reason for extension

        Raises:
            BusinessRuleViolation: If new due date is earlier than current
        """
        if new_due_date <= self.due_date:
            raise BusinessRuleViolation(
                "INVALID_DUE_DATE_EXTENSION",
                "New due date must be later than current due date",
            )

        self.due_date = new_due_date
        self.mark_updated()

    def put_on_hold(self, reason: str) -> None:
        """Put job on hold with reason."""
        self.change_status(JobStatus.ON_HOLD, reason)

    def release_from_hold(self, reason: str = "resumed") -> None:
        """Release job from hold."""
        if self.status != JobStatus.ON_HOLD:
            raise BusinessRuleViolation(
                "JOB_NOT_ON_HOLD", f"Job {self.job_number} is not on hold"
            )
        self.change_status(JobStatus.RELEASED, reason)

    def cancel(self, reason: str) -> None:
        """Cancel the job."""
        self.change_status(JobStatus.CANCELLED, reason)

    def get_job_summary(self) -> dict:
        """Get job information summary."""
        return {
            "job_number": self.job_number,
            "customer_name": self.customer_name,
            "status": self.status.value,
            "priority": self.priority.value,
            "quantity": self.quantity.value,
            "due_date": self.due_date.isoformat(),
            "days_until_due": round(self.days_until_due, 1),
            "is_overdue": self.is_overdue,
            "completion_percentage": round(self.completion_percentage, 1),
            "task_count": self.task_count,
            "completed_tasks": self.completed_task_count,
            "current_operation_sequence": self.current_operation_sequence,
            "estimated_duration": str(self.estimated_duration)
            if self.estimated_duration
            else None,
            "critical_path_task_count": len(self.critical_path_tasks),
        }

    @staticmethod
    def create(
        job_number: str,
        due_date: datetime,
        customer_name: str | None = None,
        part_number: str | None = None,
        quantity: int = 1,
        priority: PriorityLevel = PriorityLevel.NORMAL,
        created_by: str | None = None,
    ) -> "Job":
        """
        Factory method to create a new Job.

        Args:
            job_number: Unique job identifier
            due_date: When job must be completed
            customer_name: Customer name
            part_number: Part being manufactured
            quantity: Number of items to produce
            priority: Job priority level
            created_by: Who created the job

        Returns:
            New Job instance
        """
        job = Job(
            job_number=job_number,
            customer_name=customer_name,
            part_number=part_number,
            quantity=Quantity(value=quantity),
            priority=priority,
            due_date=due_date,
            created_by=created_by,
        )
        job.validate()
        return job


# Task import handled through TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task import Task
