"""
Comprehensive Unit Tests for Job Domain Entity

Tests all business logic, validation, and domain rules for the Job aggregate root.
Covers creation, state transitions, task management, and domain events.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.entities.job import (
    Job,
    JobDelayed,
    JobScheduleChanged,
    JobStatusChanged,
    TaskProgressUpdated,
)
from app.domain.scheduling.value_objects.common import Quantity
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
    TaskStatus,
)
from app.shared.base import BusinessRuleViolation
from app.tests.database.factories import JobFactory, TaskFactory


class TestJobCreation:
    """Test job creation and validation."""

    def test_create_valid_job(self):
        """Test creating a valid job with all required fields."""
        job_number = "JOB-2024-001"
        due_date = datetime.utcnow() + timedelta(days=7)
        customer_name = "Acme Corp"
        part_number = "PART-ABC-123"
        quantity = 10
        priority = PriorityLevel.HIGH
        created_by = "user123"

        job = Job.create(
            job_number=job_number,
            due_date=due_date,
            customer_name=customer_name,
            part_number=part_number,
            quantity=quantity,
            priority=priority,
            created_by=created_by,
        )

        assert job.job_number == job_number
        assert job.due_date == due_date
        assert job.customer_name == customer_name
        assert job.part_number == part_number
        assert job.quantity.value == quantity
        assert job.priority == priority
        assert job.created_by == created_by
        assert job.status == JobStatus.PLANNED
        assert job.is_valid()
        assert isinstance(job.id, UUID)

    def test_create_job_with_minimal_fields(self):
        """Test creating job with only required fields."""
        job_number = "MIN-JOB-001"
        due_date = datetime.utcnow() + timedelta(days=1)

        job = Job.create(job_number=job_number, due_date=due_date)

        assert job.job_number == job_number
        assert job.due_date == due_date
        assert job.customer_name is None
        assert job.part_number is None
        assert job.quantity.value == 1
        assert job.priority == PriorityLevel.NORMAL
        assert job.created_by is None
        assert job.is_valid()

    def test_create_job_with_invalid_job_number(self):
        """Test job creation fails with invalid job number."""
        with pytest.raises(ValueError, match="Job number"):
            Job.create(
                job_number="",  # Empty job number
                due_date=datetime.utcnow() + timedelta(days=1),
            )

        with pytest.raises(ValueError, match="Job number"):
            Job.create(
                job_number="x" * 51,  # Too long
                due_date=datetime.utcnow() + timedelta(days=1),
            )

    def test_create_job_with_past_due_date(self):
        """Test job creation fails with past due date."""
        with pytest.raises(ValueError, match="due_date"):
            Job.create(
                job_number="PAST-JOB-001",
                due_date=datetime.utcnow() - timedelta(days=1),
            )

    def test_create_job_with_invalid_quantity(self):
        """Test job creation fails with invalid quantity."""
        with pytest.raises(ValueError):
            Job.create(
                job_number="INVALID-QTY-001",
                due_date=datetime.utcnow() + timedelta(days=1),
                quantity=0,  # Invalid quantity
            )

    @pytest.mark.parametrize(
        "customer_name",
        [
            "x" * 101,  # Too long
            "<script>alert('xss')</script>",  # XSS attempt
            "'; DROP TABLE jobs; --",  # SQL injection attempt
        ],
    )
    def test_create_job_sanitizes_customer_name(self, customer_name):
        """Test that customer name is properly sanitized."""
        job = Job.create(
            job_number="SANITIZE-TEST-001",
            due_date=datetime.utcnow() + timedelta(days=1),
            customer_name=customer_name,
        )

        # Should not contain dangerous characters
        assert "<script>" not in job.customer_name
        assert "DROP TABLE" not in job.customer_name
        assert len(job.customer_name) <= 100

    def test_job_number_validation(self):
        """Test job number format validation."""
        # Valid job numbers
        valid_numbers = [
            "JOB-2024-001",
            "BATCH-123",
            "WO-ABC-456",
            "CUSTOM_ORDER_789",
        ]

        for job_number in valid_numbers:
            job = Job.create(
                job_number=job_number,
                due_date=datetime.utcnow() + timedelta(days=1),
            )
            assert job.job_number == job_number

        # Invalid job numbers should be handled by validation
        # (specific validation rules depend on SchedulingValidators implementation)


class TestJobProperties:
    """Test job computed properties and state checks."""

    def test_is_active_property(self):
        """Test is_active property for different job statuses."""
        job = JobFactory.create()

        # Test different statuses
        active_statuses = [
            JobStatus.RELEASED,
            JobStatus.IN_PROGRESS,
            JobStatus.ON_HOLD,
        ]
        inactive_statuses = [
            JobStatus.PLANNED,
            JobStatus.COMPLETED,
            JobStatus.CANCELLED,
        ]

        for status in active_statuses:
            job.status = status
            assert job.is_active, f"Job should be active with status {status}"

        for status in inactive_statuses:
            job.status = status
            assert not job.is_active, f"Job should not be active with status {status}"

    def test_is_complete_property(self):
        """Test is_complete property."""
        job = JobFactory.create()

        assert not job.is_complete  # Initially planned

        job.status = JobStatus.COMPLETED
        assert job.is_complete

        job.status = JobStatus.CANCELLED
        assert not job.is_complete

    def test_is_overdue_property(self):
        """Test is_overdue property."""
        # Create job due in the future
        future_job = JobFactory.create(due_date=datetime.utcnow() + timedelta(days=1))
        assert not future_job.is_overdue

        # Create overdue job
        overdue_job = JobFactory.create(due_date=datetime.utcnow() - timedelta(days=1))
        assert overdue_job.is_overdue

        # Completed jobs are never overdue
        completed_job = JobFactory.create(
            due_date=datetime.utcnow() - timedelta(days=1),
            status=JobStatus.COMPLETED,
        )
        assert not completed_job.is_overdue

    def test_days_until_due(self):
        """Test days_until_due calculation."""
        # Job due in 5 days
        future_job = JobFactory.create(due_date=datetime.utcnow() + timedelta(days=5))
        days_until = future_job.days_until_due
        assert 4.5 <= days_until <= 5.5  # Allow for small time differences

        # Overdue job
        overdue_job = JobFactory.create(due_date=datetime.utcnow() - timedelta(days=2))
        days_until = overdue_job.days_until_due
        assert -2.5 <= days_until <= -1.5

    def test_task_count_properties(self):
        """Test task counting properties."""
        job = JobFactory.create()

        assert job.task_count == 0
        assert job.completed_task_count == 0
        assert job.completion_percentage == 0.0

        # Add tasks
        task1 = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        task2 = TaskFactory.create(job_id=job.id, sequence_in_job=20)
        task3 = TaskFactory.create(job_id=job.id, sequence_in_job=30)

        job.add_task(task1)
        job.add_task(task2)
        job.add_task(task3)

        assert job.task_count == 3
        assert job.completed_task_count == 0
        assert job.completion_percentage == 0.0

        # Complete one task
        task1.status = TaskStatus.COMPLETED
        assert job.completed_task_count == 1
        assert abs(job.completion_percentage - 33.33) < 0.1

        # Complete all tasks
        task2.status = TaskStatus.COMPLETED
        task3.status = TaskStatus.COMPLETED
        assert job.completed_task_count == 3
        assert job.completion_percentage == 100.0

    def test_estimated_duration(self):
        """Test estimated duration calculation."""
        job = JobFactory.create()

        # No tasks = no duration
        assert job.estimated_duration is None

        # Add tasks with known durations
        task1 = TaskFactory.create(
            job_id=job.id,
            sequence_in_job=10,
            planned_duration_minutes=60,
            setup_duration_minutes=15,
        )
        task2 = TaskFactory.create(
            job_id=job.id,
            sequence_in_job=20,
            planned_duration_minutes=90,
            setup_duration_minutes=10,
        )

        job.add_task(task1)
        job.add_task(task2)

        # Total should be sum of all durations
        expected_minutes = (60 + 15) + (90 + 10)  # 175 minutes
        estimated = job.estimated_duration
        assert estimated is not None
        assert estimated.minutes == expected_minutes


class TestJobTaskManagement:
    """Test job task management operations."""

    def test_add_task_success(self):
        """Test successfully adding tasks to job."""
        job = JobFactory.create()
        task = TaskFactory.create(job_id=job.id, sequence_in_job=10)

        job.add_task(task)

        assert job.task_count == 1
        assert job.get_task_by_sequence(10) == task
        assert task in job.get_all_tasks()

    def test_add_task_with_wrong_job_id(self):
        """Test adding task with wrong job ID fails."""
        job = JobFactory.create()
        task = TaskFactory.create(job_id=uuid4(), sequence_in_job=10)  # Wrong job ID

        with pytest.raises(BusinessRuleViolation, match="job_id must match"):
            job.add_task(task)

    def test_add_task_duplicate_sequence(self):
        """Test adding task with duplicate sequence fails."""
        job = JobFactory.create()
        task1 = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        task2 = TaskFactory.create(job_id=job.id, sequence_in_job=10)  # Duplicate

        job.add_task(task1)

        with pytest.raises(BusinessRuleViolation, match="already exists"):
            job.add_task(task2)

    def test_add_task_to_completed_job(self):
        """Test adding task to completed job fails."""
        job = JobFactory.create(status=JobStatus.COMPLETED)
        task = TaskFactory.create(job_id=job.id, sequence_in_job=10)

        with pytest.raises(BusinessRuleViolation, match="completed job"):
            job.add_task(task)

    def test_add_first_task_becomes_ready(self):
        """Test that first task becomes ready automatically."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=1, status=TaskStatus.PENDING
        )

        job.add_task(task)

        assert task.status == TaskStatus.READY

    def test_remove_task_success(self):
        """Test successfully removing task from job."""
        job = JobFactory.create()
        task = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        job.add_task(task)

        job.remove_task(10)

        assert job.task_count == 0
        assert job.get_task_by_sequence(10) is None

    def test_remove_nonexistent_task(self):
        """Test removing non-existent task fails."""
        job = JobFactory.create()

        with pytest.raises(BusinessRuleViolation, match="not found"):
            job.remove_task(10)

    def test_remove_in_progress_task(self):
        """Test removing in-progress task fails."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        job.add_task(task)

        with pytest.raises(BusinessRuleViolation, match="in progress"):
            job.remove_task(10)

    def test_get_tasks_by_status(self):
        """Test getting tasks filtered by status."""
        job = JobFactory.create()

        # Add tasks in different states
        ready_task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.READY
        )
        scheduled_task = TaskFactory.create(
            job_id=job.id, sequence_in_job=20, status=TaskStatus.SCHEDULED
        )
        in_progress_task = TaskFactory.create(
            job_id=job.id, sequence_in_job=30, status=TaskStatus.IN_PROGRESS
        )
        completed_task = TaskFactory.create(
            job_id=job.id, sequence_in_job=40, status=TaskStatus.COMPLETED
        )

        job.add_task(ready_task)
        job.add_task(scheduled_task)
        job.add_task(in_progress_task)
        job.add_task(completed_task)

        # Test filtering
        ready_tasks = job.get_ready_tasks()
        assert len(ready_tasks) == 1
        assert ready_task in ready_tasks

        active_tasks = job.get_active_tasks()
        assert len(active_tasks) == 2  # SCHEDULED and IN_PROGRESS
        assert scheduled_task in active_tasks
        assert in_progress_task in active_tasks

    def test_critical_path_tasks(self):
        """Test getting critical path tasks."""
        job = JobFactory.create()

        # Add regular and critical path tasks
        regular_task = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        critical_task = TaskFactory.create_critical_path(job_id=job.id)
        critical_task.sequence_in_job = 20

        job.add_task(regular_task)
        job.add_task(critical_task)

        critical_tasks = job.critical_path_tasks
        assert len(critical_tasks) == 1
        assert critical_task in critical_tasks


class TestJobTaskCompletion:
    """Test job task completion workflow."""

    def test_complete_task_success(self):
        """Test successfully completing a task."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        job.add_task(task)

        completion_time = datetime.utcnow()
        job.complete_task(10, completion_time)

        assert task.status == TaskStatus.COMPLETED
        assert task.actual_end_time == completion_time
        assert job.current_operation_sequence == 10

    def test_complete_nonexistent_task(self):
        """Test completing non-existent task fails."""
        job = JobFactory.create()

        with pytest.raises(BusinessRuleViolation, match="not found"):
            job.complete_task(10, datetime.utcnow())

    def test_complete_task_not_in_progress(self):
        """Test completing task that's not in progress fails."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.READY
        )
        job.add_task(task)

        with pytest.raises(BusinessRuleViolation, match="not in progress"):
            job.complete_task(10, datetime.utcnow())

    def test_complete_task_updates_job_start_date(self):
        """Test completing first task sets job start date."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        task.actual_start_time = datetime.utcnow() - timedelta(hours=1)
        job.add_task(task)

        assert job.actual_start_date is None

        job.complete_task(10, datetime.utcnow())

        assert job.actual_start_date == task.actual_start_time

    def test_complete_task_makes_next_ready(self):
        """Test completing task makes next task ready."""
        job = JobFactory.create()

        task1 = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        task2 = TaskFactory.create(
            job_id=job.id, sequence_in_job=11, status=TaskStatus.PENDING
        )

        job.add_task(task1)
        job.add_task(task2)

        job.complete_task(10, datetime.utcnow())

        assert task2.status == TaskStatus.READY

    def test_complete_all_tasks_completes_job(self):
        """Test completing all tasks completes the job."""
        job = JobFactory.create()

        task1 = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        task2 = TaskFactory.create(
            job_id=job.id, sequence_in_job=20, status=TaskStatus.PENDING
        )

        job.add_task(task1)
        job.add_task(task2)

        # Complete first task
        job.complete_task(10, datetime.utcnow())
        assert job.status != JobStatus.COMPLETED

        # Complete second task - should complete job
        task2.status = TaskStatus.IN_PROGRESS
        completion_time = datetime.utcnow()
        job.complete_task(20, completion_time)

        assert job.status == JobStatus.COMPLETED
        assert job.actual_end_date == completion_time

    def test_complete_task_at_sequence_100_completes_job(self):
        """Test completing task at sequence 100 completes job regardless of other tasks."""
        job = JobFactory.create()

        task1 = TaskFactory.create(
            job_id=job.id, sequence_in_job=50, status=TaskStatus.PENDING
        )
        task2 = TaskFactory.create(
            job_id=job.id, sequence_in_job=100, status=TaskStatus.IN_PROGRESS
        )

        job.add_task(task1)
        job.add_task(task2)

        completion_time = datetime.utcnow()
        job.complete_task(100, completion_time)

        assert job.status == JobStatus.COMPLETED
        assert job.actual_end_date == completion_time

    def test_complete_task_generates_progress_event(self):
        """Test completing task generates progress event."""
        job = JobFactory.create()
        task = TaskFactory.create(
            job_id=job.id, sequence_in_job=10, status=TaskStatus.IN_PROGRESS
        )
        job.add_task(task)

        job.complete_task(10, datetime.utcnow())

        # Check domain events
        events = job.get_domain_events()
        progress_events = [e for e in events if isinstance(e, TaskProgressUpdated)]
        assert len(progress_events) == 1

        event = progress_events[0]
        assert event.job_id == job.id
        assert event.job_number == job.job_number
        assert event.completed_tasks == 1
        assert event.total_tasks == 1
        assert event.completion_percentage == 100.0


class TestJobStatusTransitions:
    """Test job status change operations."""

    def test_change_status_success(self):
        """Test successful status changes."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        job.change_status(JobStatus.RELEASED, "ready_for_production")

        assert job.status == JobStatus.RELEASED
        assert job.release_date is not None

        # Check domain event
        events = job.get_domain_events()
        status_events = [e for e in events if isinstance(e, JobStatusChanged)]
        assert len(status_events) == 1

        event = status_events[0]
        assert event.old_status == JobStatus.PLANNED
        assert event.new_status == JobStatus.RELEASED
        assert event.reason == "ready_for_production"

    def test_change_status_same_status_ignored(self):
        """Test changing to same status is ignored."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        job.change_status(JobStatus.PLANNED)

        # Should not generate events for no-change
        events = job.get_domain_events()
        status_events = [e for e in events if isinstance(e, JobStatusChanged)]
        assert len(status_events) == 0

    def test_invalid_status_transition(self):
        """Test invalid status transitions are rejected."""
        job = JobFactory.create(status=JobStatus.COMPLETED)

        with pytest.raises(BusinessRuleViolation, match="Cannot transition"):
            job.change_status(JobStatus.PLANNED)

    def test_put_on_hold(self):
        """Test putting job on hold."""
        job = JobFactory.create(status=JobStatus.RELEASED)

        job.put_on_hold("equipment_maintenance")

        assert job.status == JobStatus.ON_HOLD

    def test_release_from_hold(self):
        """Test releasing job from hold."""
        job = JobFactory.create(status=JobStatus.ON_HOLD)

        job.release_from_hold("maintenance_complete")

        assert job.status == JobStatus.RELEASED

    def test_release_from_hold_when_not_on_hold(self):
        """Test releasing job from hold when not on hold fails."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        with pytest.raises(BusinessRuleViolation, match="not on hold"):
            job.release_from_hold()

    def test_cancel_job(self):
        """Test cancelling job."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        job.cancel("customer_request")

        assert job.status == JobStatus.CANCELLED


class TestJobScheduling:
    """Test job scheduling operations."""

    def test_update_schedule_success(self):
        """Test successful schedule update."""
        job = JobFactory.create()

        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = start_time + timedelta(hours=8)

        job.update_schedule(start_time, end_time, "initial_schedule")

        assert job.planned_start_date == start_time
        assert job.planned_end_date == end_time

        # Check domain event
        events = job.get_domain_events()
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]
        assert len(schedule_events) == 1

        event = schedule_events[0]
        assert event.new_planned_start == start_time
        assert event.new_planned_end == end_time
        assert event.reason == "initial_schedule"

    def test_update_schedule_invalid_times(self):
        """Test schedule update with invalid times fails."""
        job = JobFactory.create()

        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = start_time - timedelta(hours=1)  # End before start

        with pytest.raises(BusinessRuleViolation, match="before planned end"):
            job.update_schedule(start_time, end_time)

    def test_update_schedule_creates_delay_event(self):
        """Test schedule update past due date creates delay event."""
        due_date = datetime.utcnow() + timedelta(days=1)
        job = JobFactory.create(due_date=due_date, customer_name="Test Customer")

        # Schedule to end after due date
        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = due_date + timedelta(hours=2)  # 2 hours late

        job.update_schedule(start_time, end_time, "resource_conflict")

        # Check delay event
        events = job.get_domain_events()
        delay_events = [e for e in events if isinstance(e, JobDelayed)]
        assert len(delay_events) == 1

        event = delay_events[0]
        assert event.due_date == due_date
        assert event.estimated_completion == end_time
        assert event.delay_hours == 2.0
        assert event.customer_name == "Test Customer"

    def test_adjust_priority(self):
        """Test adjusting job priority."""
        job = JobFactory.create(priority=PriorityLevel.NORMAL)

        job.adjust_priority(PriorityLevel.URGENT, "customer_escalation")

        assert job.priority == PriorityLevel.URGENT

        # Should generate schedule change event
        events = job.get_domain_events()
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]
        assert len(schedule_events) == 1

    def test_adjust_priority_no_change_ignored(self):
        """Test adjusting to same priority is ignored."""
        job = JobFactory.create(priority=PriorityLevel.NORMAL)

        job.adjust_priority(PriorityLevel.NORMAL, "no_change")

        events = job.get_domain_events()
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]
        assert len(schedule_events) == 0

    def test_extend_due_date(self):
        """Test extending job due date."""
        original_due = datetime.utcnow() + timedelta(days=7)
        job = JobFactory.create(due_date=original_due)

        new_due = original_due + timedelta(days=3)
        job.extend_due_date(new_due, "material_delay")

        assert job.due_date == new_due

    def test_extend_due_date_earlier_fails(self):
        """Test extending due date to earlier date fails."""
        original_due = datetime.utcnow() + timedelta(days=7)
        job = JobFactory.create(due_date=original_due)

        earlier_due = original_due - timedelta(days=1)

        with pytest.raises(BusinessRuleViolation, match="later than current"):
            job.extend_due_date(earlier_due, "invalid")


class TestJobSummaryAndReporting:
    """Test job summary and reporting functionality."""

    def test_get_job_summary(self):
        """Test getting comprehensive job summary."""
        job = JobFactory.create_with_tasks(
            task_count=5,
            job_number="SUMMARY-TEST-001",
            customer_name="Test Corp",
            priority=PriorityLevel.HIGH,
            quantity=25,
        )

        # Complete some tasks
        task1 = job.get_task_by_sequence(10)
        task2 = job.get_task_by_sequence(20)
        if task1:
            task1.status = TaskStatus.COMPLETED
        if task2:
            task2.status = TaskStatus.COMPLETED

        summary = job.get_job_summary()

        assert summary["job_number"] == "SUMMARY-TEST-001"
        assert summary["customer_name"] == "Test Corp"
        assert summary["status"] == JobStatus.PLANNED.value
        assert summary["priority"] == PriorityLevel.HIGH.value
        assert summary["quantity"] == 25
        assert "due_date" in summary
        assert "days_until_due" in summary
        assert "is_overdue" in summary
        assert summary["task_count"] == 5
        assert summary["completed_tasks"] == 2
        assert summary["completion_percentage"] == 40.0
        assert "current_operation_sequence" in summary
        assert "estimated_duration" in summary

    def test_job_summary_with_critical_path(self):
        """Test job summary includes critical path information."""
        job = JobFactory.create()

        # Add regular and critical tasks
        regular_task = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        critical_task = TaskFactory.create_critical_path(job_id=job.id)
        critical_task.sequence_in_job = 20

        job.add_task(regular_task)
        job.add_task(critical_task)

        summary = job.get_job_summary()
        assert summary["critical_path_task_count"] == 1


class TestJobValidationAndBusinessRules:
    """Test job validation and business rule enforcement."""

    def test_is_valid_basic_checks(self):
        """Test basic job validation."""
        # Valid job
        job = JobFactory.create()
        assert job.is_valid()

        # Invalid: empty job number
        job.job_number = ""
        assert not job.is_valid()

        # Invalid: past due date
        job.job_number = "VALID-001"
        job.due_date = datetime.utcnow() - timedelta(days=1)
        assert not job.is_valid()

        # Invalid: zero quantity
        job.due_date = datetime.utcnow() + timedelta(days=1)
        job.quantity = Quantity(value=0)
        assert not job.is_valid()

        # Invalid: operation sequence out of range
        job.quantity = Quantity(value=1)
        job.current_operation_sequence = 101
        assert not job.is_valid()

    def test_input_sanitization(self):
        """Test input sanitization for user-provided fields."""
        # Test notes sanitization
        malicious_notes = "<script>alert('xss')</script>Important notes"
        job = JobFactory.create(notes=malicious_notes)

        assert "<script>" not in job.notes
        assert "alert" not in job.notes
        assert "Important notes" in job.notes

        # Test customer name sanitization
        malicious_customer = "'; DROP TABLE users; -- Customer Corp"
        job = JobFactory.create(customer_name=malicious_customer)

        assert "DROP TABLE" not in job.customer_name
        assert "--" not in job.customer_name
        assert "Customer Corp" in job.customer_name


class TestJobDomainEvents:
    """Test domain events generated by job operations."""

    def test_job_creation_has_no_events(self):
        """Test that job creation doesn't generate events."""
        job = JobFactory.create()
        events = job.get_domain_events()
        assert len(events) == 0

    def test_status_change_events(self):
        """Test status change events are properly generated."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        job.change_status(JobStatus.RELEASED, "production_ready")

        events = job.get_domain_events()
        status_events = [e for e in events if isinstance(e, JobStatusChanged)]
        assert len(status_events) == 1

        event = status_events[0]
        assert event.job_id == job.id
        assert event.job_number == job.job_number
        assert event.old_status == JobStatus.PLANNED
        assert event.new_status == JobStatus.RELEASED
        assert event.reason == "production_ready"

    def test_multiple_status_changes_generate_multiple_events(self):
        """Test multiple status changes generate separate events."""
        job = JobFactory.create(status=JobStatus.PLANNED)

        job.change_status(JobStatus.RELEASED, "first_change")
        job.change_status(JobStatus.IN_PROGRESS, "second_change")

        events = job.get_domain_events()
        status_events = [e for e in events if isinstance(e, JobStatusChanged)]
        assert len(status_events) == 2

        assert status_events[0].new_status == JobStatus.RELEASED
        assert status_events[1].new_status == JobStatus.IN_PROGRESS

    def test_schedule_change_events(self):
        """Test schedule change events."""
        job = JobFactory.create()

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=4)

        job.update_schedule(start_time, end_time, "initial_planning")

        events = job.get_domain_events()
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]
        assert len(schedule_events) == 1

        event = schedule_events[0]
        assert event.job_id == job.id
        assert event.new_planned_start == start_time
        assert event.new_planned_end == end_time
        assert event.reason == "initial_planning"

    def test_job_delay_events(self):
        """Test job delay events."""
        due_date = datetime.utcnow() + timedelta(days=1)
        job = JobFactory.create(due_date=due_date, customer_name="Delay Customer")

        # Schedule past due date
        delayed_end = due_date + timedelta(hours=3)
        job.update_schedule(
            datetime.utcnow() + timedelta(hours=1), delayed_end, "resource_shortage"
        )

        events = job.get_domain_events()
        delay_events = [e for e in events if isinstance(e, JobDelayed)]
        assert len(delay_events) == 1

        event = delay_events[0]
        assert event.job_id == job.id
        assert event.due_date == due_date
        assert event.estimated_completion == delayed_end
        assert event.delay_hours == 3.0
        assert event.customer_name == "Delay Customer"

    def test_task_progress_events(self):
        """Test task progress events."""
        job = JobFactory.create_with_tasks(task_count=3)

        # Get first task and put it in progress
        task = job.get_task_by_sequence(10)
        task.status = TaskStatus.IN_PROGRESS

        job.complete_task(10, datetime.utcnow())

        events = job.get_domain_events()
        progress_events = [e for e in events if isinstance(e, TaskProgressUpdated)]
        assert len(progress_events) == 1

        event = progress_events[0]
        assert event.job_id == job.id
        assert event.completed_tasks == 1
        assert event.total_tasks == 3
        assert event.current_operation_sequence == 10
        assert abs(event.completion_percentage - 33.33) < 0.1

    def test_event_ordering_and_consistency(self):
        """Test that events are generated in correct order and contain consistent data."""
        job = JobFactory.create()

        # Perform multiple operations
        job.change_status(JobStatus.RELEASED, "step1")
        job.update_schedule(
            datetime.utcnow() + timedelta(hours=1),
            datetime.utcnow() + timedelta(hours=8),
            "step2",
        )
        job.adjust_priority(PriorityLevel.HIGH, "step3")

        events = job.get_domain_events()

        # Should have status change + 2 schedule changes (initial + priority)
        status_events = [e for e in events if isinstance(e, JobStatusChanged)]
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]

        assert len(status_events) == 1
        assert len(schedule_events) == 2

        # All events should have consistent job information
        for event in events:
            assert event.aggregate_id == job.id
            assert hasattr(event, "job_id") and event.job_id == job.id
            assert hasattr(event, "job_number") and event.job_number == job.job_number


class TestJobFactoryMethods:
    """Test Job factory methods and builders."""

    def test_create_factory_method_with_all_parameters(self):
        """Test Job.create factory method with all parameters."""
        job = Job.create(
            job_number="FACTORY-001",
            due_date=datetime.utcnow() + timedelta(days=14),
            customer_name="Factory Customer",
            part_number="PART-F001",
            quantity=50,
            priority=PriorityLevel.HIGH,
            created_by="factory_user",
        )

        assert job.job_number == "FACTORY-001"
        assert job.customer_name == "Factory Customer"
        assert job.part_number == "PART-F001"
        assert job.quantity.value == 50
        assert job.priority == PriorityLevel.HIGH
        assert job.created_by == "factory_user"
        assert job.is_valid()

    def test_create_factory_method_validates_input(self):
        """Test that factory method validates input."""
        with pytest.raises(ValueError):
            Job.create(
                job_number="",  # Invalid
                due_date=datetime.utcnow() + timedelta(days=1),
            )

        with pytest.raises(ValueError):
            Job.create(
                job_number="VALID-001",
                due_date=datetime.utcnow() - timedelta(days=1),  # Invalid
            )


@pytest.mark.integration
class TestJobIntegration:
    """Integration tests for job with other components."""

    def test_job_with_complete_task_workflow(self):
        """Test complete job workflow from creation to completion."""
        # Create job
        job = JobFactory.create(
            job_number="WORKFLOW-001",
            quantity=1,
            priority=PriorityLevel.NORMAL,
        )

        # Add tasks
        tasks = []
        for i in range(1, 4):
            task = TaskFactory.create(
                job_id=job.id,
                sequence_in_job=i * 10,
                planned_duration_minutes=60,
            )
            job.add_task(task)
            tasks.append(task)

        # Verify initial state
        assert job.status == JobStatus.PLANNED
        assert job.task_count == 3
        assert job.completion_percentage == 0.0
        assert tasks[0].status == TaskStatus.READY  # First task ready

        # Release job
        job.change_status(JobStatus.RELEASED)
        assert job.status == JobStatus.RELEASED
        assert job.release_date is not None

        # Start job (first task)
        tasks[0].status = TaskStatus.IN_PROGRESS
        job.change_status(JobStatus.IN_PROGRESS)

        # Complete tasks one by one
        for i, task in enumerate(tasks):
            if i > 0:  # First task already in progress
                task.status = TaskStatus.IN_PROGRESS

            completion_time = datetime.utcnow() + timedelta(minutes=i)
            job.complete_task(task.sequence_in_job, completion_time)

            # Check progress
            expected_completion = ((i + 1) / len(tasks)) * 100
            assert abs(job.completion_percentage - expected_completion) < 0.1

            if i < len(tasks) - 1:  # Not last task
                assert job.status == JobStatus.IN_PROGRESS
                # Next task should be ready
                next_task = tasks[i + 1]
                assert next_task.status == TaskStatus.READY

        # Job should be completed
        assert job.status == JobStatus.COMPLETED
        assert job.actual_end_date is not None
        assert job.completion_percentage == 100.0

        # Verify events were generated
        events = job.get_domain_events()
        assert len([e for e in events if isinstance(e, JobStatusChanged)]) >= 2
        assert len([e for e in events if isinstance(e, TaskProgressUpdated)]) == 3

    def test_job_with_delay_and_rescheduling(self):
        """Test job handling delays and rescheduling."""
        due_date = datetime.utcnow() + timedelta(days=5)
        job = JobFactory.create(due_date=due_date, customer_name="Delay Test Customer")

        # Initial schedule on time
        on_time_start = datetime.utcnow() + timedelta(hours=1)
        on_time_end = due_date - timedelta(hours=4)

        job.update_schedule(on_time_start, on_time_end, "initial_plan")

        # No delay event should be generated
        events = job.get_domain_events()
        delay_events = [e for e in events if isinstance(e, JobDelayed)]
        assert len(delay_events) == 0

        # Reschedule with delay
        delayed_start = datetime.utcnow() + timedelta(hours=2)
        delayed_end = due_date + timedelta(hours=6)  # 6 hours late

        job.update_schedule(delayed_start, delayed_end, "resource_conflict")

        # Should generate delay event
        events = job.get_domain_events()
        delay_events = [e for e in events if isinstance(e, JobDelayed)]
        assert len(delay_events) == 1

        delay_event = delay_events[0]
        assert delay_event.delay_hours == 6.0
        assert delay_event.customer_name == "Delay Test Customer"

        # Job should be marked as overdue after due date passes
        # (This would be tested in a time-dependent scenario)
        assert not job.is_overdue  # Still in future in test

    def test_job_priority_escalation_workflow(self):
        """Test job priority escalation affecting scheduling."""
        job = JobFactory.create(priority=PriorityLevel.LOW)

        # Schedule job
        start_time = datetime.utcnow() + timedelta(hours=8)
        end_time = start_time + timedelta(hours=4)
        job.update_schedule(start_time, end_time, "low_priority_slot")

        # Escalate priority
        job.adjust_priority(PriorityLevel.URGENT, "customer_escalation")

        # Should generate scheduling event for priority change
        events = job.get_domain_events()
        schedule_events = [e for e in events if isinstance(e, JobScheduleChanged)]
        priority_events = [e for e in schedule_events if "priority_changed" in e.reason]
        assert len(priority_events) == 1

        assert job.priority == PriorityLevel.URGENT

        # In real system, this would trigger rescheduling logic


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
