"""
Comprehensive Unit Tests for SchedulingService

Tests all scheduling service operations including optimization, constraint validation,
resource allocation, and workflow management. Uses mocking to isolate service logic.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.schedule import Schedule, ScheduleStatus
from app.domain.scheduling.services.optimization_service import (
    OptimizationParameters,
    OptimizationResult,
)
from app.domain.scheduling.services.resource_allocation_service import (
    ResourceAllocation,
)
from app.domain.scheduling.services.scheduling_service import (
    SchedulingRequest,
    SchedulingResult,
    SchedulingService,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import JobStatus
from app.shared.exceptions import (
    NoFeasibleSolutionError,
    OptimizationError,
    ScheduleError,
    ScheduleModificationError,
    ScheduleNotFoundError,
    SchedulePublishError,
    ValidationError,
)
from app.tests.database.factories import JobFactory, TaskFactory


@pytest.fixture
def mock_repositories():
    """Create mock repositories for testing."""
    return {
        "job_repository": AsyncMock(),
        "task_repository": AsyncMock(),
        "operator_repository": AsyncMock(),
        "machine_repository": AsyncMock(),
        "schedule_repository": AsyncMock(),
    }


@pytest.fixture
def mock_services():
    """Create mock domain services for testing."""
    return {
        "constraint_validation_service": AsyncMock(),
        "resource_allocation_service": AsyncMock(),
        "optimization_service": AsyncMock(),
        "workflow_service": AsyncMock(),
    }


@pytest.fixture
def scheduling_service(mock_repositories, mock_services):
    """Create SchedulingService with mocked dependencies."""
    return SchedulingService(
        job_repository=mock_repositories["job_repository"],
        task_repository=mock_repositories["task_repository"],
        operator_repository=mock_repositories["operator_repository"],
        machine_repository=mock_repositories["machine_repository"],
        schedule_repository=mock_repositories["schedule_repository"],
        constraint_validation_service=mock_services["constraint_validation_service"],
        resource_allocation_service=mock_services["resource_allocation_service"],
        optimization_service=mock_services["optimization_service"],
        workflow_service=mock_services["workflow_service"],
    )


@pytest.fixture
def sample_scheduling_request():
    """Create sample scheduling request for testing."""
    return SchedulingRequest(
        job_ids=[uuid4(), uuid4()],
        start_time=datetime.utcnow() + timedelta(hours=1),
        end_time=datetime.utcnow() + timedelta(days=7),
        optimization_params=OptimizationParameters(),
        constraints={"max_operators_per_task": 3},
    )


class TestSchedulingServiceInitialization:
    """Test SchedulingService initialization and dependency injection."""

    def test_service_initialization(self, scheduling_service):
        """Test service is properly initialized with dependencies."""
        assert scheduling_service is not None
        assert scheduling_service._job_repository is not None
        assert scheduling_service._task_repository is not None
        assert scheduling_service._schedule_repository is not None
        assert scheduling_service._optimization_service is not None

    def test_service_has_all_required_methods(self, scheduling_service):
        """Test service has all required public methods."""
        required_methods = [
            "create_optimized_schedule",
            "update_schedule",
            "publish_schedule",
            "execute_schedule",
            "get_schedule_status",
            "reschedule_job",
            "get_resource_conflicts",
        ]

        for method_name in required_methods:
            assert hasattr(scheduling_service, method_name)
            assert callable(getattr(scheduling_service, method_name))


class TestSchedulingRequest:
    """Test SchedulingRequest data structure."""

    def test_create_scheduling_request_with_all_parameters(self):
        """Test creating scheduling request with all parameters."""
        job_ids = [uuid4(), uuid4()]
        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = start_time + timedelta(days=14)
        optimization_params = OptimizationParameters()
        constraints = {"priority_weight": 0.8}

        request = SchedulingRequest(
            job_ids=job_ids,
            start_time=start_time,
            end_time=end_time,
            optimization_params=optimization_params,
            constraints=constraints,
        )

        assert request.job_ids == job_ids
        assert request.start_time == start_time
        assert request.end_time == end_time
        assert request.optimization_params == optimization_params
        assert request.constraints == constraints

    def test_create_scheduling_request_with_defaults(self):
        """Test creating scheduling request with default values."""
        job_ids = [uuid4()]
        start_time = datetime.utcnow() + timedelta(hours=1)

        request = SchedulingRequest(
            job_ids=job_ids,
            start_time=start_time,
        )

        assert request.job_ids == job_ids
        assert request.start_time == start_time
        # End time should default to 30 days from start
        expected_end = start_time + timedelta(days=30)
        assert abs((request.end_time - expected_end).total_seconds()) < 60
        assert request.optimization_params is not None
        assert request.constraints == {}


class TestCreateOptimizedSchedule:
    """Test create_optimized_schedule functionality."""

    @pytest.mark.asyncio
    async def test_create_optimized_schedule_success(
        self,
        scheduling_service,
        sample_scheduling_request,
        mock_repositories,
        mock_services,
    ):
        """Test successful schedule creation with optimization."""
        # Setup mocks
        jobs = [JobFactory.create() for _ in sample_scheduling_request.job_ids]

        # Mock job repository to return jobs
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        # Mock optimization service
        optimized_schedule = Schedule(
            name="Optimized Schedule",
            planning_horizon=Duration.from_timedelta(
                sample_scheduling_request.end_time
                - sample_scheduling_request.start_time
            ),
        )
        optimization_result = OptimizationResult(
            schedule=optimized_schedule,
            status="OPTIMAL",
            objective_value=100.0,
        )
        mock_services[
            "optimization_service"
        ].optimize_schedule.return_value = optimization_result

        # Mock constraint validation
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        # Mock schedule repository
        mock_repositories["schedule_repository"].save.return_value = optimized_schedule

        # Execute
        result = await scheduling_service.create_optimized_schedule(
            sample_scheduling_request,
            schedule_name="Test Schedule",
            created_by=uuid4(),
        )

        # Verify
        assert isinstance(result, SchedulingResult)
        assert result.schedule == optimized_schedule
        assert result.optimization_result == optimization_result
        assert result.violations == []
        assert isinstance(result.metrics, dict)
        assert isinstance(result.recommendations, list)

        # Verify service calls
        mock_services["optimization_service"].optimize_schedule.assert_called_once()
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.assert_called_once()
        mock_repositories["schedule_repository"].save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_schedule_with_validation_error(
        self, scheduling_service, sample_scheduling_request, mock_repositories
    ):
        """Test schedule creation fails with validation error."""
        # Mock job repository to return None (job not found)
        mock_repositories["job_repository"].get_by_id.return_value = None

        # Execute and verify exception
        with pytest.raises(ValidationError, match="Job not found"):
            await scheduling_service.create_optimized_schedule(
                sample_scheduling_request
            )

    @pytest.mark.asyncio
    async def test_create_schedule_with_inactive_job(
        self, scheduling_service, sample_scheduling_request, mock_repositories
    ):
        """Test schedule creation fails with inactive job."""
        # Create inactive job
        inactive_job = JobFactory.create(status=JobStatus.CANCELLED)
        mock_repositories["job_repository"].get_by_id.return_value = inactive_job

        # Execute and verify exception
        with pytest.raises(ValidationError, match="not active"):
            await scheduling_service.create_optimized_schedule(
                sample_scheduling_request
            )

    @pytest.mark.asyncio
    async def test_create_schedule_with_optimization_failure(
        self,
        scheduling_service,
        sample_scheduling_request,
        mock_repositories,
        mock_services,
    ):
        """Test schedule creation with optimization failure falls back to manual."""
        # Setup active jobs
        jobs = [
            JobFactory.create(status=JobStatus.RELEASED)
            for _ in sample_scheduling_request.job_ids
        ]
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        # Mock optimization failure
        failed_result = OptimizationResult(status="FAILED")
        mock_services[
            "optimization_service"
        ].optimize_schedule.return_value = failed_result

        # Mock manual allocation
        mock_services[
            "resource_allocation_service"
        ].allocate_resources_for_job.return_value = []

        # Mock other services
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        fallback_schedule = Schedule(
            name="Fallback Schedule", planning_horizon=Duration(days=7)
        )
        mock_repositories["schedule_repository"].save.return_value = fallback_schedule

        # Execute
        result = await scheduling_service.create_optimized_schedule(
            sample_scheduling_request
        )

        # Verify fallback was used
        assert result.schedule == fallback_schedule
        assert result.optimization_result == failed_result

    @pytest.mark.asyncio
    async def test_create_schedule_with_no_feasible_solution(
        self,
        scheduling_service,
        sample_scheduling_request,
        mock_repositories,
        mock_services,
    ):
        """Test handling of no feasible solution."""
        # Setup jobs
        jobs = [
            JobFactory.create(status=JobStatus.RELEASED)
            for _ in sample_scheduling_request.job_ids
        ]
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        # Mock optimization to raise no feasible solution
        mock_services[
            "optimization_service"
        ].optimize_schedule.side_effect = NoFeasibleSolutionError("No solution found")

        # Execute
        result = await scheduling_service.create_optimized_schedule(
            sample_scheduling_request
        )

        # Verify infeasible result
        assert "Infeasible" in result.schedule.name
        assert "No feasible solution found" in result.violations
        assert "Consider relaxing constraints" in result.recommendations

    @pytest.mark.asyncio
    async def test_create_schedule_with_constraints_violations(
        self,
        scheduling_service,
        sample_scheduling_request,
        mock_repositories,
        mock_services,
    ):
        """Test schedule creation with constraint violations."""
        # Setup jobs
        jobs = [
            JobFactory.create(status=JobStatus.RELEASED)
            for _ in sample_scheduling_request.job_ids
        ]
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        # Mock optimization success
        schedule = Schedule(name="Test Schedule", planning_horizon=Duration(days=7))
        optimization_result = OptimizationResult(schedule=schedule, status="OPTIMAL")
        mock_services[
            "optimization_service"
        ].optimize_schedule.return_value = optimization_result

        # Mock constraint violations
        violations = [
            "Machine M1 overbooked",
            "Operator O1 skill mismatch",
        ]
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = violations

        mock_repositories["schedule_repository"].save.return_value = schedule

        # Execute
        result = await scheduling_service.create_optimized_schedule(
            sample_scheduling_request
        )

        # Verify violations are included
        assert result.violations == violations
        assert len(result.violations) == 2


class TestUpdateSchedule:
    """Test update_schedule functionality."""

    @pytest.mark.asyncio
    async def test_update_schedule_success(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test successful schedule update."""
        schedule_id = uuid4()
        schedule = Schedule(name="Original Schedule", planning_horizon=Duration(days=7))
        changes = {
            "name": "Updated Schedule",
            "add_jobs": [str(uuid4())],
        }

        # Mock repository
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule
        mock_repositories["schedule_repository"].update.return_value = schedule

        # Mock services
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        # Execute
        result = await scheduling_service.update_schedule(
            schedule_id, changes, updated_by=uuid4()
        )

        # Verify
        assert isinstance(result, SchedulingResult)
        assert result.schedule == schedule
        mock_repositories["schedule_repository"].update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test updating non-existent schedule fails."""
        schedule_id = uuid4()
        mock_repositories["schedule_repository"].get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await scheduling_service.update_schedule(schedule_id, {})

    @pytest.mark.asyncio
    async def test_update_published_schedule_fails(
        self, scheduling_service, mock_repositories
    ):
        """Test updating published schedule fails."""
        schedule_id = uuid4()
        published_schedule = Schedule(
            name="Published", planning_horizon=Duration(days=7)
        )
        published_schedule._status = ScheduleStatus.PUBLISHED  # Force published status

        mock_repositories[
            "schedule_repository"
        ].get_by_id.return_value = published_schedule

        with pytest.raises(ScheduleModificationError):
            await scheduling_service.update_schedule(schedule_id, {"name": "New Name"})


class TestPublishSchedule:
    """Test publish_schedule functionality."""

    @pytest.mark.asyncio
    async def test_publish_schedule_success(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test successful schedule publishing."""
        schedule_id = uuid4()
        schedule = Schedule(name="Test Schedule", planning_horizon=Duration(days=7))

        # Mock repository
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule
        mock_repositories["schedule_repository"].update.return_value = schedule

        # Mock validation (no violations)
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        # Execute
        result = await scheduling_service.publish_schedule(
            schedule_id, published_by=uuid4()
        )

        # Verify
        assert result == schedule
        mock_repositories["schedule_repository"].update.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_nonexistent_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test publishing non-existent schedule fails."""
        schedule_id = uuid4()
        mock_repositories["schedule_repository"].get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await scheduling_service.publish_schedule(schedule_id)

    @pytest.mark.asyncio
    async def test_publish_schedule_with_violations(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test publishing schedule with constraint violations fails."""
        schedule_id = uuid4()
        schedule = Schedule(name="Invalid Schedule", planning_horizon=Duration(days=7))

        # Mock repository
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule

        # Mock constraint violations
        violations = ["Resource conflict detected"]
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = violations

        # Execute and verify exception
        with pytest.raises(SchedulePublishError, match="violations"):
            await scheduling_service.publish_schedule(schedule_id)


class TestExecuteSchedule:
    """Test execute_schedule functionality."""

    @pytest.mark.asyncio
    async def test_execute_schedule_success(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test successful schedule execution."""
        schedule_id = uuid4()
        job_ids = [uuid4(), uuid4()]

        schedule = Schedule(name="Execution Test", planning_horizon=Duration(days=7))
        schedule._status = ScheduleStatus.PUBLISHED  # Set as published
        # Add jobs to schedule
        for job_id in job_ids:
            schedule.add_job(job_id)

        # Mock repository
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule
        mock_repositories["schedule_repository"].update.return_value = schedule

        # Mock workflow service
        mock_services["workflow_service"].get_job_workflow_state.return_value = {
            "state": "ready"
        }
        mock_services["workflow_service"].advance_job_workflow.return_value = [
            "transition1"
        ]

        # Execute
        result = await scheduling_service.execute_schedule(
            schedule_id, executed_by=uuid4()
        )

        # Verify
        assert "schedule_id" in result
        assert "execution_started_at" in result
        assert result["jobs_processed"] == len(job_ids)
        assert "job_results" in result

        # Verify workflow service was called for each job
        assert mock_services[
            "workflow_service"
        ].get_job_workflow_state.call_count == len(job_ids)
        assert mock_services["workflow_service"].advance_job_workflow.call_count == len(
            job_ids
        )

    @pytest.mark.asyncio
    async def test_execute_nonexistent_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test executing non-existent schedule fails."""
        schedule_id = uuid4()
        mock_repositories["schedule_repository"].get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await scheduling_service.execute_schedule(schedule_id)

    @pytest.mark.asyncio
    async def test_execute_unpublished_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test executing unpublished schedule fails."""
        schedule_id = uuid4()
        schedule = Schedule(name="Draft Schedule", planning_horizon=Duration(days=7))
        # Schedule status defaults to DRAFT

        mock_repositories["schedule_repository"].get_by_id.return_value = schedule

        with pytest.raises(ScheduleError, match="Cannot execute"):
            await scheduling_service.execute_schedule(schedule_id)


class TestGetScheduleStatus:
    """Test get_schedule_status functionality."""

    @pytest.mark.asyncio
    async def test_get_schedule_status_success(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test getting schedule status information."""
        schedule_id = uuid4()
        job_ids = [uuid4(), uuid4()]

        schedule = Schedule(name="Status Test", planning_horizon=Duration(days=7))
        schedule._status = ScheduleStatus.ACTIVE
        for job_id in job_ids:
            schedule.add_job(job_id)

        # Mock repository
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule

        # Mock workflow service
        mock_services["workflow_service"].get_job_progress.return_value = {
            "total_tasks": 5,
            "completed_tasks": 2,
        }

        # Execute
        result = await scheduling_service.get_schedule_status(schedule_id)

        # Verify
        assert result["schedule_id"] == schedule_id
        assert result["status"] == ScheduleStatus.ACTIVE.value
        assert result["total_jobs"] == len(job_ids)
        assert "overall_progress" in result
        assert "total_tasks" in result
        assert "completed_tasks" in result
        assert "job_progress" in result

        # Verify progress calculation
        expected_progress = (4 / 10) * 100  # 4 completed out of 10 total
        assert result["overall_progress"] == expected_progress

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test getting status of non-existent schedule fails."""
        schedule_id = uuid4()
        mock_repositories["schedule_repository"].get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await scheduling_service.get_schedule_status(schedule_id)


class TestRescheduleJob:
    """Test reschedule_job functionality."""

    @pytest.mark.asyncio
    async def test_reschedule_job_success(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test successful job rescheduling."""
        job_id = uuid4()
        job = JobFactory.create()
        new_start_time = datetime.utcnow() + timedelta(hours=4)

        # Mock repositories
        mock_repositories["job_repository"].get_by_id.return_value = job

        # Mock resource allocation
        allocation = ResourceAllocation(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
        )
        mock_services[
            "resource_allocation_service"
        ].allocate_resources_for_job.return_value = [allocation]

        # Execute
        result = await scheduling_service.reschedule_job(job_id, new_start_time)

        # Verify
        assert isinstance(result, ResourceAllocation)
        assert result == allocation

        # Verify service calls
        mock_repositories["job_repository"].get_by_id.assert_called_once_with(job_id)
        mock_services[
            "resource_allocation_service"
        ].allocate_resources_for_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_reschedule_job_with_schedule_update(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test rescheduling job within a schedule."""
        job_id = uuid4()
        schedule_id = uuid4()
        job = JobFactory.create()
        new_start_time = datetime.utcnow() + timedelta(hours=2)

        schedule = Schedule(name="Reschedule Test", planning_horizon=Duration(days=7))
        task = TaskFactory.create()

        # Mock repositories
        mock_repositories["job_repository"].get_by_id.return_value = job
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule
        mock_repositories["schedule_repository"].update.return_value = schedule
        mock_repositories["task_repository"].get_by_id.return_value = task

        # Mock allocation
        allocation = ResourceAllocation(
            task_id=task.id,
            machine_id=uuid4(),
            operator_ids=[uuid4()],
        )
        mock_services[
            "resource_allocation_service"
        ].allocate_resources_for_job.return_value = [allocation]

        # Execute
        result = await scheduling_service.reschedule_job(
            job_id, new_start_time, schedule_id
        )

        # Verify
        assert result == allocation
        mock_repositories["schedule_repository"].update.assert_called_once()

    @pytest.mark.asyncio
    async def test_reschedule_nonexistent_job(
        self, scheduling_service, mock_repositories
    ):
        """Test rescheduling non-existent job fails."""
        job_id = uuid4()
        mock_repositories["job_repository"].get_by_id.return_value = None

        from app.shared.exceptions import JobNotFoundError

        with pytest.raises(JobNotFoundError):
            await scheduling_service.reschedule_job(job_id, datetime.utcnow())


class TestGetResourceConflicts:
    """Test get_resource_conflicts functionality."""

    @pytest.mark.asyncio
    async def test_get_resource_conflicts_success(
        self, scheduling_service, mock_repositories
    ):
        """Test getting resource conflicts."""
        schedule_id = uuid4()
        schedule = Schedule(name="Conflict Test", planning_horizon=Duration(days=7))

        # Create overlapping assignments (would be more complex in real implementation)
        machine_id = uuid4()
        now = datetime.utcnow()

        # Mock schedule with assignments
        mock_repositories["schedule_repository"].get_by_id.return_value = schedule

        # Mock the get_assignments_in_time_window method
        with patch.object(
            schedule, "get_assignments_in_time_window"
        ) as mock_assignments:
            from app.domain.scheduling.entities.schedule import ScheduleAssignment

            # Create overlapping assignments
            assignment1 = ScheduleAssignment(
                task_id=uuid4(),
                machine_id=machine_id,
                operator_ids=[],
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=3),
                setup_duration=Duration(minutes=0),
                processing_duration=Duration(minutes=120),
            )
            assignment2 = ScheduleAssignment(
                task_id=uuid4(),
                machine_id=machine_id,
                operator_ids=[],
                start_time=now + timedelta(hours=2),  # Overlaps with assignment1
                end_time=now + timedelta(hours=4),
                setup_duration=Duration(minutes=0),
                processing_duration=Duration(minutes=120),
            )

            mock_assignments.return_value = [assignment1, assignment2]

            # Execute
            conflicts = await scheduling_service.get_resource_conflicts(schedule_id)

            # Verify
            assert len(conflicts) == 1
            conflict = conflicts[0]
            assert conflict["type"] == "machine_conflict"
            assert conflict["resource_id"] == str(machine_id)

    @pytest.mark.asyncio
    async def test_get_conflicts_nonexistent_schedule(
        self, scheduling_service, mock_repositories
    ):
        """Test getting conflicts for non-existent schedule fails."""
        schedule_id = uuid4()
        mock_repositories["schedule_repository"].get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await scheduling_service.get_resource_conflicts(schedule_id)


class TestPrivateHelperMethods:
    """Test private helper methods of SchedulingService."""

    @pytest.mark.asyncio
    async def test_validate_scheduling_request_empty_jobs(self, scheduling_service):
        """Test validation fails with empty job list."""
        request = SchedulingRequest(
            job_ids=[],
            start_time=datetime.utcnow() + timedelta(hours=1),
        )

        with pytest.raises(ValidationError, match="No jobs provided"):
            await scheduling_service._validate_scheduling_request(request)

    @pytest.mark.asyncio
    async def test_validate_scheduling_request_invalid_times(self, scheduling_service):
        """Test validation fails with invalid time range."""
        request = SchedulingRequest(
            job_ids=[uuid4()],
            start_time=datetime.utcnow() + timedelta(hours=2),
            end_time=datetime.utcnow() + timedelta(hours=1),  # End before start
        )

        with pytest.raises(ValidationError, match="before end time"):
            await scheduling_service._validate_scheduling_request(request)

    @pytest.mark.asyncio
    async def test_calculate_schedule_metrics(self, scheduling_service):
        """Test schedule metrics calculation."""
        schedule = Schedule(name="Metrics Test", planning_horizon=Duration(days=7))
        schedule._makespan = Duration(hours=40)
        schedule._total_tardiness = Duration(hours=2)

        # Mock some assignments
        with patch.object(schedule, "assignments", []):
            metrics = await scheduling_service._calculate_schedule_metrics(schedule)

            assert "total_assignments" in metrics
            assert "planning_horizon_days" in metrics
            assert "makespan_hours" in metrics
            assert "total_tardiness_hours" in metrics
            assert metrics["makespan_hours"] == 40.0
            assert metrics["total_tardiness_hours"] == 2.0

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, scheduling_service):
        """Test recommendation generation."""
        schedule = Schedule(
            name="Recommendation Test", planning_horizon=Duration(days=7)
        )
        violations = ["Resource conflict", "Skill mismatch"]
        metrics = {
            "resource_utilization": 0.5,  # Low utilization
            "total_tardiness_hours": 4.0,  # Some tardiness
        }

        recommendations = await scheduling_service._generate_recommendations(
            schedule, violations, metrics
        )

        assert len(recommendations) >= 3
        assert any("violations" in rec for rec in recommendations)
        assert any("utilization" in rec for rec in recommendations)
        assert any("tardiness" in rec for rec in recommendations)


class TestSchedulingServiceErrorHandling:
    """Test error handling in SchedulingService."""

    @pytest.mark.asyncio
    async def test_optimization_service_exception_handling(
        self,
        scheduling_service,
        sample_scheduling_request,
        mock_repositories,
        mock_services,
    ):
        """Test handling of optimization service exceptions."""
        # Setup jobs
        jobs = [
            JobFactory.create(status=JobStatus.RELEASED)
            for _ in sample_scheduling_request.job_ids
        ]
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        # Mock optimization service to raise generic exception
        mock_services["optimization_service"].optimize_schedule.side_effect = Exception(
            "Optimization failed"
        )

        # Execute and verify exception is wrapped
        with pytest.raises(OptimizationError, match="Scheduling failed"):
            await scheduling_service.create_optimized_schedule(
                sample_scheduling_request
            )

    @pytest.mark.asyncio
    async def test_repository_exception_handling(
        self, scheduling_service, sample_scheduling_request, mock_repositories
    ):
        """Test handling of repository exceptions."""
        # Mock job repository to raise exception
        mock_repositories["job_repository"].get_by_id.side_effect = Exception(
            "Database error"
        )

        # Execute and verify exception propagates
        with pytest.raises(Exception, match="Database error"):
            await scheduling_service.create_optimized_schedule(
                sample_scheduling_request
            )


@pytest.mark.integration
class TestSchedulingServiceIntegration:
    """Integration tests for SchedulingService with real-like scenarios."""

    @pytest.mark.asyncio
    async def test_complete_scheduling_workflow(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test complete scheduling workflow from request to execution."""
        # Setup test data
        job_ids = [uuid4(), uuid4()]
        jobs = [JobFactory.create(status=JobStatus.RELEASED) for job_id in job_ids]

        # Create scheduling request
        request = SchedulingRequest(
            job_ids=job_ids,
            start_time=datetime.utcnow() + timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(days=3),
        )

        # Mock all dependencies for schedule creation
        mock_repositories["job_repository"].get_by_id.side_effect = lambda job_id: (
            next((job for job in jobs if job.id == job_id), None)
        )

        optimized_schedule = Schedule(
            name="Integration Test", planning_horizon=Duration(days=3)
        )
        optimization_result = OptimizationResult(
            schedule=optimized_schedule,
            status="OPTIMAL",
            objective_value=95.0,
        )
        mock_services[
            "optimization_service"
        ].optimize_schedule.return_value = optimization_result
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []
        mock_repositories["schedule_repository"].save.return_value = optimized_schedule
        mock_repositories[
            "schedule_repository"
        ].get_by_id.return_value = optimized_schedule
        mock_repositories[
            "schedule_repository"
        ].update.return_value = optimized_schedule

        # Step 1: Create optimized schedule
        create_result = await scheduling_service.create_optimized_schedule(request)

        assert isinstance(create_result, SchedulingResult)
        assert create_result.schedule == optimized_schedule
        assert create_result.optimization_result.status == "OPTIMAL"

        # Step 2: Publish schedule
        schedule_id = create_result.schedule.id
        published_schedule = await scheduling_service.publish_schedule(schedule_id)

        assert published_schedule == optimized_schedule

        # Step 3: Execute schedule
        # Add jobs to schedule for execution
        for job_id in job_ids:
            optimized_schedule.add_job(job_id)
        optimized_schedule._status = ScheduleStatus.PUBLISHED

        mock_services["workflow_service"].get_job_workflow_state.return_value = {
            "state": "ready"
        }
        mock_services["workflow_service"].advance_job_workflow.return_value = [
            "started"
        ]

        execution_result = await scheduling_service.execute_schedule(schedule_id)

        assert "schedule_id" in execution_result
        assert execution_result["jobs_processed"] == len(job_ids)

        # Step 4: Check status
        mock_services["workflow_service"].get_job_progress.return_value = {
            "total_tasks": 3,
            "completed_tasks": 1,
        }
        optimized_schedule._status = ScheduleStatus.ACTIVE

        status_result = await scheduling_service.get_schedule_status(schedule_id)

        assert status_result["status"] == ScheduleStatus.ACTIVE.value
        assert status_result["total_jobs"] == len(job_ids)

    @pytest.mark.asyncio
    async def test_schedule_modification_workflow(
        self, scheduling_service, mock_repositories, mock_services
    ):
        """Test schedule modification and update workflow."""
        schedule_id = uuid4()
        original_schedule = Schedule(name="Original", planning_horizon=Duration(days=5))

        # Mock repositories
        mock_repositories[
            "schedule_repository"
        ].get_by_id.return_value = original_schedule
        mock_repositories["schedule_repository"].update.return_value = original_schedule
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        # Step 1: Update schedule
        changes = {
            "name": "Modified Schedule",
            "add_jobs": [str(uuid4())],
        }

        update_result = await scheduling_service.update_schedule(schedule_id, changes)

        assert isinstance(update_result, SchedulingResult)
        assert update_result.schedule == original_schedule

        # Step 2: Try to publish with violations (should fail)
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = ["Resource conflict detected"]

        with pytest.raises(SchedulePublishError):
            await scheduling_service.publish_schedule(schedule_id)

        # Step 3: Fix violations and publish
        mock_services[
            "constraint_validation_service"
        ].validate_schedule.return_value = []

        published = await scheduling_service.publish_schedule(schedule_id)
        assert published == original_schedule


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
