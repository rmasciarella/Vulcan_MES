"""
Unit tests for scheduling domain events.

Tests domain event creation, validation, dispatcher functionality,
and event propagation patterns.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.events.domain_events import (
    ConstraintViolated,
    CriticalPathChanged,
    DeadlineMissed,
    DomainEvent,
    DomainEventDispatcher,
    DomainEventHandler,
    JobCompleted,
    JobCreated,
    JobDelayed,
    JobStatusChanged,
    MachineAllocated,
    MachineReleased,
    MachineStatusChanged,
    MaintenanceScheduled,
    OperatorAssigned,
    OperatorReleased,
    OperatorStatusChanged,
    PriorityChanged,
    ResourceConflictDetected,
    SchedulePublished,
    ScheduleUpdated,
    SkillRequirementNotMet,
    TaskAssignmentChanged,
    TaskCompleted,
    TaskDelayed,
    TaskScheduled,
    TaskStarted,
    TaskStatusChanged,
    get_event_dispatcher,
    publish_event,
    publish_events,
)
from app.domain.scheduling.value_objects.duration import Duration


class TestDomainEventBase:
    """Test base domain event functionality."""

    def test_domain_event_creation(self):
        """Test basic domain event creation with automatic fields."""
        event = DomainEvent()
        
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.aggregate_id is None

    def test_domain_event_with_aggregate_id(self):
        """Test domain event creation with aggregate ID."""
        aggregate_id = uuid4()
        event = DomainEvent(aggregate_id=aggregate_id)
        
        assert event.aggregate_id == aggregate_id

    def test_domain_event_immutability(self):
        """Test that domain events are immutable (frozen dataclass)."""
        event = DomainEvent()
        
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            event.event_id = uuid4()  # type: ignore

    def test_domain_event_custom_fields(self):
        """Test domain event with custom event ID and timestamp."""
        custom_id = uuid4()
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        
        event = DomainEvent(event_id=custom_id, occurred_at=custom_time)
        
        assert event.event_id == custom_id
        assert event.occurred_at == custom_time


class TestTaskEvents:
    """Test task-related domain events."""

    @pytest.fixture
    def task_ids(self):
        """Provide test UUIDs for tasks and related entities."""
        return {
            'task_id': uuid4(),
            'job_id': uuid4(),
            'machine_id': uuid4(),
            'operator_id1': uuid4(),
            'operator_id2': uuid4(),
        }

    def test_task_scheduled_event_creation(self, task_ids):
        """Test TaskScheduled event creation and fields."""
        planned_start = datetime.now()
        planned_end = planned_start + timedelta(hours=2)
        
        event = TaskScheduled(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            machine_id=task_ids['machine_id'],
            operator_ids=[task_ids['operator_id1'], task_ids['operator_id2']],
            planned_start=planned_start,
            planned_end=planned_end
        )
        
        assert event.task_id == task_ids['task_id']
        assert event.job_id == task_ids['job_id']
        assert event.machine_id == task_ids['machine_id']
        assert len(event.operator_ids) == 2
        assert event.planned_start == planned_start
        assert event.planned_end == planned_end
        assert event.event_id is not None
        assert event.occurred_at is not None

    def test_task_started_event(self, task_ids):
        """Test TaskStarted event creation."""
        actual_start = datetime.now()
        
        event = TaskStarted(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            actual_start=actual_start,
            machine_id=task_ids['machine_id'],
            operator_ids=[task_ids['operator_id1']]
        )
        
        assert event.task_id == task_ids['task_id']
        assert event.actual_start == actual_start

    def test_task_completed_event(self, task_ids):
        """Test TaskCompleted event creation."""
        actual_end = datetime.now()
        duration = Duration(minutes=120)
        
        event = TaskCompleted(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            actual_end=actual_end,
            actual_duration=duration
        )
        
        assert event.task_id == task_ids['task_id']
        assert event.actual_end == actual_end
        assert event.actual_duration == duration

    def test_task_status_changed_event(self, task_ids):
        """Test TaskStatusChanged event creation."""
        event = TaskStatusChanged(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            operation_sequence=1,
            old_status="SCHEDULED",
            new_status="IN_PROGRESS",
            reason="task_started"
        )
        
        assert event.task_id == task_ids['task_id']
        assert event.operation_sequence == 1
        assert event.old_status == "SCHEDULED"
        assert event.new_status == "IN_PROGRESS"
        assert event.reason == "task_started"

    def test_task_assignment_changed_event(self, task_ids):
        """Test TaskAssignmentChanged event creation."""
        event = TaskAssignmentChanged(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            operation_sequence=2,
            old_machine_id=None,
            new_machine_id=task_ids['machine_id'],
            operator_assignments=[task_ids['operator_id1']],
            reason="task_scheduled"
        )
        
        assert event.old_machine_id is None
        assert event.new_machine_id == task_ids['machine_id']
        assert len(event.operator_assignments) == 1

    def test_task_delayed_event(self, task_ids):
        """Test TaskDelayed event creation."""
        original_start = datetime(2024, 1, 1, 9, 0, 0)
        new_start = datetime(2024, 1, 1, 10, 30, 0)
        
        event = TaskDelayed(
            task_id=task_ids['task_id'],
            job_id=task_ids['job_id'],
            operation_sequence=1,
            original_planned_start=original_start,
            new_planned_start=new_start,
            delay_minutes=90,
            reason="resource_constraints"
        )
        
        assert event.original_planned_start == original_start
        assert event.new_planned_start == new_start
        assert event.delay_minutes == 90
        assert event.reason == "resource_constraints"


class TestJobEvents:
    """Test job-related domain events."""

    @pytest.fixture
    def job_data(self):
        """Provide test data for job events."""
        return {
            'job_id': uuid4(),
            'job_number': 'JOB-2024-001',
            'priority': 1,
            'due_date': datetime(2024, 12, 31, 23, 59, 59),
            'release_date': datetime(2024, 1, 1, 0, 0, 0),
        }

    def test_job_created_event(self, job_data):
        """Test JobCreated event creation."""
        event = JobCreated(
            job_id=job_data['job_id'],
            job_number=job_data['job_number'],
            priority=job_data['priority'],
            due_date=job_data['due_date'],
            release_date=job_data['release_date'],
            task_count=5
        )
        
        assert event.job_id == job_data['job_id']
        assert event.job_number == job_data['job_number']
        assert event.priority == job_data['priority']
        assert event.task_count == 5

    def test_job_status_changed_event(self, job_data):
        """Test JobStatusChanged event creation."""
        event = JobStatusChanged(
            job_id=job_data['job_id'],
            job_number=job_data['job_number'],
            old_status="PENDING",
            new_status="IN_PROGRESS",
            reason="first_task_started"
        )
        
        assert event.old_status == "PENDING"
        assert event.new_status == "IN_PROGRESS"
        assert event.reason == "first_task_started"

    def test_job_completed_event(self, job_data):
        """Test JobCompleted event creation."""
        completion_time = datetime.now()
        planned_completion = completion_time - timedelta(hours=2)
        actual_duration = Duration(hours=48)
        
        event = JobCompleted(
            job_id=job_data['job_id'],
            job_number=job_data['job_number'],
            completion_time=completion_time,
            planned_completion=planned_completion,
            actual_duration=actual_duration,
            delay_hours=Decimal("2.0")
        )
        
        assert event.completion_time == completion_time
        assert event.actual_duration == actual_duration
        assert event.delay_hours == Decimal("2.0")

    def test_job_delayed_event(self, job_data):
        """Test JobDelayed event creation."""
        expected_completion = job_data['due_date'] + timedelta(hours=8)
        
        event = JobDelayed(
            job_id=job_data['job_id'],
            original_due_date=job_data['due_date'],
            expected_completion=expected_completion,
            delay_hours=Decimal("8.0")
        )
        
        assert event.original_due_date == job_data['due_date']
        assert event.expected_completion == expected_completion
        assert event.delay_hours == Decimal("8.0")


class TestResourceEvents:
    """Test resource-related domain events."""

    @pytest.fixture
    def resource_ids(self):
        """Provide test UUIDs for resources."""
        return {
            'machine_id': uuid4(),
            'operator_id': uuid4(),
            'task_id': uuid4(),
            'job_id': uuid4(),
        }

    def test_operator_assigned_event(self, resource_ids):
        """Test OperatorAssigned event creation."""
        event = OperatorAssigned(
            operator_id=resource_ids['operator_id'],
            task_id=resource_ids['task_id'],
            assignment_type="full_duration"
        )
        
        assert event.operator_id == resource_ids['operator_id']
        assert event.task_id == resource_ids['task_id']
        assert event.assignment_type == "full_duration"

    def test_operator_released_event(self, resource_ids):
        """Test OperatorReleased event creation."""
        event = OperatorReleased(
            operator_id=resource_ids['operator_id'],
            task_id=resource_ids['task_id']
        )
        
        assert event.operator_id == resource_ids['operator_id']
        assert event.task_id == resource_ids['task_id']

    def test_machine_allocated_event(self, resource_ids):
        """Test MachineAllocated event creation."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=4)
        
        event = MachineAllocated(
            machine_id=resource_ids['machine_id'],
            task_id=resource_ids['task_id'],
            job_id=resource_ids['job_id'],
            allocation_start=start_time,
            allocation_end=end_time
        )
        
        assert event.allocation_start == start_time
        assert event.allocation_end == end_time

    def test_machine_released_event(self, resource_ids):
        """Test MachineReleased event creation."""
        release_time = datetime.now()
        
        event = MachineReleased(
            machine_id=resource_ids['machine_id'],
            task_id=resource_ids['task_id'],
            job_id=resource_ids['job_id'],
            release_time=release_time,
            utilization_hours=Decimal("3.5")
        )
        
        assert event.release_time == release_time
        assert event.utilization_hours == Decimal("3.5")

    def test_resource_conflict_detected_event(self, resource_ids):
        """Test ResourceConflictDetected event creation."""
        conflict_start = datetime.now()
        conflict_end = conflict_start + timedelta(minutes=30)
        conflicting_tasks = [uuid4(), uuid4()]
        
        event = ResourceConflictDetected(
            resource_type="machine",
            resource_id=resource_ids['machine_id'],
            conflicting_tasks=conflicting_tasks,
            conflict_time_start=conflict_start,
            conflict_time_end=conflict_end
        )
        
        assert event.resource_type == "machine"
        assert len(event.conflicting_tasks) == 2
        assert event.conflict_time_start == conflict_start


class TestScheduleEvents:
    """Test schedule-related domain events."""

    def test_schedule_published_event(self):
        """Test SchedulePublished event creation."""
        schedule_id = uuid4()
        effective_date = datetime.now()
        
        event = SchedulePublished(
            schedule_id=schedule_id,
            version=1,
            effective_date=effective_date,
            task_count=25,
            makespan_hours=Decimal("72.5")
        )
        
        assert event.schedule_id == schedule_id
        assert event.version == 1
        assert event.task_count == 25
        assert event.makespan_hours == Decimal("72.5")

    def test_schedule_updated_event(self):
        """Test ScheduleUpdated event creation."""
        schedule_id = uuid4()
        affected_tasks = [uuid4(), uuid4(), uuid4()]
        
        event = ScheduleUpdated(
            schedule_id=schedule_id,
            old_version=1,
            new_version=2,
            changes_description="Resource reallocation for tasks 5-7",
            affected_tasks=affected_tasks
        )
        
        assert event.old_version == 1
        assert event.new_version == 2
        assert len(event.affected_tasks) == 3


class TestConstraintAndViolationEvents:
    """Test constraint and violation domain events."""

    def test_constraint_violated_event(self):
        """Test ConstraintViolated event creation."""
        violated_by = uuid4()
        
        event = ConstraintViolated(
            constraint_type="precedence_constraint",
            constraint_description="Task B must start after Task A completes",
            violated_by=violated_by,
            violation_details="Task B started before Task A completion"
        )
        
        assert event.constraint_type == "precedence_constraint"
        assert event.violated_by == violated_by

    def test_critical_path_changed_event(self):
        """Test CriticalPathChanged event creation."""
        job_id = uuid4()
        old_tasks = [uuid4(), uuid4()]
        new_tasks = [uuid4(), uuid4(), uuid4()]
        
        event = CriticalPathChanged(
            job_id=job_id,
            old_critical_tasks=old_tasks,
            new_critical_tasks=new_tasks,
            new_makespan_hours=Decimal("80.0")
        )
        
        assert event.job_id == job_id
        assert len(event.old_critical_tasks) == 2
        assert len(event.new_critical_tasks) == 3

    def test_deadline_missed_event(self):
        """Test DeadlineMissed event creation."""
        job_id = uuid4()
        original_due = datetime(2024, 1, 15, 17, 0, 0)
        actual_completion = datetime(2024, 1, 16, 9, 0, 0)
        
        event = DeadlineMissed(
            job_id=job_id,
            job_number="JOB-2024-005",
            original_due_date=original_due,
            actual_completion=actual_completion,
            delay_hours=Decimal("16.0"),
            contributing_factors=["machine_breakdown", "operator_shortage"]
        )
        
        assert event.delay_hours == Decimal("16.0")
        assert len(event.contributing_factors) == 2

    def test_skill_requirement_not_met_event(self):
        """Test SkillRequirementNotMet event creation."""
        operator_id = uuid4()
        task_id = uuid4()
        
        event = SkillRequirementNotMet(
            operator_id=operator_id,
            task_id=task_id,
            required_skill="welding",
            required_level=3,
            operator_level=2
        )
        
        assert event.operator_id == operator_id
        assert event.required_skill == "welding"
        assert event.required_level == 3
        assert event.operator_level == 2


class TestMaintenanceEvents:
    """Test maintenance-related domain events."""

    def test_maintenance_scheduled_event(self):
        """Test MaintenanceScheduled event creation."""
        machine_id = uuid4()
        maintenance_start = datetime.now() + timedelta(days=1)
        maintenance_end = maintenance_start + timedelta(hours=4)
        affected_tasks = [uuid4(), uuid4()]
        
        event = MaintenanceScheduled(
            machine_id=machine_id,
            machine_name="CNC-Machine-01",
            maintenance_start=maintenance_start,
            maintenance_end=maintenance_end,
            maintenance_type="preventive",
            affected_tasks=affected_tasks
        )
        
        assert event.machine_name == "CNC-Machine-01"
        assert event.maintenance_type == "preventive"
        assert len(event.affected_tasks) == 2


class TestPriorityEvents:
    """Test priority change events."""

    def test_priority_changed_event(self):
        """Test PriorityChanged event creation."""
        entity_id = uuid4()
        
        event = PriorityChanged(
            entity_type="job",
            entity_id=entity_id,
            old_priority=3,
            new_priority=1,
            reason="customer_escalation"
        )
        
        assert event.entity_type == "job"
        assert event.old_priority == 3
        assert event.new_priority == 1
        assert event.reason == "customer_escalation"


class TestDomainEventDispatcher:
    """Test domain event dispatcher functionality."""

    def test_dispatcher_creation(self):
        """Test creating a new event dispatcher."""
        dispatcher = DomainEventDispatcher()
        assert dispatcher._handlers == []

    def test_register_handler(self):
        """Test registering event handlers."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        dispatcher.register_handler(handler)
        assert handler in dispatcher._handlers

    def test_register_duplicate_handler(self):
        """Test that duplicate handlers are not added."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        dispatcher.register_handler(handler)
        dispatcher.register_handler(handler)  # Duplicate
        
        assert dispatcher._handlers.count(handler) == 1

    def test_unregister_handler(self):
        """Test unregistering event handlers."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        dispatcher.register_handler(handler)
        assert handler in dispatcher._handlers
        
        dispatcher.unregister_handler(handler)
        assert handler not in dispatcher._handlers

    def test_unregister_nonexistent_handler(self):
        """Test unregistering handler that doesn't exist."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        # Should not raise exception
        dispatcher.unregister_handler(handler)

    def test_dispatch_event_to_capable_handler(self):
        """Test dispatching event to handlers that can handle it."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        dispatcher.register_handler(handler)
        
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        dispatcher.dispatch(event)
        
        assert handler.handled_events == [event]

    def test_dispatch_event_to_multiple_handlers(self):
        """Test dispatching event to multiple capable handlers."""
        dispatcher = DomainEventDispatcher()
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()
        
        dispatcher.register_handler(handler1)
        dispatcher.register_handler(handler2)
        
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=60)
        )
        
        dispatcher.dispatch(event)
        
        assert handler1.handled_events == [event]
        assert handler2.handled_events == [event]

    def test_dispatch_event_to_incapable_handler(self):
        """Test dispatching event to handlers that cannot handle it."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler(can_handle_result=False)
        
        dispatcher.register_handler(handler)
        
        event = JobCreated(
            job_id=uuid4(),
            job_number="TEST-001",
            priority=1,
            due_date=None,
            release_date=datetime.now(),
            task_count=3
        )
        
        dispatcher.dispatch(event)
        
        assert handler.handled_events == []

    def test_dispatch_all_events(self):
        """Test dispatching multiple events."""
        dispatcher = DomainEventDispatcher()
        handler = MockEventHandler()
        
        dispatcher.register_handler(handler)
        
        events = [
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[uuid4()]
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_end=datetime.now(),
                actual_duration=Duration(minutes=30)
            )
        ]
        
        dispatcher.dispatch_all(events)
        
        assert len(handler.handled_events) == 2
        assert handler.handled_events == events

    def test_handler_exception_handling(self):
        """Test that handler exceptions don't stop other handlers."""
        dispatcher = DomainEventDispatcher()
        failing_handler = MockEventHandler(should_fail=True)
        working_handler = MockEventHandler()
        
        dispatcher.register_handler(failing_handler)
        dispatcher.register_handler(working_handler)
        
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        # Should not raise exception
        dispatcher.dispatch(event)
        
        # Working handler should still receive the event
        assert working_handler.handled_events == [event]


class TestGlobalEventFunctions:
    """Test global event dispatcher functions."""

    def test_get_event_dispatcher_singleton(self):
        """Test that get_event_dispatcher returns the same instance."""
        dispatcher1 = get_event_dispatcher()
        dispatcher2 = get_event_dispatcher()
        
        assert dispatcher1 is dispatcher2

    def test_publish_event_function(self):
        """Test publish_event convenience function."""
        # Clear any existing handlers
        dispatcher = get_event_dispatcher()
        dispatcher._handlers.clear()
        
        handler = MockEventHandler()
        dispatcher.register_handler(handler)
        
        event = JobStatusChanged(
            job_id=uuid4(),
            job_number="TEST-002",
            old_status="PENDING",
            new_status="ACTIVE",
            reason="scheduled"
        )
        
        publish_event(event)
        
        assert handler.handled_events == [event]

    def test_publish_events_function(self):
        """Test publish_events convenience function."""
        # Clear any existing handlers
        dispatcher = get_event_dispatcher()
        dispatcher._handlers.clear()
        
        handler = MockEventHandler()
        dispatcher.register_handler(handler)
        
        events = [
            TaskStatusChanged(
                task_id=uuid4(),
                job_id=uuid4(),
                operation_sequence=1,
                old_status="READY",
                new_status="SCHEDULED",
                reason="resource_assigned"
            ),
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[]
            )
        ]
        
        publish_events(events)
        
        assert len(handler.handled_events) == 2


class MockEventHandler(DomainEventHandler):
    """Mock event handler for testing."""
    
    def __init__(self, can_handle_result: bool = True, should_fail: bool = False):
        self.can_handle_result = can_handle_result
        self.should_fail = should_fail
        self.handled_events: List[DomainEvent] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        return self.can_handle_result
    
    def handle(self, event: DomainEvent) -> None:
        if self.should_fail:
            raise RuntimeError("Mock handler failure")
        self.handled_events.append(event)


class TestEventFieldValidation:
    """Test event field validation and edge cases."""

    def test_event_with_empty_operator_list(self):
        """Test events with empty operator lists."""
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[],  # Empty list
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        assert event.operator_ids == []

    def test_event_with_none_values(self):
        """Test events with None values where allowed."""
        event = JobCreated(
            job_id=uuid4(),
            job_number="TEST-003",
            priority=2,
            due_date=None,  # None allowed
            release_date=datetime.now(),
            task_count=1
        )
        
        assert event.due_date is None

    def test_event_timestamp_ordering(self):
        """Test that events created sequentially have increasing timestamps."""
        event1 = DomainEvent()
        event2 = DomainEvent()
        
        # Events should have different timestamps (assuming fast execution)
        # This test might be flaky on very fast systems, but provides value
        assert event1.occurred_at <= event2.occurred_at

    def test_large_decimal_values(self):
        """Test events with large decimal values."""
        large_delay = Decimal("999999.99")
        
        event = JobDelayed(
            job_id=uuid4(),
            original_due_date=datetime.now(),
            expected_completion=datetime.now() + timedelta(days=365),
            delay_hours=large_delay
        )
        
        assert event.delay_hours == large_delay

    def test_unicode_in_string_fields(self):
        """Test events with Unicode characters in string fields."""
        event = ConstraintViolated(
            constraint_type="资源约束",  # Chinese characters
            constraint_description="Ressource contrainte violée",  # French
            violated_by=uuid4(),
            violation_details="Нарушение ограничения"  # Cyrillic
        )
        
        assert "资源约束" in event.constraint_type
        assert "violée" in event.constraint_description
        assert "Нарушение" in event.violation_details