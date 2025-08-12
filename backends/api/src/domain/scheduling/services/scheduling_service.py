"""
Scheduling Service

Main orchestrator for production scheduling operations. Coordinates all domain services
to provide high-level scheduling capabilities while maintaining clean separation of concerns.
"""

from datetime import datetime, timedelta
from uuid import UUID

from ...shared.exceptions import (
    NoFeasibleSolutionError,
    OptimizationError,
    ScheduleError,
    ScheduleModificationError,
    ScheduleNotFoundError,
    SchedulePublishError,
    ValidationError,
)
from ..entities.schedule import Schedule, ScheduleAssignment, ScheduleStatus
from ..repositories.job_repository import JobRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.schedule_repository import ScheduleRepository
from ..repositories.task_repository import TaskRepository
from ..value_objects.duration import Duration
from .constraint_validation_service import ConstraintValidationService
from .optimization_service import (
    OptimizationParameters,
    OptimizationResult,
    OptimizationService,
)
from .resource_allocation_service import ResourceAllocation, ResourceAllocationService
from .workflow_service import WorkflowService


class SchedulingRequest:
    """Request for scheduling operation."""

    def __init__(
        self,
        job_ids: list[UUID],
        start_time: datetime,
        end_time: datetime | None = None,
        optimization_params: OptimizationParameters | None = None,
        constraints: dict[str, any] | None = None,
    ) -> None:
        self.job_ids = job_ids
        self.start_time = start_time
        self.end_time = end_time or (start_time + timedelta(days=30))
        self.optimization_params = optimization_params or OptimizationParameters()
        self.constraints = constraints or {}


class SchedulingResult:
    """Result of scheduling operation."""

    def __init__(
        self,
        schedule: Schedule,
        optimization_result: OptimizationResult,
        violations: list[str],
        metrics: dict[str, float],
        recommendations: list[str],
    ) -> None:
        self.schedule = schedule
        self.optimization_result = optimization_result
        self.violations = violations
        self.metrics = metrics
        self.recommendations = recommendations


class SchedulingService:
    """
    Main scheduling service orchestrator.

    This service coordinates all scheduling domain services to provide
    comprehensive production scheduling capabilities. It acts as the
    application service layer, orchestrating complex workflows.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        task_repository: TaskRepository,
        operator_repository: OperatorRepository,
        machine_repository: MachineRepository,
        schedule_repository: ScheduleRepository,
        constraint_validation_service: ConstraintValidationService,
        resource_allocation_service: ResourceAllocationService,
        optimization_service: OptimizationService,
        workflow_service: WorkflowService,
    ) -> None:
        """
        Initialize the scheduling service.

        Args:
            job_repository: Job data access
            task_repository: Task data access
            operator_repository: Operator data access
            machine_repository: Machine data access
            schedule_repository: Schedule data access
            constraint_validation_service: Constraint validation logic
            resource_allocation_service: Resource allocation logic
            optimization_service: Mathematical optimization
            workflow_service: Workflow management
        """
        self._job_repository = job_repository
        self._task_repository = task_repository
        self._operator_repository = operator_repository
        self._machine_repository = machine_repository
        self._schedule_repository = schedule_repository
        self._constraint_validation_service = constraint_validation_service
        self._resource_allocation_service = resource_allocation_service
        self._optimization_service = optimization_service
        self._workflow_service = workflow_service

    async def create_optimized_schedule(
        self,
        request: SchedulingRequest,
        schedule_name: str = "",
        created_by: UUID | None = None,
    ) -> SchedulingResult:
        """
        Create an optimized schedule for the given jobs.

        Args:
            request: Scheduling request with jobs and parameters
            schedule_name: Name for the created schedule
            created_by: User ID creating the schedule

        Returns:
            Scheduling result with optimized schedule

        Raises:
            OptimizationError: If optimization fails
            ValidationError: If input validation fails
        """
        # Validate request
        await self._validate_scheduling_request(request)

        # Create schedule
        schedule = Schedule(
            name=schedule_name or f"Schedule {datetime.now().isoformat()}",
            planning_horizon=Duration.from_timedelta(
                request.end_time - request.start_time
            ),
            created_by=created_by,
        )

        # Add jobs to schedule
        for job_id in request.job_ids:
            schedule.add_job(job_id)

        try:
            # Run optimization
            optimization_result = await self._optimization_service.optimize_schedule(
                job_ids=request.job_ids,
                start_time=request.start_time,
                parameters=request.optimization_params,
            )

            if optimization_result.schedule:
                # Use optimized schedule
                schedule = optimization_result.schedule
            else:
                # Fallback to manual allocation if optimization failed
                print("Optimization failed, falling back to manual allocation")
                await self._create_manual_schedule(schedule, request)

            # Validate constraints
            violations = await self._constraint_validation_service.validate_schedule(
                schedule
            )

            # Calculate metrics
            metrics = await self._calculate_schedule_metrics(schedule)

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                schedule, violations, metrics
            )

            # Save schedule
            saved_schedule = await self._schedule_repository.save(schedule)

            return SchedulingResult(
                schedule=saved_schedule,
                optimization_result=optimization_result,
                violations=violations,
                metrics=metrics,
                recommendations=recommendations,
            )

        except NoFeasibleSolutionError:
            # Try alternative approaches
            return await self._handle_infeasible_schedule(
                request, schedule_name, created_by
            )

        except Exception as e:
            raise OptimizationError(f"Scheduling failed: {str(e)}")

    async def update_schedule(
        self, schedule_id: UUID, changes: dict[str, any], updated_by: UUID | None = None
    ) -> SchedulingResult:
        """
        Update an existing schedule.

        Args:
            schedule_id: Schedule to update
            changes: Changes to apply
            updated_by: User making changes

        Returns:
            Updated scheduling result

        Raises:
            ScheduleNotFoundError: If schedule doesn't exist
            ScheduleModificationError: If schedule cannot be modified
        """
        schedule = await self._schedule_repository.get_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(schedule_id)

        if schedule.is_published:
            raise ScheduleModificationError(schedule_id, schedule.status.value)

        # Apply changes
        await self._apply_schedule_changes(schedule, changes)

        # Re-validate
        violations = await self._constraint_validation_service.validate_schedule(
            schedule
        )
        metrics = await self._calculate_schedule_metrics(schedule)
        recommendations = await self._generate_recommendations(
            schedule, violations, metrics
        )

        # Save updated schedule
        updated_schedule = await self._schedule_repository.update(schedule)

        return SchedulingResult(
            schedule=updated_schedule,
            optimization_result=OptimizationResult(),  # Empty result for updates
            violations=violations,
            metrics=metrics,
            recommendations=recommendations,
        )

    async def publish_schedule(
        self, schedule_id: UUID, published_by: UUID | None = None
    ) -> Schedule:
        """
        Publish a schedule for execution.

        Args:
            schedule_id: Schedule to publish
            published_by: User publishing the schedule

        Returns:
            Published schedule

        Raises:
            ScheduleNotFoundError: If schedule doesn't exist
            SchedulePublishError: If schedule cannot be published
        """
        schedule = await self._schedule_repository.get_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(schedule_id)

        # Validate before publishing
        violations = await self._constraint_validation_service.validate_schedule(
            schedule
        )
        if violations:
            raise SchedulePublishError(
                f"Cannot publish schedule with violations: {violations[:5]}"  # Show first 5
            )

        # Publish
        schedule.publish()
        published_schedule = await self._schedule_repository.update(schedule)

        return published_schedule

    async def execute_schedule(
        self, schedule_id: UUID, executed_by: UUID | None = None
    ) -> dict[str, any]:
        """
        Execute a published schedule.

        Args:
            schedule_id: Schedule to execute
            executed_by: User executing the schedule

        Returns:
            Execution status and metrics

        Raises:
            ScheduleNotFoundError: If schedule doesn't exist
            ScheduleError: If schedule cannot be executed
        """
        schedule = await self._schedule_repository.get_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(schedule_id)

        if schedule.status != ScheduleStatus.PUBLISHED:
            raise ScheduleError(
                f"Cannot execute schedule in status {schedule.status.value}"
            )

        # Activate schedule
        schedule.activate()
        await self._schedule_repository.update(schedule)

        # Initialize workflow for all jobs
        execution_results = {}
        for job_id in schedule.job_ids:
            try:
                # Get current workflow state
                state = await self._workflow_service.get_job_workflow_state(job_id)

                # Start available tasks
                transitions = await self._workflow_service.advance_job_workflow(job_id)

                execution_results[str(job_id)] = {
                    "workflow_state": state,
                    "transitions_started": len(transitions),
                    "status": "started",
                }

            except Exception as e:
                execution_results[str(job_id)] = {"status": "error", "error": str(e)}

        return {
            "schedule_id": schedule_id,
            "execution_started_at": datetime.now().isoformat(),
            "jobs_processed": len(execution_results),
            "job_results": execution_results,
        }

    async def get_schedule_status(self, schedule_id: UUID) -> dict[str, any]:
        """
        Get current status of a schedule.

        Args:
            schedule_id: Schedule to check

        Returns:
            Schedule status information
        """
        schedule = await self._schedule_repository.get_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(schedule_id)

        # Get job progress
        job_progress = {}
        for job_id in schedule.job_ids:
            progress = await self._workflow_service.get_job_progress(job_id)
            job_progress[str(job_id)] = progress

        # Calculate overall progress
        total_tasks = sum(p["total_tasks"] for p in job_progress.values())
        completed_tasks = sum(p["completed_tasks"] for p in job_progress.values())
        overall_progress = (
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        )

        return {
            "schedule_id": schedule_id,
            "status": schedule.status.value,
            "overall_progress": overall_progress,
            "total_jobs": len(schedule.job_ids),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "job_progress": job_progress,
            "created_at": schedule.created_at.isoformat(),
            "updated_at": schedule.updated_at.isoformat(),
        }

    async def reschedule_job(
        self, job_id: UUID, new_start_time: datetime, schedule_id: UUID | None = None
    ) -> ResourceAllocation:
        """
        Reschedule a specific job within a schedule.

        Args:
            job_id: Job to reschedule
            new_start_time: New start time for job
            schedule_id: Schedule containing the job (optional)

        Returns:
            New resource allocation for the job
        """
        job = await self._job_repository.get_by_id(job_id)
        if not job:
            from ...shared.exceptions import JobNotFoundError

            raise JobNotFoundError(job_id)

        # Get new resource allocation
        allocations = (
            await self._resource_allocation_service.allocate_resources_for_job(
                job, new_start_time
            )
        )

        # Update schedule if provided
        if schedule_id:
            schedule = await self._schedule_repository.get_by_id(schedule_id)
            if schedule and not schedule.is_published:
                # Update assignments in schedule
                for allocation in allocations:
                    task = await self._task_repository.get_by_id(allocation.task_id)
                    if task:
                        end_time = new_start_time + task.total_duration.to_timedelta()

                        schedule.assign_task(
                            task_id=allocation.task_id,
                            machine_id=allocation.machine_id,
                            operator_ids=allocation.operator_ids,
                            start_time=new_start_time,
                            end_time=end_time,
                            setup_duration=task.setup_duration,
                            processing_duration=task.processing_duration,
                        )

                await self._schedule_repository.update(schedule)

        return (
            allocations[0]
            if allocations
            else ResourceAllocation(
                task_id=UUID("00000000-0000-0000-0000-000000000000"),
                machine_id=UUID("00000000-0000-0000-0000-000000000000"),
                operator_ids=[],
            )
        )

    async def get_resource_conflicts(
        self, schedule_id: UUID, time_window_hours: int = 24
    ) -> list[dict[str, any]]:
        """
        Get resource conflicts within a time window.

        Args:
            schedule_id: Schedule to analyze
            time_window_hours: Hours to look ahead

        Returns:
            List of resource conflicts
        """
        schedule = await self._schedule_repository.get_by_id(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(schedule_id)

        now = datetime.now()
        end_time = now + timedelta(hours=time_window_hours)

        # Get assignments in time window
        assignments = schedule.get_assignments_in_time_window(now, end_time)

        conflicts = []

        # Check machine conflicts
        machine_assignments: dict[UUID, list[ScheduleAssignment]] = {}
        for assignment in assignments:
            machine_id = assignment.machine_id
            if machine_id not in machine_assignments:
                machine_assignments[machine_id] = []
            machine_assignments[machine_id].append(assignment)

        for machine_id, machine_assigns in machine_assignments.items():
            if len(machine_assigns) > 1:
                sorted_assigns = sorted(machine_assigns, key=lambda a: a.start_time)
                for i in range(len(sorted_assigns) - 1):
                    current = sorted_assigns[i]
                    next_assign = sorted_assigns[i + 1]

                    if current.end_time > next_assign.start_time:
                        conflicts.append(
                            {
                                "type": "machine_conflict",
                                "resource_id": str(machine_id),
                                "task1_id": str(current.task_id),
                                "task2_id": str(next_assign.task_id),
                                "conflict_start": next_assign.start_time.isoformat(),
                                "conflict_end": min(
                                    current.end_time, next_assign.end_time
                                ).isoformat(),
                            }
                        )

        return conflicts

    async def _validate_scheduling_request(self, request: SchedulingRequest) -> None:
        """Validate scheduling request."""
        if not request.job_ids:
            raise ValidationError("No jobs provided for scheduling")

        if request.start_time >= request.end_time:
            raise ValidationError("Start time must be before end time")

        # Validate jobs exist
        for job_id in request.job_ids:
            job = await self._job_repository.get_by_id(job_id)
            if not job:
                raise ValidationError(f"Job not found: {job_id}")

            if not job.is_active:
                raise ValidationError(f"Job {job_id} is not active")

    async def _create_manual_schedule(
        self, schedule: Schedule, request: SchedulingRequest
    ) -> None:
        """Create schedule using manual allocation as fallback."""
        current_time = request.start_time

        for job_id in request.job_ids:
            job = await self._job_repository.get_by_id(job_id)
            if not job:
                continue

            try:
                allocations = (
                    await self._resource_allocation_service.allocate_resources_for_job(
                        job, current_time
                    )
                )

                for allocation in allocations:
                    task = await self._task_repository.get_by_id(allocation.task_id)
                    if task:
                        end_time = current_time + task.total_duration.to_timedelta()

                        schedule.assign_task(
                            task_id=allocation.task_id,
                            machine_id=allocation.machine_id,
                            operator_ids=allocation.operator_ids,
                            start_time=current_time,
                            end_time=end_time,
                            setup_duration=task.setup_duration,
                            processing_duration=task.processing_duration,
                        )

                        current_time = end_time

            except Exception as e:
                print(f"Failed to allocate resources for job {job_id}: {e}")

    async def _handle_infeasible_schedule(
        self, request: SchedulingRequest, schedule_name: str, created_by: UUID | None
    ) -> SchedulingResult:
        """Handle case where no feasible solution exists."""

        # Create basic schedule with violations
        schedule = Schedule(
            name=f"{schedule_name} (Infeasible)",
            planning_horizon=Duration.from_timedelta(
                request.end_time - request.start_time
            ),
            created_by=created_by,
        )

        violations = ["No feasible solution found with current constraints"]
        recommendations = [
            "Consider relaxing constraints",
            "Add more operators or machines",
            "Extend planning horizon",
            "Adjust job priorities or due dates",
        ]

        return SchedulingResult(
            schedule=schedule,
            optimization_result=OptimizationResult(status="INFEASIBLE"),
            violations=violations,
            metrics={},
            recommendations=recommendations,
        )

    async def _apply_schedule_changes(
        self, schedule: Schedule, changes: dict[str, any]
    ) -> None:
        """Apply changes to schedule."""

        if "name" in changes:
            schedule._name = changes["name"]

        if "add_jobs" in changes:
            for job_id in changes["add_jobs"]:
                schedule.add_job(UUID(job_id))

        if "remove_jobs" in changes:
            for job_id in changes["remove_jobs"]:
                schedule.remove_job(UUID(job_id))

        if "task_assignments" in changes:
            for assignment_data in changes["task_assignments"]:
                schedule.assign_task(**assignment_data)

    async def _calculate_schedule_metrics(self, schedule: Schedule) -> dict[str, float]:
        """Calculate schedule performance metrics."""
        metrics = {
            "total_assignments": len(schedule.assignments),
            "planning_horizon_days": schedule.planning_horizon.days,
            "resource_utilization": 0.0,
            "cost_estimate": 0.0,
        }

        if schedule.makespan:
            metrics["makespan_hours"] = schedule.makespan.hours

        if schedule.total_tardiness:
            metrics["total_tardiness_hours"] = schedule.total_tardiness.hours

        return metrics

    async def _generate_recommendations(
        self, schedule: Schedule, violations: list[str], metrics: dict[str, float]
    ) -> list[str]:
        """Generate recommendations for schedule improvement."""
        recommendations = []

        if violations:
            recommendations.append(f"Resolve {len(violations)} constraint violations")

        if metrics.get("resource_utilization", 0) < 0.6:
            recommendations.append(
                "Consider load balancing to improve resource utilization"
            )

        if metrics.get("total_tardiness_hours", 0) > 0:
            recommendations.append("Review job priorities to reduce tardiness")

        return recommendations
