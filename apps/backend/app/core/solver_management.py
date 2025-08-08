"""
Resilient Solver Management Service

Provides comprehensive solver lifecycle management with timeout handling, memory limits,
resource cleanup, and graceful degradation patterns for OR-Tools operations.
"""

import asyncio
import gc
import os
import resource
import tempfile
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import psutil

try:
    from ortools.sat.python import cp_model  # type: ignore[import-not-found]

    ORTOOLS_AVAILABLE = True
except ImportError:
    cp_model = None
    ORTOOLS_AVAILABLE = False

from ..domain.shared.exceptions import (
    MemoryExhaustionError,
    OptimizationTimeoutError,
    SolverConfigurationError,
    SolverError,
    SolverMemoryError,
    SystemResourceError,
)
from .circuit_breaker import CircuitBreakerConfig, with_resilience
from .observability import SOLVER_METRICS, get_logger


class SolverStatus(Enum):
    """Solver execution status."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    CRASHED = "crashed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class SolverLimits:
    """Resource limits for solver execution."""

    max_time_seconds: int = 300
    max_memory_mb: int = 4096
    max_cpu_percent: float = 80.0
    max_temp_files: int = 100
    max_temp_file_size_mb: int = 1024
    enable_swap: bool = False
    priority_level: int = 0  # -20 to 19 (lower = higher priority)


@dataclass
class SolverConfiguration:
    """Configuration for OR-Tools solver."""

    num_search_workers: int = 8
    log_search_progress: bool = True
    use_fixed_search: bool = False
    search_branching: str = "PORTFOLIO_SEARCH"
    linearization_level: int = 1
    cp_model_presolve: bool = True
    cp_model_probing_level: int = 2
    symmetry_level: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OR-Tools parameters."""
        return {
            "num_search_workers": self.num_search_workers,
            "log_search_progress": self.log_search_progress,
            "use_fixed_search": self.use_fixed_search,
            "search_branching": self.search_branching,
            "linearization_level": self.linearization_level,
            "cp_model_presolve": self.cp_model_presolve,
            "cp_model_probing_level": self.cp_model_probing_level,
            "symmetry_level": self.symmetry_level,
        }


@dataclass
class SolverMetrics:
    """Comprehensive solver execution metrics."""

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    status: SolverStatus = SolverStatus.INITIALIZING
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    num_variables: int = 0
    num_constraints: int = 0
    objective_value: float | None = None
    best_bound: float | None = None
    gap_percent: float | None = None
    num_branches: int = 0
    num_conflicts: int = 0
    wall_time: float = 0.0
    user_time: float = 0.0
    temp_files_created: int = 0
    temp_files_size_mb: float = 0.0
    solver_version: str = ""
    error_message: str | None = None
    partial_solution: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "peak_memory_mb": self.peak_memory_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "num_variables": self.num_variables,
            "num_constraints": self.num_constraints,
            "objective_value": self.objective_value,
            "best_bound": self.best_bound,
            "gap_percent": self.gap_percent,
            "num_branches": self.num_branches,
            "num_conflicts": self.num_conflicts,
            "wall_time": self.wall_time,
            "user_time": self.user_time,
            "temp_files_created": self.temp_files_created,
            "temp_files_size_mb": self.temp_files_size_mb,
            "solver_version": self.solver_version,
            "error_message": self.error_message,
            "partial_solution": self.partial_solution,
        }


class SolverResourceMonitor:
    """Monitor solver resource usage in real-time."""

    def __init__(self, limits: SolverLimits):
        self.limits = limits
        self.logger = get_logger("solver_monitor")
        self._monitoring = False
        self._process: psutil.Process | None = None
        self._metrics = SolverMetrics()

    async def start_monitoring(self, process_id: int | None = None) -> None:
        """Start monitoring solver resource usage."""
        try:
            if process_id:
                self._process = psutil.Process(process_id)
            else:
                self._process = psutil.Process(os.getpid())

            self._monitoring = True
            asyncio.create_task(self._monitor_resources())

        except psutil.NoSuchProcess:
            self.logger.warning("Cannot monitor: process not found", pid=process_id)
        except Exception as e:
            self.logger.error("Failed to start resource monitoring", error=str(e))

    async def stop_monitoring(self) -> SolverMetrics:
        """Stop monitoring and return metrics."""
        self._monitoring = False
        self._metrics.end_time = time.time()
        self._metrics.duration_seconds = (
            self._metrics.end_time - self._metrics.start_time
        )
        return self._metrics

    async def _monitor_resources(self) -> None:
        """Monitor resources continuously."""
        while self._monitoring and self._process:
            try:
                # Monitor memory usage
                memory_info = self._process.memory_info()
                current_memory_mb = memory_info.rss / (1024 * 1024)
                self._metrics.peak_memory_mb = max(
                    self._metrics.peak_memory_mb, current_memory_mb
                )

                # Monitor CPU usage
                self._metrics.cpu_usage_percent = self._process.cpu_percent(
                    interval=0.1
                )

                # Check memory limits
                if current_memory_mb > self.limits.max_memory_mb:
                    self.logger.error(
                        "Memory limit exceeded",
                        current_mb=current_memory_mb,
                        limit_mb=self.limits.max_memory_mb,
                    )
                    raise SolverMemoryError(
                        memory_limit_mb=self.limits.max_memory_mb,
                        peak_memory_mb=int(current_memory_mb),
                    )

                # Check CPU limits
                if self._metrics.cpu_usage_percent > self.limits.max_cpu_percent:
                    self.logger.warning(
                        "High CPU usage detected",
                        current_percent=self._metrics.cpu_usage_percent,
                        limit_percent=self.limits.max_cpu_percent,
                    )

                await asyncio.sleep(1.0)  # Monitor every second

            except psutil.NoSuchProcess:
                # Process terminated
                break
            except Exception as e:
                self.logger.error("Resource monitoring error", error=str(e))
                break


class ResilientSolverManager:
    """
    Comprehensive solver management with resilience patterns.

    Provides timeout handling, memory management, resource cleanup,
    and graceful degradation for OR-Tools solver operations.
    """

    def __init__(
        self,
        limits: SolverLimits | None = None,
        config: SolverConfiguration | None = None,
    ):
        """Initialize the resilient solver manager."""
        self.limits = limits or SolverLimits()
        self.config = config or SolverConfiguration()
        self.logger = get_logger(__name__)
        self._temp_files: list[Path] = []
        self._active_processes: dict[str, psutil.Process] = {}

        # Validate OR-Tools availability
        if not ORTOOLS_AVAILABLE:
            raise ImportError("OR-Tools is required for solver management")

        self.logger.info(
            "Resilient solver manager initialized",
            limits=self.limits.__dict__,
            config=self.config.__dict__,
        )

    @asynccontextmanager
    async def managed_solve(
        self, model: cp_model.CpModel, execution_id: str | None = None
    ) -> AsyncGenerator[tuple[cp_model.CpSolver, SolverMetrics], None]:
        """
        Context manager for managed solver execution with comprehensive monitoring.

        Provides resource monitoring, timeout handling, cleanup, and metrics collection.
        """
        execution_id = execution_id or str(uuid4())
        metrics = SolverMetrics(execution_id=execution_id)
        solver = None
        monitor = None

        try:
            # Pre-solve validation and setup
            await self._validate_system_resources()
            await self._setup_solver_environment()

            # Create and configure solver
            solver = cp_model.CpSolver()
            await self._configure_solver(solver, metrics)

            # Setup resource monitoring
            monitor = SolverResourceMonitor(self.limits)
            await monitor.start_monitoring()

            # Set process priority
            if self.limits.priority_level != 0:
                try:
                    os.nice(self.limits.priority_level)
                except OSError as e:
                    self.logger.warning("Failed to set process priority", error=str(e))

            metrics.status = SolverStatus.RUNNING
            self.logger.info(
                "Starting managed solver execution",
                execution_id=execution_id,
                variables=model.Proto().variables,
                constraints=len(model.Proto().constraints),
            )

            yield solver, metrics

            # Successful completion
            metrics.status = SolverStatus.COMPLETED

        except asyncio.TimeoutError:
            metrics.status = SolverStatus.TIMEOUT
            metrics.error_message = (
                f"Solver timed out after {self.limits.max_time_seconds} seconds"
            )
            raise OptimizationTimeoutError(
                timeout_seconds=self.limits.max_time_seconds,
                solver_stats=metrics.to_dict(),
            )

        except SolverMemoryError as e:
            metrics.status = SolverStatus.MEMORY_EXCEEDED
            metrics.error_message = str(e)
            raise

        except Exception as e:
            metrics.status = SolverStatus.ERROR
            metrics.error_message = str(e)
            self.logger.error(
                "Solver execution failed",
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise

        finally:
            # Stop monitoring and collect final metrics
            if monitor:
                metrics = await monitor.stop_monitoring()

            # Perform cleanup
            await self._cleanup_solver_resources(execution_id)

            # Log final metrics
            self.logger.info(
                "Solver execution completed",
                execution_id=execution_id,
                status=metrics.status.value,
                duration_seconds=metrics.duration_seconds,
                peak_memory_mb=metrics.peak_memory_mb,
                variables=metrics.num_variables,
                constraints=metrics.num_constraints,
            )

            # Update Prometheus metrics
            SOLVER_METRICS.labels(
                status=metrics.status.value,
                execution_id=execution_id,
            ).observe(metrics.duration_seconds)

    async def solve_with_timeout(
        self, model: cp_model.CpModel, timeout_seconds: int | None = None
    ) -> tuple[int, SolverMetrics]:
        """
        Solve model with comprehensive timeout and resource management.

        Returns solver status and detailed metrics.
        """
        timeout_seconds = timeout_seconds or self.limits.max_time_seconds

        async with self.managed_solve(model) as (solver, metrics):
            try:
                # Configure solver timeout
                solver.parameters.max_time_in_seconds = timeout_seconds

                # Extract model statistics
                model_proto = model.Proto()
                metrics.num_variables = len(model_proto.variables)
                metrics.num_constraints = len(model_proto.constraints)

                # Run solver with timeout
                solve_task = asyncio.create_task(
                    self._run_solver_async(solver, model, metrics)
                )

                status = await asyncio.wait_for(
                    solve_task, timeout=timeout_seconds + 10
                )

                # Collect final solver statistics
                await self._collect_solver_statistics(solver, metrics)

                return status, metrics

            except asyncio.TimeoutError:
                # Cancel the solve task
                solve_task.cancel()

                # Try to get partial solution
                try:
                    await asyncio.wait_for(solve_task, timeout=5.0)
                except:
                    pass

                metrics.partial_solution = self._has_partial_solution(solver)
                raise OptimizationTimeoutError(
                    timeout_seconds=timeout_seconds,
                    partial_solution=metrics.partial_solution,
                    solver_stats=metrics.to_dict(),
                )

    async def _run_solver_async(
        self, solver: cp_model.CpSolver, model: cp_model.CpModel, metrics: SolverMetrics
    ) -> int:
        """Run solver asynchronously."""

        def solve_in_thread():
            return solver.Solve(model)

        # Run solver in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, solve_in_thread)

    async def _validate_system_resources(self) -> None:
        """Validate system has sufficient resources."""
        # Check available memory
        memory = psutil.virtual_memory()
        available_mb = memory.available / (1024 * 1024)

        if available_mb < self.limits.max_memory_mb * 1.5:  # 50% buffer
            raise MemoryExhaustionError(
                available_mb=int(available_mb),
                required_mb=int(self.limits.max_memory_mb * 1.5),
            )

        # Check CPU load
        cpu_percent = psutil.cpu_percent(interval=1.0)
        if cpu_percent > 95.0:
            self.logger.warning(
                "High CPU load detected",
                cpu_percent=cpu_percent,
                recommended_action="Consider reducing solver workers",
            )

        # Check disk space for temp files
        disk = psutil.disk_usage(tempfile.gettempdir())
        available_gb = disk.free / (1024 * 1024 * 1024)

        if available_gb < 1.0:  # Require at least 1GB free
            raise SystemResourceError(
                "Insufficient disk space for temporary files",
                "disk",
                {"available_gb": available_gb, "required_gb": 1.0},
            )

    async def _setup_solver_environment(self) -> None:
        """Setup solver execution environment."""
        # Set memory limits using resource module
        try:
            # Convert MB to bytes
            memory_limit_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes)
            )

            self.logger.info(
                "Memory limits configured", limit_mb=self.limits.max_memory_mb
            )
        except (OSError, ValueError) as e:
            self.logger.warning("Failed to set memory limits", error=str(e))

        # Configure garbage collection
        gc.set_threshold(700, 10, 10)  # More aggressive GC

        # Create temp directory for solver files
        temp_dir = Path(tempfile.mkdtemp(prefix="solver_"))
        self._temp_files.append(temp_dir)

        # Set environment variables for solver
        os.environ["TMPDIR"] = str(temp_dir)
        os.environ["OMP_NUM_THREADS"] = str(
            min(self.config.num_search_workers, os.cpu_count() or 1)
        )

    async def _configure_solver(
        self, solver: cp_model.CpSolver, metrics: SolverMetrics
    ) -> None:
        """Configure solver parameters."""
        try:
            # Apply configuration parameters
            solver.parameters.max_time_in_seconds = self.limits.max_time_seconds
            solver.parameters.num_search_workers = self.config.num_search_workers
            solver.parameters.log_search_progress = self.config.log_search_progress

            # Advanced configuration
            solver.parameters.use_fixed_search = self.config.use_fixed_search
            solver.parameters.linearization_level = self.config.linearization_level
            solver.parameters.cp_model_presolve = self.config.cp_model_presolve
            solver.parameters.cp_model_probing_level = (
                self.config.cp_model_probing_level
            )
            solver.parameters.symmetry_level = self.config.symmetry_level

            # Memory management
            if not self.limits.enable_swap:
                solver.parameters.enumerate_all_solutions = False

            metrics.solver_version = "OR-Tools 9.8+"  # Would get actual version

            self.logger.info(
                "Solver configured",
                max_time_seconds=self.limits.max_time_seconds,
                workers=self.config.num_search_workers,
                presolve=self.config.cp_model_presolve,
            )

        except Exception as e:
            raise SolverConfigurationError(
                parameter="solver_configuration",
                value=str(self.config.to_dict()),
                reason=str(e),
            )

    async def _collect_solver_statistics(
        self, solver: cp_model.CpSolver, metrics: SolverMetrics
    ) -> None:
        """Collect detailed solver statistics."""
        try:
            # Basic statistics
            if hasattr(solver, "ObjectiveValue"):
                metrics.objective_value = solver.ObjectiveValue()
            if hasattr(solver, "BestObjectiveBound"):
                metrics.best_bound = solver.BestObjectiveBound()

            # Calculate optimality gap
            if metrics.objective_value is not None and metrics.best_bound is not None:
                if metrics.objective_value != 0:
                    metrics.gap_percent = abs(
                        (metrics.objective_value - metrics.best_bound)
                        / metrics.objective_value
                        * 100
                    )

            # Solver performance metrics
            metrics.num_branches = solver.NumBranches()
            metrics.num_conflicts = solver.NumConflicts()
            metrics.wall_time = solver.WallTime()
            metrics.user_time = solver.UserTime()

            self.logger.info(
                "Solver statistics collected",
                objective=metrics.objective_value,
                gap_percent=metrics.gap_percent,
                branches=metrics.num_branches,
                conflicts=metrics.num_conflicts,
            )

        except Exception as e:
            self.logger.warning("Failed to collect solver statistics", error=str(e))

    def _has_partial_solution(self, solver: cp_model.CpSolver) -> bool:
        """Check if solver has a partial solution available."""
        try:
            # Check if solver found any solution
            return (
                hasattr(solver, "ObjectiveValue")
                and solver.ObjectiveValue() is not None
            )
        except:
            return False

    async def _cleanup_solver_resources(self, execution_id: str) -> None:
        """Cleanup solver resources and temporary files."""
        try:
            # Remove from active processes
            if execution_id in self._active_processes:
                process = self._active_processes[execution_id]
                if process.is_running():
                    try:
                        process.terminate()
                        await asyncio.sleep(2.0)
                        if process.is_running():
                            process.kill()
                    except psutil.NoSuchProcess:
                        pass
                del self._active_processes[execution_id]

            # Cleanup temporary files
            for temp_file in self._temp_files[:]:
                try:
                    if temp_file.exists():
                        if temp_file.is_file():
                            temp_file.unlink()
                        elif temp_file.is_dir():
                            import shutil

                            shutil.rmtree(temp_file)
                        self._temp_files.remove(temp_file)
                except Exception as e:
                    self.logger.warning(
                        "Failed to cleanup temp file", path=str(temp_file), error=str(e)
                    )

            # Force garbage collection
            gc.collect()

            self.logger.info("Resource cleanup completed", execution_id=execution_id)

        except Exception as e:
            self.logger.error(
                "Resource cleanup failed", execution_id=execution_id, error=str(e)
            )

    async def emergency_shutdown(self, reason: str = "Emergency shutdown") -> None:
        """Emergency shutdown of all solver processes."""
        self.logger.warning("Emergency solver shutdown initiated", reason=reason)

        # Terminate all active processes
        for execution_id, process in list(self._active_processes.items()):
            try:
                if process.is_running():
                    process.kill()
                await self._cleanup_solver_resources(execution_id)
            except Exception as e:
                self.logger.error(
                    "Failed to kill process", execution_id=execution_id, error=str(e)
                )

        # Clear all temporary files
        for temp_file in self._temp_files[:]:
            try:
                if temp_file.exists():
                    if temp_file.is_file():
                        temp_file.unlink()
                    elif temp_file.is_dir():
                        import shutil

                        shutil.rmtree(temp_file)
            except:
                pass

        self._temp_files.clear()
        self._active_processes.clear()

        self.logger.info("Emergency shutdown completed")


# Circuit breaker configuration for solver operations
SOLVER_RESILIENCE_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=300,  # 5 minutes
    expected_exception=(SolverError, OptimizationTimeoutError, SystemResourceError),
    name="solver_operations",
)


@with_resilience(
    service_name="solver_manager",
    circuit_config=SOLVER_RESILIENCE_CONFIG,
    max_retry_attempts=2,
    min_wait=5.0,
    max_wait=30.0,
    retry_exceptions=(SolverError, SystemResourceError),
)
async def create_resilient_solver_manager(
    limits: SolverLimits | None = None, config: SolverConfiguration | None = None
) -> ResilientSolverManager:
    """Create a resilient solver manager with circuit breaker protection."""
    return ResilientSolverManager(limits=limits, config=config)
