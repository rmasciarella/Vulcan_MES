"""
Integration Tests for Job Repository Implementation

Tests the actual database operations, mapping, and data consistency for job repositories.
These tests use real database transactions and validate data persistence.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.domain.scheduling.entities.job import JobStatus
from app.domain.scheduling.value_objects.enums import PriorityLevel
from app.infrastructure.database.repositories.job_repository import SQLJobRepository
from app.shared.exceptions import ValidationError
from app.tests.database.factories import JobFactory


@pytest.mark.database
@pytest.mark.integration
class TestSQLJobRepositoryIntegration:
    """Integration tests for SQLJobRepository with actual database."""

    @pytest.fixture
    def job_repository(self, db_session: Session):
        """Create job repository with database session."""
        return SQLJobRepository(db_session)

    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return JobFactory.create(
            job_number="INTEGRATION-001",
            customer_name="Integration Test Corp",
            part_number="PART-INT-001",
            quantity=5,
            priority=PriorityLevel.HIGH,
            due_date=datetime.utcnow() + timedelta(days=14),
        )

    async def test_save_and_retrieve_job(self, job_repository, sample_job, db_session):
        """Test saving and retrieving a job from database."""
        # Save job
        saved_job = await job_repository.save(sample_job)
        db_session.commit()

        # Verify saved job
        assert saved_job.id == sample_job.id
        assert saved_job.job_number == sample_job.job_number
        assert saved_job.customer_name == sample_job.customer_name

        # Retrieve job
        retrieved_job = await job_repository.get_by_id(sample_job.id)

        # Verify retrieved job
        assert retrieved_job is not None
        assert retrieved_job.id == sample_job.id
        assert retrieved_job.job_number == sample_job.job_number
        assert retrieved_job.customer_name == sample_job.customer_name
        assert retrieved_job.part_number == sample_job.part_number
        assert retrieved_job.quantity.value == sample_job.quantity.value
        assert retrieved_job.priority == sample_job.priority
        assert retrieved_job.status == sample_job.status
        assert abs((retrieved_job.due_date - sample_job.due_date).total_seconds()) < 1

    async def test_save_job_with_tasks(self, job_repository, db_session):
        """Test saving job with associated tasks."""
        # Create job with tasks
        job = JobFactory.create_with_tasks(task_count=3, job_number="JOB-WITH-TASKS")

        # Save job (tasks should be saved too)
        await job_repository.save(job)
        db_session.commit()

        # Retrieve and verify
        retrieved_job = await job_repository.get_by_id(job.id)

        assert retrieved_job is not None
        assert retrieved_job.task_count == 3
        assert len(retrieved_job.get_all_tasks()) == 3

        # Verify tasks are properly associated
        tasks = retrieved_job.get_all_tasks()
        for task in tasks:
            assert task.job_id == job.id
            assert task.sequence_in_job > 0

    async def test_update_job(self, job_repository, sample_job, db_session):
        """Test updating an existing job."""
        # Save initial job
        await job_repository.save(sample_job)
        db_session.commit()

        # Update job properties
        sample_job.customer_name = "Updated Customer Corp"
        sample_job.priority = PriorityLevel.URGENT
        sample_job.status = JobStatus.RELEASED
        sample_job.notes = "Updated with new requirements"

        # Update in database
        updated_job = await job_repository.update(sample_job)
        db_session.commit()

        # Verify update
        assert updated_job.customer_name == "Updated Customer Corp"
        assert updated_job.priority == PriorityLevel.URGENT
        assert updated_job.status == JobStatus.RELEASED
        assert updated_job.notes == "Updated with new requirements"

        # Retrieve and verify persistence
        retrieved_job = await job_repository.get_by_id(sample_job.id)
        assert retrieved_job.customer_name == "Updated Customer Corp"
        assert retrieved_job.priority == PriorityLevel.URGENT
        assert retrieved_job.status == JobStatus.RELEASED

    async def test_delete_job(self, job_repository, sample_job, db_session):
        """Test deleting a job from database."""
        # Save job
        await job_repository.save(sample_job)
        db_session.commit()

        # Verify job exists
        retrieved_job = await job_repository.get_by_id(sample_job.id)
        assert retrieved_job is not None

        # Delete job
        await job_repository.delete(sample_job.id)
        db_session.commit()

        # Verify job is deleted
        deleted_job = await job_repository.get_by_id(sample_job.id)
        assert deleted_job is None

    async def test_get_nonexistent_job(self, job_repository):
        """Test retrieving non-existent job returns None."""
        nonexistent_id = uuid4()
        job = await job_repository.get_by_id(nonexistent_id)
        assert job is None

    async def test_get_by_job_number(self, job_repository, sample_job, db_session):
        """Test retrieving job by job number."""
        # Save job
        await job_repository.save(sample_job)
        db_session.commit()

        # Retrieve by job number
        retrieved_job = await job_repository.get_by_job_number(sample_job.job_number)

        # Verify
        assert retrieved_job is not None
        assert retrieved_job.id == sample_job.id
        assert retrieved_job.job_number == sample_job.job_number

    async def test_get_by_nonexistent_job_number(self, job_repository):
        """Test retrieving job by non-existent job number returns None."""
        job = await job_repository.get_by_job_number("NONEXISTENT-001")
        assert job is None

    async def test_find_jobs_by_status(self, job_repository, db_session):
        """Test finding jobs filtered by status."""
        # Create jobs with different statuses
        planned_job = JobFactory.create(
            job_number="PLANNED-001", status=JobStatus.PLANNED
        )
        released_job = JobFactory.create(
            job_number="RELEASED-001", status=JobStatus.RELEASED
        )
        completed_job = JobFactory.create(
            job_number="COMPLETED-001", status=JobStatus.COMPLETED
        )

        # Save all jobs
        await job_repository.save(planned_job)
        await job_repository.save(released_job)
        await job_repository.save(completed_job)
        db_session.commit()

        # Find planned jobs
        planned_jobs = await job_repository.find_by_status(JobStatus.PLANNED)
        planned_numbers = [job.job_number for job in planned_jobs]
        assert "PLANNED-001" in planned_numbers
        assert "RELEASED-001" not in planned_numbers

        # Find released jobs
        released_jobs = await job_repository.find_by_status(JobStatus.RELEASED)
        released_numbers = [job.job_number for job in released_jobs]
        assert "RELEASED-001" in released_numbers
        assert "PLANNED-001" not in released_numbers

    async def test_find_jobs_by_priority(self, job_repository, db_session):
        """Test finding jobs filtered by priority."""
        # Create jobs with different priorities
        low_job = JobFactory.create(job_number="LOW-001", priority=PriorityLevel.LOW)
        high_job = JobFactory.create(job_number="HIGH-001", priority=PriorityLevel.HIGH)
        urgent_job = JobFactory.create(
            job_number="URGENT-001", priority=PriorityLevel.URGENT
        )

        # Save all jobs
        await job_repository.save(low_job)
        await job_repository.save(high_job)
        await job_repository.save(urgent_job)
        db_session.commit()

        # Find high priority jobs
        high_jobs = await job_repository.find_by_priority(PriorityLevel.HIGH)
        high_numbers = [job.job_number for job in high_jobs]
        assert "HIGH-001" in high_numbers
        assert "LOW-001" not in high_numbers

        # Find urgent priority jobs
        urgent_jobs = await job_repository.find_by_priority(PriorityLevel.URGENT)
        urgent_numbers = [job.job_number for job in urgent_jobs]
        assert "URGENT-001" in urgent_numbers
        assert "HIGH-001" not in urgent_numbers

    async def test_find_overdue_jobs(self, job_repository, db_session):
        """Test finding overdue jobs."""
        now = datetime.utcnow()

        # Create jobs with different due dates
        future_job = JobFactory.create(
            job_number="FUTURE-001", due_date=now + timedelta(days=7)
        )
        overdue_job = JobFactory.create(
            job_number="OVERDUE-001", due_date=now - timedelta(days=2)
        )
        completed_overdue_job = JobFactory.create(
            job_number="COMPLETED-OVERDUE-001",
            due_date=now - timedelta(days=1),
            status=JobStatus.COMPLETED,
        )

        # Save all jobs
        await job_repository.save(future_job)
        await job_repository.save(overdue_job)
        await job_repository.save(completed_overdue_job)
        db_session.commit()

        # Find overdue jobs
        overdue_jobs = await job_repository.find_overdue_jobs()
        overdue_numbers = [job.job_number for job in overdue_jobs]

        assert "OVERDUE-001" in overdue_numbers
        assert "FUTURE-001" not in overdue_numbers
        assert (
            "COMPLETED-OVERDUE-001" not in overdue_numbers
        )  # Completed jobs not overdue

    async def test_find_jobs_by_customer(self, job_repository, db_session):
        """Test finding jobs by customer name."""
        # Create jobs for different customers
        acme_job1 = JobFactory.create(job_number="ACME-001", customer_name="Acme Corp")
        acme_job2 = JobFactory.create(job_number="ACME-002", customer_name="Acme Corp")
        other_job = JobFactory.create(
            job_number="OTHER-001", customer_name="Other Company"
        )

        # Save all jobs
        await job_repository.save(acme_job1)
        await job_repository.save(acme_job2)
        await job_repository.save(other_job)
        db_session.commit()

        # Find Acme jobs
        acme_jobs = await job_repository.find_by_customer("Acme Corp")
        acme_numbers = [job.job_number for job in acme_jobs]

        assert len(acme_jobs) == 2
        assert "ACME-001" in acme_numbers
        assert "ACME-002" in acme_numbers
        assert "OTHER-001" not in acme_numbers

    async def test_get_jobs_due_within_days(self, job_repository, db_session):
        """Test getting jobs due within specified number of days."""
        now = datetime.utcnow()

        # Create jobs with different due dates
        due_tomorrow = JobFactory.create(
            job_number="TOMORROW-001", due_date=now + timedelta(days=1)
        )
        due_next_week = JobFactory.create(
            job_number="NEXT-WEEK-001", due_date=now + timedelta(days=7)
        )
        due_next_month = JobFactory.create(
            job_number="NEXT-MONTH-001", due_date=now + timedelta(days=30)
        )

        # Save all jobs
        await job_repository.save(due_tomorrow)
        await job_repository.save(due_next_week)
        await job_repository.save(due_next_month)
        db_session.commit()

        # Find jobs due within 3 days
        jobs_due_soon = await job_repository.get_jobs_due_within_days(3)
        due_numbers = [job.job_number for job in jobs_due_soon]

        assert "TOMORROW-001" in due_numbers
        assert "NEXT-WEEK-001" not in due_numbers
        assert "NEXT-MONTH-001" not in due_numbers

        # Find jobs due within 14 days
        jobs_due_fortnight = await job_repository.get_jobs_due_within_days(14)
        fortnight_numbers = [job.job_number for job in jobs_due_fortnight]

        assert "TOMORROW-001" in fortnight_numbers
        assert "NEXT-WEEK-001" in fortnight_numbers
        assert "NEXT-MONTH-001" not in fortnight_numbers

    async def test_get_active_jobs(self, job_repository, db_session):
        """Test getting active jobs (non-completed, non-cancelled)."""
        # Create jobs in various states
        planned_job = JobFactory.create(
            job_number="ACTIVE-PLANNED-001", status=JobStatus.PLANNED
        )
        released_job = JobFactory.create(
            job_number="ACTIVE-RELEASED-001", status=JobStatus.RELEASED
        )
        in_progress_job = JobFactory.create(
            job_number="ACTIVE-PROGRESS-001", status=JobStatus.IN_PROGRESS
        )
        completed_job = JobFactory.create(
            job_number="COMPLETED-001", status=JobStatus.COMPLETED
        )
        cancelled_job = JobFactory.create(
            job_number="CANCELLED-001", status=JobStatus.CANCELLED
        )

        # Save all jobs
        jobs = [
            planned_job,
            released_job,
            in_progress_job,
            completed_job,
            cancelled_job,
        ]
        for job in jobs:
            await job_repository.save(job)
        db_session.commit()

        # Get active jobs
        active_jobs = await job_repository.get_active_jobs()
        active_numbers = [job.job_number for job in active_jobs]

        # Active jobs should include planned, released, in progress
        assert "ACTIVE-PLANNED-001" in active_numbers
        assert "ACTIVE-RELEASED-001" in active_numbers
        assert "ACTIVE-PROGRESS-001" in active_numbers

        # Should not include completed or cancelled
        assert "COMPLETED-001" not in active_numbers
        assert "CANCELLED-001" not in active_numbers

    async def test_bulk_save_jobs(self, job_repository, db_session):
        """Test bulk saving multiple jobs."""
        # Create multiple jobs
        jobs = [JobFactory.create(job_number=f"BULK-{i:03d}") for i in range(1, 6)]

        # Bulk save
        saved_jobs = await job_repository.save_batch(jobs)
        db_session.commit()

        # Verify all jobs were saved
        assert len(saved_jobs) == 5
        for i, job in enumerate(saved_jobs):
            assert job.job_number == f"BULK-{i+1:03d}"

        # Verify all jobs can be retrieved
        for job in saved_jobs:
            retrieved_job = await job_repository.get_by_id(job.id)
            assert retrieved_job is not None
            assert retrieved_job.job_number == job.job_number

    async def test_job_statistics(self, job_repository, db_session):
        """Test getting job statistics."""
        # Create jobs in various states
        statuses = [
            JobStatus.PLANNED,
            JobStatus.PLANNED,
            JobStatus.RELEASED,
            JobStatus.RELEASED,
            JobStatus.RELEASED,
            JobStatus.IN_PROGRESS,
            JobStatus.COMPLETED,
            JobStatus.COMPLETED,
        ]

        for i, status in enumerate(statuses):
            job = JobFactory.create(job_number=f"STATS-{i+1:03d}", status=status)
            await job_repository.save(job)

        db_session.commit()

        # Get statistics
        stats = await job_repository.get_job_statistics()

        # Verify statistics
        assert stats["total_jobs"] >= len(statuses)
        assert stats["planned_jobs"] >= 2
        assert stats["released_jobs"] >= 3
        assert stats["in_progress_jobs"] >= 1
        assert stats["completed_jobs"] >= 2

    async def test_duplicate_job_number_constraint(self, job_repository, db_session):
        """Test that duplicate job numbers are prevented."""
        # Create first job
        job1 = JobFactory.create(job_number="DUPLICATE-001")
        await job_repository.save(job1)
        db_session.commit()

        # Try to create second job with same number
        job2 = JobFactory.create(job_number="DUPLICATE-001")  # Same number

        # This should raise an integrity error
        with pytest.raises((IntegrityError, ValidationError)):
            await job_repository.save(job2)
            db_session.commit()

    async def test_cascade_delete_with_tasks(self, job_repository, db_session):
        """Test that deleting job cascades to delete associated tasks."""
        # Create job with tasks
        job = JobFactory.create_with_tasks(
            task_count=3, job_number="CASCADE-DELETE-001"
        )

        await job_repository.save(job)
        db_session.commit()

        # Verify job and tasks exist
        retrieved_job = await job_repository.get_by_id(job.id)
        assert retrieved_job is not None
        assert retrieved_job.task_count == 3

        # Delete job
        await job_repository.delete(job.id)
        db_session.commit()

        # Verify job is deleted
        deleted_job = await job_repository.get_by_id(job.id)
        assert deleted_job is None

        # Tasks should also be deleted due to cascade
        # (This would be verified by checking task repository if available)

    async def test_job_search_with_filters(self, job_repository, db_session):
        """Test searching jobs with multiple filters."""
        now = datetime.utcnow()

        # Create test jobs
        target_job = JobFactory.create(
            job_number="SEARCH-TARGET-001",
            customer_name="Target Customer",
            priority=PriorityLevel.HIGH,
            status=JobStatus.RELEASED,
            due_date=now + timedelta(days=5),
        )

        other_job = JobFactory.create(
            job_number="SEARCH-OTHER-001",
            customer_name="Other Customer",
            priority=PriorityLevel.LOW,
            status=JobStatus.PLANNED,
            due_date=now + timedelta(days=15),
        )

        await job_repository.save(target_job)
        await job_repository.save(other_job)
        db_session.commit()

        # Search with multiple filters
        search_filters = {
            "customer_name": "Target Customer",
            "priority": PriorityLevel.HIGH,
            "status": JobStatus.RELEASED,
        }

        search_results = await job_repository.search_jobs(search_filters)
        search_numbers = [job.job_number for job in search_results]

        assert "SEARCH-TARGET-001" in search_numbers
        assert "SEARCH-OTHER-001" not in search_numbers

    async def test_job_update_optimistic_locking(self, job_repository, db_session):
        """Test optimistic locking for concurrent job updates."""
        # Create and save job
        job = JobFactory.create(job_number="LOCKING-001")
        await job_repository.save(job)
        db_session.commit()

        # Get two instances of the same job
        job1 = await job_repository.get_by_id(job.id)
        job2 = await job_repository.get_by_id(job.id)

        # Update first instance
        job1.customer_name = "First Update"
        await job_repository.update(job1)
        db_session.commit()

        # Try to update second instance (should detect conflict)
        job2.customer_name = "Second Update"

        # This behavior depends on optimistic locking implementation
        # The repository might raise a conflict error or overwrite
        # The exact behavior should be documented and tested according to requirements

    async def test_job_pagination(self, job_repository, db_session):
        """Test job pagination functionality."""
        # Create many jobs
        total_jobs = 25
        jobs = [
            JobFactory.create(job_number=f"PAGE-{i+1:03d}") for i in range(total_jobs)
        ]

        for job in jobs:
            await job_repository.save(job)
        db_session.commit()

        # Test pagination
        page_size = 10
        page1 = await job_repository.get_jobs_paginated(page=1, page_size=page_size)
        page2 = await job_repository.get_jobs_paginated(page=2, page_size=page_size)
        page3 = await job_repository.get_jobs_paginated(page=3, page_size=page_size)

        # Verify page contents
        assert len(page1) == page_size
        assert len(page2) == page_size
        assert len(page3) == 5  # Remaining jobs

        # Verify no overlap between pages
        page1_numbers = {job.job_number for job in page1}
        page2_numbers = {job.job_number for job in page2}
        page3_numbers = {job.job_number for job in page3}

        assert len(page1_numbers.intersection(page2_numbers)) == 0
        assert len(page1_numbers.intersection(page3_numbers)) == 0
        assert len(page2_numbers.intersection(page3_numbers)) == 0

    async def test_job_sorting(self, job_repository, db_session):
        """Test job sorting by different fields."""
        now = datetime.utcnow()

        # Create jobs with different properties for sorting
        jobs = [
            JobFactory.create(
                job_number="SORT-C-001",
                priority=PriorityLevel.LOW,
                due_date=now + timedelta(days=10),
                created_at=now - timedelta(hours=3),
            ),
            JobFactory.create(
                job_number="SORT-A-001",
                priority=PriorityLevel.HIGH,
                due_date=now + timedelta(days=5),
                created_at=now - timedelta(hours=1),
            ),
            JobFactory.create(
                job_number="SORT-B-001",
                priority=PriorityLevel.NORMAL,
                due_date=now + timedelta(days=15),
                created_at=now - timedelta(hours=2),
            ),
        ]

        for job in jobs:
            await job_repository.save(job)
        db_session.commit()

        # Test sorting by job number
        jobs_by_number = await job_repository.get_jobs_sorted_by("job_number")
        numbers = [job.job_number for job in jobs_by_number]
        # Should include our test jobs in order
        test_jobs = [n for n in numbers if n.startswith("SORT-")]
        assert test_jobs == ["SORT-A-001", "SORT-B-001", "SORT-C-001"]

        # Test sorting by due date
        jobs_by_due_date = await job_repository.get_jobs_sorted_by("due_date")
        # Should be ordered by due date (earliest first)
        # Verify our test jobs are in correct order
        test_jobs_by_due = []
        for job in jobs_by_due_date:
            if job.job_number.startswith("SORT-"):
                test_jobs_by_due.append(job.job_number)

        expected_order = ["SORT-A-001", "SORT-C-001", "SORT-B-001"]  # By due date
        assert test_jobs_by_due == expected_order


@pytest.mark.performance
class TestJobRepositoryPerformance:
    """Performance tests for job repository operations."""

    @pytest.fixture
    def job_repository(self, db_session: Session):
        """Create job repository with database session."""
        return SQLJobRepository(db_session)

    async def test_bulk_insert_performance(
        self, job_repository, db_session, performance_monitor
    ):
        """Test performance of bulk job insertion."""
        # Create many jobs
        job_count = 100
        jobs = [
            JobFactory.create(job_number=f"PERF-{i+1:04d}") for i in range(job_count)
        ]

        # Time the bulk save operation
        with performance_monitor.time_operation("bulk_save_100_jobs"):
            await job_repository.save_batch(jobs)
            db_session.commit()

        # Verify all jobs were saved
        stats = performance_monitor.get_stats()
        assert stats["total_operations"] == 1
        assert stats["error_count"] == 0

        # Performance assertion (adjust based on requirements)
        assert stats["max_time"] < 10.0  # Should complete within 10 seconds

    async def test_search_performance_with_indexes(
        self, job_repository, db_session, performance_monitor
    ):
        """Test search performance with indexed fields."""
        # Create many jobs for performance testing
        customers = ["Customer A", "Customer B", "Customer C"]
        priorities = list(PriorityLevel)

        jobs = []
        for i in range(200):
            job = JobFactory.create(
                job_number=f"PERF-SEARCH-{i+1:04d}",
                customer_name=customers[i % len(customers)],
                priority=priorities[i % len(priorities)],
            )
            jobs.append(job)

        # Bulk save
        await job_repository.save_batch(jobs)
        db_session.commit()

        # Test search performance
        with performance_monitor.time_operation("search_by_customer"):
            customer_jobs = await job_repository.find_by_customer("Customer A")

        with performance_monitor.time_operation("search_by_priority"):
            priority_jobs = await job_repository.find_by_priority(PriorityLevel.HIGH)

        # Verify results
        assert len(customer_jobs) > 0
        assert len(priority_jobs) > 0

        # Check performance
        stats = performance_monitor.get_stats()
        assert stats["max_time"] < 5.0  # Searches should be fast with indexes

    async def test_concurrent_access_performance(
        self, job_repository, db_session, performance_monitor
    ):
        """Test performance under concurrent access patterns."""
        import asyncio

        # Create initial jobs
        jobs = [
            JobFactory.create(job_number=f"CONCURRENT-{i+1:03d}") for i in range(20)
        ]

        await job_repository.save_batch(jobs)
        db_session.commit()

        async def read_jobs():
            """Simulate concurrent read operations."""
            for job in jobs[:5]:  # Read first 5 jobs
                await job_repository.get_by_id(job.id)

        async def update_jobs():
            """Simulate concurrent update operations."""
            for job in jobs[5:10]:  # Update next 5 jobs
                job.notes = f"Updated at {datetime.utcnow()}"
                await job_repository.update(job)

        # Run concurrent operations
        with performance_monitor.time_operation("concurrent_operations"):
            await asyncio.gather(
                read_jobs(),
                update_jobs(),
                read_jobs(),  # Another read batch
            )
            db_session.commit()

        # Verify performance
        stats = performance_monitor.get_stats()
        assert stats["error_count"] == 0  # No errors during concurrent access


@pytest.mark.slow
class TestJobRepositoryStressTests:
    """Stress tests for job repository with large datasets."""

    @pytest.fixture
    def job_repository(self, clean_db: Session):
        """Create job repository with clean database."""
        return SQLJobRepository(clean_db)

    async def test_large_dataset_operations(self, job_repository, clean_db):
        """Test repository operations with large dataset."""
        # Create a large number of jobs
        large_job_count = 1000
        batch_size = 100

        total_saved = 0
        for batch_start in range(0, large_job_count, batch_size):
            batch_jobs = [
                JobFactory.create(job_number=f"LARGE-{i+1:05d}")
                for i in range(
                    batch_start, min(batch_start + batch_size, large_job_count)
                )
            ]

            await job_repository.save_batch(batch_jobs)
            total_saved += len(batch_jobs)

        clean_db.commit()

        # Verify total count
        stats = await job_repository.get_job_statistics()
        assert stats["total_jobs"] >= large_job_count

        # Test search performance with large dataset
        await job_repository.find_by_customer("Large Test Customer")
        # Search should still be reasonably fast

        # Test pagination with large dataset
        first_page = await job_repository.get_jobs_paginated(page=1, page_size=50)
        assert len(first_page) == 50

        last_page_num = (large_job_count // 50) + (1 if large_job_count % 50 else 0)
        last_page = await job_repository.get_jobs_paginated(
            page=last_page_num, page_size=50
        )
        assert len(last_page) > 0

    async def test_memory_usage_with_large_results(self, job_repository, clean_db):
        """Test memory usage when retrieving large result sets."""
        # This test would ideally monitor memory usage
        # For now, we test that large queries complete without errors

        # Create jobs
        job_count = 500
        jobs = [
            JobFactory.create(
                job_number=f"MEMORY-{i+1:04d}",
                customer_name="Memory Test Customer",  # All same customer
            )
            for i in range(job_count)
        ]

        await job_repository.save_batch(jobs)
        clean_db.commit()

        # Retrieve large result set
        all_customer_jobs = await job_repository.find_by_customer(
            "Memory Test Customer"
        )
        assert len(all_customer_jobs) == job_count

        # Test that we can iterate through all results
        job_numbers = []
        for job in all_customer_jobs:
            job_numbers.append(job.job_number)

        assert len(job_numbers) == job_count
        assert len(set(job_numbers)) == job_count  # All unique


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
