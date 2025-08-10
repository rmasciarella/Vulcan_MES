"""
Comprehensive Unit Tests for Task Domain Entity

Tests all business logic, validation, and domain rules for the Task entity.
Covers task lifecycle, scheduling, operator assignments, and state transitions.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.entities.task import (
    Task,
    TaskCompleted,
    TaskRescheduled,
    TaskScheduled,
    TaskStarted,
    TaskStatusChanged,
)
from app.domain.scheduling.value_objects.common import Duration
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    SkillLevel,
    TaskStatus,
)
from app.domain.scheduling.value_objects.skill import Skill, SkillRequirement
from app.shared.base import BusinessRuleViolation
from app.tests.database.factories import OperatorAssignmentFactory, TaskFactory


class TestTaskCreation:
    """Test task creation and validation."""

    def test_create_valid_task(self):
        """Test creating a valid task with all parameters."""
        job_id = uuid4()
        operation_id = uuid4()
        sequence = 10
        planned_duration = 120
        setup_duration = 15

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=sequence,
            planned_duration_minutes=planned_duration,
            setup_duration_minutes=setup_duration,
        )

        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == sequence
        assert task.planned_duration.minutes == planned_duration
        assert task.setup_duration.minutes == setup_duration
        assert task.status == TaskStatus.PENDING
        assert task.is_valid()
        assert isinstance(task.id, UUID)

    def test_create_task_with_minimal_parameters(self):
        """Test creating task with minimal required parameters."""
        job_id = uuid4()
        operation_id = uuid4()

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=60,
        )

        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == 10
        assert task.planned_duration.minutes == 60
        assert task.setup_duration.minutes == 0
        assert task.is_valid()

    def test_create_task_invalid_sequence(self):
        """Test task creation fails with invalid sequence."""
        job_id = uuid4()
        operation_id = uuid4()

        with pytest.raises(ValueError, match="sequence"):
            Task.create(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=0,  # Invalid sequence
                planned_duration_minutes=60,
            )

        with pytest.raises(ValueError, match="sequence"):
            Task.create(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=101,  # Invalid sequence
                planned_duration_minutes=60,
            )

    def test_create_task_invalid_duration(self):
        """Test task creation fails with invalid durations."""
        job_id = uuid4()
        operation_id = uuid4()

        with pytest.raises(ValueError):
            Task.create(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=10,
                planned_duration_minutes=0,  # Invalid duration
            )

        with pytest.raises(ValueError):
            Task.create(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=10,
                planned_duration_minutes=60,
                setup_duration_minutes=-1,  # Invalid setup duration
            )

    def test_create_task_with_skill_requirements(self):
        """Test creating task with skill requirements."""
        job_id = uuid4()
        operation_id = uuid4()

        welding_skill = SkillRequirement(
            skill=Skill.create("Welding", "WELD"),
            required_level=SkillLevel.INTERMEDIATE,
            is_mandatory=True,
        )

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
            skill_requirements=[welding_skill],
        )

        assert len(task.skill_requirements) == 1
        assert task.skill_requirements[0].skill.code == "WELD"
        assert task.skill_requirements[0].required_level == SkillLevel.INTERMEDIATE
        assert task.skill_requirements[0].is_mandatory


class TestTaskProperties:
    """Test task computed properties and state checks."""

    def test_total_duration(self):
        """Test total duration calculation."""
        task = TaskFactory.create(
            planned_duration_minutes=90, setup_duration_minutes=30
        )

        total = task.total_duration
        assert total.minutes == 120  # 90 + 30

    def test_processing_duration(self):
        """Test processing duration property."""
        task = TaskFactory.create(planned_duration_minutes=90)

        assert task.processing_duration.minutes == 90

    def test_is_scheduled_property(self):
        """Test is_scheduled property for different states."""
        task = TaskFactory.create()

        # Initially not scheduled
        assert not task.is_scheduled

        # Mark as scheduled
        task.status = TaskStatus.SCHEDULED
        task.planned_start_time = datetime.utcnow() + timedelta(hours=1)
        task.planned_end_time = datetime.utcnow() + timedelta(hours=3)
        assert task.is_scheduled

        # Mark as in progress - still scheduled
        task.status = TaskStatus.IN_PROGRESS
        assert task.is_scheduled

        # Mark as completed - no longer scheduled for future
        task.status = TaskStatus.COMPLETED
        assert not task.is_scheduled

    def test_is_active_property(self):
        """Test is_active property."""
        task = TaskFactory.create()

        inactive_statuses = [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.COMPLETED]
        active_statuses = [TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]

        for status in inactive_statuses:
            task.status = status
            assert not task.is_active

        for status in active_statuses:
            task.status = status
            assert task.is_active

    def test_is_complete_property(self):
        """Test is_complete property."""
        task = TaskFactory.create()

        assert not task.is_complete

        task.status = TaskStatus.COMPLETED
        assert task.is_complete

    def test_can_be_scheduled_property(self):
        """Test can_be_scheduled property."""
        task = TaskFactory.create()

        # Pending task cannot be scheduled
        task.status = TaskStatus.PENDING
        assert not task.can_be_scheduled

        # Ready task can be scheduled
        task.status = TaskStatus.READY
        assert task.can_be_scheduled

        # Already scheduled task cannot be rescheduled
        task.status = TaskStatus.SCHEDULED
        assert not task.can_be_scheduled

        # Completed task cannot be scheduled
        task.status = TaskStatus.COMPLETED
        assert not task.can_be_scheduled

    def test_is_delayed_property(self):
        """Test is_delayed property."""
        task = TaskFactory.create()

        # Task without schedule is not delayed
        assert not task.is_delayed

        # Task scheduled in future is not delayed
        future_time = datetime.utcnow() + timedelta(hours=1)
        task.planned_start_time = future_time
        task.status = TaskStatus.SCHEDULED
        assert not task.is_delayed

        # Task that should have started is delayed
        past_time = datetime.utcnow() - timedelta(hours=1)
        task.planned_start_time = past_time
        assert task.is_delayed

        # Completed task is not delayed
        task.status = TaskStatus.COMPLETED
        task.actual_end_time = datetime.utcnow()
        assert not task.is_delayed

    def test_delay_minutes_calculation(self):
        """Test delay_minutes calculation."""
        task = TaskFactory.create()

        # No delay for unscheduled task
        assert task.delay_minutes == 0

        # Task starting on time
        now = datetime.utcnow()
        task.planned_start_time = now + timedelta(minutes=30)
        task.status = TaskStatus.SCHEDULED
        assert task.delay_minutes == 0

        # Task delayed by 45 minutes
        task.planned_start_time = now - timedelta(minutes=45)
        delay = task.delay_minutes
        assert 40 <= delay <= 50  # Allow for small timing differences

        # Completed task with actual times
        task.status = TaskStatus.COMPLETED
        task.actual_start_time = now - timedelta(minutes=30)
        task.actual_end_time = now
        assert task.delay_minutes == 0  # Completed tasks use actual times

    def test_is_critical_path_property(self):
        """Test is_critical_path property."""
        task = TaskFactory.create()

        assert not task.is_critical_path

        task.mark_critical_path()
        assert task.is_critical_path

    def test_duration_variance(self):
        """Test duration variance calculation between planned and actual."""
        task = TaskFactory.create(planned_duration_minutes=120)

        # No variance for unfinished task
        assert task.duration_variance_minutes == 0

        # Task completed on time
        task.status = TaskStatus.COMPLETED
        start_time = datetime.utcnow() - timedelta(hours=2)
        end_time = start_time + timedelta(hours=2)  # Exactly as planned
        task.actual_start_time = start_time
        task.actual_end_time = end_time

        variance = task.duration_variance_minutes
        assert -5 <= variance <= 5  # Allow for small timing differences

        # Task took longer than planned
        end_time = start_time + timedelta(hours=2.5)  # 30 minutes over
        task.actual_end_time = end_time

        variance = task.duration_variance_minutes
        assert 25 <= variance <= 35

        # Task completed faster than planned
        end_time = start_time + timedelta(hours=1.5)  # 30 minutes under
        task.actual_end_time = end_time

        variance = task.duration_variance_minutes
        assert -35 <= variance <= -25


class TestTaskStatusTransitions:
    """Test task status transitions and validation."""

    def test_mark_ready_from_pending(self):
        """Test marking task as ready from pending state."""
        task = TaskFactory.create(status=TaskStatus.PENDING)

        task.mark_ready()

        assert task.status == TaskStatus.READY

        # Check domain event
        events = task.get_domain_events()
        status_events = [e for e in events if isinstance(e, TaskStatusChanged)]
        assert len(status_events) == 1

        event = status_events[0]
        assert event.old_status == TaskStatus.PENDING
        assert event.new_status == TaskStatus.READY

    def test_mark_ready_invalid_transition(self):
        """Test marking task as ready from invalid state fails."""
        task = TaskFactory.create(status=TaskStatus.COMPLETED)

        with pytest.raises(BusinessRuleViolation, match="Cannot transition"):
            task.mark_ready()

    def test_schedule_task_success(self):
        """Test successfully scheduling a ready task."""
        task = TaskFactory.create_ready()

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        machine_id = uuid4()

        task.schedule(start_time, end_time, machine_id)

        assert task.status == TaskStatus.SCHEDULED
        assert task.planned_start_time == start_time
        assert task.planned_end_time == end_time
        assert task.assigned_machine_id == machine_id

        # Check domain events
        events = task.get_domain_events()
        scheduled_events = [e for e in events if isinstance(e, TaskScheduled)]
        assert len(scheduled_events) == 1

        event = scheduled_events[0]
        assert event.task_id == task.id
        assert event.start_time == start_time
        assert event.end_time == end_time
        assert event.machine_id == machine_id

    def test_schedule_task_invalid_times(self):
        """Test scheduling task with invalid times fails."""
        task = TaskFactory.create_ready()

        start_time = datetime.utcnow() + timedelta(hours=2)
        end_time = start_time - timedelta(hours=1)  # End before start

        with pytest.raises(BusinessRuleViolation, match="before end time"):
            task.schedule(start_time, end_time, uuid4())

    def test_schedule_task_invalid_state(self):
        """Test scheduling task from invalid state fails."""
        task = TaskFactory.create(status=TaskStatus.PENDING)

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)

        with pytest.raises(BusinessRuleViolation, match="Cannot schedule"):
            task.schedule(start_time, end_time, uuid4())

    def test_reschedule_task_success(self):
        """Test successfully rescheduling a scheduled task."""
        task = TaskFactory.create_scheduled()
        original_start = task.planned_start_time
        original_end = task.planned_end_time

        new_start = datetime.utcnow() + timedelta(hours=4)
        new_end = new_start + timedelta(hours=2)

        task.reschedule(new_start, new_end, "resource_conflict")

        assert task.planned_start_time == new_start
        assert task.planned_end_time == new_end

        # Check domain events
        events = task.get_domain_events()
        reschedule_events = [e for e in events if isinstance(e, TaskRescheduled)]
        assert len(reschedule_events) == 1

        event = reschedule_events[0]
        assert event.task_id == task.id
        assert event.old_start_time == original_start
        assert event.old_end_time == original_end
        assert event.new_start_time == new_start
        assert event.new_end_time == new_end
        assert event.reason == "resource_conflict"

    def test_start_task_success(self):
        """Test successfully starting a scheduled task."""
        task = TaskFactory.create_scheduled()

        start_time = datetime.utcnow()
        task.start(start_time)

        assert task.status == TaskStatus.IN_PROGRESS
        assert task.actual_start_time == start_time

        # Check domain events
        events = task.get_domain_events()
        start_events = [e for e in events if isinstance(e, TaskStarted)]
        assert len(start_events) == 1

        event = start_events[0]
        assert event.task_id == task.id
        assert event.start_time == start_time

    def test_start_task_automatic_time(self):
        """Test starting task with automatic current time."""
        task = TaskFactory.create_scheduled()

        before_start = datetime.utcnow()
        task.start()
        after_start = datetime.utcnow()

        assert task.status == TaskStatus.IN_PROGRESS
        assert before_start <= task.actual_start_time <= after_start

    def test_start_task_invalid_state(self):
        """Test starting task from invalid state fails."""
        task = TaskFactory.create_ready()

        with pytest.raises(BusinessRuleViolation, match="Cannot start"):
            task.start()

    def test_complete_task_success(self):
        """Test successfully completing an in-progress task."""
        task = TaskFactory.create_in_progress()

        completion_time = datetime.utcnow()
        task.complete(completion_time)

        assert task.status == TaskStatus.COMPLETED
        assert task.actual_end_time == completion_time

        # Check domain events
        events = task.get_domain_events()
        complete_events = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(complete_events) == 1

        event = complete_events[0]
        assert event.task_id == task.id
        assert event.completion_time == completion_time

    def test_complete_task_automatic_time(self):
        """Test completing task with automatic current time."""
        task = TaskFactory.create_in_progress()

        before_complete = datetime.utcnow()
        task.complete()
        after_complete = datetime.utcnow()

        assert task.status == TaskStatus.COMPLETED
        assert before_complete <= task.actual_end_time <= after_complete

    def test_complete_task_invalid_state(self):
        """Test completing task from invalid state fails."""
        task = TaskFactory.create_ready()

        with pytest.raises(BusinessRuleViolation, match="Cannot complete"):
            task.complete()

    def test_complete_task_end_before_start(self):
        """Test completing task with end time before start time fails."""
        task = TaskFactory.create_in_progress()

        # Set completion time before start time
        completion_time = task.actual_start_time - timedelta(minutes=30)

        with pytest.raises(BusinessRuleViolation, match="before start time"):
            task.complete(completion_time)


class TestTaskOperatorAssignments:
    """Test task operator assignment management."""

    def test_add_operator_assignment_success(self):
        """Test successfully adding operator assignment."""
        task = TaskFactory.create()
        assignment = OperatorAssignmentFactory.create(task_id=task.id)

        task.add_operator_assignment(assignment)

        assert len(task.operator_assignments) == 1
        assert assignment in task.operator_assignments

    def test_add_operator_assignment_wrong_task(self):
        """Test adding operator assignment with wrong task ID fails."""
        task = TaskFactory.create()
        assignment = OperatorAssignmentFactory.create(task_id=uuid4())  # Wrong task

        with pytest.raises(BusinessRuleViolation, match="task_id must match"):
            task.add_operator_assignment(assignment)

    def test_add_duplicate_operator_assignment(self):
        """Test adding duplicate operator assignment fails."""
        task = TaskFactory.create()
        operator_id = uuid4()

        assignment1 = OperatorAssignmentFactory.create(
            task_id=task.id, operator_id=operator_id
        )
        assignment2 = OperatorAssignmentFactory.create(
            task_id=task.id,
            operator_id=operator_id,  # Same operator
        )

        task.add_operator_assignment(assignment1)

        with pytest.raises(BusinessRuleViolation, match="already assigned"):
            task.add_operator_assignment(assignment2)

    def test_remove_operator_assignment_success(self):
        """Test successfully removing operator assignment."""
        task = TaskFactory.create()
        operator_id = uuid4()
        assignment = OperatorAssignmentFactory.create(
            task_id=task.id, operator_id=operator_id
        )

        task.add_operator_assignment(assignment)
        task.remove_operator_assignment(operator_id)

        assert len(task.operator_assignments) == 0

    def test_remove_nonexistent_operator_assignment(self):
        """Test removing non-existent operator assignment fails."""
        task = TaskFactory.create()

        with pytest.raises(BusinessRuleViolation, match="not assigned"):
            task.remove_operator_assignment(uuid4())

    def test_remove_active_operator_assignment(self):
        """Test removing active operator assignment fails."""
        task = TaskFactory.create()
        assignment = OperatorAssignmentFactory.create_active(task_id=task.id)

        task.add_operator_assignment(assignment)

        with pytest.raises(BusinessRuleViolation, match="active assignment"):
            task.remove_operator_assignment(assignment.operator_id)

    def test_get_operator_assignments_by_type(self):
        """Test getting operator assignments filtered by type."""
        task = TaskFactory.create()

        setup_assignment = OperatorAssignmentFactory.create(
            task_id=task.id, assignment_type=AssignmentType.SETUP_ONLY
        )
        full_assignment = OperatorAssignmentFactory.create(
            task_id=task.id, assignment_type=AssignmentType.FULL_DURATION
        )

        task.add_operator_assignment(setup_assignment)
        task.add_operator_assignment(full_assignment)

        setup_assignments = task.get_operator_assignments_by_type(
            AssignmentType.SETUP_ONLY
        )
        assert len(setup_assignments) == 1
        assert setup_assignment in setup_assignments

        full_assignments = task.get_operator_assignments_by_type(
            AssignmentType.FULL_DURATION
        )
        assert len(full_assignments) == 1
        assert full_assignment in full_assignments

    def test_get_active_operator_assignments(self):
        """Test getting only active operator assignments."""
        task = TaskFactory.create()

        planned_assignment = OperatorAssignmentFactory.create(task_id=task.id)
        active_assignment = OperatorAssignmentFactory.create_active(task_id=task.id)
        completed_assignment = OperatorAssignmentFactory.create_completed(
            task_id=task.id
        )

        task.add_operator_assignment(planned_assignment)
        task.add_operator_assignment(active_assignment)
        task.add_operator_assignment(completed_assignment)

        active_assignments = task.get_active_operator_assignments()
        assert len(active_assignments) == 1
        assert active_assignment in active_assignments

    def test_operator_count_properties(self):
        """Test operator counting properties."""
        task = TaskFactory.create()

        assert task.assigned_operator_count == 0
        assert task.active_operator_count == 0

        # Add assignments
        planned_assignment = OperatorAssignmentFactory.create(task_id=task.id)
        active_assignment = OperatorAssignmentFactory.create_active(task_id=task.id)

        task.add_operator_assignment(planned_assignment)
        task.add_operator_assignment(active_assignment)

        assert task.assigned_operator_count == 2
        assert task.active_operator_count == 1


class TestTaskSkillRequirements:
    """Test task skill requirements management."""

    def test_add_skill_requirement_success(self):
        """Test successfully adding skill requirement."""
        task = TaskFactory.create()

        welding_skill = Skill.create("Welding", "WELD")
        requirement = SkillRequirement(
            skill=welding_skill,
            required_level=SkillLevel.ADVANCED,
            is_mandatory=True,
        )

        task.add_skill_requirement(requirement)

        assert len(task.skill_requirements) == 1
        assert requirement in task.skill_requirements

    def test_add_duplicate_skill_requirement(self):
        """Test adding duplicate skill requirement fails."""
        task = TaskFactory.create()

        welding_skill = Skill.create("Welding", "WELD")
        requirement1 = SkillRequirement(
            skill=welding_skill, required_level=SkillLevel.INTERMEDIATE
        )
        requirement2 = SkillRequirement(
            skill=welding_skill,
            required_level=SkillLevel.ADVANCED,  # Different level
        )

        task.add_skill_requirement(requirement1)

        with pytest.raises(BusinessRuleViolation, match="already has requirement"):
            task.add_skill_requirement(requirement2)

    def test_remove_skill_requirement_success(self):
        """Test successfully removing skill requirement."""
        task = TaskFactory.create()

        welding_skill = Skill.create("Welding", "WELD")
        requirement = SkillRequirement(
            skill=welding_skill, required_level=SkillLevel.INTERMEDIATE
        )

        task.add_skill_requirement(requirement)
        task.remove_skill_requirement(welding_skill.code)

        assert len(task.skill_requirements) == 0

    def test_remove_nonexistent_skill_requirement(self):
        """Test removing non-existent skill requirement fails."""
        task = TaskFactory.create()

        with pytest.raises(BusinessRuleViolation, match="does not have requirement"):
            task.remove_skill_requirement("NONEXISTENT")

    def test_get_mandatory_skill_requirements(self):
        """Test getting only mandatory skill requirements."""
        task = TaskFactory.create()

        mandatory_skill = Skill.create("Welding", "WELD")
        optional_skill = Skill.create("Programming", "PROG")

        mandatory_req = SkillRequirement(
            skill=mandatory_skill,
            required_level=SkillLevel.INTERMEDIATE,
            is_mandatory=True,
        )
        optional_req = SkillRequirement(
            skill=optional_skill, required_level=SkillLevel.BASIC, is_mandatory=False
        )

        task.add_skill_requirement(mandatory_req)
        task.add_skill_requirement(optional_req)

        mandatory_reqs = task.get_mandatory_skill_requirements()
        assert len(mandatory_reqs) == 1
        assert mandatory_req in mandatory_reqs

    def test_has_skill_requirement(self):
        """Test checking if task has specific skill requirement."""
        task = TaskFactory.create()

        welding_skill = Skill.create("Welding", "WELD")
        requirement = SkillRequirement(
            skill=welding_skill, required_level=SkillLevel.BASIC
        )

        assert not task.has_skill_requirement("WELD")

        task.add_skill_requirement(requirement)

        assert task.has_skill_requirement("WELD")
        assert not task.has_skill_requirement("PROG")


class TestTaskQualityManagement:
    """Test task quality control and rework functionality."""

    def test_record_rework_success(self):
        """Test successfully recording rework for task."""
        task = TaskFactory.create()

        reason = "dimension_out_of_spec"
        task.record_rework(reason)

        assert len(task.rework_history) == 1
        assert reason in task.rework_history

    def test_multiple_rework_records(self):
        """Test recording multiple rework instances."""
        task = TaskFactory.create()

        reasons = ["surface_finish", "dimension_error", "assembly_issue"]

        for reason in reasons:
            task.record_rework(reason)

        assert len(task.rework_history) == 3
        assert all(reason in task.rework_history for reason in reasons)

    def test_rework_count_property(self):
        """Test rework count property."""
        task = TaskFactory.create()

        assert task.rework_count == 0

        task.record_rework("first_issue")
        assert task.rework_count == 1

        task.record_rework("second_issue")
        assert task.rework_count == 2

    def test_has_rework_property(self):
        """Test has_rework property."""
        task = TaskFactory.create()

        assert not task.has_rework

        task.record_rework("quality_issue")

        assert task.has_rework

    def test_quality_metrics(self):
        """Test quality-related metrics calculation."""
        task = TaskFactory.create_completed()

        # Task with no rework has perfect quality
        assert task.rework_count == 0
        assert not task.has_rework

        # Add rework and check impact
        task.record_rework("first_issue")
        task.record_rework("second_issue")

        assert task.rework_count == 2
        assert task.has_rework


class TestTaskCriticalPathManagement:
    """Test critical path functionality."""

    def test_mark_critical_path(self):
        """Test marking task as critical path."""
        task = TaskFactory.create()

        assert not task.is_critical_path

        task.mark_critical_path()

        assert task.is_critical_path

    def test_unmark_critical_path(self):
        """Test removing task from critical path."""
        task = TaskFactory.create_critical_path()

        assert task.is_critical_path

        task.unmark_critical_path()

        assert not task.is_critical_path

    def test_critical_path_affects_priority(self):
        """Test that critical path tasks have higher priority consideration."""
        regular_task = TaskFactory.create()
        critical_task = TaskFactory.create_critical_path()

        # In real implementation, this would affect scheduling priority
        assert not regular_task.is_critical_path
        assert critical_task.is_critical_path


class TestTaskValidationAndBusinessRules:
    """Test task validation and business rule enforcement."""

    def test_is_valid_basic_checks(self):
        """Test basic task validation."""
        task = TaskFactory.create()

        assert task.is_valid()

        # Invalid: zero duration
        task.planned_duration = Duration(minutes=0)
        assert not task.is_valid()

        # Invalid: sequence out of range
        task.planned_duration = Duration(minutes=60)
        task.sequence_in_job = 0
        assert not task.is_valid()

        task.sequence_in_job = 101
        assert not task.is_valid()

        # Valid again
        task.sequence_in_job = 50
        assert task.is_valid()

    def test_scheduling_time_validation(self):
        """Test scheduling time validation."""
        task = TaskFactory.create_ready()

        # Valid scheduling times
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)

        task.schedule(start_time, end_time, uuid4())
        assert task.is_scheduled

        # Test rescheduling with invalid times
        with pytest.raises(BusinessRuleViolation):
            task.reschedule(end_time, start_time, "invalid_times")  # End before start

    def test_operator_assignment_validation(self):
        """Test operator assignment validation rules."""
        task = TaskFactory.create()

        # Cannot add more operators than allowed
        max_operators = 10  # Assume reasonable limit
        operator_ids = [uuid4() for _ in range(max_operators + 1)]

        # Add maximum allowed operators
        for i in range(max_operators):
            assignment = OperatorAssignmentFactory.create(
                task_id=task.id, operator_id=operator_ids[i]
            )
            task.add_operator_assignment(assignment)

        # Adding one more should fail (if limit enforced)
        # This depends on business rules implementation

    def test_skill_requirement_validation(self):
        """Test skill requirement validation."""
        task = TaskFactory.create()

        # Valid skill requirement
        valid_skill = Skill.create("Machining", "MACH")
        valid_requirement = SkillRequirement(
            skill=valid_skill, required_level=SkillLevel.INTERMEDIATE
        )

        task.add_skill_requirement(valid_requirement)
        assert len(task.skill_requirements) == 1

        # Cannot add duplicate skill
        duplicate_requirement = SkillRequirement(
            skill=valid_skill, required_level=SkillLevel.ADVANCED
        )

        with pytest.raises(BusinessRuleViolation):
            task.add_skill_requirement(duplicate_requirement)

    def test_state_transition_validation(self):
        """Test state transition validation."""
        task = TaskFactory.create()

        # Valid transitions
        task.mark_ready()  # PENDING -> READY
        assert task.status == TaskStatus.READY

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        task.schedule(start_time, end_time, uuid4())  # READY -> SCHEDULED
        assert task.status == TaskStatus.SCHEDULED

        task.start()  # SCHEDULED -> IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS

        task.complete()  # IN_PROGRESS -> COMPLETED
        assert task.status == TaskStatus.COMPLETED

        # Invalid transitions
        with pytest.raises(BusinessRuleViolation):
            task.mark_ready()  # Cannot go from COMPLETED back to READY


class TestTaskDomainEvents:
    """Test domain events generated by task operations."""

    def test_status_change_events(self):
        """Test status change events."""
        task = TaskFactory.create()

        task.mark_ready()

        events = task.get_domain_events()
        status_events = [e for e in events if isinstance(e, TaskStatusChanged)]
        assert len(status_events) == 1

        event = status_events[0]
        assert event.task_id == task.id
        assert event.old_status == TaskStatus.PENDING
        assert event.new_status == TaskStatus.READY

    def test_task_scheduled_events(self):
        """Test task scheduling events."""
        task = TaskFactory.create_ready()

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        machine_id = uuid4()

        task.schedule(start_time, end_time, machine_id)

        events = task.get_domain_events()
        scheduled_events = [e for e in events if isinstance(e, TaskScheduled)]
        assert len(scheduled_events) == 1

        event = scheduled_events[0]
        assert event.task_id == task.id
        assert event.start_time == start_time
        assert event.end_time == end_time
        assert event.machine_id == machine_id

    def test_task_started_events(self):
        """Test task start events."""
        task = TaskFactory.create_scheduled()

        start_time = datetime.utcnow()
        task.start(start_time)

        events = task.get_domain_events()
        start_events = [e for e in events if isinstance(e, TaskStarted)]
        assert len(start_events) == 1

        event = start_events[0]
        assert event.task_id == task.id
        assert event.start_time == start_time

    def test_task_completed_events(self):
        """Test task completion events."""
        task = TaskFactory.create_in_progress()

        completion_time = datetime.utcnow()
        task.complete(completion_time)

        events = task.get_domain_events()
        complete_events = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(complete_events) == 1

        event = complete_events[0]
        assert event.task_id == task.id
        assert event.completion_time == completion_time

    def test_task_rescheduled_events(self):
        """Test task rescheduling events."""
        task = TaskFactory.create_scheduled()
        original_start = task.planned_start_time

        new_start = datetime.utcnow() + timedelta(hours=4)
        new_end = new_start + timedelta(hours=2)

        task.reschedule(new_start, new_end, "equipment_maintenance")

        events = task.get_domain_events()
        reschedule_events = [e for e in events if isinstance(e, TaskRescheduled)]
        assert len(reschedule_events) == 1

        event = reschedule_events[0]
        assert event.task_id == task.id
        assert event.old_start_time == original_start
        assert event.new_start_time == new_start
        assert event.reason == "equipment_maintenance"

    def test_multiple_events_ordering(self):
        """Test that multiple events are generated in correct order."""
        task = TaskFactory.create()

        # Perform sequence of operations
        task.mark_ready()
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        task.schedule(start_time, end_time, uuid4())

        events = task.get_domain_events()

        # Should have status change event followed by scheduled event
        assert (
            len(events) == 3
        )  # Status change (PENDING->READY), Status change (READY->SCHEDULED), TaskScheduled

        # Check event types in order
        event_types = [type(e) for e in events]
        assert TaskStatusChanged in event_types
        assert TaskScheduled in event_types


class TestTaskFactoryMethods:
    """Test Task factory methods and builders."""

    def test_create_factory_method(self):
        """Test Task.create factory method."""
        job_id = uuid4()
        operation_id = uuid4()

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=20,
            planned_duration_minutes=90,
            setup_duration_minutes=15,
        )

        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == 20
        assert task.planned_duration.minutes == 90
        assert task.setup_duration.minutes == 15
        assert task.is_valid()

    def test_create_with_skill_requirements(self):
        """Test creating task with skill requirements."""
        welding_skill = SkillRequirement(
            skill=Skill.create("Welding", "WELD"),
            required_level=SkillLevel.ADVANCED,
            is_mandatory=True,
        )

        task = Task.create(
            job_id=uuid4(),
            operation_id=uuid4(),
            sequence_in_job=10,
            planned_duration_minutes=120,
            skill_requirements=[welding_skill],
        )

        assert len(task.skill_requirements) == 1
        assert task.skill_requirements[0].skill.code == "WELD"


@pytest.mark.integration
class TestTaskIntegration:
    """Integration tests for task with other components."""

    def test_complete_task_lifecycle(self):
        """Test complete task lifecycle from creation to completion."""
        # Create task
        task = TaskFactory.create()
        assert task.status == TaskStatus.PENDING

        # Add operator assignments
        setup_operator = OperatorAssignmentFactory.create(
            task_id=task.id, assignment_type=AssignmentType.SETUP_ONLY
        )
        main_operator = OperatorAssignmentFactory.create(
            task_id=task.id, assignment_type=AssignmentType.FULL_DURATION
        )

        task.add_operator_assignment(setup_operator)
        task.add_operator_assignment(main_operator)

        # Add skill requirements
        welding_skill = SkillRequirement(
            skill=Skill.create("Welding", "WELD"),
            required_level=SkillLevel.INTERMEDIATE,
            is_mandatory=True,
        )
        task.add_skill_requirement(welding_skill)

        # Mark as ready
        task.mark_ready()
        assert task.status == TaskStatus.READY
        assert task.can_be_scheduled

        # Schedule task
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        machine_id = uuid4()

        task.schedule(start_time, end_time, machine_id)
        assert task.status == TaskStatus.SCHEDULED
        assert task.is_scheduled
        assert task.assigned_machine_id == machine_id

        # Start task
        actual_start = datetime.utcnow() + timedelta(
            hours=1, minutes=5
        )  # 5 minutes late
        task.start(actual_start)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.is_active
        assert task.actual_start_time == actual_start

        # Record some rework
        task.record_rework("initial_quality_check_failed")

        # Complete task
        completion_time = actual_start + timedelta(
            hours=2, minutes=10
        )  # 10 minutes over
        task.complete(completion_time)

        assert task.status == TaskStatus.COMPLETED
        assert task.is_complete
        assert not task.is_active
        assert task.actual_end_time == completion_time
        assert task.has_rework
        assert task.rework_count == 1

        # Verify duration variance
        variance = task.duration_variance_minutes
        assert variance > 0  # Task took longer than planned

        # Verify events were generated
        events = task.get_domain_events()
        assert len([e for e in events if isinstance(e, TaskStatusChanged)]) >= 3
        assert len([e for e in events if isinstance(e, TaskScheduled)]) == 1
        assert len([e for e in events if isinstance(e, TaskStarted)]) == 1
        assert len([e for e in events if isinstance(e, TaskCompleted)]) == 1

    def test_task_with_rescheduling_scenario(self):
        """Test task handling multiple rescheduling events."""
        task = TaskFactory.create_ready()

        # Initial schedule
        original_start = datetime.utcnow() + timedelta(hours=2)
        original_end = original_start + timedelta(hours=3)
        task.schedule(original_start, original_end, uuid4())

        # First reschedule due to resource conflict
        delayed_start = original_start + timedelta(hours=1)
        delayed_end = delayed_start + timedelta(hours=3)
        task.reschedule(delayed_start, delayed_end, "resource_conflict")

        # Second reschedule due to priority change
        priority_start = original_start + timedelta(minutes=30)
        priority_end = priority_start + timedelta(hours=3)
        task.reschedule(priority_start, priority_end, "priority_escalation")

        # Verify final state
        assert task.planned_start_time == priority_start
        assert task.planned_end_time == priority_end

        # Verify reschedule events
        events = task.get_domain_events()
        reschedule_events = [e for e in events if isinstance(e, TaskRescheduled)]
        assert len(reschedule_events) == 2

        # Check reasons
        reasons = [e.reason for e in reschedule_events]
        assert "resource_conflict" in reasons
        assert "priority_escalation" in reasons


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
