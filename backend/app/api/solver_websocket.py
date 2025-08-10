"""
Solver WebSocket Integration

Provides real-time solver progress updates through WebSocket broadcasting.
Integrates with OR-Tools CP-SAT solver callbacks for live optimization monitoring.
"""

import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from ortools.sat.python import cp_model

from app.api.websockets import connection_manager
from app.core.observability import (
    SOLVER_METRICS,
    SOLVER_STATUS,
    get_logger,
)

logger = get_logger(__name__)


@dataclass
class SolverProgress:
    """Solver progress information."""

    iteration: int
    objective_value: float
    best_bound: float
    gap: float
    num_solutions: int
    num_branches: int
    num_conflicts: int
    wall_time: float
    user_time: float
    deterministic_time: float
    status: str
    progress_percentage: float


class WebSocketSolutionCallback(cp_model.CpSolverSolutionCallback):
    """
    CP-SAT solver callback that broadcasts progress through WebSocket.

    This callback is called each time the solver finds a new solution,
    allowing real-time monitoring of the optimization process.
    """

    def __init__(
        self,
        schedule_id: str,
        job_id: str | None = None,
        broadcast_interval: float = 1.0,
    ):
        """
        Initialize the WebSocket solution callback.

        Args:
            schedule_id: ID of the schedule being optimized
            job_id: Optional specific job ID
            broadcast_interval: Minimum seconds between broadcasts
        """
        super().__init__()
        self.schedule_id = schedule_id
        self.job_id = job_id
        self.broadcast_interval = broadcast_interval
        self.last_broadcast = 0
        self.solution_count = 0
        self.start_time = time.time()
        self.best_objective = float("inf")
        self.initial_objective = None

        # Async event loop for broadcasting
        self.loop = None
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create new event loop if none exists
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def on_solution_callback(self):
        """Called when a new solution is found."""
        self.solution_count += 1
        current_time = time.time()

        # Get current objective value
        objective_value = self.ObjectiveValue()

        # Track initial and best objectives
        if self.initial_objective is None:
            self.initial_objective = objective_value

        if objective_value < self.best_objective:
            self.best_objective = objective_value

        # Calculate progress
        current_time - self.start_time
        progress_percentage = self._calculate_progress()

        # Create progress snapshot
        progress = SolverProgress(
            iteration=self.solution_count,
            objective_value=objective_value,
            best_bound=self.BestObjectiveBound(),
            gap=self._calculate_gap(),
            num_solutions=self.solution_count,
            num_branches=self.NumBranches(),
            num_conflicts=self.NumConflicts(),
            wall_time=self.WallTime(),
            user_time=self.UserTime(),
            deterministic_time=self.DeterministicTime(),
            status="optimizing",
            progress_percentage=progress_percentage,
        )

        # Broadcast if enough time has passed
        if current_time - self.last_broadcast >= self.broadcast_interval:
            self.last_broadcast = current_time
            self._broadcast_progress(progress)

        # Log progress
        logger.info(
            "Solver found new solution",
            schedule_id=self.schedule_id,
            solution_num=self.solution_count,
            objective=objective_value,
            best_bound=self.BestObjectiveBound(),
            gap_percent=round(self._calculate_gap() * 100, 2),
            wall_time=round(self.WallTime(), 2),
        )

        # Update metrics
        SOLVER_STATUS.labels(status="solution_found").inc()

    def _calculate_gap(self) -> float:
        """Calculate the optimality gap."""
        objective = self.ObjectiveValue()
        bound = self.BestObjectiveBound()

        if abs(objective) < 1e-6:
            return 0.0

        return abs(objective - bound) / abs(objective)

    def _calculate_progress(self) -> float:
        """
        Calculate estimated progress percentage.

        This is a heuristic based on gap closure and time.
        """
        gap = self._calculate_gap()

        # Progress based on gap (0% gap = 100% progress)
        gap_progress = (1.0 - gap) * 100

        # Time-based progress (assume max 5 minutes)
        time_progress = min(self.WallTime() / 300.0, 1.0) * 100

        # Weight gap progress more heavily
        return min(gap_progress * 0.7 + time_progress * 0.3, 100.0)

    def _broadcast_progress(self, progress: SolverProgress):
        """Broadcast solver progress through WebSocket."""
        try:
            # Create broadcast message
            message = {
                "type": "solver_progress",
                "schedule_id": self.schedule_id,
                "job_id": self.job_id,
                "progress": asdict(progress),
                "timestamp": datetime.now().isoformat(),
            }

            # Broadcast to relevant topics
            topics = [f"schedule_{self.schedule_id}", "solver_progress", "dashboard"]

            if self.job_id:
                topics.append(f"job_{self.job_id}")

            # Use asyncio to broadcast
            if self.loop and self.loop.is_running():
                for topic in topics:
                    asyncio.create_task(
                        connection_manager.broadcast_to_topic(topic, message)
                    )
            else:
                # Fallback: create new event loop
                asyncio.run(self._async_broadcast(topics, message))

        except Exception as e:
            logger.error(
                "Failed to broadcast solver progress",
                error=str(e),
                schedule_id=self.schedule_id,
            )

    async def _async_broadcast(self, topics: list, message: dict):
        """Async helper for broadcasting."""
        for topic in topics:
            await connection_manager.broadcast_to_topic(topic, message)

    def on_solution_callback_end(self):
        """Called when the solver finishes."""
        # Final progress broadcast
        progress = SolverProgress(
            iteration=self.solution_count,
            objective_value=self.best_objective,
            best_bound=self.BestObjectiveBound(),
            gap=self._calculate_gap(),
            num_solutions=self.solution_count,
            num_branches=self.NumBranches(),
            num_conflicts=self.NumConflicts(),
            wall_time=self.WallTime(),
            user_time=self.UserTime(),
            deterministic_time=self.DeterministicTime(),
            status="completed",
            progress_percentage=100.0,
        )

        self._broadcast_progress(progress)

        # Update metrics
        SOLVER_METRICS.labels(status="completed").observe(self.WallTime())

        logger.info(
            "Solver completed",
            schedule_id=self.schedule_id,
            total_solutions=self.solution_count,
            best_objective=self.best_objective,
            total_time=round(self.WallTime(), 2),
        )


class WebSocketIntermediateCallback:
    """
    Callback for intermediate solver updates without solutions.

    This provides more frequent updates about solver progress,
    even when no new solutions are found.
    """

    def __init__(
        self,
        schedule_id: str,
        solver: cp_model.CpSolver,
        broadcast_interval: float = 0.5,
    ):
        """
        Initialize intermediate callback.

        Args:
            schedule_id: ID of the schedule being optimized
            solver: The CP-SAT solver instance
            broadcast_interval: Seconds between broadcasts
        """
        self.schedule_id = schedule_id
        self.solver = solver
        self.broadcast_interval = broadcast_interval
        self.last_broadcast = time.time()
        self.start_time = time.time()

    async def update_progress(self):
        """Send periodic progress updates."""
        while self.solver.StatusName() == "UNKNOWN":
            current_time = time.time()

            if current_time - self.last_broadcast >= self.broadcast_interval:
                self.last_broadcast = current_time

                # Get solver statistics
                stats = {
                    "type": "solver_stats",
                    "schedule_id": self.schedule_id,
                    "elapsed_time": current_time - self.start_time,
                    "status": self.solver.StatusName(),
                    "timestamp": datetime.now().isoformat(),
                }

                # Broadcast stats
                await connection_manager.broadcast_to_topic(
                    f"schedule_{self.schedule_id}", stats
                )

                await connection_manager.broadcast_to_topic("solver_progress", stats)

            await asyncio.sleep(self.broadcast_interval)


def create_websocket_solver(
    model: cp_model.CpModel,
    schedule_id: str,
    job_id: str | None = None,
    time_limit: float = 300.0,
    num_workers: int = 8,
    broadcast_progress: bool = True,
) -> tuple[cp_model.CpSolver, WebSocketSolutionCallback | None]:
    """
    Create a CP-SAT solver with WebSocket progress broadcasting.

    Args:
        model: The constraint programming model
        schedule_id: ID of the schedule being optimized
        job_id: Optional specific job ID
        time_limit: Maximum solving time in seconds
        num_workers: Number of parallel workers
        broadcast_progress: Whether to broadcast progress updates

    Returns:
        Tuple of (solver, callback)
    """
    solver = cp_model.CpSolver()

    # Set solver parameters
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = num_workers
    solver.parameters.log_search_progress = True

    # Create WebSocket callback if broadcasting is enabled
    callback = None
    if broadcast_progress:
        callback = WebSocketSolutionCallback(
            schedule_id=schedule_id, job_id=job_id, broadcast_interval=1.0
        )

        # Broadcast initial status
        asyncio.create_task(
            connection_manager.broadcast_to_topic(
                f"schedule_{schedule_id}",
                {
                    "type": "solver_started",
                    "schedule_id": schedule_id,
                    "job_id": job_id,
                    "time_limit": time_limit,
                    "num_workers": num_workers,
                    "timestamp": datetime.now().isoformat(),
                },
            )
        )

    return solver, callback


async def broadcast_solver_result(
    schedule_id: str,
    status: str,
    solution: dict[str, Any] | None = None,
    error: str | None = None,
):
    """
    Broadcast final solver result.

    Args:
        schedule_id: ID of the schedule
        status: Solver status (OPTIMAL, FEASIBLE, INFEASIBLE, etc.)
        solution: Optional solution data
        error: Optional error message
    """
    message = {
        "type": "solver_result",
        "schedule_id": schedule_id,
        "status": status,
        "solution": solution,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }

    # Broadcast to relevant topics
    await connection_manager.broadcast_to_topic(f"schedule_{schedule_id}", message)

    await connection_manager.broadcast_to_topic("solver_results", message)

    await connection_manager.broadcast_to_topic("dashboard", message)

    # Log result
    logger.info(
        "Solver result broadcasted",
        schedule_id=schedule_id,
        status=status,
        has_solution=solution is not None,
    )
