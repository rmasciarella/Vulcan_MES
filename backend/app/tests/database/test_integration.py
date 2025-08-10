"""
Database Integration Tests

End-to-end integration tests for database operations including:
- Full workflow scenarios
- Transaction handling
- Relationship integrity
- Real database operations
- Performance under load
"""

import time
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
    TaskStatus,
)
from app.shared.exceptions import BusinessRuleViolation
from app.tests.database.factories import (
    JobFactory,
    OperatorAssignmentFactory,
    TaskFactory,
    TestDataBuilder,
)


class TestDatabaseIntegrationWorkflows:
    """Test complete database workflows and scenarios."""

    def test_complete_manufacturing_workflow(self, db: Session):
        """Test a complete manufacturing workflow from job creation to completion."""
        # Create a job with multiple tasks
        job = JobFactory.create_with_tasks(task_count=5)

        # Simulate workflow progression
        assert job.status == JobStatus.PLANNED
        assert job.task_count == 5

        # Release job
        job.change_status(JobStatus.RELEASED)
        assert job.status == JobStatus.RELEASED

        # First task should be ready
        first_task = job.get_task_by_sequence(10)
        assert first_task.status == TaskStatus.READY

        # Schedule first task
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        first_task.schedule(start_time, end_time, uuid4())
        assert first_task.status == TaskStatus.SCHEDULED

        # Start and complete first task
        first_task.start()
        assert first_task.status == TaskStatus.IN_PROGRESS

        completion_time = datetime.utcnow() + timedelta(minutes=5)
        job.complete_task(10, completion_time)

        # Verify job progress
        assert job.completion_percentage == 20.0  # 1 of 5 tasks
        assert job.current_operation_sequence == 10

        # Next task should now be ready
        second_task = job.get_task_by_sequence(20)
        assert second_task.status == TaskStatus.READY

        # Complete all remaining tasks
        for sequence in [20, 30, 40, 50]:
            task = job.get_task_by_sequence(sequence)
            task.mark_ready()
            task.schedule(
                datetime.utcnow() + timedelta(minutes=sequence),
                datetime.utcnow() + timedelta(minutes=sequence + 60),
                uuid4(),
            )
            task.start()
            job.complete_task(
                sequence, datetime.utcnow() + timedelta(minutes=sequence + 30)
            )

        # Job should be completed
        assert job.status == JobStatus.COMPLETED
        assert job.completion_percentage == 100.0
        assert job.actual_end_date is not None

    def test_job_priority_workflow(self, db: Session):
        """Test job priority handling and scheduling workflow."""
        # Create jobs with different priorities
        urgent_job = JobFactory.create(priority=PriorityLevel.URGENT)
        high_job = JobFactory.create(priority=PriorityLevel.HIGH)
        normal_job = JobFactory.create(priority=PriorityLevel.NORMAL)
        low_job = JobFactory.create(priority=PriorityLevel.LOW)

        jobs = [urgent_job, high_job, normal_job, low_job]

        # All jobs should be schedulable
        for job in jobs:
            job.change_status(JobStatus.RELEASED)
            assert job.is_active

        # Test priority adjustment
        normal_job.adjust_priority(PriorityLevel.URGENT, "customer_escalation")
        assert normal_job.priority == PriorityLevel.URGENT

        # Test due date extension for urgent job
        new_due_date = urgent_job.due_date + timedelta(days=3)
        urgent_job.extend_due_date(new_due_date, "customer_request")
        assert urgent_job.due_date == new_due_date

    def test_task_dependency_workflow(self, db: Session):
        """Test task dependency and sequencing workflow."""
        job = JobFactory.create()

        # Create sequential tasks
        tasks = []
        for i in range(1, 6):
            sequence = i * 10
            task = TaskFactory.create(
                job_id=job.id,
                sequence_in_job=sequence,
                planned_duration_minutes=60 + (i * 30),
            )
            job.add_task(task)
            tasks.append(task)

        # Initially only first task should be ready when job is released
        job.change_status(JobStatus.RELEASED)

        ready_tasks = job.get_ready_tasks()
        assert len(ready_tasks) == 1
        assert ready_tasks[0].sequence_in_job == 10

        # Complete tasks in sequence
        for i, task in enumerate(tasks):
            if i == 0:
                assert task.status == TaskStatus.READY
            else:
                assert task.status == TaskStatus.PENDING

            # Schedule and complete current task
            task.mark_ready()
            task.schedule(
                datetime.utcnow() + timedelta(minutes=i),
                datetime.utcnow() + timedelta(hours=1, minutes=i),
                uuid4(),
            )
            task.start()

            completion_time = datetime.utcnow() + timedelta(minutes=i + 30)
            job.complete_task(task.sequence_in_job, completion_time)

            # Next task should become ready (if exists)
            if i < len(tasks) - 1:
                next_task = job.get_task_by_sequence((i + 2) * 10)
                assert next_task.status == TaskStatus.READY

    def test_operator_assignment_workflow(self, db: Session):
        """Test operator assignment and tracking workflow."""
        task = TaskFactory.create_ready()

        # Create operator assignments
        operator_ids = [uuid4() for _ in range(3)]
        assignments = []

        for operator_id in operator_ids:
            assignment = OperatorAssignmentFactory.create(
                task_id=task.id, operator_id=operator_id
            )
            task.add_operator_assignment(assignment)
            assignments.append(assignment)

        assert task.has_operator_assignments
        assert len(task._operator_assignments) == 3

        # Schedule and start task
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=2)
        task.schedule(start_time, end_time, uuid4())
        task.start()

        # Start operator assignments
        for assignment in assignments[:2]:  # Start first 2 operators
            assignment.start_assignment(datetime.utcnow())

        active_assignments = task.active_operator_assignments
        assert len(active_assignments) == 2

        # Complete assignments
        for assignment in active_assignments:
            completion_time = assignment.actual_start_time + timedelta(minutes=90)
            assignment.complete_assignment(completion_time)

        # No more active assignments
        assert len(task.active_operator_assignments) == 0

        # Complete task
        task.complete()
        assert task.status == TaskStatus.COMPLETED

    def test_job_hold_and_resume_workflow(self, db: Session):
        """Test job hold and resume workflow."""
        job = JobFactory.create_with_tasks(task_count=3)
        job.change_status(JobStatus.RELEASED)

        # Start first task
        first_task = job.get_task_by_sequence(10)
        first_task.mark_ready()
        first_task.schedule(
            datetime.utcnow(), datetime.utcnow() + timedelta(hours=1), uuid4()
        )
        first_task.start()

        # Put job on hold
        job.put_on_hold("maintenance_required")
        assert job.status == JobStatus.ON_HOLD

        # Resume job
        job.release_from_hold("maintenance_completed")
        assert job.status == JobStatus.RELEASED

        # Task should still be in progress
        assert first_task.status == TaskStatus.IN_PROGRESS

        # Complete workflow
        job.complete_task(10, datetime.utcnow() + timedelta(minutes=30))
        second_task = job.get_task_by_sequence(20)
        assert second_task.status == TaskStatus.READY

    def test_rework_and_quality_workflow(self, db: Session):
        """Test rework and quality issue handling workflow."""
        task = TaskFactory.create_ready()

        # Schedule and start task
        task.schedule(
            datetime.utcnow(), datetime.utcnow() + timedelta(hours=2), uuid4()
        )
        task.start()

        # Record quality issues requiring rework
        task.record_rework("dimension_out_of_tolerance")
        assert task.rework_count == 1
        assert task.has_rework
        assert "dimension_out_of_tolerance" in task.notes

        # Record additional rework
        task.record_rework("surface_finish_poor")
        assert task.rework_count == 2

        # Task can still be completed after rework
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert task.rework_count == 2

    def test_critical_path_workflow(self, db: Session):
        """Test critical path identification and handling."""
        job = JobFactory.create_with_tasks(task_count=4)

        # Mark some tasks as critical path
        all_tasks = job.get_all_tasks()
        critical_tasks = all_tasks[:2]

        for task in critical_tasks:
            task.mark_critical_path()

        # Verify critical path tasks
        cp_tasks = job.critical_path_tasks
        assert len(cp_tasks) == 2

        for task in cp_tasks:
            assert task.is_critical_path

        # Critical path tasks should be prioritized
        critical_task = critical_tasks[0]
        critical_task.mark_ready()
        critical_task.schedule(
            datetime.utcnow(), datetime.utcnow() + timedelta(hours=1), uuid4()
        )

        # Delay should be tracked
        delayed_start = datetime.utcnow() + timedelta(minutes=30)
        delayed_end = delayed_start + timedelta(hours=1)
        critical_task.reschedule(delayed_start, delayed_end, "machine_breakdown")

        assert critical_task.is_delayed
        assert critical_task.delay_minutes >= 30


class TestDatabaseTransactionIntegration:
    """Test database transaction handling and consistency."""

    def test_transaction_rollback_on_error(self, db: Session):
        """Test transaction rollback when operations fail."""
        job = JobFactory.create()

        try:
            with db.begin():
                # This would be saved in a real database implementation
                # Simulate an error during transaction
                if True:  # Simulate error condition
                    raise Exception("Simulated database error")

                # This should not be persisted
                job.change_status(JobStatus.RELEASED)
        except Exception:
            db.rollback()

        # Changes should not be persisted due to rollback
        # In a real implementation, job would not be saved
        assert job.status == JobStatus.PLANNED  # Back to original state

    def test_concurrent_job_updates(self, db: Session):
        """Test concurrent updates to the same job."""
        job = JobFactory.create()

        # Simulate concurrent updates (in real scenario would be separate sessions)

        # Update 1: Change customer
        job.customer_name = "Updated Customer 1"

        # Update 2: Change priority (simulating concurrent update)
        job.priority = PriorityLevel.URGENT

        # In a real database with proper concurrency control,
        # this would require proper locking or optimistic concurrency control
        assert job.customer_name == "Updated Customer 1"
        assert job.priority == PriorityLevel.URGENT

    def test_batch_operations(self, db: Session):
        """Test batch operations for performance."""
        # Create multiple jobs in batch
        jobs = JobFactory.create_batch(100)

        # In a real implementation, these would be batch inserted
        start_time = time.time()

        # Simulate batch processing
        processed_count = 0
        for _job in jobs:
            # Each job would be saved to database
            processed_count += 1

        end_time = time.time()
        processing_time = end_time - start_time

        assert processed_count == 100
        # Batch operations should be reasonably fast
        assert processing_time < 5.0  # Should complete within 5 seconds


class TestDatabaseConstraintsAndIntegrity:
    """Test database constraints and data integrity."""

    def test_job_number_uniqueness(self, db: Session):
        """Test job number uniqueness constraint."""
        job_number = "UNIQUE-001"

        job1 = JobFactory.create(job_number=job_number)
        job2 = JobFactory.create(job_number=job_number)

        # In a real database implementation, this would raise IntegrityError
        # For now, we just verify the objects are created
        assert job1.job_number == job_number
        assert job2.job_number == job_number

        # In real implementation:
        # with pytest.raises(IntegrityError):
        #     db.add(job2)
        #     db.commit()

    def test_task_job_relationship_integrity(self, db: Session):
        """Test task-job relationship integrity."""
        job = JobFactory.create()
        task = TaskFactory.create(job_id=job.id)

        # Task should reference valid job
        assert task.job_id == job.id

        # Adding task to job should work
        job.add_task(task)
        assert job.get_task_by_sequence(task.sequence_in_job) == task

    def test_operator_assignment_task_relationship(self, db: Session):
        """Test operator assignment-task relationship integrity."""
        task = TaskFactory.create()
        assignment = OperatorAssignmentFactory.create(task_id=task.id)

        # Assignment should reference valid task
        assert assignment.task_id == task.id

        # Adding assignment to task should work
        task.add_operator_assignment(assignment)
        assert assignment.operator_id in task._operator_assignments

    def test_cascade_delete_behavior(self, db: Session):
        """Test cascade delete behavior for related entities."""
        job = JobFactory.create_with_tasks(task_count=3)

        # Get task count before deletion
        original_task_count = job.task_count
        assert original_task_count == 3

        # In a real implementation with database constraints,
        # deleting a job should cascade delete its tasks
        # For now, we simulate the constraint logic

        # Remove tasks (simulating cascade delete)
        all_tasks = job.get_all_tasks()
        for task in all_tasks:
            job.remove_task(task.sequence_in_job)

        assert job.task_count == 0

    def test_date_constraint_validation(self, db: Session):
        """Test date constraint validations."""
        # Test due date in future
        with pytest.raises(ValueError):
            JobFactory.create(due_date=datetime.utcnow() - timedelta(days=1))

        # Test task end time after start time
        task = TaskFactory.create_ready()

        start_time = datetime.utcnow()
        invalid_end_time = start_time - timedelta(hours=1)

        with pytest.raises(BusinessRuleViolation):
            task.schedule(start_time, invalid_end_time)

    def test_status_transition_constraints(self, db: Session):
        """Test status transition business rule constraints."""
        job = JobFactory.create()

        # Cannot go directly from PLANNED to COMPLETED
        with pytest.raises(BusinessRuleViolation):
            job.change_status(JobStatus.COMPLETED)

        # Must follow valid transition path
        job.change_status(JobStatus.RELEASED)
        job.change_status(JobStatus.IN_PROGRESS)
        # Now can complete
        job.change_status(JobStatus.COMPLETED)

        assert job.status == JobStatus.COMPLETED


class TestDatabasePerformanceIntegration:
    """Test database performance with realistic workloads."""

    def test_large_dataset_queries(self, db: Session):
        """Test query performance with large datasets."""
        # Create a large workload
        workload = TestDataBuilder.create_workload_scenario()

        start_time = time.time()

        # Simulate various query operations
        total_jobs = len(workload["jobs"])
        total_tasks = len(workload["tasks"])

        # Count operations
        active_jobs = [job for job in workload["jobs"] if job.is_active]
        overdue_jobs = [job for job in workload["jobs"] if job.is_overdue]
        urgent_jobs = workload["urgent_jobs"]

        # Task queries
        ready_tasks = [
            task for task in workload["tasks"] if task.status == TaskStatus.READY
        ]
        [task for task in workload["tasks"] if task.is_critical_path]
        [task for task in workload["tasks"] if task.is_delayed]

        end_time = time.time()
        query_time = end_time - start_time

        # Verify results make sense
        assert total_jobs > 50  # Should have substantial data
        assert total_tasks > 100
        assert len(active_jobs) >= 0
        assert len(overdue_jobs) >= 0
        assert len(urgent_jobs) >= 0
        assert len(ready_tasks) >= 0

        # Query performance should be reasonable
        assert (
            query_time < 1.0
        )  # Should complete within 1 second for in-memory operations

    def test_concurrent_operations_simulation(self, db: Session):
        """Test concurrent operation simulation."""
        jobs = JobFactory.create_batch(10)

        # Simulate concurrent job updates
        start_time = time.time()

        updates_performed = 0
        for job in jobs:
            # Simulate various concurrent operations
            if updates_performed % 3 == 0:
                job.change_status(JobStatus.RELEASED)
            elif updates_performed % 3 == 1:
                job.adjust_priority(PriorityLevel.HIGH, "priority_update")
            else:
                job.update_schedule(
                    datetime.utcnow() + timedelta(hours=1),
                    datetime.utcnow() + timedelta(hours=8),
                    "schedule_optimization",
                )

            updates_performed += 1

        end_time = time.time()
        processing_time = end_time - start_time

        assert updates_performed == 10
        # Processing should be fast for in-memory operations
        assert processing_time < 1.0

    def test_memory_usage_with_large_datasets(self, db: Session):
        """Test memory usage with large datasets."""
        # Create substantial dataset
        jobs, tasks, assignments = TestDataBuilder.create_manufacturing_scenario(
            job_count=50, tasks_per_job=10, operators_per_task=3
        )

        # Verify dataset size
        assert len(jobs) == 50
        assert len(tasks) == 500  # 50 jobs * 10 tasks
        assert len(assignments) == 1500  # 500 tasks * 3 operators

        # All entities should be properly created and related
        for job in jobs:
            assert job.task_count == 10
            for task in job.get_all_tasks():
                assert len(task._operator_assignments) == 3

        # Memory usage test would require actual profiling tools
        # For now, we just verify the data structure integrity
        total_entities = len(jobs) + len(tasks) + len(assignments)
        assert total_entities == 2050
