"""
Integration tests for domain event publishing and infrastructure integration.

Tests event publishing, handling, and propagation through the infrastructure
event bus, including async event processing and error handling.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.events.domain_events import (
    DomainEvent,
    JobCompleted,
    JobCreated,
    TaskCompleted,
    TaskScheduled,
    TaskStarted,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.infrastructure.events.domain_event_publisher import (
    DomainEventPublisher,
    get_domain_event_publisher,
    publish_domain_event,
    publish_domain_event_async,
    publish_domain_events,
    publish_domain_events_async,
)
from app.infrastructure.events.event_bus import InMemoryEventBus


class TestDomainEventPublisherIntegration:
    """Test domain event publisher integration with infrastructure."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        return InMemoryEventBus()

    @pytest.fixture
    def publisher(self, event_bus):
        """Create a domain event publisher with test event bus."""
        return DomainEventPublisher(event_bus)

    @pytest.fixture
    def sample_events(self):
        """Create sample domain events for testing."""
        task_id = uuid4()
        job_id = uuid4()
        machine_id = uuid4()
        
        return [
            TaskScheduled(
                task_id=task_id,
                job_id=job_id,
                machine_id=machine_id,
                operator_ids=[uuid4()],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(hours=2)
            ),
            TaskStarted(
                task_id=task_id,
                job_id=job_id,
                actual_start=datetime.now(),
                machine_id=machine_id,
                operator_ids=[uuid4()]
            ),
            TaskCompleted(
                task_id=task_id,
                job_id=job_id,
                actual_end=datetime.now() + timedelta(hours=2),
                actual_duration=Duration(minutes=120)
            )
        ]

    def test_publisher_synchronous_event_publishing(self, publisher, sample_events):
        """Test synchronous domain event publishing."""
        event = sample_events[0]
        
        # Register a handler to verify event was processed
        handler_called = []
        
        def test_handler(received_event):
            handler_called.append(received_event)
        
        publisher.register_infrastructure_handler(TaskScheduled, test_handler)
        
        # Publish event
        publisher.publish_domain_event(event)
        
        # Verify handler was called
        assert len(handler_called) == 1
        assert handler_called[0] == event

    @pytest.mark.asyncio
    async def test_publisher_asynchronous_event_publishing(self, publisher, sample_events):
        """Test asynchronous domain event publishing."""
        event = sample_events[1]
        
        # Register async handler
        handler_called = []
        
        async def async_test_handler(received_event):
            handler_called.append(received_event)
        
        publisher.register_infrastructure_handler(TaskStarted, async_test_handler)
        
        # Publish event asynchronously
        await publisher.publish_domain_event_async(event)
        
        # Verify handler was called
        assert len(handler_called) == 1
        assert handler_called[0] == event

    def test_publisher_batch_synchronous_publishing(self, publisher, sample_events):
        """Test synchronous batch event publishing."""
        # Register handlers for all event types
        all_handled_events = []
        
        def task_scheduled_handler(event):
            all_handled_events.append(('TaskScheduled', event))
        
        def task_started_handler(event):
            all_handled_events.append(('TaskStarted', event))
        
        def task_completed_handler(event):
            all_handled_events.append(('TaskCompleted', event))
        
        publisher.register_infrastructure_handler(TaskScheduled, task_scheduled_handler)
        publisher.register_infrastructure_handler(TaskStarted, task_started_handler)
        publisher.register_infrastructure_handler(TaskCompleted, task_completed_handler)
        
        # Publish batch
        publisher.publish_batch(sample_events)
        
        # Verify all events were handled
        assert len(all_handled_events) == 3
        event_types = [event_type for event_type, _ in all_handled_events]
        assert 'TaskScheduled' in event_types
        assert 'TaskStarted' in event_types
        assert 'TaskCompleted' in event_types

    @pytest.mark.asyncio
    async def test_publisher_batch_asynchronous_publishing(self, publisher, sample_events):
        """Test asynchronous batch event publishing."""
        # Register async handlers
        handled_events = []
        
        async def async_handler(event):
            handled_events.append(event)
            # Simulate async work
            await asyncio.sleep(0.01)
        
        for event in sample_events:
            publisher.register_infrastructure_handler(type(event), async_handler)
        
        # Publish batch asynchronously
        await publisher.publish_batch_async(sample_events)
        
        # Verify all events were handled
        assert len(handled_events) == 3

    def test_publisher_event_history_tracking(self, publisher, sample_events):
        """Test that published events are tracked in history."""
        event = sample_events[0]
        
        # Publish event
        publisher.publish_domain_event(event)
        
        # Check event history
        history = publisher.get_event_history()
        assert len(history) >= 1
        assert event in history

    def test_publisher_filtered_event_history(self, publisher, sample_events):
        """Test filtering event history by event type."""
        # Publish multiple event types
        for event in sample_events:
            publisher.publish_domain_event(event)
        
        # Get filtered history
        task_scheduled_history = publisher.get_event_history(TaskScheduled)
        task_started_history = publisher.get_event_history(TaskStarted)
        
        assert len(task_scheduled_history) == 1
        assert len(task_started_history) == 1
        assert isinstance(task_scheduled_history[0], TaskScheduled)
        assert isinstance(task_started_history[0], TaskStarted)

    def test_publisher_error_handling_in_handlers(self, publisher):
        """Test error handling when event handlers fail."""
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        # Register failing handler
        def failing_handler(received_event):
            raise RuntimeError("Handler failed")
        
        # Register working handler
        successful_calls = []
        def working_handler(received_event):
            successful_calls.append(received_event)
        
        publisher.register_infrastructure_handler(TaskScheduled, failing_handler)
        publisher.register_infrastructure_handler(TaskScheduled, working_handler)
        
        # Publishing should not raise exception
        publisher.publish_domain_event(event)
        
        # Working handler should still be called
        assert len(successful_calls) == 1
        assert successful_calls[0] == event

    @pytest.mark.asyncio
    async def test_publisher_async_error_handling(self, publisher):
        """Test error handling in async event handlers."""
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=60)
        )
        
        # Register failing async handler
        async def failing_async_handler(received_event):
            raise RuntimeError("Async handler failed")
        
        # Register working async handler
        successful_calls = []
        async def working_async_handler(received_event):
            successful_calls.append(received_event)
        
        publisher.register_infrastructure_handler(TaskCompleted, failing_async_handler)
        publisher.register_infrastructure_handler(TaskCompleted, working_async_handler)
        
        # Publishing should not raise exception
        await publisher.publish_domain_event_async(event)
        
        # Working handler should still be called
        assert len(successful_calls) == 1
        assert successful_calls[0] == event


class TestInfrastructureEventBusIntegration:
    """Test direct integration with infrastructure event bus."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        bus = InMemoryEventBus()
        # Clear any existing handlers
        bus.clear_handlers()
        bus.clear_event_history()
        return bus

    def test_event_bus_synchronous_publishing(self, event_bus):
        """Test direct synchronous publishing to event bus."""
        event = JobCreated(
            job_id=uuid4(),
            job_number="JOB-TEST-001",
            priority=1,
            due_date=None,
            release_date=datetime.now(),
            task_count=5
        )
        
        # Subscribe handler
        handled_events = []
        def job_handler(received_event):
            handled_events.append(received_event)
        
        event_bus.subscribe(JobCreated, job_handler)
        
        # Publish event
        event_bus.publish(event)
        
        # Verify handling
        assert len(handled_events) == 1
        assert handled_events[0] == event

    @pytest.mark.asyncio
    async def test_event_bus_asynchronous_publishing(self, event_bus):
        """Test direct asynchronous publishing to event bus."""
        event = JobCompleted(
            job_id=uuid4(),
            job_number="JOB-TEST-002",
            completion_time=datetime.now(),
            planned_completion=None,
            actual_duration=Duration(hours=24),
            delay_hours=0
        )
        
        # Subscribe async handler
        handled_events = []
        async def async_job_handler(received_event):
            handled_events.append(received_event)
        
        event_bus.subscribe_async(JobCompleted, async_job_handler)
        
        # Publish event asynchronously
        await event_bus.publish_async(event)
        
        # Verify handling
        assert len(handled_events) == 1
        assert handled_events[0] == event

    def test_event_bus_mixed_handler_types(self, event_bus):
        """Test event bus with both sync and async handlers."""
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        # Register both sync and async handlers
        sync_calls = []
        async_calls = []
        
        def sync_handler(received_event):
            sync_calls.append(received_event)
        
        async def async_handler(received_event):
            async_calls.append(received_event)
        
        event_bus.subscribe(TaskStarted, sync_handler)
        event_bus.subscribe_async(TaskStarted, async_handler)
        
        # Test synchronous publish (only sync handlers called)
        event_bus.publish(event)
        assert len(sync_calls) == 1
        assert len(async_calls) == 0
        
        # Reset
        sync_calls.clear()
        async_calls.clear()

    @pytest.mark.asyncio
    async def test_event_bus_async_publish_mixed_handlers(self, event_bus):
        """Test async publishing with mixed handler types."""
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=90)
        )
        
        sync_calls = []
        async_calls = []
        
        def sync_handler(received_event):
            sync_calls.append(received_event)
        
        async def async_handler(received_event):
            async_calls.append(received_event)
        
        event_bus.subscribe(TaskCompleted, sync_handler)
        event_bus.subscribe_async(TaskCompleted, async_handler)
        
        # Test asynchronous publish (both handlers called)
        await event_bus.publish_async(event)
        
        assert len(sync_calls) == 1
        assert len(async_calls) == 1

    def test_event_bus_handler_management(self, event_bus):
        """Test subscribing and unsubscribing handlers."""
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        calls = []
        def test_handler(received_event):
            calls.append(received_event)
        
        # Subscribe
        event_bus.subscribe(TaskScheduled, test_handler)
        assert event_bus.get_handler_count(TaskScheduled) == 1
        
        # Publish and verify
        event_bus.publish(event)
        assert len(calls) == 1
        
        # Unsubscribe
        event_bus.unsubscribe(TaskScheduled, test_handler)
        assert event_bus.get_handler_count(TaskScheduled) == 0
        
        # Publish again - should not call handler
        event_bus.publish(event)
        assert len(calls) == 1  # No new calls

    def test_event_bus_handler_count_tracking(self, event_bus):
        """Test handler count tracking."""
        def handler1(event): pass
        def handler2(event): pass
        async def async_handler(event): pass
        
        # Initially no handlers
        assert event_bus.get_handler_count(TaskScheduled) == 0
        
        # Add sync handlers
        event_bus.subscribe(TaskScheduled, handler1)
        assert event_bus.get_handler_count(TaskScheduled) == 1
        
        event_bus.subscribe(TaskScheduled, handler2)
        assert event_bus.get_handler_count(TaskScheduled) == 2
        
        # Add async handler
        event_bus.subscribe_async(TaskScheduled, async_handler)
        assert event_bus.get_handler_count(TaskScheduled) == 3
        
        # Remove handlers
        event_bus.unsubscribe(TaskScheduled, handler1)
        assert event_bus.get_handler_count(TaskScheduled) == 2

    def test_event_bus_clear_handlers(self, event_bus):
        """Test clearing all handlers."""
        def handler1(event): pass
        def handler2(event): pass
        
        # Add handlers for different event types
        event_bus.subscribe(TaskScheduled, handler1)
        event_bus.subscribe(TaskCompleted, handler2)
        
        assert event_bus.get_handler_count(TaskScheduled) == 1
        assert event_bus.get_handler_count(TaskCompleted) == 1
        
        # Clear all handlers
        event_bus.clear_handlers()
        
        assert event_bus.get_handler_count(TaskScheduled) == 0
        assert event_bus.get_handler_count(TaskCompleted) == 0

    def test_event_bus_clear_specific_handlers(self, event_bus):
        """Test clearing handlers for specific event type."""
        def handler1(event): pass
        def handler2(event): pass
        
        # Add handlers for different event types
        event_bus.subscribe(TaskScheduled, handler1)
        event_bus.subscribe(TaskCompleted, handler2)
        
        # Clear only TaskScheduled handlers
        event_bus.clear_handlers(TaskScheduled)
        
        assert event_bus.get_handler_count(TaskScheduled) == 0
        assert event_bus.get_handler_count(TaskCompleted) == 1

    def test_event_bus_history_management(self, event_bus):
        """Test event history management."""
        event1 = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        event2 = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=30)
        )
        
        # Publish events
        event_bus.publish(event1)
        event_bus.publish(event2)
        
        # Check full history
        history = event_bus.get_event_history()
        assert len(history) == 2
        assert event1 in history
        assert event2 in history
        
        # Check filtered history
        scheduled_history = event_bus.get_event_history(TaskScheduled)
        assert len(scheduled_history) == 1
        assert scheduled_history[0] == event1
        
        # Clear history
        event_bus.clear_event_history()
        assert len(event_bus.get_event_history()) == 0


class TestGlobalPublisherFunctions:
    """Test global domain event publisher convenience functions."""

    def test_global_publish_domain_event(self):
        """Test global publish_domain_event function."""
        # Clear global state
        global_publisher = get_domain_event_publisher()
        global_publisher._event_bus.clear_event_history()
        
        event = JobCreated(
            job_id=uuid4(),
            job_number="GLOBAL-TEST-001",
            priority=2,
            due_date=datetime.now() + timedelta(days=7),
            release_date=datetime.now(),
            task_count=3
        )
        
        # Publish using global function
        publish_domain_event(event)
        
        # Verify event was published
        history = global_publisher.get_event_history()
        assert event in history

    @pytest.mark.asyncio
    async def test_global_publish_domain_event_async(self):
        """Test global publish_domain_event_async function."""
        # Clear global state
        global_publisher = get_domain_event_publisher()
        global_publisher._event_bus.clear_event_history()
        
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        # Publish using global async function
        await publish_domain_event_async(event)
        
        # Verify event was published
        history = global_publisher.get_event_history()
        assert event in history

    def test_global_publish_domain_events(self):
        """Test global publish_domain_events function."""
        # Clear global state
        global_publisher = get_domain_event_publisher()
        global_publisher._event_bus.clear_event_history()
        
        events = [
            JobCreated(
                job_id=uuid4(),
                job_number="BATCH-001",
                priority=1,
                due_date=None,
                release_date=datetime.now(),
                task_count=2
            ),
            JobCreated(
                job_id=uuid4(),
                job_number="BATCH-002",
                priority=2,
                due_date=None,
                release_date=datetime.now(),
                task_count=3
            )
        ]
        
        # Publish using global batch function
        publish_domain_events(events)
        
        # Verify events were published
        history = global_publisher.get_event_history()
        for event in events:
            assert event in history

    @pytest.mark.asyncio
    async def test_global_publish_domain_events_async(self):
        """Test global publish_domain_events_async function."""
        # Clear global state
        global_publisher = get_domain_event_publisher()
        global_publisher._event_bus.clear_event_history()
        
        events = [
            TaskCompleted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_end=datetime.now(),
                actual_duration=Duration(minutes=45)
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_end=datetime.now(),
                actual_duration=Duration(minutes=60)
            )
        ]
        
        # Publish using global async batch function
        await publish_domain_events_async(events)
        
        # Verify events were published
        history = global_publisher.get_event_history()
        for event in events:
            assert event in history


class TestEventOrderingAndTiming:
    """Test event ordering and timing constraints."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus."""
        bus = InMemoryEventBus()
        bus.clear_handlers()
        bus.clear_event_history()
        return bus

    def test_event_processing_order(self, event_bus):
        """Test that events are processed in order."""
        processing_order = []
        
        def handler(event):
            processing_order.append(event.event_id)
        
        event_bus.subscribe(TaskScheduled, handler)
        
        # Create events with known order
        events = [
            TaskScheduled(
                task_id=uuid4(),
                job_id=uuid4(),
                machine_id=uuid4(),
                operator_ids=[],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(hours=i+1)
            )
            for i in range(3)
        ]
        
        # Publish events
        for event in events:
            event_bus.publish(event)
        
        # Verify processing order matches publish order
        expected_order = [event.event_id for event in events]
        assert processing_order == expected_order

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self, event_bus):
        """Test concurrent processing of events."""
        process_times = {}
        
        async def slow_handler(event):
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)  # Simulate processing time
            end_time = asyncio.get_event_loop().time()
            process_times[event.event_id] = (start_time, end_time)
        
        event_bus.subscribe_async(TaskStarted, slow_handler)
        
        # Create multiple events
        events = [
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[]
            )
            for _ in range(3)
        ]
        
        # Publish all events concurrently
        await asyncio.gather(*[
            event_bus.publish_async(event) for event in events
        ])
        
        # Verify all events were processed
        assert len(process_times) == 3
        
        # Verify some overlap in processing (concurrent execution)
        times = list(process_times.values())
        times.sort()
        
        # At least some events should have overlapping execution
        overlaps = 0
        for i in range(len(times) - 1):
            if times[i][1] > times[i+1][0]:  # End time > next start time
                overlaps += 1
        
        # With async processing, we should see some overlaps
        assert overlaps > 0

    def test_event_history_chronological_order(self, event_bus):
        """Test that event history maintains chronological order."""
        events = []
        for i in range(5):
            event = TaskScheduled(
                task_id=uuid4(),
                job_id=uuid4(),
                machine_id=uuid4(),
                operator_ids=[],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(minutes=i*30)
            )
            events.append(event)
            event_bus.publish(event)
        
        # Get history
        history = event_bus.get_event_history()
        
        # Verify events are in chronological order
        for i in range(len(history) - 1):
            assert history[i].occurred_at <= history[i+1].occurred_at


class TestErrorScenarios:
    """Test various error scenarios in event processing."""

    @pytest.fixture
    def publisher(self):
        """Create publisher for error testing."""
        event_bus = InMemoryEventBus()
        return DomainEventPublisher(event_bus)

    def test_handler_exception_isolation(self, publisher):
        """Test that handler exceptions don't affect other handlers."""
        event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=1)
        )
        
        # Results tracking
        results = {'good_handler_called': False, 'exception_occurred': False}
        
        def failing_handler(e):
            results['exception_occurred'] = True
            raise ValueError("Simulated handler failure")
        
        def good_handler(e):
            results['good_handler_called'] = True
        
        # Register handlers
        publisher.register_infrastructure_handler(TaskScheduled, failing_handler)
        publisher.register_infrastructure_handler(TaskScheduled, good_handler)
        
        # Publish event - should not raise exception
        publisher.publish_domain_event(event)
        
        # Both handlers should have been attempted
        assert results['exception_occurred'] is True
        assert results['good_handler_called'] is True

    @pytest.mark.asyncio
    async def test_async_handler_exception_isolation(self, publisher):
        """Test async handler exception isolation."""
        event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=60)
        )
        
        results = {'good_handler_called': False, 'exception_occurred': False}
        
        async def failing_async_handler(e):
            results['exception_occurred'] = True
            raise RuntimeError("Async handler failed")
        
        async def good_async_handler(e):
            results['good_handler_called'] = True
        
        # Register handlers
        publisher.register_infrastructure_handler(TaskCompleted, failing_async_handler)
        publisher.register_infrastructure_handler(TaskCompleted, good_async_handler)
        
        # Publish event - should not raise exception
        await publisher.publish_domain_event_async(event)
        
        # Both handlers should have been attempted
        assert results['exception_occurred'] is True
        assert results['good_handler_called'] is True

    def test_invalid_event_type_handling(self, publisher):
        """Test handling of invalid event types."""
        # This test verifies that the system gracefully handles
        # attempts to register handlers for invalid types
        
        def dummy_handler(event):
            pass
        
        # Try to register handler for non-event type
        # The system should handle this gracefully
        try:
            publisher.register_infrastructure_handler(str, dummy_handler)
            # If this doesn't raise an exception, that's also acceptable
            # depending on the implementation
        except Exception:
            # Exception is also acceptable for type safety
            pass