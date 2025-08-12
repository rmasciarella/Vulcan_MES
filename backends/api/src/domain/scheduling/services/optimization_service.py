"""
Optimization Service

Wraps OR-Tools constraint programming solver to provide scheduling optimization
while maintaining clean separation between domain logic and solver implementation.
"""

import collections
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

try:
    from ortools.sat.python import cp_model  # type: ignore[import-not-found]
except ImportError:
    # Fallback for environments without OR-Tools
    cp_model = None

from ...shared.exceptions import (
    NoFeasibleSolutionError,
    OptimizationError,
    OptimizationTimeoutError,
    SolverError,
)
from ..entities.job import Job
from ..entities.machine import Machine
from ..entities.operator import Operator
from ..entities.schedule import Schedule
from ..entities.task import Task
from ..repositories.job_repository import JobRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.task_repository import TaskRepository
from ..value_objects.duration import Duration


class OptimizationParameters:
    """Configuration parameters for optimization."""

    def __init__(
        self,
        max_time_seconds: int = 300,
        num_workers: int = 8,
        horizon_days: int = 30,
        enable_hierarchical_optimization: bool = True,
        primary_objective_weight: int = 2,
        cost_optimization_tolerance: float = 0.1,
    ) -> None:
        self.max_time_seconds = max_time_seconds
        self.num_workers = num_workers
        self.horizon_days = horizon_days
        self.enable_hierarchical_optimization = enable_hierarchical_optimization
        self.primary_objective_weight = primary_objective_weight
        self.cost_optimization_tolerance = cost_optimization_tolerance


class OptimizationResult:
    """Results from optimization run."""

    def __init__(
        self,
        schedule: Schedule | None = None,
        makespan_minutes: float = 0.0,
        total_tardiness_minutes: float = 0.0,
        total_cost: float = 0.0,
        status: str = "UNKNOWN",
        solve_time_seconds: float = 0.0,
        job_completions: dict[UUID, float] | None = None,
        violations: list[str] | None = None,
    ) -> None:
        self.schedule = schedule
        self.makespan_minutes = makespan_minutes
        self.total_tardiness_minutes = total_tardiness_minutes
        self.total_cost = total_cost
        self.status = status
        self.solve_time_seconds = solve_time_seconds
        self.job_completions = job_completions or {}
        self.violations = violations or []


class OptimizationService:
    """
    Service that wraps OR-Tools CP-SAT solver for production scheduling.

    This service abstracts the complex OR-Tools implementation while providing
    a clean domain interface for scheduling optimization.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
    ) -> None:
        """
        Initialize the optimization service.

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

        # Check OR-Tools availability
        if cp_model is None:
            raise ImportError("OR-Tools is required for optimization service")

        # Default configuration from solver.py
        self._parameters = OptimizationParameters()

        # Business constraints from solver.py
        self._work_start_minutes = 7 * 60  # 7 AM
        self._work_end_minutes = 16 * 60  # 4 PM
        self._lunch_start_minutes = 12 * 60  # Noon
        self._lunch_duration_minutes = 45
        self._holiday_days = {5, 12, 26}

        # Task configuration patterns from solver.py
        self._flexible_routing_pattern = 10  # Every 10th task has flexible routing
        self._unattended_machine_pattern = 5  # Every 5th task is unattended
        self._two_operator_pattern = 15  # Every 15th task needs 2 operators

        # Critical sequences and WIP zones from solver.py
        self._critical_sequences = [
            (20, 28, "Critical Welding"),
            (35, 42, "Critical Machining"),
            (60, 65, "Critical Assembly"),
            (85, 92, "Critical Inspection"),
        ]

        self._wip_zones = [
            (0, 30, 3, "Initial Processing"),
            (31, 60, 2, "Bottleneck Zone"),
            (61, 99, 3, "Final Processing"),
        ]

    async def optimize_schedule(
        self,
        job_ids: list[UUID],
        start_time: datetime,
        parameters: OptimizationParameters | None = None,
    ) -> OptimizationResult:
        """
        Optimize schedule for given jobs using OR-Tools CP-SAT solver.

        Args:
            job_ids: Jobs to include in optimization
            start_time: Schedule start time
            parameters: Optimization parameters

        Returns:
            Optimization result with schedule and metrics

        Raises:
            OptimizationError: If optimization fails
            NoFeasibleSolutionError: If no feasible solution found
        """
        params = parameters or self._parameters

        try:
            # Load data
            jobs = await self._load_jobs(job_ids)
            tasks = await self._load_tasks_for_jobs(job_ids)
            operators = await self._operator_repository.get_all()
            machines = await self._machine_repository.get_all()

            # Validate input data
            self._validate_optimization_input(jobs, tasks, operators, machines)

            if params.enable_hierarchical_optimization:
                return await self._hierarchical_optimization(
                    jobs, tasks, operators, machines, start_time, params
                )
            else:
                return await self._single_phase_optimization(
                    jobs, tasks, operators, machines, start_time, params
                )

        except Exception as e:
            if isinstance(e, OptimizationError | NoFeasibleSolutionError):
                raise
            else:
                raise SolverError(f"Optimization failed: {str(e)}")

    async def _hierarchical_optimization(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Perform hierarchical optimization (primary objective first, then cost)."""

        # Phase 1: Optimize makespan and tardiness
        print("Phase 1: Optimizing makespan and tardiness...")
        phase1_result = await self._solve_primary_objective(
            jobs, tasks, operators, machines, start_time, params
        )

        if phase1_result.status not in ["OPTIMAL", "FEASIBLE"]:
            raise NoFeasibleSolutionError(f"Phase 1 failed: {phase1_result.status}")

        # Phase 2: Optimize cost while maintaining solution quality
        print("Phase 2: Optimizing operator costs...")
        phase2_result = await self._solve_cost_objective(
            jobs,
            tasks,
            operators,
            machines,
            start_time,
            params,
            phase1_result.makespan_minutes,
            phase1_result.total_tardiness_minutes,
        )

        if phase2_result.status not in ["OPTIMAL", "FEASIBLE"]:
            print("Phase 2 failed, using Phase 1 solution")
            return phase1_result

        return phase2_result

    async def _single_phase_optimization(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Perform single-phase optimization with combined objective."""

        model, variables = await self._create_scheduling_model(
            jobs, tasks, operators, machines, start_time, params
        )

        # Combined objective: primary + cost
        primary_obj = variables["primary_objective"]
        cost_obj = variables.get("operator_cost")

        if cost_obj:
            # Weight the objectives
            combined_obj = model.NewIntVar(
                0,
                params.horizon_days * 24 * 60 * 1000,  # Large range
                "combined_objective",
            )
            model.Add(
                combined_obj == params.primary_objective_weight * primary_obj + cost_obj
            )
            model.Minimize(combined_obj)
        else:
            model.Minimize(primary_obj)

        return await self._solve_model(model, variables, params)

    async def _solve_primary_objective(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Solve for primary objective (makespan + tardiness)."""

        model, variables = await self._create_scheduling_model(
            jobs, tasks, operators, machines, start_time, params
        )

        model.Minimize(variables["primary_objective"])

        return await self._solve_model(model, variables, params)

    async def _solve_cost_objective(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
        max_makespan: float,
        max_tardiness: float,
    ) -> OptimizationResult:
        """Solve for cost objective while constraining primary objectives."""

        model, variables = await self._create_scheduling_model(
            jobs, tasks, operators, machines, start_time, params
        )

        # Constrain primary objective to be within tolerance of Phase 1
        primary_bound = int(
            (params.primary_objective_weight * max_tardiness + max_makespan)
            * (1.0 + params.cost_optimization_tolerance)
        )
        model.Add(variables["primary_objective"] <= primary_bound)

        # Minimize cost
        if "operator_cost" in variables:
            model.Minimize(variables["operator_cost"])
        else:
            model.Minimize(variables["primary_objective"])

        return await self._solve_model(model, variables, params)

    async def _create_scheduling_model(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> tuple[cp_model.CpModel, dict[str, Any]]:
        """Create the OR-Tools CP-SAT model (adapted from solver.py)."""

        model = cp_model.CpModel()
        horizon = params.horizon_days * 24 * 60  # Total minutes

        # Storage for variables
        variables = {
            "task_starts": {},
            "task_ends": {},
            "task_presences": {},
            "task_intervals": {},
            "task_operators": {},
            "operator_intervals": collections.defaultdict(list),
            "machine_intervals": collections.defaultdict(list),
        }

        print("Creating variables for jobs and tasks...")

        # Create variables for each job and task
        for job in jobs:
            job_tasks = [t for t in tasks if t.job_id == job.id]
            job_tasks.sort(key=lambda t: t.position_in_job)

            for task in job_tasks:
                task_options = self._get_task_routing_options(task)
                num_options = len(task_options)

                if num_options == 1:
                    # Single routing option
                    processing_time, setup_time = task_options[0]
                    total_duration = processing_time + setup_time

                    start_var = model.NewIntVar(
                        0, horizon, f"start_j{job.id}_t{task.id}"
                    )
                    end_var = model.NewIntVar(0, horizon, f"end_j{job.id}_t{task.id}")

                    interval_var = model.NewIntervalVar(
                        start_var,
                        total_duration,
                        end_var,
                        f"interval_j{job.id}_t{task.id}",
                    )

                    variables["task_starts"][(job.id, task.id, 0)] = start_var
                    variables["task_ends"][(job.id, task.id, 0)] = end_var
                    variables["task_intervals"][(job.id, task.id, 0)] = interval_var
                    variables["task_presences"][(job.id, task.id, 0)] = (
                        model.NewConstant(1)
                    )

                    # Assign to machine
                    machine_id = self._select_machine_for_task(task, machines)
                    variables["machine_intervals"][machine_id].append(interval_var)

                else:
                    # Flexible routing
                    option_presences = []

                    for option_id, (processing_time, setup_time) in enumerate(
                        task_options
                    ):
                        total_duration = processing_time + setup_time

                        start_var = model.NewIntVar(
                            0, horizon, f"start_j{job.id}_t{task.id}_o{option_id}"
                        )
                        end_var = model.NewIntVar(
                            0, horizon, f"end_j{job.id}_t{task.id}_o{option_id}"
                        )
                        presence_var = model.NewBoolVar(
                            f"presence_j{job.id}_t{task.id}_o{option_id}"
                        )

                        interval_var = model.NewOptionalIntervalVar(
                            start_var,
                            total_duration,
                            end_var,
                            presence_var,
                            f"interval_j{job.id}_t{task.id}_o{option_id}",
                        )

                        variables["task_starts"][(job.id, task.id, option_id)] = (
                            start_var
                        )
                        variables["task_ends"][(job.id, task.id, option_id)] = end_var
                        variables["task_presences"][(job.id, task.id, option_id)] = (
                            presence_var
                        )
                        variables["task_intervals"][(job.id, task.id, option_id)] = (
                            interval_var
                        )
                        option_presences.append(presence_var)

                        # Assign to different machines for different options
                        machine_id = f"{task.id}_{option_id}"
                        variables["machine_intervals"][machine_id].append(interval_var)

                    # Exactly one option must be selected
                    model.AddExactlyOne(option_presences)

        # Add constraints
        await self._add_precedence_constraints(model, variables, jobs, tasks)
        await self._add_resource_constraints(model, variables, machines, operators)
        await self._add_business_constraints(model, variables, tasks)
        await self._add_optimization_objectives(
            model, variables, jobs, tasks, operators
        )

        return model, variables

    async def _solve_model(
        self,
        model: cp_model.CpModel,
        variables: dict[str, Any],
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Solve the CP-SAT model and return results."""

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = params.max_time_seconds
        solver.parameters.num_search_workers = params.num_workers
        solver.parameters.log_search_progress = True

        start_time = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - start_time

        status_name = solver.StatusName(status)

        if status == cp_model.INFEASIBLE:
            raise NoFeasibleSolutionError("No feasible solution exists")
        elif status == cp_model.MODEL_INVALID:
            raise SolverError("Invalid model")
        elif status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            raise OptimizationTimeoutError(params.max_time_seconds)

        # Extract solution
        schedule = await self._extract_schedule_from_solution(solver, variables)

        # Calculate metrics
        makespan = solver.Value(variables.get("makespan", 0))
        total_tardiness = sum(
            solver.Value(variables["tardiness"][j])
            for j in variables.get("tardiness", {})
        )
        total_cost = solver.Value(variables.get("operator_cost", 0))

        job_completions = {
            job_id: solver.Value(completion_var)
            for job_id, completion_var in variables.get("job_completions", {}).items()
        }

        return OptimizationResult(
            schedule=schedule,
            makespan_minutes=float(makespan),
            total_tardiness_minutes=float(total_tardiness),
            total_cost=float(total_cost),
            status=status_name,
            solve_time_seconds=solve_time,
            job_completions=job_completions,
        )

    async def _extract_schedule_from_solution(
        self, solver: cp_model.CpSolver, variables: dict[str, Any]
    ) -> Schedule:
        """Extract schedule from solver solution."""

        schedule = Schedule(name=f"Optimized Schedule {datetime.now().isoformat()}")

        # Extract task assignments
        for key, start_var in variables["task_starts"].items():
            job_id, task_id, option_id = key

            presence_key = (job_id, task_id, option_id)
            if presence_key in variables["task_presences"]:
                presence_var = variables["task_presences"][presence_key]

                if solver.Value(presence_var) == 1:  # This option is selected
                    start_minutes = solver.Value(start_var)
                    end_var = variables["task_ends"][key]
                    end_minutes = solver.Value(end_var)

                    # Convert minutes to datetime (simplified)
                    start_time = datetime.now() + timedelta(minutes=start_minutes)
                    end_time = datetime.now() + timedelta(minutes=end_minutes)

                    # Get assigned resources (simplified)
                    machine_id = UUID(
                        "00000000-0000-0000-0000-000000000001"
                    )  # Placeholder
                    operator_ids = [
                        UUID("00000000-0000-0000-0000-000000000002")
                    ]  # Placeholder

                    # Create assignment
                    schedule.assign_task(
                        task_id=task_id,
                        machine_id=machine_id,
                        operator_ids=operator_ids,
                        start_time=start_time,
                        end_time=end_time,
                        setup_duration=Duration(minutes=10),  # Simplified
                        processing_duration=Duration(
                            minutes=end_minutes - start_minutes - 10
                        ),
                    )

        return schedule

    def _get_task_routing_options(self, task: Task) -> list[tuple[int, int]]:
        """Get routing options for a task (from solver.py logic)."""
        # Every 10th task has flexible routing (based on position)
        if (task.position_in_job + 1) % self._flexible_routing_pattern == 0:
            return [
                (120, 15),  # Option A: 120 min processing + 15 min setup
                (90, 20),  # Option B: 90 min processing + 20 min setup
            ]
        else:
            return [(60, 10)]  # Single option: 60 min processing + 10 min setup

    def _select_machine_for_task(self, task: Task, machines: list[Machine]) -> UUID:
        """Select appropriate machine for task (simplified)."""
        for machine in machines:
            if machine.can_perform_task_type(task.task_type.value):
                return machine.id

        # Fallback to first machine
        return (
            machines[0].id if machines else UUID("00000000-0000-0000-0000-000000000000")
        )

    async def _add_precedence_constraints(
        self,
        model: cp_model.CpModel,
        variables: dict[str, Any],
        jobs: list[Job],
        tasks: list[Task],
    ) -> None:
        """Add precedence constraints between tasks."""
        print("Adding precedence constraints...")

        for job in jobs:
            job_tasks = [t for t in tasks if t.job_id == job.id]
            job_tasks.sort(key=lambda t: t.position_in_job)

            # Sequential precedence within jobs
            for i in range(len(job_tasks) - 1):
                current_task = job_tasks[i]
                next_task = job_tasks[i + 1]

                # Handle different routing options
                current_options = len(self._get_task_routing_options(current_task))
                next_options = len(self._get_task_routing_options(next_task))

                for curr_opt in range(current_options):
                    for next_opt in range(next_options):
                        current_end = variables["task_ends"][
                            (job.id, current_task.id, curr_opt)
                        ]
                        next_start = variables["task_starts"][
                            (job.id, next_task.id, next_opt)
                        ]
                        current_presence = variables["task_presences"][
                            (job.id, current_task.id, curr_opt)
                        ]
                        next_presence = variables["task_presences"][
                            (job.id, next_task.id, next_opt)
                        ]

                        # Next task starts after current task ends
                        model.Add(next_start >= current_end).OnlyEnforceIf(
                            [current_presence, next_presence]
                        )

    async def _add_resource_constraints(
        self,
        model: cp_model.CpModel,
        variables: dict[str, Any],
        machines: list[Machine],
        operators: list[Operator],
    ) -> None:
        """Add resource availability constraints."""
        print("Adding resource constraints...")

        # Machine no-overlap constraints
        for machine_intervals in variables["machine_intervals"].values():
            if len(machine_intervals) > 1:
                model.AddNoOverlap(machine_intervals)

        # Operator no-overlap constraints
        for operator_intervals in variables["operator_intervals"].values():
            if len(operator_intervals) > 1:
                model.AddNoOverlap(operator_intervals)

    async def _add_business_constraints(
        self, model: cp_model.CpModel, variables: dict[str, Any], tasks: list[Task]
    ) -> None:
        """Add business hours and other business constraints."""
        print("Adding business constraints...")

        # This would add business hours, holidays, lunch breaks, etc.
        # Implementation simplified for brevity
        pass

    async def _add_optimization_objectives(
        self,
        model: cp_model.CpModel,
        variables: dict[str, Any],
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
    ) -> None:
        """Add optimization objective variables."""
        print("Setting up optimization objectives...")

        horizon = self._parameters.horizon_days * 24 * 60

        # Job completion times and tardiness
        job_completions = {}
        tardiness_vars = {}

        for job in jobs:
            # Find last task for each job
            job_tasks = [t for t in tasks if t.job_id == job.id]
            if not job_tasks:
                continue

            last_task = max(job_tasks, key=lambda t: t.position_in_job)

            # Job completion is end time of last task
            completion_var = model.NewIntVar(0, horizon, f"completion_j{job.id}")

            # Link to task end time (simplified - would handle multiple options)
            last_task_end = variables["task_ends"].get((job.id, last_task.id, 0))
            if last_task_end:
                model.Add(completion_var == last_task_end)

            job_completions[job.id] = completion_var

            # Calculate tardiness
            due_date = 10 * 24 * 60  # 10 days in minutes (simplified)
            if job.due_date:
                due_date = int((job.due_date - datetime.now()).total_seconds() / 60)

            tardiness = model.NewIntVar(0, horizon, f"tardiness_j{job.id}")
            model.AddMaxEquality(tardiness, [completion_var - due_date, 0])
            tardiness_vars[job.id] = tardiness

        # Makespan
        makespan = model.NewIntVar(0, horizon, "makespan")
        if job_completions:
            model.AddMaxEquality(makespan, list(job_completions.values()))

        # Total tardiness
        total_tardiness = model.NewIntVar(0, horizon * len(jobs), "total_tardiness")
        if tardiness_vars:
            model.Add(total_tardiness == sum(tardiness_vars.values()))

        # Primary objective: minimize (2 * tardiness + makespan)
        primary_objective = model.NewIntVar(
            0, horizon * (2 * len(jobs) + 1), "primary_objective"
        )
        model.Add(primary_objective == 2 * total_tardiness + makespan)

        # Store in variables for later use
        variables["job_completions"] = job_completions
        variables["tardiness"] = tardiness_vars
        variables["makespan"] = makespan
        variables["total_tardiness"] = total_tardiness
        variables["primary_objective"] = primary_objective

    async def _load_jobs(self, job_ids: list[UUID]) -> list[Job]:
        """Load jobs from repository."""
        jobs = []
        for job_id in job_ids:
            job = await self._job_repository.get_by_id(job_id)
            if job:
                jobs.append(job)
        return jobs

    async def _load_tasks_for_jobs(self, job_ids: list[UUID]) -> list[Task]:
        """Load all tasks for given jobs."""
        all_tasks = []
        for job_id in job_ids:
            tasks = await self._task_repository.get_by_job_id(job_id)
            all_tasks.extend(tasks)
        return all_tasks

    def _validate_optimization_input(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
    ) -> None:
        """Validate input data for optimization."""
        if not jobs:
            raise OptimizationError("No jobs provided for optimization")

        if not tasks:
            raise OptimizationError("No tasks found for provided jobs")

        if not operators:
            raise OptimizationError("No operators available for scheduling")

        if not machines:
            raise OptimizationError("No machines available for scheduling")

        # Validate that all jobs have tasks
        job_ids = {job.id for job in jobs}
        task_job_ids = {task.job_id for task in tasks if task.job_id}

        if not job_ids.issubset(task_job_ids):
            missing_jobs = job_ids - task_job_ids
            raise OptimizationError(f"Jobs without tasks: {missing_jobs}")

    def set_parameters(self, parameters: OptimizationParameters) -> None:
        """Set optimization parameters."""
        self._parameters = parameters

    def set_business_hours(
        self,
        start_hour: int,
        end_hour: int,
        lunch_start_hour: int = 12,
        lunch_duration_minutes: int = 45,
    ) -> None:
        """Configure business hours."""
        self._work_start_minutes = start_hour * 60
        self._work_end_minutes = end_hour * 60
        self._lunch_start_minutes = lunch_start_hour * 60
        self._lunch_duration_minutes = lunch_duration_minutes

    def set_holiday_days(self, holiday_days: set[int]) -> None:
        """Set holiday days."""
        self._holiday_days = holiday_days
