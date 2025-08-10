"""
Constraint Validation Service

Validates scheduling constraints including precedence, WIP limits, skills, and business hours.
This service contains the core business logic for ensuring schedule validity.
"""

from datetime import datetime
from uuid import UUID

from ..entities.machine import Machine
from ..entities.operator import Operator
from ..entities.schedule import Schedule, ScheduleAssignment
from ..entities.task import Task
from ..repositories.job_repository import JobRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.task_repository import TaskRepository


class WIPZone:
    """Represents a Work-In-Progress constraint zone."""

    def __init__(
        self, start_position: int, end_position: int, max_jobs: int, name: str = ""
    ):
        self.start_position = start_position
        self.end_position = end_position
        self.max_jobs = max_jobs
        self.name = name or f"Zone_{start_position}_{end_position}"

    def contains_position(self, position: int) -> bool:
        """Check if a task position falls within this zone."""
        return self.start_position <= position <= self.end_position


class ConstraintValidationService:
    """
    Service for validating scheduling constraints.

    This service encapsulates the business logic for validating various
    scheduling constraints including precedence, resource conflicts,
    skill requirements, and business rules.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
    ) -> None:
        """
        Initialize the constraint validation service.

        Args:
            job_repository: Job data access interface
            task_repository: Task data access interface
            operator_repository: Operator data access interface
            machine_repository: Machine data access interface
        """
        self._job_repository = job_repository
        self._task_repository = task_repository
        self._operator_repository = operator_repository
        self._machine_repository = machine_repository

        # Business hours configuration (from solver.py)
        self._work_start_minutes = 7 * 60  # 7 AM
        self._work_end_minutes = 16 * 60  # 4 PM
        self._lunch_start_minutes = 12 * 60  # Noon
        self._lunch_end_minutes = 12 * 60 + 45  # 12:45 PM

        # Holiday dates (configurable)
        self._holiday_days: set[int] = {
            5,
            12,
            26,
        }  # Days from start of planning horizon

        # WIP zones configuration (from solver.py)
        self._wip_zones = [
            WIPZone(0, 30, 3, "Initial Processing"),
            WIPZone(31, 60, 2, "Bottleneck Zone"),
            WIPZone(61, 99, 3, "Final Processing"),
        ]

        # Critical sequences requiring strict ordering
        self._critical_sequences = [
            (20, 28, "Critical Welding"),
            (35, 42, "Critical Machining"),
            (60, 65, "Critical Assembly"),
            (85, 92, "Critical Inspection"),
        ]

    async def validate_schedule(self, schedule: Schedule) -> list[str]:
        """
        Validate all constraints for a complete schedule.

        Args:
            schedule: Schedule to validate

        Returns:
            List of constraint violation descriptions

        Raises:
            RepositoryError: If data access fails
        """
        violations = []

        # Validate individual assignments
        for assignment in schedule.assignments.values():
            violations.extend(await self._validate_assignment(assignment, schedule))

        # Validate resource conflicts across assignments
        violations.extend(await self._validate_resource_conflicts(schedule))

        # Validate precedence constraints
        violations.extend(await self._validate_precedence_constraints(schedule))

        # Validate WIP limits
        violations.extend(await self._validate_wip_constraints(schedule))

        # Validate critical sequences
        violations.extend(await self._validate_critical_sequences(schedule))

        return violations

    async def validate_task_assignment(
        self,
        task: Task,
        machine: Machine,
        operators: list[Operator],
        start_time: datetime,
        end_time: datetime,
    ) -> list[str]:
        """
        Validate a single task assignment against all constraints.

        Args:
            task: Task to assign
            machine: Machine to assign to
            operators: Operators to assign
            start_time: Proposed start time
            end_time: Proposed end time

        Returns:
            List of constraint violations
        """
        violations = []

        # Validate machine capability
        violations.extend(self._validate_machine_capability(task, machine))

        # Validate operator skills
        violations.extend(self._validate_operator_skills(task, operators))

        # Validate business hours
        violations.extend(self._validate_business_hours(task, start_time, end_time))

        # Validate operator count
        violations.extend(self._validate_operator_count(task, operators))

        return violations

    async def validate_precedence_for_job(
        self, job_id: UUID, schedule: Schedule
    ) -> list[str]:
        """
        Validate precedence constraints for all tasks in a job.

        Args:
            job_id: Job to validate
            schedule: Current schedule

        Returns:
            List of precedence violations
        """
        violations = []

        # Get all tasks for the job
        tasks = await self._task_repository.get_by_job_id(job_id)
        tasks.sort(key=lambda t: t.position_in_job)

        # Validate sequential precedence
        for i in range(len(tasks) - 1):
            current_task = tasks[i]
            next_task = tasks[i + 1]

            current_assignment = schedule.get_assignment(current_task.id)
            next_assignment = schedule.get_assignment(next_task.id)

            if current_assignment and next_assignment:
                if next_assignment.start_time < current_assignment.end_time:
                    violations.append(
                        f"Task {next_task.id} starts before predecessor {current_task.id} completes"
                    )

        return violations

    async def validate_wip_limits(
        self, schedule: Schedule, job_ids: list[UUID]
    ) -> list[str]:
        """
        Validate Work-In-Progress limits for all zones.

        Args:
            schedule: Current schedule
            job_ids: Jobs to validate

        Returns:
            List of WIP violations
        """
        violations = []

        for zone in self._wip_zones:
            violations.extend(
                await self._validate_zone_wip_limit(schedule, job_ids, zone)
            )

        return violations

    async def _validate_assignment(
        self, assignment: ScheduleAssignment, schedule: Schedule
    ) -> list[str]:
        """Validate a single assignment."""
        violations = []

        try:
            # Get entities
            task = await self._task_repository.get_by_id(assignment.task_id)
            machine = await self._machine_repository.get_by_id(assignment.machine_id)
            operators = []
            for op_id in assignment.operator_ids:
                operator = await self._operator_repository.get_by_id(op_id)
                if operator:
                    operators.append(operator)

            if not task or not machine:
                violations.append(
                    f"Task or machine not found for assignment {assignment.task_id}"
                )
                return violations

            # Validate assignment
            violations.extend(
                await self.validate_task_assignment(
                    task, machine, operators, assignment.start_time, assignment.end_time
                )
            )

        except Exception as e:
            violations.append(
                f"Error validating assignment {assignment.task_id}: {str(e)}"
            )

        return violations

    async def _validate_resource_conflicts(self, schedule: Schedule) -> list[str]:
        """Validate that no resources are double-booked."""
        violations = []

        # Check machine conflicts
        machine_assignments: dict[UUID, list[ScheduleAssignment]] = {}
        for assignment in schedule.assignments.values():
            machine_id = assignment.machine_id
            if machine_id not in machine_assignments:
                machine_assignments[machine_id] = []
            machine_assignments[machine_id].append(assignment)

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

        # Check operator conflicts
        operator_assignments: dict[UUID, list[ScheduleAssignment]] = {}
        for assignment in schedule.assignments.values():
            for operator_id in assignment.operator_ids:
                if operator_id not in operator_assignments:
                    operator_assignments[operator_id] = []
                operator_assignments[operator_id].append(assignment)

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

    async def _validate_precedence_constraints(self, schedule: Schedule) -> list[str]:
        """Validate precedence constraints across all jobs."""
        violations = []

        # Group assignments by job
        for job_id in schedule.job_ids:
            job_violations = await self.validate_precedence_for_job(job_id, schedule)
            violations.extend(job_violations)

        return violations

    async def _validate_wip_constraints(self, schedule: Schedule) -> list[str]:
        """Validate WIP constraints for all zones."""
        violations = []

        job_ids = list(schedule.job_ids)
        wip_violations = await self.validate_wip_limits(schedule, job_ids)
        violations.extend(wip_violations)

        return violations

    async def _validate_critical_sequences(self, schedule: Schedule) -> list[str]:
        """Validate critical sequence constraints."""
        violations = []

        for start_pos, end_pos, sequence_name in self._critical_sequences:
            # Find jobs that have tasks in this critical sequence
            job_sequences = await self._get_job_sequences_in_range(
                schedule, start_pos, end_pos
            )

            # Validate that jobs don't overlap in critical sequences
            if len(job_sequences) > 1:
                sorted_sequences = sorted(
                    job_sequences, key=lambda x: x[1]
                )  # Sort by start time

                for i in range(len(sorted_sequences) - 1):
                    current_job, current_start, current_end = sorted_sequences[i]
                    next_job, next_start, next_end = sorted_sequences[i + 1]

                    if next_start < current_end:
                        violations.append(
                            f"Critical sequence {sequence_name} violation: "
                            f"Job {next_job} enters before Job {current_job} exits"
                        )

        return violations

    async def _get_job_sequences_in_range(
        self, schedule: Schedule, start_pos: int, end_pos: int
    ) -> list[tuple[UUID, datetime, datetime]]:
        """Get job sequences that overlap with a position range."""
        sequences = []

        for job_id in schedule.job_ids:
            tasks = await self._task_repository.get_by_job_id(job_id)

            # Find first and last task in range
            first_task_time = None
            last_task_time = None

            for task in tasks:
                if start_pos <= task.position_in_job <= end_pos:
                    assignment = schedule.get_assignment(task.id)
                    if assignment:
                        if first_task_time is None:
                            first_task_time = assignment.start_time
                        last_task_time = assignment.end_time

            if first_task_time and last_task_time:
                sequences.append((job_id, first_task_time, last_task_time))

        return sequences

    async def _validate_zone_wip_limit(
        self, schedule: Schedule, job_ids: list[UUID], zone: WIPZone
    ) -> list[str]:
        """Validate WIP limit for a specific zone."""
        violations = []

        # This is a simplified implementation
        # Full implementation would check WIP at all time points
        jobs_in_zone = 0
        for job_id in job_ids:
            if await self._job_overlaps_zone(job_id, zone, schedule):
                jobs_in_zone += 1

        if jobs_in_zone > zone.max_jobs:
            violations.append(
                f"WIP limit exceeded in {zone.name}: {jobs_in_zone} > {zone.max_jobs}"
            )

        return violations

    async def _job_overlaps_zone(
        self, job_id: UUID, zone: WIPZone, schedule: Schedule
    ) -> bool:
        """Check if a job has any tasks in the WIP zone."""
        tasks = await self._task_repository.get_by_job_id(job_id)

        for task in tasks:
            if zone.contains_position(task.position_in_job):
                assignment = schedule.get_assignment(task.id)
                if assignment:
                    return True

        return False

    def _validate_machine_capability(self, task: Task, machine: Machine) -> list[str]:
        """Validate that machine can perform the task."""
        violations = []

        if not machine.can_perform_task_type(task.task_type.value):
            violations.append(
                f"Machine {machine.id} cannot perform task type {task.task_type.value}"
            )

        return violations

    def _validate_operator_skills(
        self, task: Task, operators: list[Operator]
    ) -> list[str]:
        """Validate that operators have required skills."""
        violations = []

        for skill_req in task.skill_requirements:
            # Check if at least one operator has the required skill
            has_skill = False
            for operator in operators:
                if operator.has_skill(skill_req.skill_type, skill_req.minimum_level):
                    has_skill = True
                    break

            if not has_skill:
                violations.append(
                    f"No operator has required skill {skill_req.skill_type} "
                    f"(level {skill_req.minimum_level}) for task {task.id}"
                )

        return violations

    def _validate_business_hours(
        self, task: Task, start_time: datetime, end_time: datetime
    ) -> list[str]:
        """Validate that attended tasks are scheduled during business hours."""
        violations = []

        # Only validate business hours for attended tasks
        if not task.is_attended:
            return violations

        # Convert to minutes within day
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        # Check work hours
        if (
            start_minutes < self._work_start_minutes
            or end_minutes > self._work_end_minutes
        ):
            violations.append(
                f"Task {task.id} scheduled outside business hours "
                f"({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
            )

        # Check lunch break
        if (
            start_minutes < self._lunch_end_minutes
            and end_minutes > self._lunch_start_minutes
        ):
            violations.append(f"Task {task.id} overlaps lunch break")

        # Check holidays (simplified - would need proper date handling)
        day_of_period = start_time.day  # Simplified
        if day_of_period in self._holiday_days:
            violations.append(
                f"Task {task.id} scheduled on holiday (day {day_of_period})"
            )

        return violations

    def _validate_operator_count(
        self, task: Task, operators: list[Operator]
    ) -> list[str]:
        """Validate that correct number of operators are assigned."""
        violations = []

        required_count = 2 if task.requires_multiple_operators() else 1
        actual_count = len(operators)

        if actual_count != required_count:
            violations.append(
                f"Task {task.id} requires {required_count} operators, "
                f"but {actual_count} assigned"
            )

        # For multi-operator tasks, ensure different operators
        if required_count > 1 and len({op.id for op in operators}) != len(operators):
            violations.append(f"Task {task.id} has duplicate operator assignments")

        return violations

    def set_business_hours(self, start_hour: int, end_hour: int) -> None:
        """
        Configure business hours.

        Args:
            start_hour: Work start hour (0-23)
            end_hour: Work end hour (0-23)
        """
        self._work_start_minutes = start_hour * 60
        self._work_end_minutes = end_hour * 60

    def set_lunch_break(self, start_hour: int, duration_minutes: int) -> None:
        """
        Configure lunch break.

        Args:
            start_hour: Lunch start hour (0-23)
            duration_minutes: Lunch duration in minutes
        """
        self._lunch_start_minutes = start_hour * 60
        self._lunch_end_minutes = self._lunch_start_minutes + duration_minutes

    def add_wip_zone(
        self, start_pos: int, end_pos: int, max_jobs: int, name: str = ""
    ) -> None:
        """
        Add a WIP constraint zone.

        Args:
            start_pos: Starting task position
            end_pos: Ending task position
            max_jobs: Maximum jobs allowed in zone
            name: Zone name
        """
        zone = WIPZone(start_pos, end_pos, max_jobs, name)
        self._wip_zones.append(zone)

    def add_critical_sequence(self, start_pos: int, end_pos: int, name: str) -> None:
        """
        Add a critical sequence constraint.

        Args:
            start_pos: Starting task position
            end_pos: Ending task position
            name: Sequence name
        """
        self._critical_sequences.append((start_pos, end_pos, name))

    def set_holiday_days(self, holiday_days: set[int]) -> None:
        """
        Set holiday days.

        Args:
            holiday_days: Set of holiday day numbers
        """
        self._holiday_days = holiday_days
