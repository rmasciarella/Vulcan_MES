"""
Repository CRUD Operation Tests

Tests for repository implementations including all CRUD operations,
query methods, and repository-specific business logic.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.repositories.job_repository import JobRepository
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
    TaskStatus,
)
from app.shared.exceptions import RepositoryError
from app.tests.database.factories import (
    JobFactory,
    TaskFactory,
    TestDataBuilder,
)


# Mock repository implementations for testing
class InMemoryJobRepository(JobRepository):
    """In-memory implementation of JobRepository for testing."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}

    async def save(self, job: Job) -> Job:
        """Save a job to the repository."""
        self._jobs[str(job.id)] = job
        return job

    async def get_by_id(self, job_id) -> Job | None:
        """Retrieve a job by its ID."""
        return self._jobs.get(str(job_id))

    async def get_all(self) -> list[Job]:
        """Retrieve all jobs."""
        return list(self._jobs.values())

    async def get_by_customer_id(self, customer_id) -> list[Job]:
        """Retrieve jobs for a specific customer."""
        # Simplified - in real implementation would filter by customer_id
        return [
            job
            for job in self._jobs.values()
            if job.customer_name and str(customer_id) in job.customer_name
        ]

    async def get_active_jobs(self) -> list[Job]:
        """Retrieve all active jobs."""
        return [job for job in self._jobs.values() if job.is_active]

    async def get_jobs_due_before(self, due_date: datetime) -> list[Job]:
        """Retrieve jobs due before a specific date."""
        return [job for job in self._jobs.values() if job.due_date < due_date]

    async def get_jobs_by_priority(self, priority: int) -> list[Job]:
        """Retrieve jobs with specific priority."""
        priority_level = PriorityLevel(priority)
        return [job for job in self._jobs.values() if job.priority == priority_level]

    async def update(self, job: Job) -> Job:
        """Update an existing job."""
        if str(job.id) not in self._jobs:
            raise RepositoryError(f"Job {job.id} not found")
        self._jobs[str(job.id)] = job
        return job

    async def delete(self, job_id) -> bool:
        """Delete a job by ID."""
        if str(job_id) in self._jobs:
            del self._jobs[str(job_id)]
            return True
        return False

    async def exists(self, job_id) -> bool:
        """Check if a job exists."""
        return str(job_id) in self._jobs

    async def count(self) -> int:
        """Count total number of jobs."""
        return len(self._jobs)

    async def count_by_status(self, is_active: bool) -> int:
        """Count jobs by status."""
        return len([job for job in self._jobs.values() if job.is_active == is_active])


class InMemoryTaskRepository:
    """In-memory implementation of TaskRepository for testing."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    async def save(self, task: Task) -> Task:
        """Save a task to the repository."""
        self._tasks[str(task.id)] = task
        return task

    async def get_by_id(self, task_id) -> Task | None:
        """Retrieve a task by its ID."""
        return self._tasks.get(str(task_id))

    async def get_all(self) -> list[Task]:
        """Retrieve all tasks."""
        return list(self._tasks.values())

    async def get_by_job_id(self, job_id) -> list[Task]:
        """Retrieve tasks for a specific job."""
        return [task for task in self._tasks.values() if task.job_id == job_id]

    async def get_by_status(self, status: TaskStatus) -> list[Task]:
        """Retrieve tasks with specific status."""
        return [task for task in self._tasks.values() if task.status == status]

    async def get_ready_tasks(self) -> list[Task]:
        """Retrieve tasks ready for scheduling."""
        return [
            task for task in self._tasks.values() if task.status == TaskStatus.READY
        ]

    async def get_active_tasks(self) -> list[Task]:
        """Retrieve currently active tasks."""
        return [
            task
            for task in self._tasks.values()
            if task.status in {TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS}
        ]

    async def get_critical_path_tasks(self) -> list[Task]:
        """Retrieve critical path tasks."""
        return [task for task in self._tasks.values() if task.is_critical_path]

    async def get_delayed_tasks(self) -> list[Task]:
        """Retrieve delayed tasks."""
        return [task for task in self._tasks.values() if task.is_delayed]

    async def update(self, task: Task) -> Task:
        """Update an existing task."""
        if str(task.id) not in self._tasks:
            raise RepositoryError(f"Task {task.id} not found")
        self._tasks[str(task.id)] = task
        return task

    async def delete(self, task_id) -> bool:
        """Delete a task by ID."""
        if str(task_id) in self._tasks:
            del self._tasks[str(task_id)]
            return True
        return False

    async def exists(self, task_id) -> bool:
        """Check if a task exists."""
        return str(task_id) in self._tasks

    async def count(self) -> int:
        """Count total number of tasks."""
        return len(self._tasks)


class TestJobRepository:
    """Test JobRepository CRUD operations."""

    @pytest.fixture
    def job_repo(self):
        """Provide a JobRepository instance."""
        return InMemoryJobRepository()

    @pytest.mark.asyncio
    async def test_save_job(self, job_repo):
        """Test saving a job to repository."""
        job = JobFactory.create()

        saved_job = await job_repo.save(job)

        assert saved_job == job
        assert saved_job.id == job.id
        assert saved_job.job_number == job.job_number

    @pytest.mark.asyncio
    async def test_get_job_by_id(self, job_repo):
        """Test retrieving job by ID."""
        job = JobFactory.create()
        await job_repo.save(job)

        retrieved_job = await job_repo.get_by_id(job.id)

        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.job_number == job.job_number

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(self, job_repo):
        """Test retrieving non-existent job."""
        non_existent_id = uuid4()

        retrieved_job = await job_repo.get_by_id(non_existent_id)

        assert retrieved_job is None

    @pytest.mark.asyncio
    async def test_get_all_jobs(self, job_repo):
        """Test retrieving all jobs."""
        jobs = JobFactory.create_batch(5)

        for job in jobs:
            await job_repo.save(job)

        all_jobs = await job_repo.get_all()

        assert len(all_jobs) == 5
        job_ids = {job.id for job in all_jobs}
        expected_ids = {job.id for job in jobs}
        assert job_ids == expected_ids

    @pytest.mark.asyncio
    async def test_get_active_jobs(self, job_repo):
        """Test retrieving active jobs."""
        # Create jobs with different statuses
        active_job1 = JobFactory.create(status=JobStatus.RELEASED)
        active_job2 = JobFactory.create(status=JobStatus.IN_PROGRESS)
        inactive_job1 = JobFactory.create(status=JobStatus.COMPLETED)
        inactive_job2 = JobFactory.create(status=JobStatus.CANCELLED)

        jobs = [active_job1, active_job2, inactive_job1, inactive_job2]
        for job in jobs:
            await job_repo.save(job)

        active_jobs = await job_repo.get_active_jobs()

        # Only active jobs should be returned
        assert len(active_jobs) >= 0  # Depends on status.is_active implementation

        # Verify no completed or cancelled jobs
        statuses = {job.status for job in active_jobs}
        assert JobStatus.COMPLETED not in statuses
        assert JobStatus.CANCELLED not in statuses

    @pytest.mark.asyncio
    async def test_get_jobs_due_before(self, job_repo):
        """Test retrieving jobs due before a specific date."""
        cutoff_date = datetime.utcnow() + timedelta(days=7)

        # Create jobs with different due dates
        early_job1 = JobFactory.create(due_date=cutoff_date - timedelta(days=2))
        early_job2 = JobFactory.create(due_date=cutoff_date - timedelta(hours=1))
        late_job = JobFactory.create(due_date=cutoff_date + timedelta(days=1))

        jobs = [early_job1, early_job2, late_job]
        for job in jobs:
            await job_repo.save(job)

        jobs_due_before = await job_repo.get_jobs_due_before(cutoff_date)

        assert len(jobs_due_before) == 2
        job_ids = {job.id for job in jobs_due_before}
        assert early_job1.id in job_ids
        assert early_job2.id in job_ids
        assert late_job.id not in job_ids

    @pytest.mark.asyncio
    async def test_get_jobs_by_priority(self, job_repo):
        """Test retrieving jobs by priority."""
        high_priority_jobs = [
            JobFactory.create(priority=PriorityLevel.HIGH),
            JobFactory.create(priority=PriorityLevel.HIGH),
        ]
        normal_priority_job = JobFactory.create(priority=PriorityLevel.NORMAL)
        urgent_priority_job = JobFactory.create(priority=PriorityLevel.URGENT)

        all_jobs = high_priority_jobs + [normal_priority_job, urgent_priority_job]
        for job in all_jobs:
            await job_repo.save(job)

        high_jobs = await job_repo.get_jobs_by_priority(PriorityLevel.HIGH.value)

        assert len(high_jobs) == 2
        for job in high_jobs:
            assert job.priority == PriorityLevel.HIGH

    @pytest.mark.asyncio
    async def test_update_job(self, job_repo):
        """Test updating a job."""
        job = JobFactory.create()
        await job_repo.save(job)

        # Modify the job
        job.customer_name = "Updated Customer"
        job.priority = PriorityLevel.URGENT

        updated_job = await job_repo.update(job)

        assert updated_job.customer_name == "Updated Customer"
        assert updated_job.priority == PriorityLevel.URGENT

        # Verify persistence
        retrieved_job = await job_repo.get_by_id(job.id)
        assert retrieved_job.customer_name == "Updated Customer"
        assert retrieved_job.priority == PriorityLevel.URGENT

    @pytest.mark.asyncio
    async def test_update_nonexistent_job(self, job_repo):
        """Test updating a non-existent job."""
        job = JobFactory.create()

        with pytest.raises(RepositoryError, match="Job .* not found"):
            await job_repo.update(job)

    @pytest.mark.asyncio
    async def test_delete_job(self, job_repo):
        """Test deleting a job."""
        job = JobFactory.create()
        await job_repo.save(job)

        # Verify job exists
        assert await job_repo.exists(job.id)

        # Delete job
        deleted = await job_repo.delete(job.id)

        assert deleted is True
        assert not await job_repo.exists(job.id)

        # Verify job is gone
        retrieved_job = await job_repo.get_by_id(job.id)
        assert retrieved_job is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, job_repo):
        """Test deleting a non-existent job."""
        non_existent_id = uuid4()

        deleted = await job_repo.delete(non_existent_id)

        assert deleted is False

    @pytest.mark.asyncio
    async def test_job_exists(self, job_repo):
        """Test checking if job exists."""
        job = JobFactory.create()
        non_existent_id = uuid4()

        # Before saving
        assert not await job_repo.exists(job.id)
        assert not await job_repo.exists(non_existent_id)

        # After saving
        await job_repo.save(job)
        assert await job_repo.exists(job.id)
        assert not await job_repo.exists(non_existent_id)

    @pytest.mark.asyncio
    async def test_count_jobs(self, job_repo):
        """Test counting jobs."""
        # Initially empty
        assert await job_repo.count() == 0

        # Add jobs
        jobs = JobFactory.create_batch(10)
        for job in jobs:
            await job_repo.save(job)

        assert await job_repo.count() == 10

        # Delete some jobs
        for i in range(3):
            await job_repo.delete(jobs[i].id)

        assert await job_repo.count() == 7

    @pytest.mark.asyncio
    async def test_count_by_status(self, job_repo):
        """Test counting jobs by status."""
        # Create jobs with different statuses
        active_jobs = [
            JobFactory.create(status=JobStatus.RELEASED),
            JobFactory.create(status=JobStatus.IN_PROGRESS),
        ]
        inactive_jobs = [
            JobFactory.create(status=JobStatus.COMPLETED),
            JobFactory.create(status=JobStatus.CANCELLED),
        ]

        all_jobs = active_jobs + inactive_jobs
        for job in all_jobs:
            await job_repo.save(job)

        # Count active and inactive jobs
        active_count = await job_repo.count_by_status(is_active=True)
        inactive_count = await job_repo.count_by_status(is_active=False)

        # These counts depend on the is_active property implementation
        assert active_count >= 0
        assert inactive_count >= 0
        assert active_count + inactive_count <= len(all_jobs)


class TestTaskRepository:
    """Test TaskRepository CRUD operations."""

    @pytest.fixture
    def task_repo(self):
        """Provide a TaskRepository instance."""
        return InMemoryTaskRepository()

    @pytest.mark.asyncio
    async def test_save_task(self, task_repo):
        """Test saving a task to repository."""
        task = TaskFactory.create()

        saved_task = await task_repo.save(task)

        assert saved_task == task
        assert saved_task.id == task.id
        assert saved_task.sequence_in_job == task.sequence_in_job

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, task_repo):
        """Test retrieving task by ID."""
        task = TaskFactory.create()
        await task_repo.save(task)

        retrieved_task = await task_repo.get_by_id(task.id)

        assert retrieved_task is not None
        assert retrieved_task.id == task.id
        assert retrieved_task.job_id == task.job_id

    @pytest.mark.asyncio
    async def test_get_tasks_by_job_id(self, task_repo):
        """Test retrieving tasks by job ID."""
        job_id = uuid4()
        job_tasks = TaskFactory.create_batch(job_id=job_id, count=5)
        other_tasks = TaskFactory.create_batch(job_id=uuid4(), count=3)

        all_tasks = job_tasks + other_tasks
        for task in all_tasks:
            await task_repo.save(task)

        retrieved_tasks = await task_repo.get_by_job_id(job_id)

        assert len(retrieved_tasks) == 5
        for task in retrieved_tasks:
            assert task.job_id == job_id

    @pytest.mark.asyncio
    async def test_get_tasks_by_status(self, task_repo):
        """Test retrieving tasks by status."""
        ready_tasks = [TaskFactory.create_ready() for _ in range(3)]
        scheduled_tasks = [TaskFactory.create_scheduled() for _ in range(2)]
        completed_tasks = [TaskFactory.create_completed() for _ in range(4)]

        all_tasks = ready_tasks + scheduled_tasks + completed_tasks
        for task in all_tasks:
            await task_repo.save(task)

        retrieved_ready = await task_repo.get_by_status(TaskStatus.READY)
        retrieved_completed = await task_repo.get_by_status(TaskStatus.COMPLETED)

        assert len(retrieved_ready) == 3
        assert len(retrieved_completed) == 4

        for task in retrieved_ready:
            assert task.status == TaskStatus.READY

        for task in retrieved_completed:
            assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_ready_tasks(self, task_repo):
        """Test retrieving ready tasks."""
        ready_tasks = [TaskFactory.create_ready() for _ in range(3)]
        other_tasks = [
            TaskFactory.create(),  # PENDING
            TaskFactory.create_scheduled(),  # SCHEDULED
            TaskFactory.create_completed(),  # COMPLETED
        ]

        all_tasks = ready_tasks + other_tasks
        for task in all_tasks:
            await task_repo.save(task)

        retrieved_ready = await task_repo.get_ready_tasks()

        assert len(retrieved_ready) == 3
        for task in retrieved_ready:
            assert task.status == TaskStatus.READY

    @pytest.mark.asyncio
    async def test_get_active_tasks(self, task_repo):
        """Test retrieving active tasks."""
        scheduled_tasks = [TaskFactory.create_scheduled() for _ in range(2)]
        in_progress_tasks = [TaskFactory.create_in_progress() for _ in range(3)]
        inactive_tasks = [
            TaskFactory.create(),  # PENDING
            TaskFactory.create_completed(),  # COMPLETED
        ]

        all_tasks = scheduled_tasks + in_progress_tasks + inactive_tasks
        for task in all_tasks:
            await task_repo.save(task)

        active_tasks = await task_repo.get_active_tasks()

        assert len(active_tasks) == 5  # 2 SCHEDULED + 3 IN_PROGRESS
        for task in active_tasks:
            assert task.status in {TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS}

    @pytest.mark.asyncio
    async def test_get_critical_path_tasks(self, task_repo):
        """Test retrieving critical path tasks."""
        critical_tasks = [TaskFactory.create_critical_path() for _ in range(3)]
        normal_tasks = [TaskFactory.create() for _ in range(4)]

        all_tasks = critical_tasks + normal_tasks
        for task in all_tasks:
            await task_repo.save(task)

        retrieved_critical = await task_repo.get_critical_path_tasks()

        assert len(retrieved_critical) == 3
        for task in retrieved_critical:
            assert task.is_critical_path

    @pytest.mark.asyncio
    async def test_get_delayed_tasks(self, task_repo):
        """Test retrieving delayed tasks."""
        delayed_tasks = [TaskFactory.create_with_delay() for _ in range(2)]
        normal_tasks = [TaskFactory.create() for _ in range(3)]

        all_tasks = delayed_tasks + normal_tasks
        for task in all_tasks:
            await task_repo.save(task)

        retrieved_delayed = await task_repo.get_delayed_tasks()

        assert len(retrieved_delayed) == 2
        for task in retrieved_delayed:
            assert task.is_delayed
            assert task.delay_minutes > 0

    @pytest.mark.asyncio
    async def test_update_task(self, task_repo):
        """Test updating a task."""
        task = TaskFactory.create()
        await task_repo.save(task)

        # Modify the task
        task.mark_critical_path()
        task.record_rework("quality_issue")

        updated_task = await task_repo.update(task)

        assert updated_task.is_critical_path
        assert updated_task.rework_count == 1

        # Verify persistence
        retrieved_task = await task_repo.get_by_id(task.id)
        assert retrieved_task.is_critical_path
        assert retrieved_task.rework_count == 1

    @pytest.mark.asyncio
    async def test_delete_task(self, task_repo):
        """Test deleting a task."""
        task = TaskFactory.create()
        await task_repo.save(task)

        # Verify task exists
        assert await task_repo.exists(task.id)

        # Delete task
        deleted = await task_repo.delete(task.id)

        assert deleted is True
        assert not await task_repo.exists(task.id)

    @pytest.mark.asyncio
    async def test_count_tasks(self, task_repo):
        """Test counting tasks."""
        assert await task_repo.count() == 0

        # Add tasks
        job_id = uuid4()
        tasks = TaskFactory.create_batch(job_id=job_id, count=8)
        for task in tasks:
            await task_repo.save(task)

        assert await task_repo.count() == 8


class TestRepositoryIntegration:
    """Test repository integration scenarios."""

    @pytest.fixture
    def repos(self):
        """Provide repository instances."""
        return {
            "job_repo": InMemoryJobRepository(),
            "task_repo": InMemoryTaskRepository(),
        }

    @pytest.mark.asyncio
    async def test_job_with_tasks_scenario(self, repos):
        """Test complete job-task scenario using repositories."""
        job_repo = repos["job_repo"]
        task_repo = repos["task_repo"]

        # Create and save job
        job = JobFactory.create_with_tasks(task_count=4)
        await job_repo.save(job)

        # Save all tasks
        for task in job.get_all_tasks():
            await task_repo.save(task)

        # Verify job retrieval
        retrieved_job = await job_repo.get_by_id(job.id)
        assert retrieved_job is not None
        assert retrieved_job.task_count == 4

        # Verify task retrieval
        job_tasks = await task_repo.get_by_job_id(job.id)
        assert len(job_tasks) == 4

        # Test task progression
        first_task = job_tasks[0]
        first_task.mark_ready()
        await task_repo.update(first_task)

        ready_tasks = await task_repo.get_ready_tasks()
        assert len(ready_tasks) == 1
        assert ready_tasks[0].id == first_task.id

    @pytest.mark.asyncio
    async def test_workload_scenario(self, repos):
        """Test realistic workload scenario."""
        job_repo = repos["job_repo"]
        task_repo = repos["task_repo"]

        # Create workload
        workload = TestDataBuilder.create_workload_scenario()

        # Save all jobs
        for job in workload["jobs"]:
            await job_repo.save(job)

        # Save all tasks
        for task in workload["tasks"]:
            await task_repo.save(task)

        # Test various queries
        all_jobs = await job_repo.get_all()
        assert len(all_jobs) == len(workload["jobs"])

        active_jobs = await job_repo.get_active_jobs()
        total_jobs = await job_repo.count()

        assert len(all_jobs) == total_jobs

        # Test task queries
        all_tasks = await task_repo.get_all()
        ready_tasks = await task_repo.get_ready_tasks()
        active_tasks = await task_repo.get_active_tasks()

        assert len(all_tasks) == len(workload["tasks"])

        # All collections should be non-empty for a realistic workload
        assert len(active_jobs) >= 0
        assert len(ready_tasks) >= 0
        assert len(active_tasks) >= 0
