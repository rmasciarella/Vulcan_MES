"""
Schedule Entity

Represents a production schedule that assigns tasks to machines and operators
over time. Acts as the aggregate root for scheduling operations.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from ..value_objects.duration import Duration


class ScheduleStatus(Enum):
    """Schedule status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScheduleAssignment:
    """A single task assignment within a schedule."""

    def __init__(
        self,
        task_id: UUID,
        machine_id: UUID,
        operator_ids: list[UUID],
        start_time: datetime,
        end_time: datetime,
        setup_duration: Duration,
        processing_duration: Duration,
    ) -> None:
        self.task_id = task_id
        self.machine_id = machine_id
        self.operator_ids = operator_ids.copy()
        self.start_time = start_time
        self.end_time = end_time
        self.setup_duration = setup_duration
        self.processing_duration = processing_duration

    @property
    def total_duration(self) -> Duration:
        """Get total duration of assignment."""
        return self.setup_duration + self.processing_duration

    @property
    def operator_duration(self) -> Duration:
        """Get duration operators are needed."""
        # This would be determined by task requirements
        # For now, assume operators needed for full duration
        return self.total_duration

    def __str__(self) -> str:
        return (
            f"Assignment(task={self.task_id}, machine={self.machine_id}, "
            f"operators={self.operator_ids}, start={self.start_time})"
        )


class Schedule:
    """
    A production schedule that assigns tasks to resources over time.

    This is the aggregate root that maintains consistency across
    all scheduling decisions and enforces business rules.
    """

    def __init__(
        self,
        schedule_id: UUID | None = None,
        name: str = "",
        planning_horizon: Duration | None = None,
        created_by: UUID | None = None,
    ) -> None:
        """
        Initialize a new Schedule.

        Args:
            schedule_id: Unique identifier for the schedule
            name: Human-readable schedule name
            planning_horizon: How far into the future this schedule covers
            created_by: ID of user who created the schedule
        """
        self._id = schedule_id or uuid4()
        self._name = name
        self._planning_horizon = planning_horizon or Duration(days=30)
        self._created_by = created_by
        self._created_at = datetime.now()
        self._updated_at = self._created_at

        # Schedule content
        self._assignments: dict[UUID, ScheduleAssignment] = {}  # task_id -> assignment
        self._job_ids: set[UUID] = set()  # Jobs included in this schedule

        # Schedule properties
        self._status = ScheduleStatus.DRAFT
        self._start_date: datetime | None = None
        self._end_date: datetime | None = None

        # Metrics (calculated when schedule is optimized)
        self._makespan: Duration | None = None
        self._total_tardiness: Duration | None = None
        self._total_cost: float | None = None
        self._resource_utilization: dict[UUID, float] = {}

        # Constraints violated (for validation feedback)
        self._constraint_violations: list[str] = []

    @property
    def id(self) -> UUID:
        """Get schedule ID."""
        return self._id

    @property
    def name(self) -> str:
        """Get schedule name."""
        return self._name

    @property
    def status(self) -> ScheduleStatus:
        """Get schedule status."""
        return self._status

    @property
    def planning_horizon(self) -> Duration:
        """Get planning horizon."""
        return self._planning_horizon

    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at

    @property
    def start_date(self) -> datetime | None:
        """Get schedule start date."""
        return self._start_date

    @property
    def end_date(self) -> datetime | None:
        """Get schedule end date."""
        return self._end_date

    @property
    def assignments(self) -> dict[UUID, ScheduleAssignment]:
        """Get all task assignments."""
        return self._assignments.copy()

    @property
    def job_ids(self) -> set[UUID]:
        """Get job IDs included in schedule."""
        return self._job_ids.copy()

    @property
    def makespan(self) -> Duration | None:
        """Get makespan (total schedule duration)."""
        return self._makespan

    @property
    def total_tardiness(self) -> Duration | None:
        """Get total tardiness across all jobs."""
        return self._total_tardiness

    @property
    def total_cost(self) -> float | None:
        """Get total schedule cost."""
        return self._total_cost

    @property
    def constraint_violations(self) -> list[str]:
        """Get list of constraint violations."""
        return self._constraint_violations.copy()

    @property
    def is_valid(self) -> bool:
        """Check if schedule is valid (no constraint violations)."""
        return len(self._constraint_violations) == 0

    @property
    def is_published(self) -> bool:
        """Check if schedule is published."""
        return self._status in [
            ScheduleStatus.PUBLISHED,
            ScheduleStatus.ACTIVE,
            ScheduleStatus.COMPLETED,
        ]

    def add_job(self, job_id: UUID) -> None:
        """
        Add a job to this schedule.

        Args:
            job_id: Job to include in schedule
        """
        if self._status not in [ScheduleStatus.DRAFT]:
            raise ValueError("Cannot modify published schedule")

        self._job_ids.add(job_id)
        self._mark_updated()

    def remove_job(self, job_id: UUID) -> None:
        """
        Remove a job from this schedule.

        Args:
            job_id: Job to remove
        """
        if self._status not in [ScheduleStatus.DRAFT]:
            raise ValueError("Cannot modify published schedule")

        # Remove all assignments for tasks in this job
        [
            task_id
            for task_id, assignment in self._assignments.items()
            # Would need task repository to check job_id
        ]

        self._job_ids.discard(job_id)
        self._mark_updated()

    def assign_task(
        self,
        task_id: UUID,
        machine_id: UUID,
        operator_ids: list[UUID],
        start_time: datetime,
        end_time: datetime,
        setup_duration: Duration,
        processing_duration: Duration,
    ) -> None:
        """
        Assign a task to resources at a specific time.

        Args:
            task_id: Task to assign
            machine_id: Machine to assign task to
            operator_ids: Operators to assign to task
            start_time: When task should start
            end_time: When task should end
            setup_duration: Setup time required
            processing_duration: Processing time required

        Raises:
            ValueError: If schedule cannot be modified or assignment conflicts
        """
        if self._status not in [ScheduleStatus.DRAFT]:
            raise ValueError("Cannot modify published schedule")

        assignment = ScheduleAssignment(
            task_id=task_id,
            machine_id=machine_id,
            operator_ids=operator_ids,
            start_time=start_time,
            end_time=end_time,
            setup_duration=setup_duration,
            processing_duration=processing_duration,
        )

        self._assignments[task_id] = assignment
        self._update_schedule_bounds(start_time, end_time)
        self._mark_updated()

    def unassign_task(self, task_id: UUID) -> None:
        """
        Remove a task assignment.

        Args:
            task_id: Task to unassign
        """
        if self._status not in [ScheduleStatus.DRAFT]:
            raise ValueError("Cannot modify published schedule")

        self._assignments.pop(task_id, None)
        self._mark_updated()

    def get_assignment(self, task_id: UUID) -> ScheduleAssignment | None:
        """
        Get assignment for a specific task.

        Args:
            task_id: Task to get assignment for

        Returns:
            Task assignment or None if not assigned
        """
        return self._assignments.get(task_id)

    def get_assignments_for_machine(self, machine_id: UUID) -> list[ScheduleAssignment]:
        """
        Get all assignments for a specific machine.

        Args:
            machine_id: Machine to get assignments for

        Returns:
            List of assignments for this machine, sorted by start time
        """
        machine_assignments = [
            assignment
            for assignment in self._assignments.values()
            if assignment.machine_id == machine_id
        ]
        return sorted(machine_assignments, key=lambda a: a.start_time)

    def get_assignments_for_operator(
        self, operator_id: UUID
    ) -> list[ScheduleAssignment]:
        """
        Get all assignments for a specific operator.

        Args:
            operator_id: Operator to get assignments for

        Returns:
            List of assignments for this operator, sorted by start time
        """
        operator_assignments = [
            assignment
            for assignment in self._assignments.values()
            if operator_id in assignment.operator_ids
        ]
        return sorted(operator_assignments, key=lambda a: a.start_time)

    def get_assignments_in_time_window(
        self, start: datetime, end: datetime
    ) -> list[ScheduleAssignment]:
        """
        Get all assignments within a time window.

        Args:
            start: Window start time
            end: Window end time

        Returns:
            List of assignments in the time window
        """
        return [
            assignment
            for assignment in self._assignments.values()
            if (assignment.start_time < end and assignment.end_time > start)
        ]

    def validate_constraints(self) -> list[str]:
        """
        Validate schedule against business constraints.

        Returns:
            List of constraint violation descriptions
        """
        violations = []

        # Check for resource conflicts
        violations.extend(self._check_machine_conflicts())
        violations.extend(self._check_operator_conflicts())

        # Check precedence constraints (would need job/task repository)
        # violations.extend(self._check_precedence_constraints())

        # Check business hours
        violations.extend(self._check_business_hours())

        self._constraint_violations = violations
        return violations

    def _check_machine_conflicts(self) -> list[str]:
        """Check for machine double-booking."""
        violations = []
        machine_assignments = {}

        # Group assignments by machine
        for assignment in self._assignments.values():
            machine_id = assignment.machine_id
            if machine_id not in machine_assignments:
                machine_assignments[machine_id] = []
            machine_assignments[machine_id].append(assignment)

        # Check for overlaps on each machine
        for machine_id, assignments in machine_assignments.items():
            sorted_assignments = sorted(assignments, key=lambda a: a.start_time)

            for i in range(len(sorted_assignments) - 1):
                current = sorted_assignments[i]
                next_assignment = sorted_assignments[i + 1]

                if current.end_time > next_assignment.start_time:
                    violations.append(
                        f"Machine {machine_id} double-booked: tasks {current.task_id} "
                        f"and {next_assignment.task_id} overlap"
                    )

        return violations

    def _check_operator_conflicts(self) -> list[str]:
        """Check for operator double-booking."""
        violations = []
        operator_assignments = {}

        # Group assignments by operator
        for assignment in self._assignments.values():
            for operator_id in assignment.operator_ids:
                if operator_id not in operator_assignments:
                    operator_assignments[operator_id] = []
                operator_assignments[operator_id].append(assignment)

        # Check for overlaps for each operator
        for operator_id, assignments in operator_assignments.items():
            sorted_assignments = sorted(assignments, key=lambda a: a.start_time)

            for i in range(len(sorted_assignments) - 1):
                current = sorted_assignments[i]
                next_assignment = sorted_assignments[i + 1]

                if current.end_time > next_assignment.start_time:
                    violations.append(
                        f"Operator {operator_id} double-booked: tasks {current.task_id} "
                        f"and {next_assignment.task_id} overlap"
                    )

        return violations

    def _check_business_hours(self) -> list[str]:
        """Check that tasks are scheduled during business hours."""
        violations = []

        # Standard business hours (7 AM to 4 PM)
        business_start = 7 * 60  # 7 AM in minutes
        business_end = 16 * 60  # 4 PM in minutes
        lunch_start = 12 * 60  # Noon
        lunch_end = 12 * 60 + 45  # 12:45 PM

        for assignment in self._assignments.values():
            start_minutes = (
                assignment.start_time.hour * 60 + assignment.start_time.minute
            )
            end_minutes = assignment.end_time.hour * 60 + assignment.end_time.minute

            # Check if within business hours
            if start_minutes < business_start or end_minutes > business_end:
                violations.append(
                    f"Task {assignment.task_id} scheduled outside business hours"
                )

            # Check if overlaps lunch break
            if start_minutes < lunch_end and end_minutes > lunch_start:
                violations.append(f"Task {assignment.task_id} overlaps lunch break")

        return violations

    def _update_schedule_bounds(self, start_time: datetime, end_time: datetime) -> None:
        """Update schedule start and end dates based on assignment times."""
        if self._start_date is None or start_time < self._start_date:
            self._start_date = start_time

        if self._end_date is None or end_time > self._end_date:
            self._end_date = end_time

    def _mark_updated(self) -> None:
        """Mark schedule as updated."""
        self._updated_at = datetime.now()

    def calculate_metrics(self, job_due_dates: dict[UUID, datetime]) -> None:
        """
        Calculate schedule performance metrics.

        Args:
            job_due_dates: Mapping of job IDs to due dates
        """
        if not self._assignments:
            return

        # Calculate makespan
        if self._start_date and self._end_date:
            self._makespan = Duration.from_timedelta(self._end_date - self._start_date)

        # Calculate total tardiness (would need job completion times)
        # This requires knowledge of which tasks complete which jobs

        # Calculate resource utilization
        self._calculate_resource_utilization()

    def _calculate_resource_utilization(self) -> None:
        """Calculate utilization for each resource."""
        if not self._start_date or not self._end_date:
            return

        total_time = (self._end_date - self._start_date).total_seconds() / 60  # minutes

        # Machine utilization
        machine_busy_time = {}
        for assignment in self._assignments.values():
            machine_id = assignment.machine_id
            duration = assignment.total_duration.minutes
            machine_busy_time[machine_id] = (
                machine_busy_time.get(machine_id, 0) + duration
            )

        for machine_id, busy_time in machine_busy_time.items():
            self._resource_utilization[machine_id] = busy_time / total_time

    def publish(self) -> None:
        """Publish the schedule for execution."""
        if self._status != ScheduleStatus.DRAFT:
            raise ValueError(f"Cannot publish schedule in {self._status} status")

        # Validate before publishing
        violations = self.validate_constraints()
        if violations:
            raise ValueError(f"Cannot publish schedule with violations: {violations}")

        self._status = ScheduleStatus.PUBLISHED
        self._mark_updated()

    def activate(self) -> None:
        """Activate the schedule for execution."""
        if self._status != ScheduleStatus.PUBLISHED:
            raise ValueError("Can only activate published schedules")

        self._status = ScheduleStatus.ACTIVE
        self._mark_updated()

    def complete(self) -> None:
        """Mark schedule as completed."""
        if self._status != ScheduleStatus.ACTIVE:
            raise ValueError("Can only complete active schedules")

        self._status = ScheduleStatus.COMPLETED
        self._mark_updated()

    def cancel(self) -> None:
        """Cancel the schedule."""
        if self._status == ScheduleStatus.COMPLETED:
            raise ValueError("Cannot cancel completed schedule")

        self._status = ScheduleStatus.CANCELLED
        self._mark_updated()

    def __str__(self) -> str:
        """String representation of schedule."""
        return (
            f"Schedule({self.name}, jobs={len(self._job_ids)}, "
            f"assignments={len(self._assignments)}, status={self._status.value})"
        )

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"Schedule(id={self.id}, name='{self.name}', "
            f"status={self._status.value}, jobs={len(self._job_ids)}, "
            f"assignments={len(self._assignments)}, "
            f"start={self._start_date}, end={self._end_date})"
        )
