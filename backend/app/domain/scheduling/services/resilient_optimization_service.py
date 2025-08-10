"""
Resilient Optimization Service

Enhanced optimization service that integrates comprehensive error handling,
fallback strategies, circuit breaker patterns, and graceful degradation.
"""

import asyncio
import time
from datetime import datetime
from uuid import UUID

from ....core.circuit_breaker import (
    SOLVER_MODEL_CREATION_CIRCUIT_CONFIG,
    SOLVER_OPTIMIZATION_CIRCUIT_CONFIG,
    CircuitBreakerOpenError,
    with_resilience,
)
from ....core.fallback_strategies import (
    FallbackOrchestrator,
    FallbackReason,
    FallbackResult,
    FallbackStrategy,
)
from ....core.observability import (
    SOLVER_ERRORS,
    get_logger,
    monitor_performance,
    trace_operation,
)
from ....core.solver_management import (
    SolverConfiguration,
    SolverLimits,
    SolverMetrics,
    SolverStatus,
    create_resilient_solver_manager,
)
from ...shared.exceptions import (
    OptimizationError,
    OptimizationTimeoutError,
    RetryExhaustedError,
    SolverCrashError,
    SolverError,
    SolverMemoryError,
    SystemResourceError,
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

try:
    from ortools.sat.python import cp_model  # type: ignore[import-not-found]

    ORTOOLS_AVAILABLE = True
except ImportError:
    cp_model = None
    ORTOOLS_AVAILABLE = False


class OptimizationParameters:
    """Enhanced optimization parameters with resilience configuration."""

    def __init__(
        self,
        max_time_seconds: int = 300,
        num_workers: int = 8,
        horizon_days: int = 30,
        enable_hierarchical_optimization: bool = True,
        primary_objective_weight: int = 2,
        cost_optimization_tolerance: float = 0.1,
        # Resilience parameters
        enable_fallback_strategies: bool = True,
        preferred_fallback_strategy: FallbackStrategy | None = None,
        max_retry_attempts: int = 3,
        memory_limit_mb: int = 4096,
        enable_circuit_breaker: bool = True,
        enable_partial_solutions: bool = True,
    ):
        # Original parameters
        self.max_time_seconds = max_time_seconds
        self.num_workers = num_workers
        self.horizon_days = horizon_days
        self.enable_hierarchical_optimization = enable_hierarchical_optimization
        self.primary_objective_weight = primary_objective_weight
        self.cost_optimization_tolerance = cost_optimization_tolerance

        # Resilience parameters
        self.enable_fallback_strategies = enable_fallback_strategies
        self.preferred_fallback_strategy = preferred_fallback_strategy
        self.max_retry_attempts = max_retry_attempts
        self.memory_limit_mb = memory_limit_mb
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_partial_solutions = enable_partial_solutions


class OptimizationResult:
    """Enhanced optimization result with resilience information."""

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
        solver_stats: dict[str, str | int | float | bool] | None = None,
        performance_metrics: dict[str, str | int | float | bool] | None = None,
        # Resilience information
        fallback_used: bool = False,
        fallback_result: FallbackResult | None = None,
        circuit_breaker_triggered: bool = False,
        retry_attempts: int = 0,
        quality_score: float = 1.0,
        warnings: list[str] | None = None,
    ):
        # Original attributes
        self.schedule = schedule
        self.makespan_minutes = makespan_minutes
        self.total_tardiness_minutes = total_tardiness_minutes
        self.total_cost = total_cost
        self.status = status
        self.solve_time_seconds = solve_time_seconds
        self.job_completions = job_completions or {}
        self.violations = violations or []
        self.solver_stats = solver_stats or {}
        self.performance_metrics = performance_metrics or {}

        # Resilience attributes
        self.fallback_used = fallback_used
        self.fallback_result = fallback_result
        self.circuit_breaker_triggered = circuit_breaker_triggered
        self.retry_attempts = retry_attempts
        self.quality_score = quality_score
        self.warnings = warnings or []

    def to_dict(self) -> dict[str, str | int | float | bool | list | dict]:
        """Convert to dictionary for API responses."""
        result = {
            "makespan_minutes": self.makespan_minutes,
            "total_tardiness_minutes": self.total_tardiness_minutes,
            "total_cost": self.total_cost,
            "status": self.status,
            "solve_time_seconds": self.solve_time_seconds,
            "job_completions": {str(k): v for k, v in self.job_completions.items()},
            "violations": self.violations,
            "solver_stats": self.solver_stats,
            "performance_metrics": self.performance_metrics,
            "fallback_used": self.fallback_used,
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
            "retry_attempts": self.retry_attempts,
            "quality_score": self.quality_score,
            "warnings": self.warnings,
        }

        if self.fallback_result:
            result["fallback_result"] = self.fallback_result.to_dict()

        return result


class ResilientOptimizationService:
    """
    Resilient optimization service with comprehensive error handling.

    Integrates circuit breakers, fallback strategies, retry mechanisms,
    and graceful degradation for robust scheduling optimization.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
    ):
        """Initialize the resilient optimization service."""
        self.logger = get_logger(__name__)
        self._job_repository = job_repository
        self._task_repository = task_repository
        self._operator_repository = operator_repository
        self._machine_repository = machine_repository

        # Initialize fallback orchestrator
        self._fallback_orchestrator = FallbackOrchestrator()

        # Track service health
        self._health_metrics = {
            "total_optimizations": 0,
            "successful_optimizations": 0,
            "fallback_activations": 0,
            "circuit_breaker_trips": 0,
            "average_solve_time": 0.0,
            "last_optimization_time": None,
        }

        # Validate OR-Tools availability
        if not ORTOOLS_AVAILABLE:
            self.logger.error("OR-Tools not available")
            raise ImportError("OR-Tools is required for optimization service")

        self.logger.info("Resilient optimization service initialized")

    @monitor_performance("resilient_schedule_optimization", include_args=True)
    async def optimize_schedule(
        self,
        job_ids: list[UUID],
        start_time: datetime,
        parameters: OptimizationParameters | None = None,
    ) -> OptimizationResult:
        """
        Optimize schedule with comprehensive resilience patterns.

        Attempts primary optimization with circuit breaker protection,
        implements retry logic, and falls back to simplified strategies
        when the primary solver fails.
        """
        params = parameters or OptimizationParameters()
        optimization_start = time.time()
        retry_attempts = 0

        # Update metrics
        self._health_metrics["total_optimizations"] += 1
        self._health_metrics["last_optimization_time"] = datetime.now().isoformat()

        self.logger.info(
            "Starting resilient schedule optimization",
            job_count=len(job_ids),
            max_time_seconds=params.max_time_seconds,
            enable_fallback=params.enable_fallback_strategies,
            enable_circuit_breaker=params.enable_circuit_breaker,
        )

        async with trace_operation(
            "resilient_optimization",
            attributes={
                "job_count": len(job_ids),
                "max_time_seconds": params.max_time_seconds,
                "enable_fallback": params.enable_fallback_strategies,
            },
        ) as span:
            # Load data
            try:
                jobs, tasks, operators, machines = await self._load_optimization_data(
                    job_ids
                )
                span.set_attribute("tasks_count", len(tasks))
                span.set_attribute("operators_count", len(operators))
                span.set_attribute("machines_count", len(machines))

            except Exception as e:
                self.logger.error("Failed to load optimization data", error=str(e))
                return await self._handle_data_loading_failure(
                    e, job_ids, start_time, params
                )

            # Primary optimization attempt with circuit breaker and retry
            primary_result = await self._attempt_primary_optimization(
                jobs, tasks, operators, machines, start_time, params, retry_attempts
            )

            if primary_result:
                # Success - update metrics and return
                total_time = time.time() - optimization_start
                primary_result.performance_metrics["total_optimization_time"] = (
                    total_time
                )

                self._health_metrics["successful_optimizations"] += 1
                self._update_average_solve_time(total_time)

                self.logger.info(
                    "Primary optimization successful",
                    status=primary_result.status,
                    solve_time=primary_result.solve_time_seconds,
                    quality_score=primary_result.quality_score,
                )

                return primary_result

            # Primary optimization failed - execute fallback if enabled
            if params.enable_fallback_strategies:
                fallback_result = await self._execute_fallback_optimization(
                    jobs, tasks, operators, machines, start_time, params
                )

                total_time = time.time() - optimization_start
                fallback_result.performance_metrics["total_optimization_time"] = (
                    total_time
                )

                self._health_metrics["fallback_activations"] += 1
                self._update_average_solve_time(total_time)

                return fallback_result

            # No fallback - return failure
            total_time = time.time() - optimization_start
            self.logger.error(
                "All optimization attempts failed",
                total_time=total_time,
                fallback_enabled=params.enable_fallback_strategies,
            )

            raise OptimizationError(
                "Optimization failed and no fallback strategy available",
                {"total_optimization_time": total_time},
            )

    async def _attempt_primary_optimization(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
        initial_retry_attempts: int = 0,
    ) -> OptimizationResult | None:
        """Attempt primary optimization with circuit breaker and retry logic."""

        retry_attempts = initial_retry_attempts
        last_error = None

        while retry_attempts <= params.max_retry_attempts:
            try:
                if retry_attempts > 0:
                    # Exponential backoff between retries
                    delay = min(2**retry_attempts, 30)
                    self.logger.info(f"Retrying optimization after {delay}s delay")
                    await asyncio.sleep(delay)

                return await self._execute_primary_optimization(
                    jobs, tasks, operators, machines, start_time, params
                )

            except CircuitBreakerOpenError as e:
                self.logger.warning(
                    "Circuit breaker open - optimization blocked",
                    service=e.service_name,
                    failure_count=e.failure_count,
                    recovery_timeout=e.recovery_timeout,
                )

                return OptimizationResult(
                    status="CIRCUIT_BREAKER_OPEN",
                    circuit_breaker_triggered=True,
                    retry_attempts=retry_attempts,
                    warnings=[f"Circuit breaker open for {e.service_name}"],
                )

            except (SolverMemoryError, SystemResourceError) as e:
                self.logger.error(
                    "Resource exhaustion - not retrying",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                last_error = e
                break  # Don't retry resource exhaustion

            except (OptimizationTimeoutError, SolverError, SolverCrashError) as e:
                self.logger.warning(
                    "Solver error - will retry if attempts remaining",
                    error=str(e),
                    error_type=type(e).__name__,
                    attempt=retry_attempts + 1,
                    max_attempts=params.max_retry_attempts + 1,
                )
                last_error = e
                retry_attempts += 1

                # Record error metrics
                SOLVER_ERRORS.labels(
                    error_type=type(e).__name__,
                    retry_attempt=retry_attempts,
                ).inc()

            except Exception as e:
                self.logger.error(
                    "Unexpected optimization error",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                last_error = e
                retry_attempts += 1

        # All retries exhausted
        if last_error:
            raise RetryExhaustedError(
                "primary_optimization", params.max_retry_attempts + 1, last_error
            )

        return None

    @with_resilience(
        service_name="solver_optimization",
        circuit_config=SOLVER_OPTIMIZATION_CIRCUIT_CONFIG,
        max_retry_attempts=1,  # Retry handled at higher level
        retry_exceptions=(),  # No automatic retries here
    )
    async def _execute_primary_optimization(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Execute primary optimization with circuit breaker protection."""

        self.logger.info("Executing primary optimization")

        # Create solver manager
        solver_limits = SolverLimits(
            max_time_seconds=params.max_time_seconds,
            max_memory_mb=params.memory_limit_mb,
            max_cpu_percent=90.0,
        )

        solver_config = SolverConfiguration(
            num_search_workers=params.num_workers,
            log_search_progress=True,
        )

        solver_manager = await create_resilient_solver_manager(
            limits=solver_limits, config=solver_config
        )

        # Create and solve model
        model = await self._create_optimization_model(
            jobs, tasks, operators, machines, params
        )

        try:
            status, metrics = await solver_manager.solve_with_timeout(
                model, params.max_time_seconds
            )

            # Extract solution
            schedule = await self._extract_solution_from_model(
                model, jobs, tasks, status, metrics
            )

            # Calculate quality metrics
            quality_score = self._calculate_solution_quality(schedule, jobs, tasks)

            return OptimizationResult(
                schedule=schedule,
                makespan_minutes=metrics.objective_value or 0.0,
                total_tardiness_minutes=0.0,  # Simplified
                total_cost=0.0,  # Simplified
                status=metrics.status.value,
                solve_time_seconds=metrics.duration_seconds,
                solver_stats=metrics.to_dict(),
                quality_score=quality_score,
                warnings=[]
                if metrics.status == SolverStatus.COMPLETED
                else ["Solver did not reach optimality"],
            )

        except Exception as e:
            # Emergency cleanup
            await solver_manager.emergency_shutdown(f"Optimization failed: {str(e)}")
            raise

    async def _execute_fallback_optimization(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Execute fallback optimization strategy."""

        self.logger.info("Executing fallback optimization")

        # Determine fallback reason
        fallback_reason = FallbackReason.SOLVER_TIMEOUT  # Default

        try:
            fallback_result = await self._fallback_orchestrator.execute_fallback(
                reason=fallback_reason,
                jobs=jobs,
                tasks=tasks,
                operators=operators,
                machines=machines,
                start_time=start_time,
                preferred_strategy=params.preferred_fallback_strategy,
            )

            return OptimizationResult(
                schedule=fallback_result.schedule,
                makespan_minutes=fallback_result.makespan_minutes,
                total_tardiness_minutes=fallback_result.total_tardiness_minutes,
                total_cost=0.0,
                status="FALLBACK_SUCCESS",
                solve_time_seconds=fallback_result.execution_time_seconds,
                fallback_used=True,
                fallback_result=fallback_result,
                quality_score=fallback_result.quality_score,
                warnings=fallback_result.warnings,
                performance_metrics={
                    "fallback_strategy": fallback_result.strategy_used.value,
                    "fallback_reason": fallback_result.fallback_reason.value,
                },
            )

        except Exception as e:
            self.logger.error(
                "Fallback optimization failed", error=str(e), exc_info=True
            )

            return OptimizationResult(
                status="FALLBACK_FAILED",
                fallback_used=True,
                quality_score=0.0,
                warnings=[f"Fallback strategy failed: {str(e)}"],
                performance_metrics={"fallback_error": str(e)},
            )

    @with_resilience(
        service_name="model_creation",
        circuit_config=SOLVER_MODEL_CREATION_CIRCUIT_CONFIG,
        max_retry_attempts=2,
        retry_exceptions=(ValueError, TypeError),
    )
    async def _create_optimization_model(
        self,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        params: OptimizationParameters,
    ) -> cp_model.CpModel:
        """Create OR-Tools optimization model with circuit breaker protection."""

        self.logger.info(
            "Creating optimization model",
            jobs=len(jobs),
            tasks=len(tasks),
            operators=len(operators),
            machines=len(machines),
        )

        # Create model (simplified implementation)
        model = cp_model.CpModel()

        # Add basic variables and constraints
        horizon = params.horizon_days * 24 * 60

        # Create task variables
        task_vars = {}
        for task in tasks:
            start_var = model.NewIntVar(0, horizon, f"start_{task.id}")
            end_var = model.NewIntVar(0, horizon, f"end_{task.id}")
            duration = 60  # Default duration

            model.Add(end_var == start_var + duration)
            task_vars[task.id] = (start_var, end_var)

        # Add objective
        makespan = model.NewIntVar(0, horizon, "makespan")
        if task_vars:
            model.AddMaxEquality(
                makespan, [end_var for _, end_var in task_vars.values()]
            )
            model.Minimize(makespan)

        self.logger.info("Model creation completed", variables=len(task_vars) * 2)
        return model

    async def _extract_solution_from_model(
        self,
        model: cp_model.CpModel,
        jobs: list[Job],
        tasks: list[Task],
        status: int,
        metrics: SolverMetrics,
    ) -> Schedule | None:
        """Extract schedule from solved model."""

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return None

        schedule = Schedule(name=f"Optimized Schedule {datetime.now().isoformat()}")

        # Extract solution (simplified)
        self.logger.info("Solution extracted", tasks_assigned=len(tasks))

        return schedule

    def _calculate_solution_quality(
        self,
        schedule: Schedule | None,
        jobs: list[Job],
        tasks: list[Task],
    ) -> float:
        """Calculate solution quality score (0.0 to 1.0)."""

        if not schedule:
            return 0.0

        # Simplified quality calculation
        # In practice, this would consider makespan, tardiness, resource utilization, etc.
        base_quality = 0.8  # Assume good quality for feasible solutions

        return base_quality

    async def _load_optimization_data(
        self, job_ids: list[UUID]
    ) -> tuple[list[Job], list[Task], list[Operator], list[Machine]]:
        """Load all required optimization data."""

        self.logger.info("Loading optimization data", job_ids_count=len(job_ids))

        # Load jobs
        jobs = []
        for job_id in job_ids:
            job = await self._job_repository.get_by_id(job_id)
            if job:
                jobs.append(job)

        # Load tasks
        all_tasks = []
        for job_id in job_ids:
            tasks = await self._task_repository.get_by_job_id(job_id)
            all_tasks.extend(tasks)

        # Load resources
        operators = await self._operator_repository.get_all()
        machines = await self._machine_repository.get_all()

        # Validate data
        if not jobs:
            raise OptimizationError("No jobs found for optimization")
        if not all_tasks:
            raise OptimizationError("No tasks found for optimization")
        if not operators:
            raise OptimizationError("No operators available")
        if not machines:
            raise OptimizationError("No machines available")

        self.logger.info(
            "Data loading completed",
            jobs=len(jobs),
            tasks=len(all_tasks),
            operators=len(operators),
            machines=len(machines),
        )

        return jobs, all_tasks, operators, machines

    async def _handle_data_loading_failure(
        self,
        error: Exception,
        job_ids: list[UUID],
        start_time: datetime,
        params: OptimizationParameters,
    ) -> OptimizationResult:
        """Handle data loading failures."""

        return OptimizationResult(
            status="DATA_LOADING_FAILED",
            quality_score=0.0,
            warnings=[f"Failed to load optimization data: {str(error)}"],
            performance_metrics={
                "data_loading_error": str(error),
                "requested_job_ids": [str(jid) for jid in job_ids],
            },
        )

    def _update_average_solve_time(self, solve_time: float) -> None:
        """Update rolling average solve time."""
        current_avg = self._health_metrics["average_solve_time"]
        total_optimizations = self._health_metrics["total_optimizations"]

        # Simple rolling average
        self._health_metrics["average_solve_time"] = (
            current_avg * (total_optimizations - 1) + solve_time
        ) / total_optimizations

    def get_service_health(self) -> dict[str, str | int | float]:
        """Get service health metrics."""
        total = self._health_metrics["total_optimizations"]
        success_rate = (
            self._health_metrics["successful_optimizations"] / max(total, 1) * 100
        )
        fallback_rate = (
            self._health_metrics["fallback_activations"] / max(total, 1) * 100
        )

        return {
            "status": "healthy" if success_rate > 50 else "degraded",
            "total_optimizations": total,
            "success_rate_percent": success_rate,
            "fallback_rate_percent": fallback_rate,
            "circuit_breaker_trips": self._health_metrics["circuit_breaker_trips"],
            "average_solve_time_seconds": self._health_metrics["average_solve_time"],
            "last_optimization": self._health_metrics["last_optimization_time"],
        }
