"""Task entity for individual work assignments and resource management."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from ...shared.base import BusinessRuleViolation, Entity
from ...shared.validation import (
    BusinessRuleValidators,
    DataSanitizer,
    SchedulingValidators,
    ValidationError,
)
from ..events import (
    TaskAssignmentChanged,
    TaskDelayed,
    TaskStatusChanged,
)
from ..value_objects.common import Duration, TimeWindow
from ..value_objects.enums import AssignmentType, TaskStatus
from ..value_objects.machine_option import MachineOption
from ..value_objects.skill_proficiency import SkillRequirement
from ..value_objects.role_requirement import AttendanceRequirement, RoleRequirement


class OperatorAssignment(BaseModel):
    """Represents an operator assignment to a task."""
    
    # Identity fields
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    
    # Required assignment fields
    task_id: UUID
    operator_id: UUID
    assignment_type: AssignmentType
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None

    def is_valid(self) -> bool:
        """Validate business rules."""
        return bool(self.task_id and self.operator_id)
    
    def mark_updated(self) -> None:
        """Mark the entity as updated."""
        self.updated_at = datetime.utcnow()

    @property
    def is_active(self) -> bool:
        """Check if assignment is currently active."""
        return self.actual_start_time is not None and self.actual_end_time is None

    @property
    def planned_duration(self) -> Duration | None:
        """Get planned duration of assignment."""
        if self.planned_start_time and self.planned_end_time:
            delta = self.planned_end_time - self.planned_start_time
            return Duration(minutes=int(delta.total_seconds() / 60))
        return None

    @property
    def actual_duration(self) -> Duration | None:
        """Get actual duration of assignment."""
        if self.actual_start_time and self.actual_end_time:
            delta = self.actual_end_time - self.actual_start_time
            return Duration(minutes=int(delta.total_seconds() / 60))
        return None

    def start_assignment(self, start_time: datetime) -> None:
        """Start the operator assignment."""
        self.actual_start_time = start_time
        self.mark_updated()

    def complete_assignment(self, end_time: datetime) -> None:
        """Complete the operator assignment."""
        if not self.actual_start_time:
            raise BusinessRuleViolation(
                "ASSIGNMENT_NOT_STARTED",
                "Cannot complete assignment that hasn't been started",
            )

        if end_time <= self.actual_start_time:
            raise BusinessRuleViolation(
                "INVALID_END_TIME", "End time must be after start time"
            )

        self.actual_end_time = end_time
        self.mark_updated()


class Task(Entity):
    """
    Task entity representing a single work assignment in a job.

    Tasks represent instances of operations for specific jobs. They manage
    resource assignments, timing, and status progression while enforcing
    business rules about sequencing and resource allocation.
    """

    job_id: UUID
    operation_id: UUID
    sequence_in_job: int = Field(ge=1, le=100)
    status: TaskStatus = Field(default=TaskStatus.PENDING)

    # Organizational routing
    department: str = Field(default="general", min_length=1, max_length=50)

    # Machine routing options - matches DOMAIN.md specification
    machine_options: list[MachineOption] = Field(default_factory=list)
    # Legacy per-skill requirements (kept for compatibility)
    skill_requirements: list[SkillRequirement] = Field(default_factory=list)
    # New role-based operator requirements (with counts and attendance)
    role_requirements: list[RoleRequirement] = Field(default_factory=list)

    predecessor_ids: list[UUID] = Field(default_factory=list)
    is_critical: bool = Field(default=False)

    # Planning data
    planned_start_time: datetime | None = None
    planned_end_time: datetime | None = None
    planned_duration: Duration | None = None
    planned_setup_duration: Duration | None = Field(default=Duration(minutes=0))

    # Execution data
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    actual_duration: Duration | None = None
    actual_setup_duration: Duration | None = None

    # Resource assignments
    assigned_machine_id: UUID | None = None

    # Tracking and quality
    is_critical_path: bool = Field(default=False)
    delay_minutes: int = Field(default=0, ge=0)
    rework_count: int = Field(default=0, ge=0)
    quality_notes: str | None = None
    notes: str | None = None

    @validator("delay_minutes")
    def validate_delay_minutes(cls, v):
        """Delay minutes cannot be negative."""
        try:
            SchedulingValidators.validate_duration_minutes(v)
            return v
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("rework_count")
    def validate_rework_count(cls, v):
        """Rework count cannot be negative."""
        try:
            BusinessRuleValidators.validate_range("rework_count", v, 0, None)
            return v
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("quality_notes")
    def sanitize_quality_notes(cls, v):
        """Sanitize quality notes input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=500)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    @validator("notes")
    def sanitize_notes(cls, v):
        """Sanitize notes input."""
        if v:
            try:
                return DataSanitizer.sanitize_string(v, max_length=1000)
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    # Operator assignments (managed internally)
    operator_assignments: dict[UUID, OperatorAssignment] = Field(default_factory=dict)

    @validator("sequence_in_job")
    def validate_sequence(cls, v):
        """Sequence must be between 1 and 100."""
        try:
            SchedulingValidators.validate_task_sequence(v)
            return v
        except ValidationError as e:
            raise ValueError(e.message)

    @validator("actual_end_time")
    def end_after_start(cls, v, values):
        """Actual end time must be after actual start time."""
        if v and "actual_start_time" in values and values["actual_start_time"]:
            try:
                BusinessRuleValidators.validate_date_range(
                    "actual_start_time",
                    values["actual_start_time"],
                    "actual_end_time",
                    v,
                )
            except ValidationError as e:
                raise ValueError(e.message)
        return v

    @validator("machine_options")
    def validate_machine_options(cls, v):
        """Task must have at least one machine option when scheduling."""
        # Allow empty during creation, but not when scheduling
        return v

    def is_valid(self) -> bool:
        """Validate business rules."""
        return (
            1 <= self.sequence_in_job <= 100
            and self.delay_minutes >= 0
            and self.rework_count >= 0
        )

    @property
    def is_ready_to_schedule(self) -> bool:
        """Check if task is ready to be scheduled."""
        return self.status == TaskStatus.READY

    @property
    def is_scheduled(self) -> bool:
        """Check if task is scheduled."""
        return self.status == TaskStatus.SCHEDULED

    @property
    def is_active(self) -> bool:
        """Check if task is currently active."""
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def is_complete(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED

    @property
    def requires_machine(self) -> bool:
        """Check if task requires machine assignment."""
        return self.assigned_machine_id is not None

    @property
    def hasoperator_assignments(self) -> bool:
        """Check if task has operator assignments."""
        return len(self.operator_assignments) > 0

    def get_machine_option_for(self, machine_id: UUID) -> MachineOption | None:
        """Return the machine option matching a specific machine id, if present."""
        for opt in self.machine_options:
            if opt.machine_id == machine_id:
                return opt
        return None

    def required_operator_count(self) -> int:
        """Total number of operators required across all role requirements."""
        if self.role_requirements:
            return sum(r.count for r in self.role_requirements)
        # Fallback: if legacy skill requirements imply single operator
        return 1 if self.skill_requirements else 0

    def operator_required_duration_minutes(
        self, option: MachineOption, role: RoleRequirement
    ) -> int:
        """
        Compute the duration in minutes that operators of a role are required,
        based on the machine option attendance and role attendance.
        """
        # If either requires full duration, use full; otherwise setup only
        if (
            option.requires_operator_full_duration
            or role.attendance == AttendanceRequirement.FULL_DURATION
        ):
            return int(option.total_duration().minutes)
        return int(option.setup_duration.minutes)

    @property
    def activeoperator_assignments(self) -> list[OperatorAssignment]:
        """Get currently active operator assignments."""
        return [
            assignment
            for assignment in self.operator_assignments.values()
            if assignment.is_active
        ]

    @property
    def planned_time_window(self) -> TimeWindow | None:
        """Get planned time window for this task."""
        if self.planned_start_time and self.planned_end_time:
            return TimeWindow(
                start_time=self.planned_start_time, end_time=self.planned_end_time
            )
        return None

    @property
    def actual_time_window(self) -> TimeWindow | None:
        """Get actual time window for this task."""
        if self.actual_start_time and self.actual_end_time:
            return TimeWindow(
                start_time=self.actual_start_time, end_time=self.actual_end_time
            )
        return None

    @property
    def is_delayed(self) -> bool:
        """Check if task is delayed."""
        return self.delay_minutes > 0

    @property
    def has_rework(self) -> bool:
        """Check if task required rework."""
        return self.rework_count > 0

    def mark_ready(self) -> None:
        """
        Mark task as ready for scheduling.

        Raises:
            BusinessRuleViolation: If task is not in pending state
        """
        if not self.status.can_transition_to(TaskStatus.READY):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot mark task as ready from status {self.status}",
            )

        self._change_status(TaskStatus.READY, "prerequisites_met")

    def schedule(
        self, start_time: datetime, end_time: datetime, machine_id: UUID | None = None
    ) -> None:
        """
        Schedule the task with specific timing and optional machine.

        Args:
            start_time: Planned start time
            end_time: Planned end time
            machine_id: Optional machine assignment

        Raises:
            BusinessRuleViolation: If task is not ready or timing is invalid
        """
        if not self.status.can_transition_to(TaskStatus.SCHEDULED):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot schedule task from status {self.status}",
            )

        if start_time >= end_time:
            raise BusinessRuleViolation(
                "INVALID_SCHEDULE_TIME", "Start time must be before end time"
            )

        # Check for delays
        if self.planned_start_time and start_time > self.planned_start_time:
            self.delay_minutes = int(
                (start_time - self.planned_start_time).total_seconds() / 60
            )

            self.add_domain_event(
                TaskDelayed(
                    aggregate_id=self.id,
                    task_id=self.id,
                    job_id=self.job_id,
                    operation_sequence=self.sequence_in_job,
                    original_planned_start=self.planned_start_time,
                    new_planned_start=start_time,
                    delay_minutes=self.delay_minutes,
                    reason="resource_constraints",
                )
            )

        old_machine = self.assigned_machine_id

        self.planned_start_time = start_time
        self.planned_end_time = end_time
        self.assigned_machine_id = machine_id

        duration = end_time - start_time
        self.planned_duration = Duration(minutes=int(duration.total_seconds() / 60))

        self._change_status(TaskStatus.SCHEDULED, "scheduled_with_resources")

        # Raise assignment change event if machine changed
        if old_machine != machine_id:
            self.add_domain_event(
                TaskAssignmentChanged(
                    aggregate_id=self.id,
                    task_id=self.id,
                    job_id=self.job_id,
                    operation_sequence=self.sequence_in_job,
                    old_machine_id=old_machine,
                    new_machine_id=machine_id,
                    operator_assignments=list(self.operator_assignments.keys()),
                    reason="task_scheduled",
                )
            )

    def start(self, start_time: datetime | None = None) -> None:
        """
        Start task execution.

        Args:
            start_time: Actual start time (defaults to now)

        Raises:
            BusinessRuleViolation: If task is not scheduled
        """
        if not self.status.can_transition_to(TaskStatus.IN_PROGRESS):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot start task from status {self.status}",
            )

        self.actual_start_time = start_time or datetime.utcnow()
        self._change_status(TaskStatus.IN_PROGRESS, "task_started")

        # Start all operator assignments
        for assignment in self.operator_assignments.values():
            if assignment.assignment_type == AssignmentType.FULL_DURATION:
                assignment.start_assignment(self.actual_start_time)

    def complete(self, end_time: datetime | None = None) -> None:
        """
        Complete task execution.

        Args:
            end_time: Actual completion time (defaults to now)

        Raises:
            BusinessRuleViolation: If task is not in progress
        """
        if not self.status.can_transition_to(TaskStatus.COMPLETED):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot complete task from status {self.status}",
            )

        if not self.actual_start_time:
            raise BusinessRuleViolation(
                "TASK_NOT_STARTED", "Cannot complete task that hasn't been started"
            )

        completion_time = end_time or datetime.utcnow()

        if completion_time <= self.actual_start_time:
            raise BusinessRuleViolation(
                "INVALID_COMPLETION_TIME", "Completion time must be after start time"
            )

        self.actual_end_time = completion_time

        duration = completion_time - self.actual_start_time
        self.actual_duration = Duration(minutes=int(duration.total_seconds() / 60))

        self._change_status(TaskStatus.COMPLETED, "task_completed")

        # Complete all active operator assignments
        for assignment in self.activeoperator_assignments:
            assignment.complete_assignment(completion_time)

    def fail(self, reason: str, failure_time: datetime | None = None) -> None:
        """
        Mark task as failed.

        Args:
            reason: Reason for failure
            failure_time: When failure occurred (defaults to now)
        """
        if not self.status.can_transition_to(TaskStatus.FAILED):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot fail task from status {self.status}",
            )

        self.actual_end_time = failure_time or datetime.utcnow()
        if self.actual_start_time and self.actual_end_time:
            duration = self.actual_end_time - self.actual_start_time
            self.actual_duration = Duration(minutes=int(duration.total_seconds() / 60))

        self._change_status(TaskStatus.FAILED, reason)

    def cancel(self, reason: str) -> None:
        """
        Cancel the task.

        Args:
            reason: Reason for cancellation
        """
        if not self.status.can_transition_to(TaskStatus.CANCELLED):
            raise BusinessRuleViolation(
                "INVALID_STATUS_TRANSITION",
                f"Cannot cancel task from status {self.status}",
            )

        self._change_status(TaskStatus.CANCELLED, reason)

    def add_operator_assignment(self, assignment: OperatorAssignment) -> None:
        """
        Add an operator assignment to the task.

        Args:
            assignment: Operator assignment to add

        Raises:
            BusinessRuleViolation: If assignment conflicts
        """
        if assignment.task_id != self.id:
            raise BusinessRuleViolation(
                "ASSIGNMENT_TASK_MISMATCH",
                "Assignment task_id must match this task's ID",
            )

        if assignment.operator_id in self.operator_assignments:
            raise BusinessRuleViolation(
                "DUPLICATE_OPERATOR_ASSIGNMENT",
                f"Operator {assignment.operator_id} is already assigned to this task",
            )

        self.operator_assignments[assignment.operator_id] = assignment
        self.mark_updated()

    def remove_operator_assignment(self, operator_id: UUID) -> None:
        """
        Remove an operator assignment from the task.

        Args:
            operator_id: ID of operator to unassign

        Raises:
            BusinessRuleViolation: If operator is actively working
        """
        assignment = self.operator_assignments.get(operator_id)
        if not assignment:
            return  # Assignment doesn't exist

        if assignment.is_active:
            raise BusinessRuleViolation(
                "CANNOT_REMOVE_ACTIVE_ASSIGNMENT",
                f"Cannot remove operator {operator_id} while actively working on task",
            )

        del self.operator_assignments[operator_id]
        self.mark_updated()

    def record_rework(self, reason: str) -> None:
        """
        Record that task required rework.

        Args:
            reason: Reason for rework
        """
        self.rework_count += 1
        if self.notes:
            self.notes += f"\nRework #{self.rework_count}: {reason}"
        else:
            self.notes = f"Rework #{self.rework_count}: {reason}"
        self.mark_updated()

    def mark_critical_path(self) -> None:
        """Mark this task as being on the critical path."""
        if not self.is_critical_path:
            self.is_critical_path = True
            self.mark_updated()

    def remove_critical_path_marking(self) -> None:
        """Remove critical path marking from this task."""
        if self.is_critical_path:
            self.is_critical_path = False
            self.mark_updated()

    def reschedule(self, new_start: datetime, new_end: datetime, reason: str) -> None:
        """
        Reschedule the task to new times.

        Args:
            new_start: New planned start time
            new_end: New planned end time
            reason: Reason for rescheduling

        Raises:
            BusinessRuleViolation: If task is in progress or times are invalid
        """
        if self.status == TaskStatus.IN_PROGRESS:
            raise BusinessRuleViolation(
                "CANNOT_RESCHEDULE_ACTIVE_TASK",
                "Cannot reschedule task that is in progress",
            )

        if new_start >= new_end:
            raise BusinessRuleViolation(
                "INVALID_RESCHEDULE_TIME", "New start time must be before new end time"
            )

        old_start = self.planned_start_time

        self.planned_start_time = new_start
        self.planned_end_time = new_end

        duration = new_end - new_start
        self.planned_duration = Duration(minutes=int(duration.total_seconds() / 60))

        # Check for delays
        if old_start and new_start > old_start:
            additional_delay = int((new_start - old_start).total_seconds() / 60)
            self.delay_minutes += additional_delay

            self.add_domain_event(
                TaskDelayed(
                    aggregate_id=self.id,
                    task_id=self.id,
                    job_id=self.job_id,
                    operation_sequence=self.sequence_in_job,
                    original_planned_start=old_start,
                    new_planned_start=new_start,
                    delay_minutes=additional_delay,
                    reason=reason,
                )
            )

        self.mark_updated()

    def _change_status(self, new_status: TaskStatus, reason: str) -> None:
        """Internal method to change task status and raise events."""
        old_status = self.status
        self.status = new_status
        self.mark_updated()

        self.add_domain_event(
            TaskStatusChanged(
                aggregate_id=self.id,
                task_id=self.id,
                job_id=self.job_id,
                operation_sequence=self.sequence_in_job,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
            )
        )

    def get_task_summary(self) -> dict:
        """Get task information summary."""
        return {
            "sequence_in_job": self.sequence_in_job,
            "status": self.status.value,
            "planned_duration": str(self.planned_duration)
            if self.planned_duration
            else None,
            "actual_duration": str(self.actual_duration)
            if self.actual_duration
            else None,
            "is_critical_path": self.is_critical_path,
            "is_delayed": self.is_delayed,
            "delay_minutes": self.delay_minutes,
            "rework_count": self.rework_count,
            "has_machine": self.requires_machine,
            "operator_count": len(self.operator_assignments),
            "active_operators": len(self.activeoperator_assignments),
            "planned_start": self.planned_start_time.isoformat()
            if self.planned_start_time
            else None,
            "planned_end": self.planned_end_time.isoformat()
            if self.planned_end_time
            else None,
        }

    @staticmethod
    def create(
        job_id: UUID,
        operation_id: UUID,
        sequence_in_job: int,
        planned_duration_minutes: int | None = None,
        setup_duration_minutes: int = 0,
    ) -> "Task":
        """
        Factory method to create a new Task.

        Args:
            job_id: ID of the job this task belongs to
            operation_id: ID of the operation being performed
            sequence_in_job: Sequence number within the job
            planned_duration_minutes: Planned duration in minutes
            setup_duration_minutes: Setup duration in minutes

        Returns:
            New Task instance
        """
        task = Task(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=sequence_in_job,
            machine_options=[],  # Must be set after creation
            skill_requirements=[],
            predecessor_ids=[],
            is_critical=False,
            planned_duration=Duration(minutes=planned_duration_minutes)
            if planned_duration_minutes
            else None,
            planned_setup_duration=Duration(minutes=setup_duration_minutes),
        )
        task.validate()
        return task

    def can_start(self, predecessor_statuses: dict[UUID, TaskStatus]) -> bool:
        """
        Check if all predecessors are complete.
        Matches DOMAIN.md specification exactly.

        Args:
            predecessor_statuses: Map of predecessor task IDs to their current status

        Returns:
            True if all predecessors are completed
        """
        for pred_id in self.predecessor_ids:
            if predecessor_statuses.get(pred_id) != TaskStatus.COMPLETED:
                return False
        return True
