"""
Resource Allocation Service

Handles assignment of machines and operators to tasks based on availability,
capabilities, and optimization criteria.
"""

from datetime import datetime, timedelta
from uuid import UUID

from ...shared.exceptions import (
    MachineUnavailableError,
    OperatorUnavailableError,
)
from ..entities.job import Job
from ..entities.machine import Machine, MachineStatus
from ..entities.operator import Operator, OperatorStatus
from ..entities.task import Task
from ..repositories.job_repository import JobRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.task_repository import TaskRepository


class ResourceAllocation:
    """Represents a resource allocation decision."""

    def __init__(
        self,
        task_id: UUID,
        machine_id: UUID,
        operator_ids: list[UUID],
        allocation_score: float = 0.0,
        reasoning: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.machine_id = machine_id
        self.operator_ids = operator_ids.copy()
        self.allocation_score = allocation_score
        self.reasoning = reasoning or ""


class ResourceAllocationService:
    """
    Service for allocating machines and operators to tasks.

    This service implements the business logic for matching tasks
    with the best available resources based on capabilities,
    availability, and cost considerations.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
    ) -> None:
        """
        Initialize the resource allocation service.

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

        # Allocation preferences
        self._prefer_lowest_cost = True
        self._prefer_highest_skill = False
        self._load_balancing_enabled = True

    async def allocate_resources_for_task(
        self,
        task: Task,
        start_time: datetime,
        excluded_machine_ids: set[UUID] | None = None,
        excluded_operator_ids: set[UUID] | None = None,
    ) -> ResourceAllocation:
        """
        Allocate the best available resources for a task.

        Args:
            task: Task requiring resource allocation
            start_time: When task should start
            excluded_machine_ids: Machines to exclude from consideration
            excluded_operator_ids: Operators to exclude from consideration

        Returns:
            Resource allocation decision

        Raises:
            MachineUnavailableError: If no suitable machine available
            OperatorUnavailableError: If no suitable operators available
        """
        excluded_machines = excluded_machine_ids or set()
        excluded_operators = excluded_operator_ids or set()

        # Find best machine
        machine = await self._find_best_machine_for_task(task, excluded_machines)
        if not machine:
            raise MachineUnavailableError(
                UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
                f"No suitable machine found for task {task.id}",
            )

        # Find best operators
        operators = await self._find_best_operators_for_task(
            task, start_time, machine, excluded_operators
        )

        required_operator_count = task.required_operator_count()
        if len(operators) < required_operator_count:
            raise OperatorUnavailableError(
                UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
                f"Insufficient operators found for task {task.id}. "
                f"Required: {required_operator_count}, Found: {len(operators)}",
            )

        # Select the best operators
        selected_operators = operators[:required_operator_count]

        # Calculate allocation score
        score = await self._calculate_allocation_score(
            task, machine, selected_operators
        )

        # Generate reasoning
        reasoning = await self._generate_allocation_reasoning(
            task, machine, selected_operators
        )

        return ResourceAllocation(
            task_id=task.id,
            machine_id=machine.id,
            operator_ids=[op.id for op in selected_operators],
            allocation_score=score,
            reasoning=reasoning,
        )

    async def allocate_resources_for_job(
        self, job: Job, start_time: datetime
    ) -> list[ResourceAllocation]:
        """
        Allocate resources for all tasks in a job.

        Args:
            job: Job requiring resource allocation
            start_time: When job should start

        Returns:
            List of resource allocations for each task
        """
        allocations = []
        tasks = await self._task_repository.get_by_job_id(job.id)
        tasks.sort(key=lambda t: t.position_in_job)

        current_time = start_time
        used_machines: set[UUID] = set()
        used_operators: set[UUID] = set()

        for task in tasks:
            # For sequential tasks, exclude previously used resources
            # (simplified - would need proper time-based availability)
            allocation = await self.allocate_resources_for_task(
                task, current_time, used_machines, used_operators
            )

            allocations.append(allocation)

            # Track used resources (simplified)
            used_machines.add(allocation.machine_id)
            used_operators.update(allocation.operator_ids)

            # Advance time for next task
            current_time = current_time + task.total_duration.to_timedelta()

        return allocations

    async def find_alternative_allocation(
        self,
        original_allocation: ResourceAllocation,
        excluded_resources: dict[str, list[UUID]] | None = None,
    ) -> ResourceAllocation | None:
        """
        Find alternative resource allocation.

        Args:
            original_allocation: Current allocation to replace
            excluded_resources: Resources to exclude from search

        Returns:
            Alternative allocation or None if none found
        """
        task = await self._task_repository.get_by_id(original_allocation.task_id)
        if not task:
            return None

        excluded = excluded_resources or {}
        excluded_machines = set(excluded.get("machines", []))
        excluded_operators = set(excluded.get("operators", []))

        # Exclude original resources
        excluded_machines.add(original_allocation.machine_id)
        excluded_operators.update(original_allocation.operator_ids)

        try:
            return await self.allocate_resources_for_task(
                task,
                datetime.now(),  # Would need proper start time
                excluded_machines,
                excluded_operators,
            )
        except (MachineUnavailableError, OperatorUnavailableError):
            return None

    async def validate_resource_availability(
        self,
        machine_id: UUID,
        operator_ids: list[UUID],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, bool]:
        """
        Validate that resources are available during specified time window.

        Args:
            machine_id: Machine to check
            operator_ids: Operators to check
            start_time: Window start time
            end_time: Window end time

        Returns:
            Dictionary with availability status for each resource
        """
        availability = {}

        # Check machine availability
        machine = await self._machine_repository.get_by_id(machine_id)
        availability[f"machine_{machine_id}"] = (
            machine is not None and machine.is_available
        )

        # Check operator availability
        for operator_id in operator_ids:
            operator = await self._operator_repository.get_by_id(operator_id)
            availability[f"operator_{operator_id}"] = (
                operator is not None
                and operator.status == OperatorStatus.AVAILABLE
                and self._is_operator_available_at_time(operator, start_time, end_time)
            )

        return availability

    async def get_resource_utilization_stats(
        self, start_time: datetime, end_time: datetime
    ) -> dict[str, float]:
        """
        Calculate resource utilization statistics.

        Args:
            start_time: Period start time
            end_time: Period end time

        Returns:
            Dictionary with utilization percentages
        """
        stats = {}

        # Machine utilization
        machines = await self._machine_repository.get_all()
        for machine in machines:
            utilization = machine.get_utilization_window(start_time, end_time)
            stats[f"machine_{machine.id}_utilization"] = utilization

        # Operator utilization (simplified calculation)
        operators = await self._operator_repository.get_all()
        total_operator_time = (end_time - start_time).total_seconds() / 60  # minutes

        for operator in operators:
            # This would require tracking actual work hours
            # For now, estimate based on assignments
            assigned_time = 0  # Would calculate from actual assignments
            utilization = (
                assigned_time / total_operator_time if total_operator_time > 0 else 0
            )
            stats[f"operator_{operator.id}_utilization"] = min(1.0, utilization)

        return stats

    async def _find_best_machine_for_task(
        self, task: Task, excluded_machine_ids: set[UUID]
    ) -> Machine | None:
        """Find the best available machine for a task."""
        # Get machines capable of performing this task type
        capable_machines = await self._machine_repository.get_machines_for_task_type(
            task.task_type.value
        )

        # Filter out excluded and unavailable machines
        available_machines = [
            machine
            for machine in capable_machines
            if (
                machine.id not in excluded_machine_ids
                and machine.is_available
                and machine.status == MachineStatus.AVAILABLE
            )
        ]

        if not available_machines:
            return None

        # Score machines based on suitability
        scored_machines = []
        for machine in available_machines:
            score = self._score_machine_for_task(task, machine)
            scored_machines.append((machine, score))

        # Sort by score (higher is better)
        scored_machines.sort(key=lambda x: x[1], reverse=True)

        return scored_machines[0][0]

    async def _find_best_operators_for_task(
        self,
        task: Task,
        start_time: datetime,
        machine: Machine,
        excluded_operator_ids: set[UUID],
    ) -> list[Operator]:
        """Find the best available operators for a task, honoring role counts and department."""
        selected: list[Operator] = []
        selected_ids: set[UUID] = set()

        # Determine operator-required time window based on the chosen machine option
        option = task.get_machine_option_for(machine.id)

        # If role requirements are provided, satisfy them explicitly
        if task.role_requirements and option is not None:
            for role in task.role_requirements:
                # Get candidates by skill
                candidates = await self._operator_repository.get_operators_with_skill(
                    role.skill_type, role.minimum_level
                )
                # Filter by department membership and availability
                filtered = []
                minutes_required = task.operator_required_duration_minutes(option, role)
                end_time = start_time
                if minutes_required > 0:
                    end_time = start_time + timedelta(minutes=minutes_required)
                for op in candidates:
                    if (
                        op.id not in excluded_operator_ids
                        and op.id not in selected_ids
                        and op.status == OperatorStatus.AVAILABLE
                        and getattr(op, "department", None) == task.department
                        and self._is_operator_available_at_time(op, start_time, end_time)
                    ):
                        filtered.append(op)
                # Simple sorting heuristic: fewer current assignments first, then id
                filtered.sort(key=lambda o: (len(getattr(o, "current_task_assignments", [])), str(o.id)))
                # Pick required count
                for op in filtered[: role.count]:
                    selected.append(op)
                    selected_ids.add(op.id)

            return selected

        # Fallback to legacy skill_requirements if roles are not provided
        suitable_operators: list[Operator] = []
        for skill_req in task.skill_requirements:
            operators = await self._operator_repository.get_operators_with_skill(
                skill_req.skill_type, skill_req.minimum_level
            )
            available_operators = [
                op
                for op in operators
                if (
                    op.id not in excluded_operator_ids
                    and op.status == OperatorStatus.AVAILABLE
                    and getattr(op, "department", None) == task.department
                    and self._is_operator_available_at_time(op, start_time, start_time)
                )
            ]
            suitable_operators.extend(available_operators)

        # De-duplicate while preserving order
        seen_ids: set[UUID] = set()
        unique_operators: list[Operator] = []
        for op in suitable_operators:
            if op.id not in seen_ids:
                unique_operators.append(op)
                seen_ids.add(op.id)

        return unique_operators

    def _score_machine_for_task(self, task: Task, machine: Machine) -> float:
        """Calculate suitability score for machine-task pairing."""
        score = 0.0

        # Base score for capability
        if machine.can_perform_task_type(task.task_type.value):
            score += 10.0

        # Speed bonus
        speed_factor = machine.processing_speed_multiplier
        if speed_factor > 1.0:
            score += speed_factor * 2.0  # Bonus for faster machines

        # Attendance requirement match
        if machine.requires_operator == task.is_attended:
            score += 5.0

        # Lower utilization bonus (if load balancing enabled)
        if self._load_balancing_enabled:
            # This would require real utilization data
            utilization = 0.5  # Placeholder
            score += (1.0 - utilization) * 3.0

        return score

    def _score_operator_for_task(self, task: Task, operator: Operator) -> float:
        """Calculate suitability score for operator-task pairing."""
        score = 0.0

        # Skill matching
        for skill_req in task.skill_requirements:
            if operator.has_skill(skill_req.skill_type, skill_req.minimum_level):
                skill_level = operator.get_skill_level(skill_req.skill_type) or 0
                score += skill_level * 3.0  # Higher skill levels get more points

                # Bonus for exceeding minimum requirement
                if skill_level > skill_req.minimum_level:
                    score += (skill_level - skill_req.minimum_level) * 2.0

        # Cost consideration
        if self._prefer_lowest_cost:
            cost_per_minute = operator.calculate_cost_per_minute()
            max_cost = 10.0  # Arbitrary max for normalization
            cost_score = (max_cost - min(cost_per_minute, max_cost)) / max_cost
            score += cost_score * 5.0

        # Experience bonus
        highest_skill = operator.get_highest_skill_level()
        score += highest_skill * 1.0

        # Load balancing
        if self._load_balancing_enabled:
            # Bonus for less busy operators
            assignment_count = len(operator.current_task_assignments)
            if assignment_count == 0:
                score += 3.0
            elif assignment_count == 1:
                score += 1.0

        return score

    def _is_operator_available_at_time(
        self, operator: Operator, start_time: datetime, end_time: datetime | None = None
    ) -> bool:
        """Check if operator is available at specific time."""
        # Check date availability
        if not operator.is_available_on_date(start_time.date()):
            return False

        # Check time of day availability
        time_minutes = start_time.hour * 60 + start_time.minute
        if not operator.is_available_at_time(time_minutes):
            return False

        # If end time provided, check the entire window
        if end_time:
            current_time = start_time
            while current_time < end_time:
                minutes = current_time.hour * 60 + current_time.minute
                if not operator.is_available_at_time(minutes):
                    return False
                # Advance by 15 minutes (simplified check)
                current_time = current_time.replace(
                    minute=(current_time.minute + 15) % 60
                )
                if current_time.minute == 0:
                    current_time = current_time.replace(hour=current_time.hour + 1)

        return True

    async def _calculate_allocation_score(
        self, task: Task, machine: Machine, operators: list[Operator]
    ) -> float:
        """Calculate overall allocation quality score."""
        machine_score = self._score_machine_for_task(task, machine)

        operator_scores = [self._score_operator_for_task(task, op) for op in operators]
        avg_operator_score = (
            sum(operator_scores) / len(operator_scores) if operator_scores else 0
        )

        # Combine scores with weights
        total_score = (machine_score * 0.4) + (avg_operator_score * 0.6)

        return total_score

    async def _generate_allocation_reasoning(
        self, task: Task, machine: Machine, operators: list[Operator]
    ) -> str:
        """Generate human-readable reasoning for allocation decision."""
        reasons = []

        # Machine reasoning
        reasons.append(
            f"Machine {machine.name} selected for {task.task_type.value} capability"
        )

        if machine.processing_speed_multiplier > 1.0:
            reasons.append(
                f"Fast machine (speed factor: {machine.processing_speed_multiplier:.1f})"
            )

        # Operator reasoning
        for i, operator in enumerate(operators):
            skill_desc = []
            for skill_req in task.skill_requirements:
                if operator.has_skill(skill_req.skill_type, skill_req.minimum_level):
                    level = operator.get_skill_level(skill_req.skill_type)
                    skill_desc.append(f"{skill_req.skill_type} (level {level})")

            if skill_desc:
                reasons.append(
                    f"Operator {i+1} ({operator.name}) has skills: {', '.join(skill_desc)}"
                )

        # Cost consideration
        if self._prefer_lowest_cost and operators:
            avg_cost = sum(op.calculate_cost_per_minute() for op in operators) / len(
                operators
            )
            reasons.append(f"Average operator cost: ${avg_cost:.2f}/min")

        return "; ".join(reasons)

    def set_allocation_preferences(
        self,
        prefer_lowest_cost: bool = True,
        prefer_highest_skill: bool = False,
        load_balancing_enabled: bool = True,
    ) -> None:
        """
        Configure allocation preferences.

        Args:
            prefer_lowest_cost: Prefer lower-cost operators
            prefer_highest_skill: Prefer higher-skilled operators
            load_balancing_enabled: Balance load across resources
        """
        self._prefer_lowest_cost = prefer_lowest_cost
        self._prefer_highest_skill = prefer_highest_skill
        self._load_balancing_enabled = load_balancing_enabled
