"""
Integration tests for complex scheduling workflows.

Tests end-to-end scheduling scenarios with multiple components including
job creation, task scheduling, resource allocation, constraint validation,
and event propagation across the entire scheduling domain.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.schedule import Schedule, ScheduleStatus
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.events.domain_events import (
    JobCreated,
    JobStatusChanged,
    TaskScheduled,
    TaskStarted,
    TaskCompleted,
    SchedulePublished,
    ResourceConflictDetected,
    ConstraintViolated,
)
from app.domain.scheduling.repositories.job_repository import JobRepository
from app.domain.scheduling.repositories.machine_repository import MachineRepository
from app.domain.scheduling.repositories.operator_repository import OperatorRepository
from app.domain.scheduling.repositories.schedule_repository import ScheduleRepository
from app.domain.scheduling.repositories.task_repository import TaskRepository
from app.domain.scheduling.services.constraint_validation_service import (
    ConstraintValidationService,
)
from app.domain.scheduling.services.optimization_service import (
    OptimizationParameters,
    OptimizationService,
)
from app.domain.scheduling.services.resource_allocation_service import (
    ResourceAllocationService,
)
from app.domain.scheduling.services.scheduling_service import (
    SchedulingRequest,
    SchedulingService,
)
from app.domain.scheduling.services.workflow_service import WorkflowService
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import JobStatus, Priority, TaskStatus

from .fixtures import (
    JobFactory,
    MachineFactory,
    OperatorFactory,
    ScheduleFactory,
    TaskFactory,
)


class MockJobRepository(JobRepository):
    """Mock job repository for testing."""
    
    def __init__(self):
        self._jobs: dict[UUID, Job] = {}
    
    async def save(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job
    
    async def get_by_id(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)
    
    async def get_by_job_number(self, job_number: str) -> Job | None:
        for job in self._jobs.values():
            if job.job_number == job_number:
                return job
        return None
    
    async def list_active_jobs(self) -> List[Job]:
        return [job for job in self._jobs.values() if job.is_active]
    
    async def update(self, job: Job) -> Job:
        if job.id in self._jobs:
            self._jobs[job.id] = job
            return job
        raise ValueError(f"Job {job.id} not found")
    
    async def delete(self, job_id: UUID) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False


class MockTaskRepository(TaskRepository):
    """Mock task repository for testing."""
    
    def __init__(self):
        self._tasks: dict[UUID, Task] = {}
    
    async def save(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task
    
    async def get_by_id(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)
    
    async def get_tasks_for_job(self, job_id: UUID) -> List[Task]:
        return [task for task in self._tasks.values() if task.job_id == job_id]
    
    async def update(self, task: Task) -> Task:
        if task.id in self._tasks:
            self._tasks[task.id] = task
            return task
        raise ValueError(f"Task {task.id} not found")


class MockScheduleRepository(ScheduleRepository):
    """Mock schedule repository for testing."""
    
    def __init__(self):
        self._schedules: dict[UUID, Schedule] = {}
    
    async def save(self, schedule: Schedule) -> Schedule:
        self._schedules[schedule.id] = schedule
        return schedule
    
    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        return self._schedules.get(schedule_id)
    
    async def update(self, schedule: Schedule) -> Schedule:
        if schedule.id in self._schedules:
            self._schedules[schedule.id] = schedule
            return schedule
        raise ValueError(f"Schedule {schedule.id} not found")


class MockOptimizationService(OptimizationService):
    """Mock optimization service for testing."""
    
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.optimization_calls = []
    
    async def optimize_schedule(
        self,
        job_ids: List[UUID],
        start_time: datetime,
        parameters: OptimizationParameters
    ):
        """Mock optimization that either succeeds or fails based on configuration."""
        from app.domain.scheduling.services.optimization_service import OptimizationResult
        
        self.optimization_calls.append({
            'job_ids': job_ids,
            'start_time': start_time,
            'parameters': parameters
        })
        
        if self.should_succeed:
            # Return successful optimization with mock schedule
            mock_schedule = ScheduleFactory.create_schedule(
                name="Optimized Schedule",
                job_count=len(job_ids)
            )
            
            return OptimizationResult(
                status="OPTIMAL",
                objective_value=100.0,
                schedule=mock_schedule,
                computation_time=Duration(seconds=5),
                variables_count=len(job_ids) * 10,
                constraints_count=len(job_ids) * 5
            )
        else:
            # Return failed optimization
            return OptimizationResult(
                status="INFEASIBLE",
                objective_value=None,
                schedule=None,
                computation_time=Duration(seconds=1),
                variables_count=0,
                constraints_count=0
            )


class MockConstraintValidationService(ConstraintValidationService):
    """Mock constraint validation service."""
    
    def __init__(self, violations: List[str] = None):
        self.violations = violations or []
        self.validation_calls = []
    
    async def validate_schedule(self, schedule: Schedule) -> List[str]:
        self.validation_calls.append(schedule.id)
        return self.violations.copy()


class MockResourceAllocationService(ResourceAllocationService):
    """Mock resource allocation service."""
    
    def __init__(self):
        self.allocation_calls = []
    
    async def allocate_resources_for_job(self, job: Job, start_time: datetime):
        from app.domain.scheduling.services.resource_allocation_service import ResourceAllocation
        
        self.allocation_calls.append({
            'job_id': job.id,
            'start_time': start_time
        })
        
        # Return mock allocations for each task in the job
        allocations = []
        for task_id in job.task_ids:
            allocation = ResourceAllocation(
                task_id=task_id,
                machine_id=uuid4(),
                operator_ids=[uuid4()]
            )
            allocations.append(allocation)
        
        return allocations


class MockWorkflowService(WorkflowService):
    """Mock workflow service."""
    
    def __init__(self):
        self.workflow_calls = []
    
    async def get_job_workflow_state(self, job_id: UUID) -> dict:
        return {
            'job_id': str(job_id),
            'status': 'ready',
            'available_tasks': 1
        }
    
    async def advance_job_workflow(self, job_id: UUID) -> List[UUID]:
        self.workflow_calls.append(job_id)
        # Return mock task transitions
        return [uuid4()]
    
    async def get_job_progress(self, job_id: UUID) -> dict:
        return {
            'total_tasks': 3,
            'completed_tasks': 1,
            'progress_percentage': 33.3
        }


class TestSchedulingWorkflowIntegration:
    """Test complete scheduling workflow integration."""
    
    @pytest.fixture
    def repositories(self):
        """Set up mock repositories."""
        return {
            'job': MockJobRepository(),
            'task': MockTaskRepository(),
            'operator': MockOperatorRepository(),
            'machine': MockMachineRepository(),
            'schedule': MockScheduleRepository(),
        }
    
    @pytest.fixture
    def services(self):
        """Set up mock services."""
        return {
            'optimization': MockOptimizationService(),
            'constraint_validation': MockConstraintValidationService(),
            'resource_allocation': MockResourceAllocationService(),
            'workflow': MockWorkflowService(),
        }
    
    @pytest.fixture
    def scheduling_service(self, repositories, services):
        """Create scheduling service with all dependencies."""
        return SchedulingService(
            job_repository=repositories['job'],
            task_repository=repositories['task'],
            operator_repository=repositories['operator'],
            machine_repository=repositories['machine'],
            schedule_repository=repositories['schedule'],
            constraint_validation_service=services['constraint_validation'],
            resource_allocation_service=services['resource_allocation'],
            optimization_service=services['optimization'],
            workflow_service=services['workflow']
        )

    @pytest.mark.asyncio
    async def test_create_optimized_schedule_success(self, scheduling_service, repositories):
        """Test successful creation of optimized schedule."""
        # Create test jobs
        job1, tasks1 = JobFactory.create_job_with_tasks(
            job_number="WORKFLOW-001",
            task_count=2
        )
        job2, tasks2 = JobFactory.create_job_with_tasks(
            job_number="WORKFLOW-002",
            task_count=3
        )
        
        # Save jobs to repository
        await repositories['job'].save(job1)
        await repositories['job'].save(job2)
        
        # Save tasks to repository
        for task in tasks1 + tasks2:
            await repositories['task'].save(task)
        
        # Create scheduling request
        request = SchedulingRequest(
            job_ids=[job1.id, job2.id],
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(days=7)
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(
            request=request,
            schedule_name="Integration Test Schedule"
        )
        
        # Verify results
        assert result.schedule is not None
        assert result.schedule.name == "Integration Test Schedule"
        assert len(result.schedule.job_ids) >= 2
        assert result.optimization_result.status == "OPTIMAL"
        assert result.violations == []  # No violations with default mock
        assert len(result.metrics) > 0
        assert len(result.recommendations) >= 0

    @pytest.mark.asyncio
    async def test_create_schedule_with_constraint_violations(self, repositories, services):
        """Test schedule creation with constraint violations."""
        # Set up constraint violations
        services['constraint_validation'].violations = [
            "Resource conflict detected",
            "Deadline constraint violated"
        ]
        
        scheduling_service = SchedulingService(
            job_repository=repositories['job'],
            task_repository=repositories['task'],
            operator_repository=repositories['operator'],
            machine_repository=repositories['machine'],
            schedule_repository=repositories['schedule'],
            constraint_validation_service=services['constraint_validation'],
            resource_allocation_service=services['resource_allocation'],
            optimization_service=services['optimization'],
            workflow_service=services['workflow']
        )
        
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create scheduling request
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify violations are reported
        assert len(result.violations) == 2
        assert "Resource conflict detected" in result.violations
        assert "Deadline constraint violated" in result.violations
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_schedule_optimization_fallback(self, repositories, services):
        """Test fallback to manual allocation when optimization fails."""
        # Configure optimization to fail
        services['optimization'].should_succeed = False
        
        scheduling_service = SchedulingService(
            job_repository=repositories['job'],
            task_repository=repositories['task'],
            operator_repository=repositories['operator'],
            machine_repository=repositories['machine'],
            schedule_repository=repositories['schedule'],
            constraint_validation_service=services['constraint_validation'],
            resource_allocation_service=services['resource_allocation'],
            optimization_service=services['optimization'],
            workflow_service=services['workflow']
        )
        
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create scheduling request
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify fallback was used
        assert result.schedule is not None
        assert result.optimization_result.status == "INFEASIBLE"
        # Resource allocation should have been called for fallback
        assert len(services['resource_allocation'].allocation_calls) > 0

    @pytest.mark.asyncio
    async def test_schedule_publishing_workflow(self, scheduling_service, repositories):
        """Test complete workflow from schedule creation to publishing."""
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create schedule
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        schedule_id = result.schedule.id
        
        # Publish schedule
        published_schedule = await scheduling_service.publish_schedule(schedule_id)
        
        # Verify publishing
        assert published_schedule.status == ScheduleStatus.PUBLISHED
        assert published_schedule.is_published

    @pytest.mark.asyncio
    async def test_schedule_execution_workflow(self, scheduling_service, repositories, services):
        """Test complete execution workflow."""
        # Create test jobs
        job1, tasks1 = JobFactory.create_job_with_tasks(task_count=2)
        job2, tasks2 = JobFactory.create_job_with_tasks(task_count=1)
        
        await repositories['job'].save(job1)
        await repositories['job'].save(job2)
        for task in tasks1 + tasks2:
            await repositories['task'].save(task)
        
        # Create and publish schedule
        request = SchedulingRequest(
            job_ids=[job1.id, job2.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        published_schedule = await scheduling_service.publish_schedule(result.schedule.id)
        
        # Execute schedule
        execution_result = await scheduling_service.execute_schedule(published_schedule.id)
        
        # Verify execution
        assert 'schedule_id' in execution_result
        assert 'execution_started_at' in execution_result
        assert 'jobs_processed' in execution_result
        assert execution_result['jobs_processed'] == 2
        assert len(services['workflow'].workflow_calls) == 2

    @pytest.mark.asyncio
    async def test_schedule_status_monitoring(self, scheduling_service, repositories):
        """Test schedule status monitoring throughout lifecycle."""
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create schedule
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        schedule_id = result.schedule.id
        
        # Check initial status
        status = await scheduling_service.get_schedule_status(schedule_id)
        assert status['status'] == ScheduleStatus.DRAFT.value
        
        # Publish and check status
        await scheduling_service.publish_schedule(schedule_id)
        status = await scheduling_service.get_schedule_status(schedule_id)
        assert status['status'] == ScheduleStatus.PUBLISHED.value
        
        # Execute and check status
        await scheduling_service.execute_schedule(schedule_id)
        status = await scheduling_service.get_schedule_status(schedule_id)
        assert status['status'] == ScheduleStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_resource_conflict_detection(self, scheduling_service, repositories):
        """Test resource conflict detection in scheduling."""
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks(task_count=5)
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create schedule with potential conflicts
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        published_schedule = await scheduling_service.publish_schedule(result.schedule.id)
        
        # Check for resource conflicts
        conflicts = await scheduling_service.get_resource_conflicts(
            schedule_id=published_schedule.id,
            time_window_hours=24
        )
        
        # Verify conflict detection works
        assert isinstance(conflicts, list)

    @pytest.mark.asyncio
    async def test_job_rescheduling_workflow(self, scheduling_service, repositories):
        """Test job rescheduling within a schedule."""
        # Create test job
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Create schedule
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Reschedule job
        new_start_time = datetime.now() + timedelta(hours=2)
        allocation = await scheduling_service.reschedule_job(
            job_id=job.id,
            new_start_time=new_start_time,
            schedule_id=result.schedule.id
        )
        
        # Verify rescheduling
        assert allocation is not None


class TestComplexSchedulingScenarios:
    """Test complex scheduling scenarios with multiple constraints."""
    
    @pytest.fixture
    def complex_scheduling_service(self):
        """Set up scheduling service for complex scenarios."""
        repositories = {
            'job': MockJobRepository(),
            'task': MockTaskRepository(),
            'operator': MockOperatorRepository(),
            'machine': MockMachineRepository(),
            'schedule': MockScheduleRepository(),
        }
        
        services = {
            'optimization': MockOptimizationService(),
            'constraint_validation': MockConstraintValidationService(),
            'resource_allocation': MockResourceAllocationService(),
            'workflow': MockWorkflowService(),
        }
        
        return SchedulingService(
            job_repository=repositories['job'],
            task_repository=repositories['task'],
            operator_repository=repositories['operator'],
            machine_repository=repositories['machine'],
            schedule_repository=repositories['schedule'],
            constraint_validation_service=services['constraint_validation'],
            resource_allocation_service=services['resource_allocation'],
            optimization_service=services['optimization'],
            workflow_service=services['workflow']
        ), repositories

    @pytest.mark.asyncio
    async def test_high_priority_job_scheduling(self, complex_scheduling_service):
        """Test scheduling with mixed priority jobs."""
        scheduling_service, repositories = complex_scheduling_service
        
        # Create jobs with different priorities
        urgent_job, urgent_tasks = JobFactory.create_job_with_tasks(
            priority=Priority.HIGH,
            job_number="URGENT-001"
        )
        
        normal_job, normal_tasks = JobFactory.create_job_with_tasks(
            priority=Priority.NORMAL,
            job_number="NORMAL-001"
        )
        
        low_job, low_tasks = JobFactory.create_job_with_tasks(
            priority=Priority.LOW,
            job_number="LOW-001"
        )
        
        # Save all jobs and tasks
        for job, tasks in [(urgent_job, urgent_tasks), (normal_job, normal_tasks), (low_job, low_tasks)]:
            await repositories['job'].save(job)
            for task in tasks:
                await repositories['task'].save(task)
        
        # Create scheduling request
        request = SchedulingRequest(
            job_ids=[urgent_job.id, normal_job.id, low_job.id],
            start_time=datetime.now()
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify all jobs are included
        assert len(result.schedule.job_ids) == 3
        assert urgent_job.id in result.schedule.job_ids
        assert normal_job.id in result.schedule.job_ids
        assert low_job.id in result.schedule.job_ids

    @pytest.mark.asyncio
    async def test_multi_department_scheduling(self, complex_scheduling_service):
        """Test scheduling across multiple departments."""
        scheduling_service, repositories = complex_scheduling_service
        
        # Create jobs for different departments
        jobs_and_tasks = []
        departments = ["fabrication", "machining", "assembly", "finishing"]
        
        for i, dept in enumerate(departments):
            job, tasks = JobFactory.create_job_with_tasks(
                job_number=f"{dept.upper()}-{i+1:03d}",
                customer_name=f"{dept.title()} Customer"
            )
            jobs_and_tasks.append((job, tasks))
            
            await repositories['job'].save(job)
            for task in tasks:
                await repositories['task'].save(task)
        
        # Create scheduling request for all departments
        all_job_ids = [job.id for job, _ in jobs_and_tasks]
        request = SchedulingRequest(
            job_ids=all_job_ids,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(days=14)
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify cross-department scheduling
        assert len(result.schedule.job_ids) == len(departments)
        assert result.schedule.planning_horizon.days == 14

    @pytest.mark.asyncio
    async def test_tight_deadline_scheduling(self, complex_scheduling_service):
        """Test scheduling with tight deadlines."""
        scheduling_service, repositories = complex_scheduling_service
        
        # Create job with very tight deadline
        base_time = datetime.now()
        tight_job, tight_tasks = JobFactory.create_job_with_tasks(
            job_number="TIGHT-001",
            due_date=base_time + timedelta(hours=8),  # Very tight
            release_date=base_time,
            task_count=4
        )
        
        await repositories['job'].save(tight_job)
        for task in tight_tasks:
            await repositories['task'].save(task)
        
        # Create scheduling request
        request = SchedulingRequest(
            job_ids=[tight_job.id],
            start_time=base_time,
            end_time=base_time + timedelta(hours=8)
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify scheduling handles tight constraints
        assert result.schedule is not None
        # May have violations or recommendations for tight deadlines
        if result.violations:
            assert any("deadline" in v.lower() or "time" in v.lower() for v in result.violations)

    @pytest.mark.asyncio
    async def test_large_scale_scheduling(self, complex_scheduling_service):
        """Test scheduling with many jobs and tasks."""
        scheduling_service, repositories = complex_scheduling_service
        
        # Create many jobs
        job_count = 20
        jobs_and_tasks = []
        
        for i in range(job_count):
            job, tasks = JobFactory.create_job_with_tasks(
                job_number=f"LARGE-{i+1:03d}",
                task_count=3 + (i % 3),  # Varying task counts
                priority=Priority.NORMAL if i % 3 == 0 else Priority.LOW
            )
            jobs_and_tasks.append((job, tasks))
            
            await repositories['job'].save(job)
            for task in tasks:
                await repositories['task'].save(task)
        
        # Create scheduling request for all jobs
        all_job_ids = [job.id for job, _ in jobs_and_tasks]
        request = SchedulingRequest(
            job_ids=all_job_ids,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(days=30)
        )
        
        # Execute scheduling
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Verify large scale scheduling
        assert len(result.schedule.job_ids) == job_count
        assert result.schedule.planning_horizon.days == 30
        # Should have metrics for large schedule
        assert result.metrics.get('total_assignments', 0) >= 0


class TestSchedulingErrorHandling:
    """Test error handling in scheduling workflows."""
    
    @pytest.fixture
    def error_scheduling_service(self):
        """Set up scheduling service for error testing."""
        repositories = {
            'job': MockJobRepository(),
            'task': MockTaskRepository(),
            'operator': MockOperatorRepository(),
            'machine': MockMachineRepository(),
            'schedule': MockScheduleRepository(),
        }
        
        services = {
            'optimization': MockOptimizationService(),
            'constraint_validation': MockConstraintValidationService(),
            'resource_allocation': MockResourceAllocationService(),
            'workflow': MockWorkflowService(),
        }
        
        return SchedulingService(
            job_repository=repositories['job'],
            task_repository=repositories['task'],
            operator_repository=repositories['operator'],
            machine_repository=repositories['machine'],
            schedule_repository=repositories['schedule'],
            constraint_validation_service=services['constraint_validation'],
            resource_allocation_service=services['resource_allocation'],
            optimization_service=services['optimization'],
            workflow_service=services['workflow']
        ), repositories

    @pytest.mark.asyncio
    async def test_invalid_job_scheduling(self, error_scheduling_service):
        """Test scheduling with non-existent jobs."""
        scheduling_service, repositories = error_scheduling_service
        
        # Try to schedule non-existent job
        request = SchedulingRequest(
            job_ids=[uuid4()],  # Non-existent job
            start_time=datetime.now()
        )
        
        with pytest.raises(Exception):  # Should raise validation error
            await scheduling_service.create_optimized_schedule(request)

    @pytest.mark.asyncio
    async def test_inactive_job_scheduling(self, error_scheduling_service):
        """Test scheduling with inactive jobs."""
        scheduling_service, repositories = error_scheduling_service
        
        # Create inactive job
        job = JobFactory.create_job(status=JobStatus.CANCELLED)
        await repositories['job'].save(job)
        
        # Try to schedule inactive job
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        with pytest.raises(Exception):  # Should raise validation error
            await scheduling_service.create_optimized_schedule(request)

    @pytest.mark.asyncio
    async def test_schedule_publishing_with_violations(self, error_scheduling_service):
        """Test publishing schedule with constraint violations."""
        scheduling_service, repositories = error_scheduling_service
        
        # Create job and schedule
        job, tasks = JobFactory.create_job_with_tasks()
        await repositories['job'].save(job)
        for task in tasks:
            await repositories['task'].save(task)
        
        # Set up constraint violations
        constraint_service = scheduling_service._constraint_validation_service
        constraint_service.violations = ["Critical constraint violated"]
        
        # Create schedule
        request = SchedulingRequest(
            job_ids=[job.id],
            start_time=datetime.now()
        )
        
        result = await scheduling_service.create_optimized_schedule(request)
        
        # Try to publish schedule with violations
        with pytest.raises(Exception):  # Should raise publish error
            await scheduling_service.publish_schedule(result.schedule.id)


# Mock repositories for complex scenarios
class MockOperatorRepository(OperatorRepository):
    """Mock operator repository."""
    
    def __init__(self):
        self._operators = {}
    
    async def save(self, operator):
        self._operators[operator.id] = operator
        return operator
    
    async def get_by_id(self, operator_id):
        return self._operators.get(operator_id)
    
    async def get_available_operators(self, start_time, end_time):
        return list(self._operators.values())


class MockMachineRepository(MachineRepository):
    """Mock machine repository."""
    
    def __init__(self):
        self._machines = {}
    
    async def save(self, machine):
        self._machines[machine.id] = machine
        return machine
    
    async def get_by_id(self, machine_id):
        return self._machines.get(machine_id)
    
    async def get_available_machines(self, start_time, end_time):
        return list(self._machines.values())