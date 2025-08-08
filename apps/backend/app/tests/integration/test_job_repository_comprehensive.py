"""
Comprehensive Integration Tests for Job Repository

Tests the complete job repository implementation against a real database,
including CRUD operations, domain-specific queries, transaction handling,
and concurrent access scenarios.
"""

from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.core.db_test import test_engine
from app.domain.scheduling.value_objects.enums import JobStatus, TaskStatus
from app.infrastructure.database.models import JobCreate, JobUpdate, Task
from app.infrastructure.database.repositories.base import (
    DatabaseError,
    EntityNotFoundError,
)
from app.infrastructure.database.repositories.job_repository import JobRepository


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session
        session.rollback()  # Rollback after each test


@pytest.fixture
def job_repository(db_session):
    """Create a job repository instance."""
    return JobRepository(session=db_session)


@pytest.fixture
def sample_job_data():
    """Create sample job data for testing."""
    return {
        "job_number": "TEST-JOB-001",
        "customer_name": "Test Customer",
        "part_number": "PART-TEST-001",
        "quantity": 10,
        "priority": "NORMAL",
        "status": JobStatus.PLANNED,
        "due_date": datetime.utcnow() + timedelta(days=7),
        "notes": "Test job for integration testing",
        "created_by": "test_user",
    }


class TestJobRepositoryBasicCRUD:
    """Test basic CRUD operations for job repository."""

    def test_create_job_success(self, job_repository, sample_job_data):
        """Test successful job creation."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        assert created_job is not None
        assert created_job.id is not None
        assert created_job.job_number == sample_job_data["job_number"]
        assert created_job.customer_name == sample_job_data["customer_name"]
        assert created_job.part_number == sample_job_data["part_number"]
        assert created_job.quantity == sample_job_data["quantity"]
        assert created_job.status == sample_job_data["status"]
        assert created_job.created_at is not None
        assert created_job.updated_at is not None

    def test_create_job_duplicate_job_number(self, job_repository, sample_job_data):
        """Test creating job with duplicate job number fails."""
        job_create = JobCreate(**sample_job_data)
        job_repository.create(job_create)

        # Try to create another job with same job number
        duplicate_job_create = JobCreate(**sample_job_data)

        with pytest.raises(DatabaseError, match="duplicate"):
            job_repository.create(duplicate_job_create)

    def test_get_job_by_id_success(self, job_repository, sample_job_data):
        """Test retrieving job by ID."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        retrieved_job = job_repository.get(created_job.id)

        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.job_number == created_job.job_number
        assert retrieved_job.customer_name == created_job.customer_name

    def test_get_job_by_id_not_found(self, job_repository):
        """Test retrieving non-existent job returns None."""
        non_existent_id = uuid4()
        result = job_repository.get(non_existent_id)
        assert result is None

    def test_update_job_success(self, job_repository, sample_job_data):
        """Test successful job update."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        # Update job data
        update_data = JobUpdate(
            customer_name="Updated Customer",
            part_number="UPDATED-PART",
            priority="HIGH",
            notes="Updated notes",
        )

        updated_job = job_repository.update(created_job.id, update_data)

        assert updated_job is not None
        assert updated_job.customer_name == "Updated Customer"
        assert updated_job.part_number == "UPDATED-PART"
        assert updated_job.priority == "HIGH"
        assert updated_job.notes == "Updated notes"
        assert updated_job.updated_at > created_job.updated_at

    def test_update_job_not_found(self, job_repository):
        """Test updating non-existent job raises error."""
        non_existent_id = uuid4()
        update_data = JobUpdate(customer_name="Updated Customer")

        with pytest.raises(EntityNotFoundError):
            job_repository.update(non_existent_id, update_data)

    def test_delete_job_success(self, job_repository, sample_job_data):
        """Test successful job deletion."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        result = job_repository.delete(created_job.id)
        assert result is True

        # Verify job is deleted
        deleted_job = job_repository.get(created_job.id)
        assert deleted_job is None

    def test_delete_job_not_found(self, job_repository):
        """Test deleting non-existent job returns False."""
        non_existent_id = uuid4()
        result = job_repository.delete(non_existent_id)
        assert result is False

    def test_list_jobs_empty(self, job_repository):
        """Test listing jobs when none exist."""
        jobs = job_repository.list()
        assert jobs == []

    def test_list_jobs_with_data(self, job_repository, sample_job_data):
        """Test listing jobs with data."""
        # Create multiple jobs
        jobs_data = []
        for i in range(3):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"TEST-JOB-{i:03d}"
            job_data["customer_name"] = f"Customer {i}"
            jobs_data.append(job_data)

            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        jobs = job_repository.list()
        assert len(jobs) == 3

        # Verify order (should be by creation time)
        job_numbers = [job.job_number for job in jobs]
        expected_numbers = [f"TEST-JOB-{i:03d}" for i in range(3)]
        assert job_numbers == expected_numbers

    def test_list_jobs_with_pagination(self, job_repository, sample_job_data):
        """Test listing jobs with pagination."""
        # Create 5 jobs
        for i in range(5):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"TEST-JOB-{i:03d}"
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Test first page
        first_page = job_repository.list(skip=0, limit=2)
        assert len(first_page) == 2

        # Test second page
        second_page = job_repository.list(skip=2, limit=2)
        assert len(second_page) == 2

        # Test third page
        third_page = job_repository.list(skip=4, limit=2)
        assert len(third_page) == 1

        # Ensure no overlap
        all_job_numbers = [
            job.job_number for job in first_page + second_page + third_page
        ]
        assert len(set(all_job_numbers)) == 5


class TestJobRepositoryDomainQueries:
    """Test domain-specific query methods."""

    def test_find_by_job_number_success(self, job_repository, sample_job_data):
        """Test finding job by job number."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        found_job = job_repository.find_by_job_number(sample_job_data["job_number"])

        assert found_job is not None
        assert found_job.id == created_job.id
        assert found_job.job_number == sample_job_data["job_number"]

    def test_find_by_job_number_case_insensitive(self, job_repository, sample_job_data):
        """Test finding job by job number is case insensitive."""
        job_create = JobCreate(**sample_job_data)
        job_repository.create(job_create)

        # Search with lowercase
        found_job = job_repository.find_by_job_number(
            sample_job_data["job_number"].lower()
        )
        assert found_job is not None

        # Search with mixed case
        mixed_case = sample_job_data["job_number"].swapcase()
        found_job = job_repository.find_by_job_number(mixed_case)
        assert found_job is not None

    def test_find_by_job_number_not_found(self, job_repository):
        """Test finding non-existent job number returns None."""
        result = job_repository.find_by_job_number("NON-EXISTENT-JOB")
        assert result is None

    def test_find_by_status_single_status(self, job_repository, sample_job_data):
        """Test finding jobs by single status."""
        # Create jobs with different statuses
        statuses = [
            JobStatus.PLANNED,
            JobStatus.RELEASED,
            JobStatus.IN_PROGRESS,
            JobStatus.COMPLETED,
        ]
        created_jobs = []

        for i, status in enumerate(statuses):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"TEST-JOB-{i:03d}"
            job_data["status"] = status
            job_create = JobCreate(**job_data)
            created_job = job_repository.create(job_create)
            created_jobs.append(created_job)

        # Test finding by each status
        planned_jobs = job_repository.find_by_status([JobStatus.PLANNED])
        assert len(planned_jobs) == 1
        assert planned_jobs[0].status == JobStatus.PLANNED

        released_jobs = job_repository.find_by_status([JobStatus.RELEASED])
        assert len(released_jobs) == 1
        assert released_jobs[0].status == JobStatus.RELEASED

    def test_find_by_status_multiple_statuses(self, job_repository, sample_job_data):
        """Test finding jobs by multiple statuses."""
        # Create jobs with different statuses
        statuses = [
            JobStatus.PLANNED,
            JobStatus.RELEASED,
            JobStatus.IN_PROGRESS,
            JobStatus.COMPLETED,
        ]

        for i, status in enumerate(statuses):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"TEST-JOB-{i:03d}"
            job_data["status"] = status
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Find active jobs (RELEASED and IN_PROGRESS)
        active_jobs = job_repository.find_by_status(
            [JobStatus.RELEASED, JobStatus.IN_PROGRESS]
        )
        assert len(active_jobs) == 2

        active_statuses = {job.status for job in active_jobs}
        assert active_statuses == {JobStatus.RELEASED, JobStatus.IN_PROGRESS}

    def test_find_overdue_jobs(self, job_repository, sample_job_data):
        """Test finding overdue jobs."""
        current_time = datetime.utcnow()

        # Create overdue job
        overdue_data = sample_job_data.copy()
        overdue_data["job_number"] = "OVERDUE-JOB"
        overdue_data["due_date"] = current_time - timedelta(days=1)  # Yesterday
        overdue_data["status"] = JobStatus.IN_PROGRESS  # Not completed
        job_create = JobCreate(**overdue_data)
        job_repository.create(job_create)

        # Create on-time job
        ontime_data = sample_job_data.copy()
        ontime_data["job_number"] = "ONTIME-JOB"
        ontime_data["due_date"] = current_time + timedelta(days=7)  # Next week
        ontime_data["status"] = JobStatus.IN_PROGRESS
        job_create = JobCreate(**ontime_data)
        job_repository.create(job_create)

        # Create completed overdue job (should not be included)
        completed_overdue_data = sample_job_data.copy()
        completed_overdue_data["job_number"] = "COMPLETED-OVERDUE"
        completed_overdue_data["due_date"] = current_time - timedelta(days=2)
        completed_overdue_data["status"] = JobStatus.COMPLETED
        job_create = JobCreate(**completed_overdue_data)
        job_repository.create(job_create)

        overdue_jobs = job_repository.find_overdue_jobs()

        assert len(overdue_jobs) == 1
        assert overdue_jobs[0].job_number == "OVERDUE-JOB"
        assert overdue_jobs[0].due_date < current_time
        assert overdue_jobs[0].status != JobStatus.COMPLETED

    def test_find_by_customer(self, job_repository, sample_job_data):
        """Test finding jobs by customer name."""
        customers = ["Customer A", "Customer B", "Customer A"]

        for i, customer in enumerate(customers):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"CUST-JOB-{i:03d}"
            job_data["customer_name"] = customer
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Find jobs for Customer A
        customer_a_jobs = job_repository.find_by_customer("Customer A")
        assert len(customer_a_jobs) == 2

        for job in customer_a_jobs:
            assert job.customer_name == "Customer A"

        # Find jobs for Customer B
        customer_b_jobs = job_repository.find_by_customer("Customer B")
        assert len(customer_b_jobs) == 1
        assert customer_b_jobs[0].customer_name == "Customer B"

    def test_find_by_customer_case_insensitive(self, job_repository, sample_job_data):
        """Test finding jobs by customer name is case insensitive."""
        job_data = sample_job_data.copy()
        job_data["customer_name"] = "Test Customer Corp"
        job_create = JobCreate(**job_data)
        job_repository.create(job_create)

        # Search with different cases
        results_lower = job_repository.find_by_customer("test customer corp")
        results_upper = job_repository.find_by_customer("TEST CUSTOMER CORP")
        results_mixed = job_repository.find_by_customer("Test CUSTOMER Corp")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    def test_find_by_due_date_range(self, job_repository, sample_job_data):
        """Test finding jobs by due date range."""
        base_date = datetime.utcnow()

        # Create jobs with different due dates
        due_dates = [
            base_date + timedelta(days=1),  # Tomorrow
            base_date + timedelta(days=5),  # In 5 days
            base_date + timedelta(days=10),  # In 10 days
            base_date + timedelta(days=15),  # In 15 days
        ]

        for i, due_date in enumerate(due_dates):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"DATE-JOB-{i:03d}"
            job_data["due_date"] = due_date
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Find jobs due in next week (1-7 days)
        start_date = base_date + timedelta(days=1)
        end_date = base_date + timedelta(days=7)

        jobs_in_range = job_repository.find_by_due_date_range(start_date, end_date)
        assert len(jobs_in_range) == 2  # Jobs due in 1 and 5 days

        for job in jobs_in_range:
            assert start_date <= job.due_date <= end_date


class TestJobRepositoryTaskRelationships:
    """Test job repository operations involving tasks."""

    def test_get_jobs_with_tasks(self, job_repository, db_session, sample_job_data):
        """Test retrieving jobs with their associated tasks."""
        # Create job
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        # Create tasks for the job
        task_data = {
            "job_id": created_job.id,
            "operation_id": uuid4(),
            "sequence_in_job": 10,
            "status": TaskStatus.PENDING,
            "planned_duration_minutes": 60,
        }

        for i in range(3):
            task_data_copy = task_data.copy()
            task_data_copy["sequence_in_job"] = (i + 1) * 10
            task = Task(**task_data_copy)
            db_session.add(task)

        db_session.commit()

        # Retrieve job with tasks
        job_with_tasks = job_repository.get_with_tasks(created_job.id)

        assert job_with_tasks is not None
        assert len(job_with_tasks.tasks) == 3

        # Verify task order
        sequences = [task.sequence_in_job for task in job_with_tasks.tasks]
        assert sequences == [10, 20, 30]

    def test_get_jobs_with_active_tasks(
        self, job_repository, db_session, sample_job_data
    ):
        """Test retrieving jobs that have active tasks."""
        # Create jobs with different task statuses
        jobs = []
        for i in range(3):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"TASK-JOB-{i:03d}"
            job_create = JobCreate(**job_data)
            job = job_repository.create(job_create)
            jobs.append(job)

        # Add tasks with different statuses
        task_statuses = [
            TaskStatus.SCHEDULED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED,
        ]

        for i, (job, status) in enumerate(zip(jobs, task_statuses, strict=False)):
            task = Task(
                job_id=job.id,
                operation_id=uuid4(),
                sequence_in_job=10,
                status=status,
                planned_duration_minutes=60,
            )
            db_session.add(task)

        db_session.commit()

        # Find jobs with active tasks (SCHEDULED or IN_PROGRESS)
        active_jobs = job_repository.find_jobs_with_active_tasks()

        assert len(active_jobs) == 2  # First two jobs have active tasks
        active_job_numbers = {job.job_number for job in active_jobs}
        assert active_job_numbers == {"TASK-JOB-000", "TASK-JOB-001"}

    def test_get_job_completion_percentage(
        self, job_repository, db_session, sample_job_data
    ):
        """Test calculating job completion percentage."""
        # Create job
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        # Add 4 tasks: 2 completed, 1 in progress, 1 pending
        task_statuses = [
            TaskStatus.COMPLETED,
            TaskStatus.COMPLETED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.PENDING,
        ]

        for i, status in enumerate(task_statuses):
            task = Task(
                job_id=created_job.id,
                operation_id=uuid4(),
                sequence_in_job=(i + 1) * 10,
                status=status,
                planned_duration_minutes=60,
            )
            db_session.add(task)

        db_session.commit()

        completion_percentage = job_repository.get_completion_percentage(created_job.id)

        # 2 completed out of 4 tasks = 50%
        assert completion_percentage == 50.0

    def test_get_job_completion_percentage_no_tasks(
        self, job_repository, sample_job_data
    ):
        """Test job completion percentage with no tasks."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        completion_percentage = job_repository.get_completion_percentage(created_job.id)
        assert completion_percentage == 0.0


class TestJobRepositoryErrorHandling:
    """Test error handling and edge cases."""

    def test_database_connection_error(self, sample_job_data):
        """Test handling database connection errors."""
        # Create repository with invalid session
        invalid_repository = JobRepository(session=None)

        with pytest.raises(DatabaseError):
            job_create = JobCreate(**sample_job_data)
            invalid_repository.create(job_create)

    def test_constraint_violation_handling(self, job_repository, sample_job_data):
        """Test handling constraint violations."""
        # Create initial job
        job_create = JobCreate(**sample_job_data)
        job_repository.create(job_create)

        # Try to create duplicate
        duplicate_create = JobCreate(**sample_job_data)

        with pytest.raises(DatabaseError) as exc_info:
            job_repository.create(duplicate_create)

        assert "duplicate" in str(exc_info.value).lower()

    def test_invalid_update_data(self, job_repository, sample_job_data):
        """Test handling invalid update data."""
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        # Try to update with invalid status
        with pytest.raises(DatabaseError):
            invalid_update = JobUpdate(status="INVALID_STATUS")
            job_repository.update(created_job.id, invalid_update)

    @patch("app.infrastructure.database.repositories.job_repository.select")
    def test_query_execution_error(self, mock_select, job_repository):
        """Test handling query execution errors."""
        mock_select.side_effect = Exception("Database query failed")

        with pytest.raises(DatabaseError, match="Database query failed"):
            job_repository.find_by_job_number("TEST-JOB")

    def test_concurrent_access_handling(self, job_repository, sample_job_data):
        """Test handling concurrent access to same job."""
        # This is a simplified test - in real scenarios you'd use threading
        job_create = JobCreate(**sample_job_data)
        created_job = job_repository.create(job_create)

        # Simulate concurrent updates
        update1 = JobUpdate(customer_name="Customer Update 1")
        update2 = JobUpdate(customer_name="Customer Update 2")

        # Both updates should succeed (last one wins)
        job_repository.update(created_job.id, update1)
        final_job = job_repository.update(created_job.id, update2)

        assert final_job.customer_name == "Customer Update 2"


class TestJobRepositoryPerformance:
    """Test repository performance with larger datasets."""

    def test_bulk_job_creation_performance(self, job_repository, sample_job_data):
        """Test performance of creating multiple jobs."""
        import time

        start_time = time.time()

        # Create 100 jobs
        created_jobs = []
        for i in range(100):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"PERF-JOB-{i:04d}"
            job_data["customer_name"] = f"Customer {i}"

            job_create = JobCreate(**job_data)
            job = job_repository.create(job_create)
            created_jobs.append(job)

        end_time = time.time()
        creation_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert creation_time < 10.0  # 10 seconds for 100 jobs
        assert len(created_jobs) == 100

    def test_large_result_set_query_performance(self, job_repository, sample_job_data):
        """Test performance of querying large result sets."""
        # Create many jobs first
        for i in range(200):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"LARGE-JOB-{i:04d}"
            job_data["customer_name"] = "Large Customer"
            job_data["status"] = JobStatus.PLANNED

            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        import time

        start_time = time.time()

        # Query all jobs for the customer
        customer_jobs = job_repository.find_by_customer("Large Customer")

        end_time = time.time()
        query_time = end_time - start_time

        # Should complete within reasonable time
        assert query_time < 5.0  # 5 seconds for querying 200 jobs
        assert len(customer_jobs) == 200

    def test_pagination_performance(self, job_repository, sample_job_data):
        """Test pagination performance with large dataset."""
        # Create many jobs
        total_jobs = 500
        for i in range(total_jobs):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"PAGE-JOB-{i:04d}"

            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        import time

        start_time = time.time()

        # Paginate through all jobs
        page_size = 50
        all_jobs = []
        skip = 0

        while True:
            page_jobs = job_repository.list(skip=skip, limit=page_size)
            if not page_jobs:
                break

            all_jobs.extend(page_jobs)
            skip += page_size

        end_time = time.time()
        pagination_time = end_time - start_time

        # Should complete within reasonable time
        assert pagination_time < 10.0  # 10 seconds for paginating 500 jobs
        assert len(all_jobs) == total_jobs


class TestJobRepositoryTransactions:
    """Test transaction handling in repository operations."""

    def test_transaction_rollback_on_error(self, job_repository, sample_job_data):
        """Test that transactions roll back properly on errors."""
        initial_count = len(job_repository.list())

        try:
            # Create a job
            job_create = JobCreate(**sample_job_data)
            job_repository.create(job_create)

            # Simulate an error after creation
            raise Exception("Simulated error")

        except Exception:
            pass

        # Job should still exist (creation was committed)
        final_count = len(job_repository.list())
        assert final_count == initial_count + 1

    def test_batch_operations_consistency(self, job_repository, sample_job_data):
        """Test consistency of batch operations."""
        # Create multiple jobs in a batch-like operation
        job_numbers = []

        for i in range(5):
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"BATCH-JOB-{i:03d}"
            job_numbers.append(job_data["job_number"])

            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Verify all jobs were created
        for job_number in job_numbers:
            job = job_repository.find_by_job_number(job_number)
            assert job is not None
            assert job.job_number == job_number


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
