"""
SQLModel Entity Tests

Tests for SQLModel database models including validation, relationships,
and database constraints for Job, Task, and related entities.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import OperatorAssignment, Task
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    PriorityLevel,
    TaskStatus,
)
from app.shared.exceptions import BusinessRuleViolation


class TestJobModelValidation:
    """Test Job entity validation and business rules."""

    def test_job_creation_with_valid_data(self):
        """Test creating a job with valid data."""
        due_date = datetime.utcnow() + timedelta(days=7)

        job = Job.create(
            job_number="J2024-001",
            due_date=due_date,
            customer_name="Test Customer",
            part_number="PART-001",
            quantity=10,
            priority=PriorityLevel.HIGH,
            created_by="test_user",
        )

        assert job.job_number == "J2024-001"
        assert job.customer_name == "Test Customer"
        assert job.part_number == "PART-001"
        assert job.quantity.value == 10
        assert job.priority == PriorityLevel.HIGH
        assert job.status == JobStatus.PLANNED
        assert job.due_date == due_date
        assert job.created_by == "test_user"
        assert job.is_valid()

    def test_job_number_validation(self):
        """Test job number validation."""
        due_date = datetime.utcnow() + timedelta(days=7)

        # Test empty job number
        with pytest.raises(ValueError, match="Job number cannot be empty"):
            Job.create(job_number="", due_date=due_date)

        # Test whitespace job number
        with pytest.raises(ValueError, match="Job number cannot be empty"):
            Job.create(job_number="   ", due_date=due_date)

    def test_due_date_validation(self):
        """Test due date validation."""
        past_date = datetime.utcnow() - timedelta(days=1)

        with pytest.raises(ValueError, match="Due date must be in the future"):
            Job.create(job_number="J2024-001", due_date=past_date)

    def test_job_status_transitions(self):
        """Test valid and invalid job status transitions."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        # Valid transition: PLANNED -> RELEASED
        job.change_status(JobStatus.RELEASED)
        assert job.status == JobStatus.RELEASED
        assert job.release_date is not None

        # Valid transition: RELEASED -> IN_PROGRESS
        job.change_status(JobStatus.IN_PROGRESS)
        assert job.status == JobStatus.IN_PROGRESS

        # Valid transition: IN_PROGRESS -> ON_HOLD
        job.change_status(JobStatus.ON_HOLD, "maintenance required")
        assert job.status == JobStatus.ON_HOLD

        # Valid transition: ON_HOLD -> RELEASED
        job.change_status(JobStatus.RELEASED, "maintenance complete")
        assert job.status == JobStatus.RELEASED

    def test_job_properties(self):
        """Test job computed properties."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        # Test days_until_due
        assert job.days_until_due > 6.9
        assert job.days_until_due < 7.1

        # Test is_overdue (should be False)
        assert not job.is_overdue

        # Test with past due date
        job.due_date = datetime.utcnow() - timedelta(days=1)
        assert job.is_overdue

        # Test completion percentage with no tasks
        assert job.completion_percentage == 0.0

        # Test task count
        assert job.task_count == 0

    def test_job_schedule_update(self):
        """Test job schedule updates."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=5)

        job.update_schedule(start_date, end_date, "initial_schedule")

        assert job.planned_start_date == start_date
        assert job.planned_end_date == end_date

        # Test invalid schedule (start after end)
        with pytest.raises(
            BusinessRuleViolation, match="Planned start date must be before"
        ):
            job.update_schedule(end_date, start_date, "invalid_schedule")

    def test_job_priority_adjustment(self):
        """Test job priority adjustments."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date, priority=PriorityLevel.NORMAL)

        job.adjust_priority(PriorityLevel.URGENT, "customer_request")
        assert job.priority == PriorityLevel.URGENT

    def test_job_hold_operations(self):
        """Test putting job on hold and releasing."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)
        job.change_status(JobStatus.RELEASED)

        # Put on hold
        job.put_on_hold("maintenance_required")
        assert job.status == JobStatus.ON_HOLD

        # Release from hold
        job.release_from_hold("maintenance_complete")
        assert job.status == JobStatus.RELEASED

        # Test releasing job not on hold
        with pytest.raises(BusinessRuleViolation, match="Job .* is not on hold"):
            job.release_from_hold("invalid")


class TestTaskModelValidation:
    """Test Task entity validation and business rules."""

    def test_task_creation_with_valid_data(self):
        """Test creating a task with valid data."""
        job_id = uuid4()
        operation_id = uuid4()

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
            setup_duration_minutes=15,
        )

        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == 10
        assert task.planned_duration.minutes == 120
        assert task.planned_setup_duration.minutes == 15
        assert task.status == TaskStatus.PENDING
        assert task.is_valid()

    def test_task_sequence_validation(self):
        """Test task sequence number validation."""
        job_id = uuid4()
        operation_id = uuid4()

        # Test invalid sequence numbers
        with pytest.raises(ValueError, match="Task sequence must be between 1 and 100"):
            Task.create(job_id, operation_id, 0)

        with pytest.raises(ValueError, match="Task sequence must be between 1 and 100"):
            Task.create(job_id, operation_id, 101)

    def test_task_status_transitions(self):
        """Test valid task status transitions."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)

        # PENDING -> READY
        task.mark_ready()
        assert task.status == TaskStatus.READY

        # READY -> SCHEDULED
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        machine_id = uuid4()

        task.schedule(start_time, end_time, machine_id)
        assert task.status == TaskStatus.SCHEDULED
        assert task.planned_start_time == start_time
        assert task.planned_end_time == end_time
        assert task.assigned_machine_id == machine_id

        # SCHEDULED -> IN_PROGRESS
        actual_start = datetime.utcnow()
        task.start(actual_start)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.actual_start_time == actual_start

        # IN_PROGRESS -> COMPLETED
        actual_end = datetime.utcnow() + timedelta(minutes=5)
        task.complete(actual_end)
        assert task.status == TaskStatus.COMPLETED
        assert task.actual_end_time == actual_end

    def test_task_scheduling_validation(self):
        """Test task scheduling validation."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)
        task.mark_ready()

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time - timedelta(hours=1)  # Invalid: end before start

        with pytest.raises(
            BusinessRuleViolation, match="Start time must be before end time"
        ):
            task.schedule(start_time, end_time)

    def test_task_completion_validation(self):
        """Test task completion validation."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)
        task.mark_ready()

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=2)
        task.schedule(start_time, end_time)
        task.start()

        # Test completing with end time before start time
        invalid_end = task.actual_start_time - timedelta(minutes=1)
        with pytest.raises(
            BusinessRuleViolation, match="Completion time must be after start time"
        ):
            task.complete(invalid_end)

    def test_task_delay_tracking(self):
        """Test task delay tracking."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)
        task.mark_ready()

        # Schedule task
        original_start = datetime.utcnow() + timedelta(hours=1)
        original_end = original_start + timedelta(hours=2)
        task.schedule(original_start, original_end)

        # Reschedule with delay
        delayed_start = original_start + timedelta(minutes=30)
        delayed_end = original_end + timedelta(minutes=30)
        task.reschedule(delayed_start, delayed_end, "resource_conflict")

        assert task.delay_minutes >= 30
        assert task.is_delayed

    def test_task_rework_tracking(self):
        """Test task rework tracking."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)

        assert task.rework_count == 0
        assert not task.has_rework

        task.record_rework("quality_issue")
        assert task.rework_count == 1
        assert task.has_rework
        assert "quality_issue" in task.notes

        task.record_rework("dimension_issue")
        assert task.rework_count == 2

    def test_task_critical_path_marking(self):
        """Test critical path marking."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)

        assert not task.is_critical_path

        task.mark_critical_path()
        assert task.is_critical_path

        task.remove_critical_path_marking()
        assert not task.is_critical_path


class TestOperatorAssignmentModel:
    """Test OperatorAssignment entity validation."""

    def test_operator_assignment_creation(self):
        """Test creating operator assignment."""
        task_id = uuid4()
        operator_id = uuid4()

        assignment = OperatorAssignment(
            task_id=task_id,
            operator_id=operator_id,
            assignment_type=AssignmentType.FULL_DURATION,
            planned_start_time=datetime.utcnow(),
            planned_end_time=datetime.utcnow() + timedelta(hours=2),
        )

        assert assignment.task_id == task_id
        assert assignment.operator_id == operator_id
        assert assignment.assignment_type == AssignmentType.FULL_DURATION
        assert assignment.is_valid()
        assert not assignment.is_active

    def test_operator_assignment_timing(self):
        """Test operator assignment timing operations."""
        assignment = OperatorAssignment(
            task_id=uuid4(),
            operator_id=uuid4(),
            assignment_type=AssignmentType.FULL_DURATION,
            planned_start_time=datetime.utcnow(),
            planned_end_time=datetime.utcnow() + timedelta(hours=2),
        )

        # Test planned duration
        assert assignment.planned_duration is not None
        assert assignment.planned_duration.minutes == 120

        # Test starting assignment
        start_time = datetime.utcnow()
        assignment.start_assignment(start_time)
        assert assignment.actual_start_time == start_time
        assert assignment.is_active

        # Test completing assignment
        end_time = start_time + timedelta(minutes=90)
        assignment.complete_assignment(end_time)
        assert assignment.actual_end_time == end_time
        assert not assignment.is_active
        assert assignment.actual_duration.minutes == 90

    def test_operator_assignment_validation(self):
        """Test operator assignment business rule validation."""
        assignment = OperatorAssignment(
            task_id=uuid4(),
            operator_id=uuid4(),
            assignment_type=AssignmentType.FULL_DURATION,
        )

        # Test completing assignment without starting
        with pytest.raises(
            BusinessRuleViolation,
            match="Cannot complete assignment that hasn't been started",
        ):
            assignment.complete_assignment(datetime.utcnow())

        # Start assignment
        start_time = datetime.utcnow()
        assignment.start_assignment(start_time)

        # Test invalid end time
        invalid_end = start_time - timedelta(minutes=1)
        with pytest.raises(
            BusinessRuleViolation, match="End time must be after start time"
        ):
            assignment.complete_assignment(invalid_end)


class TestJobTaskRelationships:
    """Test relationships between Job and Task entities."""

    def test_job_task_coordination(self):
        """Test job-task coordination and relationships."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        # Create tasks
        operation_id1 = uuid4()
        operation_id2 = uuid4()

        task1 = Task.create(job.id, operation_id1, 10, 60)
        task2 = Task.create(job.id, operation_id2, 20, 90)

        # Add tasks to job
        job.add_task(task1)
        job.add_task(task2)

        assert job.task_count == 2
        assert job.get_task_by_sequence(10) == task1
        assert job.get_task_by_sequence(20) == task2

        # Test task ordering
        all_tasks = job.get_all_tasks()
        assert len(all_tasks) == 2
        assert all_tasks[0].sequence_in_job < all_tasks[1].sequence_in_job

    def test_job_task_progression(self):
        """Test job progression through task completion."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        # Add tasks
        task1 = Task.create(job.id, uuid4(), 10, 60)
        task2 = Task.create(job.id, uuid4(), 20, 60)
        job.add_task(task1)
        job.add_task(task2)

        # Initially no tasks completed
        assert job.completion_percentage == 0.0
        assert job.completed_task_count == 0

        # Complete first task
        task1.mark_ready()
        task1.schedule(datetime.utcnow(), datetime.utcnow() + timedelta(hours=1))
        task1.start()
        completion_time = datetime.utcnow()
        job.complete_task(10, completion_time)

        # Check progress
        assert job.completion_percentage == 50.0
        assert job.completed_task_count == 1
        assert job.current_operation_sequence == 10

        # Second task should now be ready
        task2_updated = job.get_task_by_sequence(20)
        assert task2_updated.status == TaskStatus.READY

    def test_job_task_business_rules(self):
        """Test business rules between jobs and tasks."""
        due_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create("J2024-001", due_date)

        # Complete job first
        job.change_status(JobStatus.COMPLETED)

        # Try to add task to completed job
        task = Task.create(job.id, uuid4(), 10)
        with pytest.raises(
            BusinessRuleViolation, match="Cannot add tasks to completed job"
        ):
            job.add_task(task)

    def test_task_operator_assignments(self):
        """Test task operator assignment management."""
        job_id = uuid4()
        operation_id = uuid4()
        task = Task.create(job_id, operation_id, 10)

        operator_id1 = uuid4()
        operator_id2 = uuid4()

        # Add operator assignments
        assignment1 = OperatorAssignment(
            task_id=task.id,
            operator_id=operator_id1,
            assignment_type=AssignmentType.FULL_DURATION,
        )
        assignment2 = OperatorAssignment(
            task_id=task.id,
            operator_id=operator_id2,
            assignment_type=AssignmentType.SETUP_ONLY,
        )

        task.add_operator_assignment(assignment1)
        task.add_operator_assignment(assignment2)

        assert task.has_operator_assignments
        assert len(task._operator_assignments) == 2

        # Test duplicate assignment
        duplicate = OperatorAssignment(
            task_id=task.id,
            operator_id=operator_id1,
            assignment_type=AssignmentType.SETUP_ONLY,
        )

        with pytest.raises(
            BusinessRuleViolation, match="Operator .* is already assigned"
        ):
            task.add_operator_assignment(duplicate)

        # Test removing assignment
        task.remove_operator_assignment(operator_id2)
        assert len(task._operator_assignments) == 1
