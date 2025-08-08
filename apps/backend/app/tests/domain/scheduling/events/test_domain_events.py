"""
Comprehensive Unit Tests for Domain Events

Tests all domain event classes, event handlers, event dispatcher, and event publishing
functionality with proper validation and edge cases.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
from freezegun import freeze_time

from app.domain.scheduling.events.domain_events import (
    CriticalPathChanged,
    ConstraintViolated,
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


class TestDomainEvent:
    """Test the base DomainEvent class."""

    @freeze_time("2024-01-10 10:00:00")
    def test_domain_event_creation_with_defaults(self):
        """Test creating domain event with default values."""
        event = DomainEvent()
        
        assert event.event_id is not None
        assert event.occurred_at == datetime(2024, 1, 10, 10, 0, 0)
        assert event.aggregate_id is None

    def test_domain_event_creation_with_values(self):
        """Test creating domain event with specified values."""
        event_id = uuid4()
        aggregate_id = uuid4()
        occurred_at = datetime(2024, 1, 10, 15, 30, 0)
        
        event = DomainEvent(
            event_id=event_id,
            occurred_at=occurred_at,
            aggregate_id=aggregate_id
        )
        
        assert event.event_id == event_id
        assert event.occurred_at == occurred_at
        assert event.aggregate_id == aggregate_id

    def test_domain_event_immutability(self):
        """Test that domain events are immutable (frozen dataclass)."""
        event = DomainEvent()
        original_event_id = event.event_id
        
        # Should not be able to modify event after creation
        with pytest.raises(AttributeError):
            event.event_id = uuid4()
        
        assert event.event_id == original_event_id


class TestTaskEvents:
    """Test task-related domain events."""

    def test_task_scheduled_event(self):
        """Test TaskScheduled event creation."""
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4(), uuid4()],
            planned_start=datetime(2024, 1, 10, 9, 0),
            planned_end=datetime(2024, 1, 10, 11, 0)
        )
        
        assert isinstance(event, DomainEvent)
        assert event.task_id is not None
        assert event.job_id is not None
        assert event.machine_id is not None
        assert len(event.operator_ids) == 2
        assert event.planned_start < event.planned_end

    def test_task_started_event(self):
        """Test TaskStarted event creation."""
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime(2024, 1, 10, 9, 15),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        assert isinstance(event, DomainEvent)
        assert event.actual_start is not None

    def test_task_completed_event(self):
        """Test TaskCompleted event creation."""
        duration = Duration.from_minutes(125)
        
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime(2024, 1, 10, 11, 5),
            actual_duration=duration
        )
        
        assert isinstance(event, DomainEvent)
        assert event.actual_duration == duration

    def test_task_status_changed_event(self):
        """Test TaskStatusChanged event creation."""
        event = TaskStatusChanged(
            task_id=uuid4(),
            job_id=uuid4(),
            operation_sequence=20,
            old_status="PENDING",
            new_status="IN_PROGRESS",
            reason="Started by operator"
        )
        
        assert event.operation_sequence == 20
        assert event.old_status == "PENDING"
        assert event.new_status == "IN_PROGRESS"
        assert event.reason == "Started by operator"

    def test_task_status_changed_event_no_reason(self):
        """Test TaskStatusChanged event without reason."""
        event = TaskStatusChanged(
            task_id=uuid4(),
            job_id=uuid4(),
            operation_sequence=10,
            old_status="READY",
            new_status="STARTED"
        )
        
        assert event.reason is None

    def test_task_assignment_changed_event(self):
        """Test TaskAssignmentChanged event creation."""
        event = TaskAssignmentChanged(
            task_id=uuid4(),
            job_id=uuid4(),
            operation_sequence=15,
            old_machine_id=uuid4(),
            new_machine_id=uuid4(),
            operator_assignments=[uuid4(), uuid4()],
            reason="Resource conflict resolution"
        )
        
        assert event.old_machine_id is not None
        assert event.new_machine_id is not None
        assert len(event.operator_assignments) == 2
        assert event.reason == "Resource conflict resolution"

    def test_task_assignment_changed_event_new_assignment(self):
        """Test TaskAssignmentChanged event for new assignment."""
        event = TaskAssignmentChanged(
            task_id=uuid4(),
            job_id=uuid4(),
            operation_sequence=10,
            old_machine_id=None,  # New assignment
            new_machine_id=uuid4(),
            operator_assignments=[uuid4()],
            reason="Initial assignment"
        )
        
        assert event.old_machine_id is None
        assert event.new_machine_id is not None

    def test_task_delayed_event(self):
        """Test TaskDelayed event creation."""
        event = TaskDelayed(
            task_id=uuid4(),
            job_id=uuid4(),
            operation_sequence=25,
            original_planned_start=datetime(2024, 1, 10, 9, 0),
            new_planned_start=datetime(2024, 1, 10, 10, 30),
            delay_minutes=90,
            reason="Machine breakdown"
        )
        
        assert event.delay_minutes == 90
        assert event.new_planned_start > event.original_planned_start
        assert event.reason == "Machine breakdown"


class TestJobEvents:
    """Test job-related domain events."""

    def test_job_created_event(self):
        """Test JobCreated event creation."""
        event = JobCreated(
            job_id=uuid4(),
            job_number="JOB-001",
            priority=5,
            due_date=datetime(2024, 1, 15, 16, 0),
            release_date=datetime(2024, 1, 10, 8, 0),
            task_count=6
        )
        
        assert event.job_number == "JOB-001"
        assert event.priority == 5
        assert event.task_count == 6
        assert event.due_date is not None
        assert event.release_date is not None

    def test_job_created_event_no_due_date(self):
        """Test JobCreated event without due date."""
        event = JobCreated(
            job_id=uuid4(),
            job_number="JOB-002",
            priority=3,
            due_date=None,
            release_date=datetime(2024, 1, 10, 8, 0),
            task_count=4
        )
        
        assert event.due_date is None

    def test_job_status_changed_event(self):
        """Test JobStatusChanged event creation."""
        event = JobStatusChanged(
            job_id=uuid4(),
            job_number="JOB-003",
            old_status="PLANNED",
            new_status="RELEASED",
            reason="All prerequisites met"
        )
        
        assert event.old_status == "PLANNED"
        assert event.new_status == "RELEASED"
        assert event.reason == "All prerequisites met"

    def test_job_completed_event(self):
        """Test JobCompleted event creation."""
        event = JobCompleted(
            job_id=uuid4(),
            job_number="JOB-004",
            completion_time=datetime(2024, 1, 12, 15, 30),
            planned_completion=datetime(2024, 1, 12, 16, 0),
            actual_duration=Duration.from_minutes(480),  # 8 hours
            delay_hours=Decimal("0")  # On time
        )
        
        assert event.completion_time < event.planned_completion
        assert event.delay_hours == Decimal("0")
        assert event.actual_duration == Duration.from_minutes(480)

    def test_job_delayed_event(self):
        """Test JobDelayed event creation."""
        event = JobDelayed(
            job_id=uuid4(),
            original_due_date=datetime(2024, 1, 15, 16, 0),
            expected_completion=datetime(2024, 1, 16, 14, 0),
            delay_hours=Decimal("22.0")  # 22 hours late
        )
        
        assert event.expected_completion > event.original_due_date
        assert event.delay_hours == Decimal("22.0")


class TestOperatorEvents:
    """Test operator-related domain events."""

    def test_operator_assigned_event(self):
        """Test OperatorAssigned event creation."""
        event = OperatorAssigned(
            operator_id=uuid4(),
            task_id=uuid4(),
            assignment_type="full_duration"
        )
        
        assert event.assignment_type == "full_duration"

    def test_operator_assigned_event_setup_only(self):
        """Test OperatorAssigned event for setup-only assignment."""
        event = OperatorAssigned(
            operator_id=uuid4(),
            task_id=uuid4(),
            assignment_type="setup_only"
        )
        
        assert event.assignment_type == "setup_only"

    def test_operator_released_event(self):
        """Test OperatorReleased event creation."""
        event = OperatorReleased(
            operator_id=uuid4(),
            task_id=uuid4()
        )
        
        assert isinstance(event, DomainEvent)

    def test_operator_status_changed_event(self):
        """Test OperatorStatusChanged event creation."""
        event = OperatorStatusChanged(
            operator_id=uuid4(),
            operator_name="John Doe",
            old_status="AVAILABLE",
            new_status="BUSY",
            reason="Assigned to task"
        )
        
        assert event.operator_name == "John Doe"
        assert event.old_status == "AVAILABLE"
        assert event.new_status == "BUSY"
        assert event.reason == "Assigned to task"


class TestMachineEvents:
    """Test machine-related domain events."""

    def test_machine_allocated_event(self):
        """Test MachineAllocated event creation."""
        event = MachineAllocated(
            machine_id=uuid4(),
            task_id=uuid4(),
            job_id=uuid4(),
            allocation_start=datetime(2024, 1, 10, 9, 0),
            allocation_end=datetime(2024, 1, 10, 11, 0)
        )
        
        assert event.allocation_end > event.allocation_start

    def test_machine_released_event(self):
        """Test MachineReleased event creation."""
        event = MachineReleased(
            machine_id=uuid4(),
            task_id=uuid4(),
            job_id=uuid4(),
            release_time=datetime(2024, 1, 10, 11, 5),
            utilization_hours=Decimal("2.08")  # 2 hours 5 minutes
        )
        
        assert event.utilization_hours == Decimal("2.08")

    def test_machine_status_changed_event(self):
        """Test MachineStatusChanged event creation."""
        event = MachineStatusChanged(
            machine_id=uuid4(),
            machine_name="CNC-001",
            old_status="AVAILABLE",
            new_status="MAINTENANCE",
            reason="Scheduled maintenance"
        )
        
        assert event.machine_name == "CNC-001"
        assert event.old_status == "AVAILABLE"
        assert event.new_status == "MAINTENANCE"
        assert event.reason == "Scheduled maintenance"


class TestScheduleEvents:
    """Test schedule-related domain events."""

    def test_schedule_published_event(self):
        """Test SchedulePublished event creation."""
        event = SchedulePublished(
            schedule_id=uuid4(),
            version=1,
            effective_date=datetime(2024, 1, 11, 8, 0),
            task_count=25,
            makespan_hours=Decimal("16.5")
        )
        
        assert event.version == 1
        assert event.task_count == 25
        assert event.makespan_hours == Decimal("16.5")

    def test_schedule_updated_event(self):
        """Test ScheduleUpdated event creation."""
        event = ScheduleUpdated(
            schedule_id=uuid4(),
            old_version=1,
            new_version=2,
            changes_description="Machine reassignment due to breakdown",
            affected_tasks=[uuid4(), uuid4(), uuid4()]
        )
        
        assert event.old_version == 1
        assert event.new_version == 2
        assert len(event.affected_tasks) == 3
        assert event.changes_description.startswith("Machine reassignment")


class TestConstraintAndConflictEvents:
    """Test constraint and conflict-related domain events."""

    def test_constraint_violated_event(self):
        """Test ConstraintViolated event creation."""
        event = ConstraintViolated(
            constraint_type="PRECEDENCE",
            constraint_description="Task T2 must start after T1 completes",
            violated_by=uuid4(),
            violation_details="T2 scheduled to start before T1 completion"
        )
        
        assert event.constraint_type == "PRECEDENCE"
        assert event.constraint_description.startswith("Task T2")
        assert event.violation_details.startswith("T2 scheduled")

    def test_resource_conflict_detected_event(self):
        """Test ResourceConflictDetected event creation."""
        event = ResourceConflictDetected(
            resource_type="machine",
            resource_id=uuid4(),
            conflicting_tasks=[uuid4(), uuid4()],
            conflict_time_start=datetime(2024, 1, 10, 10, 0),
            conflict_time_end=datetime(2024, 1, 10, 11, 0)
        )
        
        assert event.resource_type == "machine"
        assert len(event.conflicting_tasks) == 2
        assert event.conflict_time_end > event.conflict_time_start

    def test_resource_conflict_detected_operator(self):
        """Test ResourceConflictDetected event for operator."""
        event = ResourceConflictDetected(
            resource_type="operator",
            resource_id=uuid4(),
            conflicting_tasks=[uuid4(), uuid4(), uuid4()],
            conflict_time_start=datetime(2024, 1, 10, 9, 30),
            conflict_time_end=datetime(2024, 1, 10, 10, 45)
        )
        
        assert event.resource_type == "operator"
        assert len(event.conflicting_tasks) == 3

    def test_skill_requirement_not_met_event(self):
        """Test SkillRequirementNotMet event creation."""
        event = SkillRequirementNotMet(
            operator_id=uuid4(),
            task_id=uuid4(),
            required_skill="WELDING",
            required_level=5,
            operator_level=2
        )
        
        assert event.required_skill == "WELDING"
        assert event.required_level == 5
        assert event.operator_level == 2

    def test_skill_requirement_not_met_no_skill(self):
        """Test SkillRequirementNotMet event when operator has no skill."""
        event = SkillRequirementNotMet(
            operator_id=uuid4(),
            task_id=uuid4(),
            required_skill="ASSEMBLY",
            required_level=3,
            operator_level=None
        )
        
        assert event.operator_level is None


class TestSpecializedEvents:
    """Test specialized domain events."""

    def test_critical_path_changed_event(self):
        """Test CriticalPathChanged event creation."""
        old_tasks = [uuid4(), uuid4()]
        new_tasks = [uuid4(), uuid4(), uuid4()]
        
        event = CriticalPathChanged(
            job_id=uuid4(),
            old_critical_tasks=old_tasks,
            new_critical_tasks=new_tasks,
            new_makespan_hours=Decimal("18.5")
        )
        
        assert len(event.old_critical_tasks) == 2
        assert len(event.new_critical_tasks) == 3
        assert event.new_makespan_hours == Decimal("18.5")

    def test_priority_changed_event_job(self):
        """Test PriorityChanged event for job."""
        event = PriorityChanged(
            entity_type="job",
            entity_id=uuid4(),
            old_priority=5,
            new_priority=10,
            reason="Customer request for expedite"
        )
        
        assert event.entity_type == "job"
        assert event.old_priority == 5
        assert event.new_priority == 10
        assert event.reason.startswith("Customer request")

    def test_priority_changed_event_task(self):
        """Test PriorityChanged event for task."""
        event = PriorityChanged(
            entity_type="task",
            entity_id=uuid4(),
            old_priority=3,
            new_priority=8
        )
        
        assert event.entity_type == "task"
        assert event.reason is None

    def test_maintenance_scheduled_event(self):
        """Test MaintenanceScheduled event creation."""
        affected_tasks = [uuid4(), uuid4()]
        
        event = MaintenanceScheduled(
            machine_id=uuid4(),
            machine_name="MILL-003",
            maintenance_start=datetime(2024, 1, 11, 18, 0),
            maintenance_end=datetime(2024, 1, 12, 6, 0),
            maintenance_type="PREVENTIVE",
            affected_tasks=affected_tasks
        )
        
        assert event.machine_name == "MILL-003"
        assert event.maintenance_type == "PREVENTIVE"
        assert len(event.affected_tasks) == 2
        assert event.maintenance_end > event.maintenance_start

    def test_deadline_missed_event(self):
        """Test DeadlineMissed event creation."""
        contributing_factors = [
            "Machine breakdown",
            "Operator unavailability",
            "Material delay"
        ]
        
        event = DeadlineMissed(
            job_id=uuid4(),
            job_number="LATE-001",
            original_due_date=datetime(2024, 1, 15, 16, 0),
            actual_completion=datetime(2024, 1, 17, 10, 30),
            delay_hours=Decimal("42.5"),
            contributing_factors=contributing_factors
        )
        
        assert event.job_number == "LATE-001"
        assert event.delay_hours == Decimal("42.5")
        assert len(event.contributing_factors) == 3
        assert "Machine breakdown" in event.contributing_factors


class TestDomainEventHandler:
    """Test the domain event handler interface."""

    def test_domain_event_handler_interface(self):
        """Test that DomainEventHandler is an interface."""
        handler = DomainEventHandler()
        
        # Should raise NotImplementedError for interface methods
        with pytest.raises(NotImplementedError):
            handler.can_handle(DomainEvent())
        
        with pytest.raises(NotImplementedError):
            handler.handle(DomainEvent())


class TestConcreteEventHandler:
    """Test a concrete event handler implementation."""

    class TaskEventHandler(DomainEventHandler):
        """Concrete handler for task events."""
        
        def __init__(self):
            self.handled_events = []
        
        def can_handle(self, event: DomainEvent) -> bool:
            return isinstance(event, (TaskScheduled, TaskStarted, TaskCompleted))
        
        def handle(self, event: DomainEvent) -> None:
            self.handled_events.append(event)

    def test_concrete_handler_can_handle_task_events(self):
        """Test concrete handler can identify task events."""
        handler = self.TaskEventHandler()
        
        task_scheduled = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=2)
        )
        
        job_created = JobCreated(
            job_id=uuid4(),
            job_number="TEST",
            priority=1,
            due_date=None,
            release_date=datetime.now(),
            task_count=1
        )
        
        assert handler.can_handle(task_scheduled) is True
        assert handler.can_handle(job_created) is False

    def test_concrete_handler_handles_events(self):
        """Test concrete handler processes events."""
        handler = self.TaskEventHandler()
        
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        handler.handle(event)
        
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event


class TestDomainEventDispatcher:
    """Test the domain event dispatcher."""

    class MockHandler(DomainEventHandler):
        """Mock event handler for testing."""
        
        def __init__(self, can_handle_result=True):
            self.can_handle_result = can_handle_result
            self.handled_events = []
            self.can_handle_calls = []
        
        def can_handle(self, event: DomainEvent) -> bool:
            self.can_handle_calls.append(event)
            return self.can_handle_result
        
        def handle(self, event: DomainEvent) -> None:
            self.handled_events.append(event)

    def test_dispatcher_initialization(self):
        """Test dispatcher initialization."""
        dispatcher = DomainEventDispatcher()
        assert dispatcher._handlers == []

    def test_register_handler(self):
        """Test registering event handler."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler()
        
        dispatcher.register_handler(handler)
        
        assert len(dispatcher._handlers) == 1
        assert dispatcher._handlers[0] == handler

    def test_register_handler_duplicate(self):
        """Test registering same handler multiple times."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler()
        
        dispatcher.register_handler(handler)
        dispatcher.register_handler(handler)  # Duplicate
        
        assert len(dispatcher._handlers) == 1  # Should not add duplicate

    def test_unregister_handler(self):
        """Test unregistering event handler."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler()
        
        dispatcher.register_handler(handler)
        dispatcher.unregister_handler(handler)
        
        assert len(dispatcher._handlers) == 0

    def test_unregister_handler_not_registered(self):
        """Test unregistering handler that was never registered."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler()
        
        # Should not raise exception
        dispatcher.unregister_handler(handler)
        
        assert len(dispatcher._handlers) == 0

    def test_dispatch_event_to_capable_handler(self):
        """Test dispatching event to handler that can handle it."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler(can_handle_result=True)
        
        dispatcher.register_handler(handler)
        
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        dispatcher.dispatch(event)
        
        assert len(handler.can_handle_calls) == 1
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event

    def test_dispatch_event_to_incapable_handler(self):
        """Test dispatching event to handler that cannot handle it."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler(can_handle_result=False)
        
        dispatcher.register_handler(handler)
        
        event = JobCreated(
            job_id=uuid4(),
            job_number="TEST",
            priority=1,
            due_date=None,
            release_date=datetime.now(),
            task_count=1
        )
        
        dispatcher.dispatch(event)
        
        assert len(handler.can_handle_calls) == 1
        assert len(handler.handled_events) == 0  # Should not handle

    def test_dispatch_event_multiple_handlers(self):
        """Test dispatching event to multiple handlers."""
        dispatcher = DomainEventDispatcher()
        handler1 = self.MockHandler(can_handle_result=True)
        handler2 = self.MockHandler(can_handle_result=True)
        handler3 = self.MockHandler(can_handle_result=False)
        
        dispatcher.register_handler(handler1)
        dispatcher.register_handler(handler2)
        dispatcher.register_handler(handler3)
        
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration.from_minutes(120)
        )
        
        dispatcher.dispatch(event)
        
        # All handlers should be asked if they can handle
        assert len(handler1.can_handle_calls) == 1
        assert len(handler2.can_handle_calls) == 1
        assert len(handler3.can_handle_calls) == 1
        
        # Only capable handlers should handle
        assert len(handler1.handled_events) == 1
        assert len(handler2.handled_events) == 1
        assert len(handler3.handled_events) == 0

    def test_dispatch_event_handler_exception(self):
        """Test dispatching event when handler raises exception."""
        dispatcher = DomainEventDispatcher()
        
        class FailingHandler(DomainEventHandler):
            def can_handle(self, event: DomainEvent) -> bool:
                return True
            
            def handle(self, event: DomainEvent) -> None:
                raise ValueError("Handler error")
        
        working_handler = self.MockHandler(can_handle_result=True)
        failing_handler = FailingHandler()
        
        dispatcher.register_handler(working_handler)
        dispatcher.register_handler(failing_handler)
        
        event = DomainEvent()
        
        # Should not raise exception despite failing handler
        dispatcher.dispatch(event)
        
        # Working handler should still process event
        assert len(working_handler.handled_events) == 1

    def test_dispatch_all_events(self):
        """Test dispatching multiple events at once."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler(can_handle_result=True)
        
        dispatcher.register_handler(handler)
        
        events = [
            TaskScheduled(
                task_id=uuid4(),
                job_id=uuid4(),
                machine_id=uuid4(),
                operator_ids=[uuid4()],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(hours=1)
            ),
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[uuid4()]
            )
        ]
        
        dispatcher.dispatch_all(events)
        
        assert len(handler.handled_events) == 2

    def test_dispatch_all_empty_list(self):
        """Test dispatching empty event list."""
        dispatcher = DomainEventDispatcher()
        handler = self.MockHandler()
        
        dispatcher.register_handler(handler)
        
        dispatcher.dispatch_all([])
        
        assert len(handler.handled_events) == 0


class TestGlobalEventDispatcher:
    """Test global event dispatcher functions."""

    def test_get_event_dispatcher(self):
        """Test getting global event dispatcher."""
        dispatcher1 = get_event_dispatcher()
        dispatcher2 = get_event_dispatcher()
        
        # Should return same instance (singleton pattern)
        assert dispatcher1 is dispatcher2
        assert isinstance(dispatcher1, DomainEventDispatcher)

    def test_publish_event(self):
        """Test publishing single event using global dispatcher."""
        # Clear any existing handlers
        global_dispatcher = get_event_dispatcher()
        global_dispatcher._handlers.clear()
        
        # Add test handler
        class TestHandler(DomainEventHandler):
            def __init__(self):
                self.events = []
            
            def can_handle(self, event: DomainEvent) -> bool:
                return True
            
            def handle(self, event: DomainEvent) -> None:
                self.events.append(event)
        
        test_handler = TestHandler()
        global_dispatcher.register_handler(test_handler)
        
        event = JobCreated(
            job_id=uuid4(),
            job_number="GLOBAL-TEST",
            priority=1,
            due_date=None,
            release_date=datetime.now(),
            task_count=1
        )
        
        publish_event(event)
        
        assert len(test_handler.events) == 1
        assert test_handler.events[0] == event

    def test_publish_events(self):
        """Test publishing multiple events using global dispatcher."""
        # Clear any existing handlers
        global_dispatcher = get_event_dispatcher()
        global_dispatcher._handlers.clear()
        
        # Add test handler
        class TestHandler(DomainEventHandler):
            def __init__(self):
                self.events = []
            
            def can_handle(self, event: DomainEvent) -> bool:
                return True
            
            def handle(self, event: DomainEvent) -> None:
                self.events.append(event)
        
        test_handler = TestHandler()
        global_dispatcher.register_handler(test_handler)
        
        events = [
            JobCreated(
                job_id=uuid4(),
                job_number="BATCH-1",
                priority=1,
                due_date=None,
                release_date=datetime.now(),
                task_count=1
            ),
            JobCreated(
                job_id=uuid4(),
                job_number="BATCH-2",
                priority=2,
                due_date=None,
                release_date=datetime.now(),
                task_count=2
            )
        ]
        
        publish_events(events)
        
        assert len(test_handler.events) == 2


class TestEventIntegrationScenarios:
    """Test realistic event scenarios."""

    def test_task_lifecycle_events(self):
        """Test complete task lifecycle event sequence."""
        task_id = uuid4()
        job_id = uuid4()
        machine_id = uuid4()
        operator_id = uuid4()
        
        # Task scheduled
        scheduled_event = TaskScheduled(
            task_id=task_id,
            job_id=job_id,
            machine_id=machine_id,
            operator_ids=[operator_id],
            planned_start=datetime(2024, 1, 10, 9, 0),
            planned_end=datetime(2024, 1, 10, 11, 0)
        )
        
        # Task started (slightly late)
        started_event = TaskStarted(
            task_id=task_id,
            job_id=job_id,
            actual_start=datetime(2024, 1, 10, 9, 15),
            machine_id=machine_id,
            operator_ids=[operator_id]
        )
        
        # Task completed (on time despite late start)
        completed_event = TaskCompleted(
            task_id=task_id,
            job_id=job_id,
            actual_end=datetime(2024, 1, 10, 11, 0),
            actual_duration=Duration.from_minutes(105)  # 1h 45m
        )
        
        # Verify event consistency
        assert scheduled_event.task_id == started_event.task_id == completed_event.task_id
        assert started_event.actual_start > scheduled_event.planned_start
        assert completed_event.actual_end <= scheduled_event.planned_end

    def test_resource_conflict_resolution_events(self):
        """Test resource conflict detection and resolution event sequence."""
        machine_id = uuid4()
        task1_id = uuid4()
        task2_id = uuid4()
        
        # Conflict detected
        conflict_event = ResourceConflictDetected(
            resource_type="machine",
            resource_id=machine_id,
            conflicting_tasks=[task1_id, task2_id],
            conflict_time_start=datetime(2024, 1, 10, 10, 0),
            conflict_time_end=datetime(2024, 1, 10, 11, 0)
        )
        
        # Task reassigned to resolve conflict
        reassignment_event = TaskAssignmentChanged(
            task_id=task2_id,
            job_id=uuid4(),
            operation_sequence=20,
            old_machine_id=machine_id,
            new_machine_id=uuid4(),  # Different machine
            operator_assignments=[uuid4()],
            reason="Resource conflict resolution"
        )
        
        # Verify resolution
        assert machine_id in [conflict_event.resource_id, reassignment_event.old_machine_id]
        assert reassignment_event.new_machine_id != machine_id
        assert "conflict" in reassignment_event.reason.lower()

    def test_job_priority_escalation_events(self):
        """Test job priority escalation event sequence."""
        job_id = uuid4()
        
        # Initial job creation
        job_created = JobCreated(
            job_id=job_id,
            job_number="ESCALATE-001",
            priority=5,
            due_date=datetime(2024, 1, 15, 16, 0),
            release_date=datetime(2024, 1, 10, 8, 0),
            task_count=4
        )
        
        # Job becomes delayed
        job_delayed = JobDelayed(
            job_id=job_id,
            original_due_date=datetime(2024, 1, 15, 16, 0),
            expected_completion=datetime(2024, 1, 16, 10, 0),
            delay_hours=Decimal("18.0")
        )
        
        # Priority increased due to delay
        priority_changed = PriorityChanged(
            entity_type="job",
            entity_id=job_id,
            old_priority=5,
            new_priority=10,
            reason="Escalated due to delay risk"
        )
        
        # Verify escalation logic
        assert job_created.job_id == job_id
        assert job_delayed.delay_hours > Decimal("0")
        assert priority_changed.new_priority > priority_changed.old_priority
        assert "delay" in priority_changed.reason.lower()

    def test_maintenance_impact_events(self):
        """Test maintenance scheduling and impact event sequence."""
        machine_id = uuid4()
        affected_tasks = [uuid4(), uuid4()]
        
        # Maintenance scheduled
        maintenance_event = MaintenanceScheduled(
            machine_id=machine_id,
            machine_name="CNC-001",
            maintenance_start=datetime(2024, 1, 11, 18, 0),
            maintenance_end=datetime(2024, 1, 12, 6, 0),
            maintenance_type="PREVENTIVE",
            affected_tasks=affected_tasks
        )
        
        # Machine status changed
        status_changed = MachineStatusChanged(
            machine_id=machine_id,
            machine_name="CNC-001",
            old_status="AVAILABLE",
            new_status="MAINTENANCE",
            reason="Scheduled preventive maintenance"
        )
        
        # Tasks delayed due to maintenance
        task_delayed = TaskDelayed(
            task_id=affected_tasks[0],
            job_id=uuid4(),
            operation_sequence=15,
            original_planned_start=datetime(2024, 1, 11, 20, 0),
            new_planned_start=datetime(2024, 1, 12, 8, 0),
            delay_minutes=720,  # 12 hours
            reason="Machine maintenance"
        )
        
        # Verify maintenance impact chain
        assert maintenance_event.machine_id == status_changed.machine_id
        assert affected_tasks[0] == task_delayed.task_id
        assert task_delayed.delay_minutes > 0
        assert "maintenance" in task_delayed.reason.lower()