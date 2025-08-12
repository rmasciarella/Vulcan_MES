"""
Schedule Validator Domain Service

Domain service for validating schedule constraints.
Matches DOMAIN.md specification exactly.
"""

from ..entities.job import Job
from ..entities.machine import Machine
from ..entities.operator import Operator
from ..entities.schedule import Schedule
from ..value_objects.business_calendar import BusinessCalendar
from ..value_objects.enums import TaskStatus


class ScheduleValidator:
    """
    Domain service for validating schedule constraints.
    Matches DOMAIN.md specification exactly.
    """

    def __init__(self, calendar: BusinessCalendar):
        self._calendar = calendar

    def validate_precedence_constraints(
        self, job: Job, schedule: Schedule
    ) -> list[str]:
        """
        Validate that all precedence constraints are satisfied.
        Matches DOMAIN.md specification exactly.

        Args:
            job: Job to validate
            schedule: Schedule to check against

        Returns:
            List of constraint violations
        """
        violations = []

        for task in job.get_tasks_in_sequence():
            assignment = schedule.get_assignment(task.id)
            if not assignment:
                continue

            _, _, task_window = assignment

            for pred_id in task.predecessor_ids:
                pred_assignment = schedule.get_assignment(pred_id)
                if not pred_assignment:
                    violations.append(
                        f"Predecessor {pred_id} not scheduled for task {task.id}"
                    )
                    continue

                _, _, pred_window = pred_assignment
                if pred_window.end > task_window.start:
                    violations.append(
                        f"Task {task.id} starts before predecessor {pred_id} completes"
                    )

        return violations

    def validate_calendar_constraints(self, schedule: Schedule) -> list[str]:
        """
        Validate that all tasks are scheduled during business hours.
        Matches DOMAIN.md specification exactly.

        Args:
            schedule: Schedule to validate

        Returns:
            List of constraint violations
        """
        violations = []

        for task_id, (_, _, window) in schedule._assignments.items():
            if not self._calendar.is_working_time(window.start):
                violations.append(f"Task {task_id} starts outside business hours")
            if not self._calendar.is_working_time(window.end):
                violations.append(f"Task {task_id} ends outside business hours")

        return violations

    def validate_resource_conflicts(self, schedule: Schedule) -> list[str]:
        """
        Validate no resource conflicts exist.
        Matches DOMAIN.md specification exactly.

        Args:
            schedule: Schedule to validate

        Returns:
            List of resource conflicts
        """
        violations = []

        # Check machine conflicts
        for machine_id, windows in schedule._machine_timeline.items():
            for i, window1 in enumerate(windows):
                for window2 in windows[i + 1 :]:
                    if window1.overlaps(window2):
                        violations.append(
                            f"Machine {machine_id} has overlapping assignments"
                        )

        # Check operator conflicts
        for operator_id, windows in schedule._operator_timeline.items():
            for i, window1 in enumerate(windows):
                for window2 in windows[i + 1 :]:
                    if window1.overlaps(window2):
                        violations.append(
                            f"Operator {operator_id} has overlapping assignments"
                        )

        return violations

    def validate_skill_requirements(
        self,
        schedule: Schedule,
        machines: dict[str, Machine],
        operators: dict[str, Operator],
    ) -> list[str]:
        """
        Validate that operators meet skill requirements for assigned machines.

        Args:
            schedule: Schedule to validate
            machines: Available machines mapped by ID
            operators: Available operators mapped by ID

        Returns:
            List of skill requirement violations
        """
        violations = []

        for task_id, (
            machine_id,
            operator_ids,
            _window,
        ) in schedule._assignments.items():
            machine = machines.get(str(machine_id))
            if not machine:
                violations.append(f"Machine {machine_id} not found for task {task_id}")
                continue

            for operator_id in operator_ids:
                operator = operators.get(str(operator_id))
                if not operator:
                    violations.append(
                        f"Operator {operator_id} not found for task {task_id}"
                    )
                    continue

                if not operator.can_operate_machine(machine):
                    violations.append(
                        f"Operator {operator_id} lacks required skills for machine {machine_id} "
                        f"on task {task_id}"
                    )

        return violations

    def validate_capacity_constraints(
        self, schedule: Schedule, machine_capacities: dict[str, int]
    ) -> list[str]:
        """
        Validate that machine capacity constraints are not violated.

        Args:
            schedule: Schedule to validate
            machine_capacities: Machine capacity limits

        Returns:
            List of capacity violations
        """
        violations = []

        # Track concurrent usage by machine and time
        machine_usage = {}

        for task_id, (
            machine_id,
            _operator_ids,
            window,
        ) in schedule._assignments.items():
            machine_key = str(machine_id)
            if machine_key not in machine_usage:
                machine_usage[machine_key] = []

            machine_usage[machine_key].append((window.start, window.end, task_id))

        # Check for capacity violations
        for machine_id, usages in machine_usage.items():
            capacity = machine_capacities.get(machine_id, 1)  # Default capacity of 1

            # Sort by start time
            usages.sort(key=lambda x: x[0])

            # Check overlapping periods
            for i, (_start1, end1, task1) in enumerate(usages):
                concurrent_count = 1
                concurrent_tasks = [task1]

                for start2, _end2, task2 in usages[i + 1 :]:
                    if start2 < end1:  # Overlap detected
                        concurrent_count += 1
                        concurrent_tasks.append(task2)

                        if concurrent_count > capacity:
                            violations.append(
                                f"Machine {machine_id} capacity exceeded: "
                                f"{concurrent_count} concurrent tasks "
                                f"({', '.join(str(t) for t in concurrent_tasks)}) "
                                f"but capacity is {capacity}"
                            )
                            break

        return violations

    def validate_complete(self, job: Job, schedule: Schedule) -> tuple[bool, list[str]]:
        """
        Complete validation of schedule for a job.
        Matches DOMAIN.md specification exactly.

        Args:
            job: Job to validate
            schedule: Schedule to validate

        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        all_violations = []

        all_violations.extend(self.validate_precedence_constraints(job, schedule))
        all_violations.extend(self.validate_calendar_constraints(schedule))
        all_violations.extend(self.validate_resource_conflicts(schedule))

        return len(all_violations) == 0, all_violations

    def validate_task_readiness(self, job: Job) -> list[str]:
        """
        Validate that tasks are ready based on predecessor completion.

        Args:
            job: Job to validate

        Returns:
            List of readiness violations
        """
        violations = []

        for task in job.get_tasks_in_sequence():
            if task.status == TaskStatus.READY:
                # Check if all predecessors are actually completed
                predecessor_statuses = {}
                for pred_id in task.predecessor_ids:
                    pred_task = job.get_task(pred_id)
                    if pred_task:
                        predecessor_statuses[pred_id] = pred_task.status
                    else:
                        violations.append(
                            f"Predecessor task {pred_id} not found for task {task.id}"
                        )

                if not task.can_start(predecessor_statuses):
                    violations.append(
                        f"Task {task.id} marked as ready but predecessors are not completed"
                    )

        return violations

    def validate_due_date_feasibility(self, job: Job, schedule: Schedule) -> list[str]:
        """
        Validate that job can meet its due date based on schedule.

        Args:
            job: Job to validate
            schedule: Current schedule

        Returns:
            List of due date violations
        """
        violations = []

        if not job.due_date:
            return violations  # No due date to validate

        # Find latest task completion time
        latest_completion = None

        for task in job.get_tasks_in_sequence():
            assignment = schedule.get_assignment(task.id)
            if assignment:
                _, _, window = assignment
                if latest_completion is None or window.end > latest_completion:
                    latest_completion = window.end

        if latest_completion and latest_completion > job.due_date:
            delay_hours = (latest_completion - job.due_date).total_seconds() / 3600
            violations.append(
                f"Job {job.job_number} will miss due date by {delay_hours:.1f} hours"
            )

        return violations

    def validate_work_in_progress_limits(
        self, schedule: Schedule, wip_limits: dict[str, int]
    ) -> list[str]:
        """
        Validate work-in-progress limits by zone or resource.

        Args:
            schedule: Schedule to validate
            wip_limits: WIP limits by zone/resource

        Returns:
            List of WIP violations
        """
        violations = []

        # This would need zone information which isn't in the current model
        # Placeholder for when zone information is added to machines

        return violations
