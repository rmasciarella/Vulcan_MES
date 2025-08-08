"""
Workflow Service

Manages job progression and task state transitions through the production workflow.
Handles task dependencies, status updates, and workflow orchestration.
"""

from datetime import datetime
from uuid import UUID

from ...shared.exceptions import (
    BusinessRuleError,
    PrecedenceConstraintError,
    TaskStatusError,
)
from ..entities.task import Task, TaskStatus
from ..repositories.job_repository import JobRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.task_repository import TaskRepository


class WorkflowState:
    """Represents current workflow state for a job."""

    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id
        self.current_task_id: UUID | None = None
        self.completed_task_ids: set[UUID] = set()
        self.blocked_task_ids: set[UUID] = set()
        self.next_available_tasks: list[UUID] = []


class TaskTransition:
    """Represents a task state transition."""

    def __init__(
        self,
        task_id: UUID,
        from_status: TaskStatus,
        to_status: TaskStatus,
        timestamp: datetime,
        operator_id: UUID | None = None,
        notes: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.from_status = from_status
        self.to_status = to_status
        self.timestamp = timestamp
        self.operator_id = operator_id
        self.notes = notes or ""


class WorkflowService:
    """
    Service for managing job workflow and task state transitions.

    This service orchestrates the progression of jobs through their task sequences,
    managing state transitions, dependencies, and business rules.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
    ) -> None:
        """
        Initialize the workflow service.

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

        # Workflow configuration
        self._auto_start_next_task = True
        self._require_explicit_completion = False
        self._allow_parallel_tasks = False

        # Track state transitions
        self._transition_history: list[TaskTransition] = []

    async def get_job_workflow_state(self, job_id: UUID) -> WorkflowState:
        """
        Get current workflow state for a job.

        Args:
            job_id: Job identifier

        Returns:
            Current workflow state

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job = await self._job_repository.get_by_id(job_id)
        if not job:
            from ...shared.exceptions import JobNotFoundError

            raise JobNotFoundError(job_id)

        state = WorkflowState(job_id)

        # Get all tasks for job
        tasks = await self._task_repository.get_by_job_id(job_id)
        tasks.sort(key=lambda t: t.position_in_job)

        # Analyze task states
        for task in tasks:
            if task.status == TaskStatus.COMPLETED:
                state.completed_task_ids.add(task.id)
            elif task.status == TaskStatus.IN_PROGRESS:
                state.current_task_id = task.id
            elif task.status == TaskStatus.PENDING:
                # Check if task can start (predecessors completed)
                if await self._can_task_start(task, state.completed_task_ids):
                    state.next_available_tasks.append(task.id)
                else:
                    state.blocked_task_ids.add(task.id)

        return state

    async def start_task(
        self,
        task_id: UUID,
        operator_id: UUID | None = None,
        actual_start_time: datetime | None = None,
    ) -> TaskTransition:
        """
        Start execution of a task.

        Args:
            task_id: Task to start
            operator_id: Operator starting the task
            actual_start_time: Actual start time (defaults to now)

        Returns:
            Task transition record

        Raises:
            TaskStatusError: If task cannot be started
            PrecedenceConstraintError: If prerequisites not met
        """
        task = await self._task_repository.get_by_id(task_id)
        if not task:
            from ...shared.exceptions import TaskNotFoundError

            raise TaskNotFoundError(task_id)

        # Validate current status
        if task.status != TaskStatus.PENDING:
            raise TaskStatusError(
                task_id, task.status.value, TaskStatus.IN_PROGRESS.value
            )

        # Check prerequisites
        await self._validate_task_prerequisites(task)

        # Update task
        start_time = actual_start_time or datetime.now()
        task.start_execution(start_time)
        await self._task_repository.update(task)

        # Record transition
        transition = TaskTransition(
            task_id=task_id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.IN_PROGRESS,
            timestamp=start_time,
            operator_id=operator_id,
            notes=f"Task started by operator {operator_id}"
            if operator_id
            else "Task started",
        )
        self._transition_history.append(transition)

        return transition

    async def complete_task(
        self,
        task_id: UUID,
        operator_id: UUID | None = None,
        actual_end_time: datetime | None = None,
        quality_check_passed: bool = True,
    ) -> TaskTransition:
        """
        Complete execution of a task.

        Args:
            task_id: Task to complete
            operator_id: Operator completing the task
            actual_end_time: Actual completion time (defaults to now)
            quality_check_passed: Whether quality check passed

        Returns:
            Task transition record

        Raises:
            TaskStatusError: If task cannot be completed
            BusinessRuleError: If business rules prevent completion
        """
        task = await self._task_repository.get_by_id(task_id)
        if not task:
            from ...shared.exceptions import TaskNotFoundError

            raise TaskNotFoundError(task_id)

        # Validate current status
        if task.status != TaskStatus.IN_PROGRESS:
            raise TaskStatusError(
                task_id, task.status.value, TaskStatus.COMPLETED.value
            )

        # Quality check
        if not quality_check_passed:
            raise BusinessRuleError(
                f"Task {task_id} failed quality check", {"quality_check": False}
            )

        # Update task
        end_time = actual_end_time or datetime.now()
        task.complete_execution(end_time)
        await self._task_repository.update(task)

        # Record transition
        transition = TaskTransition(
            task_id=task_id,
            from_status=TaskStatus.IN_PROGRESS,
            to_status=TaskStatus.COMPLETED,
            timestamp=end_time,
            operator_id=operator_id,
            notes=f"Task completed by operator {operator_id}"
            if operator_id
            else "Task completed",
        )
        self._transition_history.append(transition)

        # Check if job is complete
        if task.job_id:
            await self._check_job_completion(task.job_id)

        # Auto-start next task if enabled
        if self._auto_start_next_task and task.job_id:
            await self._try_auto_start_next_task(task.job_id)

        return transition

    async def cancel_task(
        self, task_id: UUID, reason: str, operator_id: UUID | None = None
    ) -> TaskTransition:
        """
        Cancel a task.

        Args:
            task_id: Task to cancel
            reason: Cancellation reason
            operator_id: Operator cancelling the task

        Returns:
            Task transition record

        Raises:
            TaskStatusError: If task cannot be cancelled
        """
        task = await self._task_repository.get_by_id(task_id)
        if not task:
            from ...shared.exceptions import TaskNotFoundError

            raise TaskNotFoundError(task_id)

        # Validate can be cancelled
        if task.status == TaskStatus.COMPLETED:
            raise TaskStatusError(
                task_id, task.status.value, TaskStatus.CANCELLED.value
            )

        original_status = task.status
        task.cancel()
        await self._task_repository.update(task)

        # Record transition
        transition = TaskTransition(
            task_id=task_id,
            from_status=original_status,
            to_status=TaskStatus.CANCELLED,
            timestamp=datetime.now(),
            operator_id=operator_id,
            notes=f"Task cancelled: {reason}",
        )
        self._transition_history.append(transition)

        return transition

    async def restart_task(
        self, task_id: UUID, operator_id: UUID | None = None
    ) -> TaskTransition:
        """
        Restart a cancelled or completed task.

        Args:
            task_id: Task to restart
            operator_id: Operator restarting the task

        Returns:
            Task transition record

        Raises:
            TaskStatusError: If task cannot be restarted
        """
        task = await self._task_repository.get_by_id(task_id)
        if not task:
            from ...shared.exceptions import TaskNotFoundError

            raise TaskNotFoundError(task_id)

        # Can only restart cancelled tasks or reset completed ones
        if task.status not in [TaskStatus.CANCELLED, TaskStatus.COMPLETED]:
            raise TaskStatusError(task_id, task.status.value, TaskStatus.PENDING.value)

        original_status = task.status
        task.reset()
        await self._task_repository.update(task)

        # Record transition
        transition = TaskTransition(
            task_id=task_id,
            from_status=original_status,
            to_status=TaskStatus.PENDING,
            timestamp=datetime.now(),
            operator_id=operator_id,
            notes="Task restarted",
        )
        self._transition_history.append(transition)

        return transition

    async def advance_job_workflow(self, job_id: UUID) -> list[TaskTransition]:
        """
        Advance job workflow by starting all available next tasks.

        Args:
            job_id: Job to advance

        Returns:
            List of task transitions performed
        """
        transitions = []
        state = await self.get_job_workflow_state(job_id)

        for task_id in state.next_available_tasks:
            try:
                transition = await self.start_task(task_id)
                transitions.append(transition)
            except (TaskStatusError, PrecedenceConstraintError) as e:
                # Log error but continue with other tasks
                print(f"Could not start task {task_id}: {e}")

        return transitions

    async def get_job_progress(self, job_id: UUID) -> dict[str, any]:
        """
        Get job progress metrics.

        Args:
            job_id: Job identifier

        Returns:
            Progress metrics dictionary
        """
        tasks = await self._task_repository.get_by_job_id(job_id)

        if not tasks:
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "in_progress_tasks": 0,
                "pending_tasks": 0,
                "cancelled_tasks": 0,
                "completion_percentage": 0.0,
            }

        status_counts = {
            "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "in_progress": len(
                [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
            ),
            "pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "cancelled": len([t for t in tasks if t.status == TaskStatus.CANCELLED]),
        }

        total_tasks = len(tasks)
        completion_percentage = (
            (status_counts["completed"] / total_tasks) * 100 if total_tasks > 0 else 0
        )

        return {
            "total_tasks": total_tasks,
            "completed_tasks": status_counts["completed"],
            "in_progress_tasks": status_counts["in_progress"],
            "pending_tasks": status_counts["pending"],
            "cancelled_tasks": status_counts["cancelled"],
            "completion_percentage": completion_percentage,
        }

    async def get_critical_path_tasks(self, job_id: UUID) -> list[Task]:
        """
        Get tasks on the critical path for a job.

        Args:
            job_id: Job identifier

        Returns:
            List of critical path tasks
        """
        tasks = await self._task_repository.get_by_job_id(job_id)
        tasks.sort(key=lambda t: t.position_in_job)

        # For sequential workflow, all tasks are on critical path
        # More sophisticated analysis would be needed for parallel workflows
        return tasks

    async def get_bottleneck_tasks(self, job_ids: list[UUID]) -> list[tuple[Task, str]]:
        """
        Identify bottleneck tasks across multiple jobs.

        Args:
            job_ids: Jobs to analyze

        Returns:
            List of (task, bottleneck_reason) tuples
        """
        bottlenecks = []

        for job_id in job_ids:
            tasks = await self._task_repository.get_by_job_id(job_id)

            for task in tasks:
                # Check for common bottleneck conditions
                if task.status == TaskStatus.PENDING:
                    # Check if waiting for predecessors
                    if not await self._can_task_start(task, set()):
                        bottlenecks.append((task, "Waiting for predecessors"))

                elif task.status == TaskStatus.IN_PROGRESS:
                    # Check if task is overdue
                    if task.scheduled_end and datetime.now() > task.scheduled_end:
                        bottlenecks.append((task, "Overdue task"))

                # Check for resource constraints
                if task.requires_multiple_operators():
                    available_ops = (
                        await self._operator_repository.get_available_operators()
                    )
                    qualified_ops = [
                        op
                        for op in available_ops
                        if all(
                            op.has_skill(req.skill_type, req.minimum_level)
                            for req in task.skill_requirements
                        )
                    ]
                    if len(qualified_ops) < 2:
                        bottlenecks.append((task, "Insufficient qualified operators"))

        return bottlenecks

    async def _can_task_start(self, task: Task, completed_task_ids: set[UUID]) -> bool:
        """Check if task prerequisites are met."""
        if not task.job_id:
            return True

        # Get previous task in sequence
        if task.position_in_job == 0:
            return True  # First task can always start

        # Find immediately preceding task
        tasks = await self._task_repository.get_by_job_id(task.job_id)
        preceding_tasks = [t for t in tasks if t.position_in_job < task.position_in_job]

        if not preceding_tasks:
            return True

        # Check if immediate predecessor is completed
        immediate_predecessor = max(preceding_tasks, key=lambda t: t.position_in_job)
        return immediate_predecessor.id in completed_task_ids

    async def _validate_task_prerequisites(self, task: Task) -> None:
        """Validate that task prerequisites are met."""
        if not task.job_id:
            return

        # Get job workflow state
        state = await self.get_job_workflow_state(task.job_id)

        # Check if task can start
        if not await self._can_task_start(task, state.completed_task_ids):
            # Find which predecessor is blocking
            tasks = await self._task_repository.get_by_job_id(task.job_id)
            preceding_tasks = [
                t
                for t in tasks
                if t.position_in_job < task.position_in_job
                and t.status != TaskStatus.COMPLETED
            ]

            if preceding_tasks:
                blocking_task = max(preceding_tasks, key=lambda t: t.position_in_job)
                raise PrecedenceConstraintError(task.id, blocking_task.id)

    async def _check_job_completion(self, job_id: UUID) -> None:
        """Check if job is complete and update accordingly."""
        job = await self._job_repository.get_by_id(job_id)
        if not job or job.is_completed:
            return

        tasks = await self._task_repository.get_by_job_id(job_id)

        # Check if all tasks are completed
        all_completed = all(task.status == TaskStatus.COMPLETED for task in tasks)

        if all_completed and tasks:
            # Find latest completion time
            latest_completion = max(
                task.actual_end for task in tasks if task.actual_end is not None
            )

            job.mark_completed(latest_completion or datetime.now())
            await self._job_repository.update(job)

    async def _try_auto_start_next_task(self, job_id: UUID) -> TaskTransition | None:
        """Try to automatically start the next task in sequence."""
        state = await self.get_job_workflow_state(job_id)

        if state.next_available_tasks:
            next_task_id = state.next_available_tasks[0]  # Start first available task
            try:
                return await self.start_task(next_task_id)
            except (TaskStatusError, PrecedenceConstraintError):
                return None

        return None

    def get_transition_history(
        self, task_id: UUID | None = None, job_id: UUID | None = None
    ) -> list[TaskTransition]:
        """
        Get task transition history.

        Args:
            task_id: Filter by task ID (optional)
            job_id: Filter by job ID (optional)

        Returns:
            List of transitions
        """
        transitions = self._transition_history.copy()

        if task_id:
            transitions = [t for t in transitions if t.task_id == task_id]

        # Filter by job_id would require loading tasks (simplified for now)

        return sorted(transitions, key=lambda t: t.timestamp)

    def configure_workflow(
        self,
        auto_start_next_task: bool = True,
        require_explicit_completion: bool = False,
        allow_parallel_tasks: bool = False,
    ) -> None:
        """
        Configure workflow behavior.

        Args:
            auto_start_next_task: Automatically start next task when predecessor completes
            require_explicit_completion: Require explicit completion confirmation
            allow_parallel_tasks: Allow parallel execution of independent tasks
        """
        self._auto_start_next_task = auto_start_next_task
        self._require_explicit_completion = require_explicit_completion
        self._allow_parallel_tasks = allow_parallel_tasks
