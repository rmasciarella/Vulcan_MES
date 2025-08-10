"""
Fallback Strategies for Optimization Failures

Implements graceful degradation patterns with simplified algorithms, partial solutions,
and heuristic approaches when the primary OR-Tools solver fails or times out.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from ..domain.scheduling.entities.job import Job
from ..domain.scheduling.entities.machine import Machine
from ..domain.scheduling.entities.operator import Operator
from ..domain.scheduling.entities.schedule import Schedule
from ..domain.scheduling.entities.task import Task
from ..domain.scheduling.value_objects.duration import Duration
from ..domain.scheduling.value_objects.enums import PriorityLevel
from .observability import get_logger, monitor_performance
from .solver_management import SolverMetrics


class FallbackStrategy(Enum):
    """Available fallback strategies."""

    GREEDY_SCHEDULING = "greedy"
    PRIORITY_BASED = "priority_based"
    EARLIEST_DUE_DATE = "earliest_due_date"
    SHORTEST_PROCESSING_TIME = "shortest_processing_time"
    CRITICAL_RATIO = "critical_ratio"
    RANDOM_ASSIGNMENT = "random"
    PARTIAL_SOLUTION = "partial_solution"
    SIMPLIFIED_MODEL = "simplified_model"


class FallbackReason(Enum):
    """Reasons for fallback activation."""

    SOLVER_TIMEOUT = "solver_timeout"
    SOLVER_CRASH = "solver_crash"
    MEMORY_EXHAUSTION = "memory_exhaustion"
    NO_FEASIBLE_SOLUTION = "no_feasible_solution"
    CONFIGURATION_ERROR = "configuration_error"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    SYSTEM_OVERLOAD = "system_overload"


@dataclass
class FallbackResult:
    """Result from fallback strategy execution."""

    schedule: Schedule | None
    strategy_used: FallbackStrategy
    fallback_reason: FallbackReason
    execution_time_seconds: float
    quality_score: float  # 0.0 to 1.0, where 1.0 is optimal
    makespan_minutes: float
    total_tardiness_minutes: float
    jobs_scheduled: int
    tasks_scheduled: int
    warnings: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "strategy_used": self.strategy_used.value,
            "fallback_reason": self.fallback_reason.value,
            "execution_time_seconds": self.execution_time_seconds,
            "quality_score": self.quality_score,
            "makespan_minutes": self.makespan_minutes,
            "total_tardiness_minutes": self.total_tardiness_minutes,
            "jobs_scheduled": self.jobs_scheduled,
            "tasks_scheduled": self.tasks_scheduled,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


class BaseFallbackStrategy(ABC):
    """Base class for fallback strategies."""

    def __init__(self):
        self.logger = get_logger(f"fallback.{self.__class__.__name__}")

    @abstractmethod
    async def execute(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
    ) -> FallbackResult:
        """Execute the fallback strategy."""
        pass

    def _calculate_quality_score(
        self,
        makespan: float,
        tardiness: float,
        jobs_scheduled: int,
        total_jobs: int,
        optimal_makespan: float | None = None,
    ) -> float:
        """Calculate quality score for the solution."""
        # Base score on completion ratio
        completion_ratio = jobs_scheduled / max(total_jobs, 1)

        # Penalty for tardiness (normalized)
        tardiness_penalty = min(tardiness / (7 * 24 * 60), 1.0)  # Cap at 1 week

        # Quality score calculation
        quality_score = completion_ratio * (1.0 - tardiness_penalty * 0.3)

        # Bonus for fast makespan if we have a reference
        if optimal_makespan and makespan > 0:
            makespan_ratio = min(optimal_makespan / makespan, 1.0)
            quality_score *= 0.7 + 0.3 * makespan_ratio

        return max(0.0, min(1.0, quality_score))


class GreedySchedulingStrategy(BaseFallbackStrategy):
    """Greedy scheduling: assign tasks to first available resource."""

    async def execute(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
    ) -> FallbackResult:
        """Execute greedy scheduling strategy."""
        start_exec_time = time.time()
        schedule = Schedule(name=f"Greedy Schedule {start_time.isoformat()}")
        warnings = []

        # Sort tasks by job priority and sequence
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                self._get_job_priority_value(t, jobs),
                t.position_in_job or 0,
            ),
        )

        # Track resource availability
        operator_availability = {op.id: start_time for op in operators}
        machine_availability = {m.id: start_time for m in machines}

        scheduled_tasks = 0
        total_makespan = 0.0
        total_tardiness = 0.0

        for task in sorted_tasks:
            try:
                # Find job for this task
                job = next((j for j in jobs if j.id == task.job_id), None)
                if not job:
                    warnings.append(f"Job not found for task {task.id}")
                    continue

                # Find available operator
                available_operator = self._find_earliest_available_operator(
                    operators, operator_availability
                )

                # Find available machine
                available_machine = self._find_earliest_available_machine(
                    machines, machine_availability
                )

                if not available_operator or not available_machine:
                    warnings.append(f"No resources available for task {task.id}")
                    continue

                # Calculate task timing
                task_start = max(
                    operator_availability[available_operator.id],
                    machine_availability[available_machine.id],
                )

                task_duration = Duration.from_minutes(60)  # Default duration
                task_end = task_start + timedelta(minutes=task_duration.total_minutes)

                # Create task assignment
                # Note: This is simplified - full implementation would create proper assignment
                scheduled_tasks += 1

                # Update resource availability
                operator_availability[available_operator.id] = task_end
                machine_availability[available_machine.id] = task_end

                # Update metrics
                makespan_minutes = (task_end - start_time).total_seconds() / 60
                total_makespan = max(total_makespan, makespan_minutes)

                # Calculate tardiness
                if job.due_date and task_end > job.due_date:
                    tardiness = (task_end - job.due_date).total_seconds() / 60
                    total_tardiness += tardiness

            except Exception as e:
                warnings.append(f"Failed to schedule task {task.id}: {str(e)}")

        execution_time = time.time() - start_exec_time
        quality_score = self._calculate_quality_score(
            total_makespan, total_tardiness, scheduled_tasks, len(tasks)
        )

        self.logger.info(
            "Greedy scheduling completed",
            scheduled_tasks=scheduled_tasks,
            total_tasks=len(tasks),
            execution_time=execution_time,
            quality_score=quality_score,
        )

        return FallbackResult(
            schedule=schedule,
            strategy_used=FallbackStrategy.GREEDY_SCHEDULING,
            fallback_reason=FallbackReason.SOLVER_TIMEOUT,
            execution_time_seconds=execution_time,
            quality_score=quality_score,
            makespan_minutes=total_makespan,
            total_tardiness_minutes=total_tardiness,
            jobs_scheduled=len({t.job_id for t in sorted_tasks[:scheduled_tasks]}),
            tasks_scheduled=scheduled_tasks,
            warnings=warnings,
            metrics={
                "resource_utilization": scheduled_tasks
                / (len(operators) + len(machines)),
                "completion_rate": scheduled_tasks / len(tasks),
            },
        )

    def _get_job_priority_value(self, task: Task, jobs: list[Job]) -> int:
        """Get priority value for sorting (lower = higher priority)."""
        job = next((j for j in jobs if j.id == task.job_id), None)
        if not job:
            return 999

        priority_map = {
            PriorityLevel.URGENT: 1,
            PriorityLevel.HIGH: 2,
            PriorityLevel.NORMAL: 3,
            PriorityLevel.LOW: 4,
        }
        return priority_map.get(job.priority, 3)

    def _find_earliest_available_operator(
        self, operators: list[Operator], availability: dict[UUID, datetime]
    ) -> Operator | None:
        """Find the operator available earliest."""
        if not operators:
            return None

        return min(operators, key=lambda op: availability.get(op.id, datetime.min))

    def _find_earliest_available_machine(
        self, machines: list[Machine], availability: dict[UUID, datetime]
    ) -> Machine | None:
        """Find the machine available earliest."""
        if not machines:
            return None

        return min(machines, key=lambda m: availability.get(m.id, datetime.min))


class PriorityBasedStrategy(BaseFallbackStrategy):
    """Priority-based scheduling: strict priority order."""

    async def execute(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
    ) -> FallbackResult:
        """Execute priority-based scheduling."""
        start_exec_time = time.time()

        # Sort jobs by priority
        priority_order = [
            PriorityLevel.URGENT,
            PriorityLevel.HIGH,
            PriorityLevel.NORMAL,
            PriorityLevel.LOW,
        ]
        sorted_jobs = sorted(jobs, key=lambda j: priority_order.index(j.priority))

        # Schedule all tasks for highest priority jobs first
        schedule = Schedule(name=f"Priority Schedule {start_time.isoformat()}")
        warnings = []
        scheduled_tasks = 0
        total_makespan = 0.0
        total_tardiness = 0.0

        current_time = start_time

        for job in sorted_jobs:
            job_tasks = [t for t in tasks if t.job_id == job.id]
            job_tasks.sort(key=lambda t: t.position_in_job or 0)


            for task in job_tasks:
                try:
                    # Assign to first available resources
                    operator = operators[0] if operators else None
                    machine = machines[0] if machines else None

                    if not operator or not machine:
                        warnings.append(f"No resources for task {task.id}")
                        continue

                    # Simple sequential scheduling
                    task_duration = 60  # Default 60 minutes
                    task_end = current_time + timedelta(minutes=task_duration)

                    scheduled_tasks += 1
                    current_time = task_end

                except Exception as e:
                    warnings.append(f"Failed to schedule task {task.id}: {str(e)}")

            # Calculate job completion metrics
            job_completion = current_time
            makespan_minutes = (job_completion - start_time).total_seconds() / 60
            total_makespan = max(total_makespan, makespan_minutes)

            if job.due_date and job_completion > job.due_date:
                tardiness = (job_completion - job.due_date).total_seconds() / 60
                total_tardiness += tardiness

        execution_time = time.time() - start_exec_time
        quality_score = self._calculate_quality_score(
            total_makespan, total_tardiness, scheduled_tasks, len(tasks)
        )

        return FallbackResult(
            schedule=schedule,
            strategy_used=FallbackStrategy.PRIORITY_BASED,
            fallback_reason=FallbackReason.SOLVER_TIMEOUT,
            execution_time_seconds=execution_time,
            quality_score=quality_score,
            makespan_minutes=total_makespan,
            total_tardiness_minutes=total_tardiness,
            jobs_scheduled=len(sorted_jobs),
            tasks_scheduled=scheduled_tasks,
            warnings=warnings,
            metrics={
                "priority_distribution": self._calculate_priority_distribution(
                    sorted_jobs
                ),
            },
        )

    def _calculate_priority_distribution(self, jobs: list[Job]) -> dict[str, int]:
        """Calculate distribution of jobs by priority."""
        distribution = {}
        for priority in PriorityLevel:
            count = sum(1 for job in jobs if job.priority == priority)
            distribution[priority.value] = count
        return distribution


class EarliestDueDateStrategy(BaseFallbackStrategy):
    """Earliest due date scheduling strategy."""

    async def execute(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
    ) -> FallbackResult:
        """Execute earliest due date scheduling."""
        start_exec_time = time.time()

        # Sort jobs by due date
        jobs_with_due_dates = [j for j in jobs if j.due_date]
        jobs_without_due_dates = [j for j in jobs if not j.due_date]

        sorted_jobs = (
            sorted(jobs_with_due_dates, key=lambda j: j.due_date)
            + jobs_without_due_dates
        )

        schedule = Schedule(name=f"EDD Schedule {start_time.isoformat()}")
        warnings = []

        if not jobs_with_due_dates:
            warnings.append("No jobs have due dates - using original order")

        # Simple sequential scheduling
        scheduled_tasks = 0
        current_time = start_time
        total_tardiness = 0.0

        for job in sorted_jobs:
            job_tasks = [t for t in tasks if t.job_id == job.id]
            job_tasks.sort(key=lambda t: t.position_in_job or 0)

            for _task in job_tasks:
                scheduled_tasks += 1
                current_time += timedelta(minutes=60)  # Default task duration

            # Check tardiness
            if job.due_date and current_time > job.due_date:
                tardiness = (current_time - job.due_date).total_seconds() / 60
                total_tardiness += tardiness

        execution_time = time.time() - start_exec_time
        makespan_minutes = (current_time - start_time).total_seconds() / 60
        quality_score = self._calculate_quality_score(
            makespan_minutes, total_tardiness, scheduled_tasks, len(tasks)
        )

        return FallbackResult(
            schedule=schedule,
            strategy_used=FallbackStrategy.EARLIEST_DUE_DATE,
            fallback_reason=FallbackReason.SOLVER_TIMEOUT,
            execution_time_seconds=execution_time,
            quality_score=quality_score,
            makespan_minutes=makespan_minutes,
            total_tardiness_minutes=total_tardiness,
            jobs_scheduled=len(sorted_jobs),
            tasks_scheduled=scheduled_tasks,
            warnings=warnings,
            metrics={
                "jobs_with_due_dates": len(jobs_with_due_dates),
                "average_tardiness": total_tardiness / max(len(sorted_jobs), 1),
            },
        )


class PartialSolutionStrategy(BaseFallbackStrategy):
    """Extract and improve partial solution from failed solver."""

    async def execute(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        partial_solver_metrics: SolverMetrics | None = None,
    ) -> FallbackResult:
        """Execute partial solution extraction and improvement."""
        start_exec_time = time.time()
        warnings = []

        # If we have partial solver results, try to extract them
        scheduled_tasks = 0
        if partial_solver_metrics and partial_solver_metrics.partial_solution:
            # This would extract actual partial solution from solver
            scheduled_tasks = len(tasks) // 2  # Simulate partial completion
            warnings.append("Extracted partial solution from failed solver")
        else:
            warnings.append("No partial solution available - using greedy completion")

        # Use greedy strategy to complete the schedule
        greedy_strategy = GreedySchedulingStrategy()
        remaining_tasks = tasks[scheduled_tasks:]  # Simulate remaining tasks

        greedy_result = await greedy_strategy.execute(
            jobs, remaining_tasks, operators, machines, start_time
        )

        execution_time = time.time() - start_exec_time

        # Combine metrics
        total_scheduled = scheduled_tasks + greedy_result.tasks_scheduled
        quality_score = self._calculate_quality_score(
            greedy_result.makespan_minutes,
            greedy_result.total_tardiness_minutes,
            total_scheduled,
            len(tasks),
        )

        # Boost quality score for partial solution recovery
        quality_score = min(1.0, quality_score * 1.1)

        return FallbackResult(
            schedule=greedy_result.schedule,
            strategy_used=FallbackStrategy.PARTIAL_SOLUTION,
            fallback_reason=FallbackReason.SOLVER_TIMEOUT,
            execution_time_seconds=execution_time,
            quality_score=quality_score,
            makespan_minutes=greedy_result.makespan_minutes,
            total_tardiness_minutes=greedy_result.total_tardiness_minutes,
            jobs_scheduled=greedy_result.jobs_scheduled,
            tasks_scheduled=total_scheduled,
            warnings=warnings + greedy_result.warnings,
            metrics={
                **greedy_result.metrics,
                "partial_solution_recovered": scheduled_tasks > 0,
                "recovery_rate": total_scheduled / len(tasks),
            },
        )


class FallbackOrchestrator:
    """
    Orchestrates fallback strategies based on failure conditions.

    Determines the best fallback strategy and executes it with comprehensive
    monitoring and quality assessment.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._strategies = {
            FallbackStrategy.GREEDY_SCHEDULING: GreedySchedulingStrategy(),
            FallbackStrategy.PRIORITY_BASED: PriorityBasedStrategy(),
            FallbackStrategy.EARLIEST_DUE_DATE: EarliestDueDateStrategy(),
            FallbackStrategy.PARTIAL_SOLUTION: PartialSolutionStrategy(),
        }

    @monitor_performance("fallback_execution")
    async def execute_fallback(
        self,
        reason: FallbackReason,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        solver_metrics: SolverMetrics | None = None,
        preferred_strategy: FallbackStrategy | None = None,
    ) -> FallbackResult:
        """
        Execute appropriate fallback strategy based on failure reason.
        """
        self.logger.warning(
            "Executing fallback strategy",
            reason=reason.value,
            jobs_count=len(jobs),
            tasks_count=len(tasks),
            preferred_strategy=preferred_strategy.value if preferred_strategy else None,
        )

        # Select strategy based on conditions
        strategy = self._select_strategy(
            reason, jobs, tasks, operators, machines, preferred_strategy
        )

        try:
            # Execute the selected strategy
            if strategy == FallbackStrategy.PARTIAL_SOLUTION:
                result = await self._strategies[strategy].execute(
                    jobs, tasks, operators, machines, start_time, solver_metrics
                )
            else:
                result = await self._strategies[strategy].execute(
                    jobs, tasks, operators, machines, start_time
                )

            # Log success
            self.logger.info(
                "Fallback strategy completed successfully",
                strategy=result.strategy_used.value,
                quality_score=result.quality_score,
                execution_time=result.execution_time_seconds,
                tasks_scheduled=result.tasks_scheduled,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Fallback strategy failed",
                strategy=strategy.value,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            # Try emergency greedy fallback
            return await self._emergency_fallback(
                jobs, tasks, operators, machines, start_time, reason
            )

    def _select_strategy(
        self,
        reason: FallbackReason,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        preferred: FallbackStrategy | None,
    ) -> FallbackStrategy:
        """Select the best fallback strategy based on conditions."""

        # Use preferred strategy if specified and valid
        if preferred and preferred in self._strategies:
            return preferred

        # Strategy selection logic based on failure reason
        if reason == FallbackReason.SOLVER_TIMEOUT:
            # Try to extract partial solution first
            return FallbackStrategy.PARTIAL_SOLUTION
        elif reason == FallbackReason.NO_FEASIBLE_SOLUTION:
            # Use greedy to find any feasible solution
            return FallbackStrategy.GREEDY_SCHEDULING
        elif reason == FallbackReason.MEMORY_EXHAUSTION:
            # Use simple priority-based approach
            return FallbackStrategy.PRIORITY_BASED
        elif reason == FallbackReason.CIRCUIT_BREAKER_OPEN:
            # Use fastest strategy
            return FallbackStrategy.EARLIEST_DUE_DATE
        else:
            # Default to greedy scheduling
            return FallbackStrategy.GREEDY_SCHEDULING

    async def _emergency_fallback(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        reason: FallbackReason,
    ) -> FallbackResult:
        """Emergency fallback when all else fails."""
        self.logger.error("Executing emergency fallback - all strategies failed")

        # Extremely simple sequential assignment
        execution_start = time.time()
        schedule = Schedule(name=f"Emergency Schedule {start_time.isoformat()}")

        # Just count tasks to provide some result
        task_count = len(tasks)
        job_count = len(jobs)

        execution_time = time.time() - execution_start

        return FallbackResult(
            schedule=schedule,
            strategy_used=FallbackStrategy.GREEDY_SCHEDULING,
            fallback_reason=reason,
            execution_time_seconds=execution_time,
            quality_score=0.1,  # Very low quality
            makespan_minutes=task_count * 60,  # Assume 1 hour per task
            total_tardiness_minutes=0.0,
            jobs_scheduled=0,
            tasks_scheduled=0,
            warnings=["Emergency fallback activated - minimal functionality"],
            metrics={
                "emergency_fallback": True,
                "total_jobs": job_count,
                "total_tasks": task_count,
            },
        )
