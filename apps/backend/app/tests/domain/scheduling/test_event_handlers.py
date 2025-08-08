"""
Event handler mock implementations and tests for event propagation and side effects.

Tests domain event handlers, event-driven workflows, side effects of events,
and cross-domain integration through events.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.events.domain_events import (
    ConstraintViolated,
    DomainEvent,
    DomainEventHandler,
    JobCompleted,
    JobCreated,
    JobStatusChanged,
    MachineAllocated,
    MachineReleased,
    OperatorAssigned,
    OperatorReleased,
    ResourceConflictDetected,
    SchedulePublished,
    TaskCompleted,
    TaskDelayed,
    TaskScheduled,
    TaskStarted,
    TaskStatusChanged,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.infrastructure.events.domain_event_publisher import DomainEventPublisher
from app.infrastructure.events.event_bus import InMemoryEventBus


class MockEventHandler(DomainEventHandler):
    """Base mock event handler for testing."""
    
    def __init__(self, event_types: List[type] = None, should_fail: bool = False):
        """
        Initialize mock handler.
        
        Args:
            event_types: Types of events this handler can handle
            should_fail: Whether handler should simulate failure
        """
        self.event_types = event_types or []
        self.should_fail = should_fail
        self.handled_events: List[DomainEvent] = []
        self.call_count = 0
        self.side_effects: List[Dict[str, Any]] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if handler can handle the event type."""
        if not self.event_types:
            return True  # Handle all events if no specific types
        return type(event) in self.event_types
    
    def handle(self, event: DomainEvent) -> None:
        """Handle the event and record side effects."""
        if self.should_fail:
            raise RuntimeError(f"Mock handler failure for {type(event).__name__}")
        
        self.call_count += 1
        self.handled_events.append(event)
        
        # Record side effects for analysis
        side_effect = {
            'timestamp': datetime.now(),
            'event_type': type(event).__name__,
            'event_id': event.event_id,
            'handler_id': id(self)
        }
        self.side_effects.append(side_effect)
    
    def reset(self) -> None:
        """Reset handler state."""
        self.handled_events.clear()
        self.call_count = 0
        self.side_effects.clear()


class TaskProgressTracker(DomainEventHandler):
    """Handler that tracks task progress through events."""
    
    def __init__(self):
        self.task_states: Dict[UUID, Dict[str, Any]] = {}
        self.progress_timeline: List[Dict[str, Any]] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Handle task-related events."""
        return isinstance(event, (TaskScheduled, TaskStarted, TaskCompleted, TaskStatusChanged))
    
    def handle(self, event: DomainEvent) -> None:
        """Track task progress based on events."""
        timestamp = datetime.now()
        
        if isinstance(event, TaskScheduled):
            self.task_states[event.task_id] = {
                'status': 'scheduled',
                'job_id': event.job_id,
                'machine_id': event.machine_id,
                'operators': event.operator_ids.copy(),
                'planned_start': event.planned_start,
                'planned_end': event.planned_end,
                'last_updated': timestamp
            }
            
            self.progress_timeline.append({
                'timestamp': timestamp,
                'task_id': event.task_id,
                'event_type': 'task_scheduled',
                'details': {
                    'machine_id': str(event.machine_id),
                    'operator_count': len(event.operator_ids)
                }
            })
        
        elif isinstance(event, TaskStarted):
            if event.task_id in self.task_states:
                self.task_states[event.task_id].update({
                    'status': 'in_progress',
                    'actual_start': event.actual_start,
                    'last_updated': timestamp
                })
            
            self.progress_timeline.append({
                'timestamp': timestamp,
                'task_id': event.task_id,
                'event_type': 'task_started',
                'details': {
                    'actual_start': event.actual_start.isoformat()
                }
            })
        
        elif isinstance(event, TaskCompleted):
            if event.task_id in self.task_states:
                self.task_states[event.task_id].update({
                    'status': 'completed',
                    'actual_end': event.actual_end,
                    'actual_duration': event.actual_duration,
                    'last_updated': timestamp
                })
            
            self.progress_timeline.append({
                'timestamp': timestamp,
                'task_id': event.task_id,
                'event_type': 'task_completed',
                'details': {
                    'actual_end': event.actual_end.isoformat(),
                    'duration_minutes': event.actual_duration.minutes
                }
            })
        
        elif isinstance(event, TaskStatusChanged):
            if event.task_id in self.task_states:
                old_status = self.task_states[event.task_id].get('status', 'unknown')
                self.task_states[event.task_id].update({
                    'status': event.new_status,
                    'last_updated': timestamp
                })
                
                self.progress_timeline.append({
                    'timestamp': timestamp,
                    'task_id': event.task_id,
                    'event_type': 'status_changed',
                    'details': {
                        'old_status': old_status,
                        'new_status': event.new_status,
                        'reason': event.reason
                    }
                })
    
    def get_task_progress(self, task_id: UUID) -> Dict[str, Any] | None:
        """Get current progress for a task."""
        return self.task_states.get(task_id)
    
    def get_timeline_for_task(self, task_id: UUID) -> List[Dict[str, Any]]:
        """Get timeline of events for a specific task."""
        return [event for event in self.progress_timeline if event['task_id'] == task_id]


class ResourceUtilizationTracker(DomainEventHandler):
    """Handler that tracks resource utilization through allocation events."""
    
    def __init__(self):
        self.machine_allocations: Dict[UUID, List[Dict[str, Any]]] = {}
        self.operator_assignments: Dict[UUID, List[Dict[str, Any]]] = {}
        self.conflicts: List[Dict[str, Any]] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Handle resource allocation events."""
        return isinstance(event, (
            MachineAllocated, MachineReleased,
            OperatorAssigned, OperatorReleased,
            ResourceConflictDetected
        ))
    
    def handle(self, event: DomainEvent) -> None:
        """Track resource utilization."""
        timestamp = datetime.now()
        
        if isinstance(event, MachineAllocated):
            if event.machine_id not in self.machine_allocations:
                self.machine_allocations[event.machine_id] = []
            
            self.machine_allocations[event.machine_id].append({
                'task_id': event.task_id,
                'job_id': event.job_id,
                'allocated_at': timestamp,
                'allocation_start': event.allocation_start,
                'allocation_end': event.allocation_end,
                'status': 'allocated'
            })
        
        elif isinstance(event, MachineReleased):
            if event.machine_id in self.machine_allocations:
                # Find and update the allocation
                for allocation in self.machine_allocations[event.machine_id]:
                    if (allocation['task_id'] == event.task_id and 
                        allocation['status'] == 'allocated'):
                        allocation.update({
                            'released_at': timestamp,
                            'release_time': event.release_time,
                            'utilization_hours': event.utilization_hours,
                            'status': 'released'
                        })
                        break
        
        elif isinstance(event, OperatorAssigned):
            if event.operator_id not in self.operator_assignments:
                self.operator_assignments[event.operator_id] = []
            
            self.operator_assignments[event.operator_id].append({
                'task_id': event.task_id,
                'assigned_at': timestamp,
                'assignment_type': event.assignment_type,
                'status': 'assigned'
            })
        
        elif isinstance(event, OperatorReleased):
            if event.operator_id in self.operator_assignments:
                # Find and update the assignment
                for assignment in self.operator_assignments[event.operator_id]:
                    if (assignment['task_id'] == event.task_id and 
                        assignment['status'] == 'assigned'):
                        assignment.update({
                            'released_at': timestamp,
                            'status': 'released'
                        })
                        break
        
        elif isinstance(event, ResourceConflictDetected):
            self.conflicts.append({
                'detected_at': timestamp,
                'resource_type': event.resource_type,
                'resource_id': event.resource_id,
                'conflicting_tasks': event.conflicting_tasks.copy(),
                'conflict_start': event.conflict_time_start,
                'conflict_end': event.conflict_time_end
            })
    
    def get_machine_utilization(self, machine_id: UUID) -> Dict[str, Any]:
        """Get utilization statistics for a machine."""
        allocations = self.machine_allocations.get(machine_id, [])
        
        total_allocated_hours = sum(
            float(alloc.get('utilization_hours', 0)) 
            for alloc in allocations 
            if alloc.get('utilization_hours')
        )
        
        active_allocations = [
            alloc for alloc in allocations 
            if alloc['status'] == 'allocated'
        ]
        
        return {
            'machine_id': str(machine_id),
            'total_allocations': len(allocations),
            'active_allocations': len(active_allocations),
            'total_utilized_hours': total_allocated_hours,
            'conflicts': len([c for c in self.conflicts if c['resource_id'] == machine_id])
        }
    
    def get_operator_workload(self, operator_id: UUID) -> Dict[str, Any]:
        """Get workload statistics for an operator."""
        assignments = self.operator_assignments.get(operator_id, [])
        
        active_assignments = [
            assign for assign in assignments 
            if assign['status'] == 'assigned'
        ]
        
        return {
            'operator_id': str(operator_id),
            'total_assignments': len(assignments),
            'active_assignments': len(active_assignments),
            'conflicts': len([c for c in self.conflicts if c['resource_id'] == operator_id])
        }


class ScheduleQualityMonitor(DomainEventHandler):
    """Handler that monitors schedule quality through various events."""
    
    def __init__(self):
        self.quality_metrics: Dict[str, Any] = {
            'total_delays': 0,
            'total_constraint_violations': 0,
            'resource_conflicts': 0,
            'schedule_changes': 0
        }
        self.quality_events: List[Dict[str, Any]] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Handle quality-related events."""
        return isinstance(event, (
            TaskDelayed, ConstraintViolated, ResourceConflictDetected,
            SchedulePublished, JobCompleted
        ))
    
    def handle(self, event: DomainEvent) -> None:
        """Monitor schedule quality metrics."""
        timestamp = datetime.now()
        
        if isinstance(event, TaskDelayed):
            self.quality_metrics['total_delays'] += 1
            self.quality_events.append({
                'timestamp': timestamp,
                'type': 'delay',
                'task_id': event.task_id,
                'delay_minutes': event.delay_minutes,
                'reason': event.reason
            })
        
        elif isinstance(event, ConstraintViolated):
            self.quality_metrics['total_constraint_violations'] += 1
            self.quality_events.append({
                'timestamp': timestamp,
                'type': 'constraint_violation',
                'constraint_type': event.constraint_type,
                'violated_by': event.violated_by,
                'details': event.violation_details
            })
        
        elif isinstance(event, ResourceConflictDetected):
            self.quality_metrics['resource_conflicts'] += 1
            self.quality_events.append({
                'timestamp': timestamp,
                'type': 'resource_conflict',
                'resource_type': event.resource_type,
                'resource_id': event.resource_id,
                'conflicting_tasks': len(event.conflicting_tasks)
            })
        
        elif isinstance(event, SchedulePublished):
            self.quality_metrics['schedule_changes'] += 1
            self.quality_events.append({
                'timestamp': timestamp,
                'type': 'schedule_published',
                'schedule_id': event.schedule_id,
                'version': event.version,
                'task_count': event.task_count
            })
    
    def get_quality_score(self) -> float:
        """Calculate overall schedule quality score (0-100)."""
        # Simple scoring algorithm - more sophisticated scoring could be implemented
        base_score = 100.0
        
        # Penalties for quality issues
        delay_penalty = min(self.quality_metrics['total_delays'] * 2, 30)
        violation_penalty = min(self.quality_metrics['total_constraint_violations'] * 5, 40)
        conflict_penalty = min(self.quality_metrics['resource_conflicts'] * 3, 20)
        
        quality_score = max(0, base_score - delay_penalty - violation_penalty - conflict_penalty)
        return quality_score
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        return {
            'quality_score': self.get_quality_score(),
            'metrics': self.quality_metrics.copy(),
            'recent_events': self.quality_events[-10:],  # Last 10 events
            'event_counts_by_type': self._count_events_by_type(),
            'recommendations': self._generate_recommendations()
        }
    
    def _count_events_by_type(self) -> Dict[str, int]:
        """Count events by type."""
        counts = {}
        for event in self.quality_events:
            event_type = event['type']
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def _generate_recommendations(self) -> List[str]:
        """Generate quality improvement recommendations."""
        recommendations = []
        
        if self.quality_metrics['total_delays'] > 5:
            recommendations.append("Consider reviewing task duration estimates")
            recommendations.append("Implement buffer time between dependent tasks")
        
        if self.quality_metrics['total_constraint_violations'] > 3:
            recommendations.append("Review and validate scheduling constraints")
            recommendations.append("Check resource availability and skill matching")
        
        if self.quality_metrics['resource_conflicts'] > 2:
            recommendations.append("Improve resource allocation algorithms")
            recommendations.append("Consider increasing resource capacity")
        
        return recommendations


class WorkflowOrchestrator(DomainEventHandler):
    """Handler that orchestrates workflows based on events."""
    
    def __init__(self):
        self.active_workflows: Dict[UUID, Dict[str, Any]] = {}
        self.workflow_steps: List[Dict[str, Any]] = []
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Handle workflow-triggering events."""
        return isinstance(event, (
            JobCreated, JobStatusChanged, TaskCompleted, 
            SchedulePublished
        ))
    
    def handle(self, event: DomainEvent) -> None:
        """Orchestrate workflows based on events."""
        timestamp = datetime.now()
        
        if isinstance(event, JobCreated):
            # Start job workflow
            workflow_id = uuid4()
            self.active_workflows[workflow_id] = {
                'type': 'job_processing',
                'job_id': event.job_id,
                'status': 'started',
                'started_at': timestamp,
                'steps_completed': 0,
                'total_steps': 5  # Example: validation, scheduling, resource allocation, execution, completion
            }
            
            self.workflow_steps.append({
                'workflow_id': workflow_id,
                'step': 'job_created',
                'timestamp': timestamp,
                'details': {
                    'job_number': event.job_number,
                    'task_count': event.task_count
                }
            })
        
        elif isinstance(event, TaskCompleted):
            # Check if job is complete
            job_id = event.job_id
            job_workflows = [
                wf for wf in self.active_workflows.values() 
                if wf.get('job_id') == job_id
            ]
            
            for workflow in job_workflows:
                workflow['steps_completed'] += 1
                
                self.workflow_steps.append({
                    'workflow_id': [k for k, v in self.active_workflows.items() if v == workflow][0],
                    'step': 'task_completed',
                    'timestamp': timestamp,
                    'details': {
                        'task_id': str(event.task_id),
                        'duration_minutes': event.actual_duration.minutes
                    }
                })
        
        elif isinstance(event, SchedulePublished):
            # Trigger schedule activation workflow
            workflow_id = uuid4()
            self.active_workflows[workflow_id] = {
                'type': 'schedule_activation',
                'schedule_id': event.schedule_id,
                'status': 'started',
                'started_at': timestamp,
                'steps_completed': 1,
                'total_steps': 3  # publish, validate, activate
            }
            
            self.workflow_steps.append({
                'workflow_id': workflow_id,
                'step': 'schedule_published',
                'timestamp': timestamp,
                'details': {
                    'schedule_id': str(event.schedule_id),
                    'version': event.version
                }
            })
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflows."""
        return [
            {
                'workflow_id': str(wf_id),
                **workflow_data,
                'progress_percentage': (workflow_data['steps_completed'] / workflow_data['total_steps']) * 100
            }
            for wf_id, workflow_data in self.active_workflows.items()
            if workflow_data['status'] != 'completed'
        ]
    
    def complete_workflow(self, workflow_id: UUID) -> None:
        """Mark workflow as completed."""
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id]['status'] = 'completed'
            self.active_workflows[workflow_id]['completed_at'] = datetime.now()


class TestEventHandlers:
    """Test event handler implementations."""
    
    @pytest.fixture
    def event_bus(self):
        """Create fresh event bus for each test."""
        bus = InMemoryEventBus()
        bus.clear_handlers()
        bus.clear_event_history()
        return bus
    
    @pytest.fixture
    def event_publisher(self, event_bus):
        """Create event publisher with test event bus."""
        return DomainEventPublisher(event_bus)
    
    def test_mock_event_handler_basic_functionality(self, event_publisher):
        """Test basic mock event handler functionality."""
        handler = MockEventHandler(event_types=[TaskScheduled, TaskStarted])
        
        # Register handler
        event_publisher.register_domain_handler(handler)
        
        # Create test events
        scheduled_event = TaskScheduled(
            task_id=uuid4(),
            job_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(hours=2)
        )
        
        completed_event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=120)
        )
        
        # Publish events
        event_publisher.publish_domain_event(scheduled_event)
        event_publisher.publish_domain_event(completed_event)
        
        # Verify handler processed correct events
        assert handler.call_count == 1  # Only handles TaskScheduled, not TaskCompleted
        assert scheduled_event in handler.handled_events
        assert completed_event not in handler.handled_events
        assert len(handler.side_effects) == 1
    
    def test_mock_event_handler_failure_simulation(self, event_publisher):
        """Test mock handler failure simulation."""
        failing_handler = MockEventHandler(should_fail=True)
        working_handler = MockEventHandler()
        
        # Register both handlers
        event_publisher.register_domain_handler(failing_handler)
        event_publisher.register_domain_handler(working_handler)
        
        # Create test event
        event = TaskStarted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_start=datetime.now(),
            machine_id=uuid4(),
            operator_ids=[]
        )
        
        # Publish event - should not raise exception due to error handling
        event_publisher.publish_domain_event(event)
        
        # Verify failing handler was called but working handler still processed event
        assert failing_handler.call_count == 1
        assert working_handler.call_count == 1
        assert event in working_handler.handled_events
    
    def test_task_progress_tracker(self, event_publisher):
        """Test task progress tracking handler."""
        tracker = TaskProgressTracker()
        event_publisher.register_domain_handler(tracker)
        
        task_id = uuid4()
        job_id = uuid4()
        machine_id = uuid4()
        operator_id = uuid4()
        
        # Create sequence of task events
        events = [
            TaskScheduled(
                task_id=task_id,
                job_id=job_id,
                machine_id=machine_id,
                operator_ids=[operator_id],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(hours=2)
            ),
            TaskStarted(
                task_id=task_id,
                job_id=job_id,
                actual_start=datetime.now(),
                machine_id=machine_id,
                operator_ids=[operator_id]
            ),
            TaskCompleted(
                task_id=task_id,
                job_id=job_id,
                actual_end=datetime.now() + timedelta(hours=2),
                actual_duration=Duration(minutes=120)
            )
        ]
        
        # Publish events in sequence
        for event in events:
            event_publisher.publish_domain_event(event)
        
        # Verify progress tracking
        progress = tracker.get_task_progress(task_id)
        assert progress is not None
        assert progress['status'] == 'completed'
        assert progress['job_id'] == job_id
        assert progress['machine_id'] == machine_id
        
        # Verify timeline
        timeline = tracker.get_timeline_for_task(task_id)
        assert len(timeline) == 3
        assert timeline[0]['event_type'] == 'task_scheduled'
        assert timeline[1]['event_type'] == 'task_started'
        assert timeline[2]['event_type'] == 'task_completed'
    
    def test_resource_utilization_tracker(self, event_publisher):
        """Test resource utilization tracking handler."""
        tracker = ResourceUtilizationTracker()
        event_publisher.register_domain_handler(tracker)
        
        machine_id = uuid4()
        operator_id = uuid4()
        task_id = uuid4()
        job_id = uuid4()
        
        # Create resource allocation events
        allocation_events = [
            MachineAllocated(
                machine_id=machine_id,
                task_id=task_id,
                job_id=job_id,
                allocation_start=datetime.now(),
                allocation_end=datetime.now() + timedelta(hours=2)
            ),
            OperatorAssigned(
                operator_id=operator_id,
                task_id=task_id,
                assignment_type="full_duration"
            ),
            ResourceConflictDetected(
                resource_type="machine",
                resource_id=machine_id,
                conflicting_tasks=[task_id, uuid4()],
                conflict_time_start=datetime.now(),
                conflict_time_end=datetime.now() + timedelta(minutes=30)
            ),
            MachineReleased(
                machine_id=machine_id,
                task_id=task_id,
                job_id=job_id,
                release_time=datetime.now() + timedelta(hours=2),
                utilization_hours=2.0
            ),
            OperatorReleased(
                operator_id=operator_id,
                task_id=task_id
            )
        ]
        
        # Publish events
        for event in allocation_events:
            event_publisher.publish_domain_event(event)
        
        # Verify utilization tracking
        machine_util = tracker.get_machine_utilization(machine_id)
        assert machine_util['total_allocations'] == 1
        assert machine_util['active_allocations'] == 0  # Released
        assert machine_util['total_utilized_hours'] == 2.0
        assert machine_util['conflicts'] == 1
        
        operator_workload = tracker.get_operator_workload(operator_id)
        assert operator_workload['total_assignments'] == 1
        assert operator_workload['active_assignments'] == 0  # Released
    
    def test_schedule_quality_monitor(self, event_publisher):
        """Test schedule quality monitoring handler."""
        monitor = ScheduleQualityMonitor()
        event_publisher.register_domain_handler(monitor)
        
        # Create quality-affecting events
        quality_events = [
            TaskDelayed(
                task_id=uuid4(),
                job_id=uuid4(),
                operation_sequence=1,
                original_planned_start=datetime.now(),
                new_planned_start=datetime.now() + timedelta(hours=1),
                delay_minutes=60,
                reason="resource_unavailable"
            ),
            ConstraintViolated(
                constraint_type="precedence_constraint",
                constraint_description="Task dependency violated",
                violated_by=uuid4(),
                violation_details="Task started before predecessor completed"
            ),
            ResourceConflictDetected(
                resource_type="operator",
                resource_id=uuid4(),
                conflicting_tasks=[uuid4(), uuid4()],
                conflict_time_start=datetime.now(),
                conflict_time_end=datetime.now() + timedelta(minutes=45)
            )
        ]
        
        # Publish events
        for event in quality_events:
            event_publisher.publish_domain_event(event)
        
        # Verify quality monitoring
        quality_report = monitor.get_quality_report()
        
        assert quality_report['metrics']['total_delays'] == 1
        assert quality_report['metrics']['total_constraint_violations'] == 1
        assert quality_report['metrics']['resource_conflicts'] == 1
        assert quality_report['quality_score'] < 100  # Should be penalized
        assert len(quality_report['recommendations']) > 0
    
    def test_workflow_orchestrator(self, event_publisher):
        """Test workflow orchestration handler."""
        orchestrator = WorkflowOrchestrator()
        event_publisher.register_domain_handler(orchestrator)
        
        job_id = uuid4()
        
        # Create workflow-triggering events
        workflow_events = [
            JobCreated(
                job_id=job_id,
                job_number="WORKFLOW-001",
                priority=1,
                due_date=None,
                release_date=datetime.now(),
                task_count=3
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=job_id,
                actual_end=datetime.now() + timedelta(hours=1),
                actual_duration=Duration(minutes=60)
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=job_id,
                actual_end=datetime.now() + timedelta(hours=2),
                actual_duration=Duration(minutes=60)
            )
        ]
        
        # Publish events
        for event in workflow_events:
            event_publisher.publish_domain_event(event)
        
        # Verify workflow orchestration
        active_workflows = orchestrator.get_active_workflows()
        assert len(active_workflows) == 1
        
        workflow = active_workflows[0]
        assert workflow['type'] == 'job_processing'
        assert workflow['steps_completed'] == 2  # 2 tasks completed
        assert workflow['progress_percentage'] == 40  # 2/5 = 40%
    
    @pytest.mark.asyncio
    async def test_asynchronous_event_handler_processing(self, event_publisher):
        """Test asynchronous processing of events by handlers."""
        
        class AsyncEventHandler(DomainEventHandler):
            def __init__(self):
                self.processed_events = []
                self.processing_times = []
            
            def can_handle(self, event: DomainEvent) -> bool:
                return True
            
            def handle(self, event: DomainEvent) -> None:
                # Simulate async processing
                start_time = datetime.now()
                # In real async handler, this would be await asyncio.sleep()
                import time
                time.sleep(0.01)  # 10ms processing time
                end_time = datetime.now()
                
                self.processed_events.append(event)
                self.processing_times.append((end_time - start_time).total_seconds())
        
        async_handler = AsyncEventHandler()
        event_publisher.register_domain_handler(async_handler)
        
        # Create multiple events
        events = [
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[]
            )
            for _ in range(5)
        ]
        
        # Publish events
        start_time = datetime.now()
        for event in events:
            event_publisher.publish_domain_event(event)
        end_time = datetime.now()
        
        # Verify all events were processed
        assert len(async_handler.processed_events) == 5
        assert len(async_handler.processing_times) == 5
        
        # Verify processing happened (non-zero times)
        assert all(t > 0 for t in async_handler.processing_times)
    
    def test_event_handler_chaining(self, event_publisher):
        """Test chaining of event handlers and side effects."""
        
        class PrimaryHandler(DomainEventHandler):
            def __init__(self, publisher):
                self.publisher = publisher
                self.processed_events = []
            
            def can_handle(self, event: DomainEvent) -> bool:
                return isinstance(event, TaskCompleted)
            
            def handle(self, event: DomainEvent) -> None:
                self.processed_events.append(event)
                
                # Trigger secondary event as side effect
                secondary_event = JobStatusChanged(
                    job_id=event.job_id,
                    job_number="AUTO-UPDATE",
                    old_status="IN_PROGRESS",
                    new_status="COMPLETED",
                    reason="all_tasks_completed"
                )
                
                # Publish secondary event
                self.publisher.publish_domain_event(secondary_event)
        
        class SecondaryHandler(DomainEventHandler):
            def __init__(self):
                self.processed_events = []
            
            def can_handle(self, event: DomainEvent) -> bool:
                return isinstance(event, JobStatusChanged)
            
            def handle(self, event: DomainEvent) -> None:
                self.processed_events.append(event)
        
        # Set up handlers
        primary_handler = PrimaryHandler(event_publisher)
        secondary_handler = SecondaryHandler()
        
        event_publisher.register_domain_handler(primary_handler)
        event_publisher.register_domain_handler(secondary_handler)
        
        # Trigger initial event
        initial_event = TaskCompleted(
            task_id=uuid4(),
            job_id=uuid4(),
            actual_end=datetime.now(),
            actual_duration=Duration(minutes=90)
        )
        
        event_publisher.publish_domain_event(initial_event)
        
        # Verify event chaining
        assert len(primary_handler.processed_events) == 1
        assert len(secondary_handler.processed_events) == 1
        
        # Verify correct events were processed
        assert primary_handler.processed_events[0] == initial_event
        assert isinstance(secondary_handler.processed_events[0], JobStatusChanged)
    
    def test_handler_performance_metrics(self, event_publisher):
        """Test collection of handler performance metrics."""
        
        class MetricsCollectingHandler(DomainEventHandler):
            def __init__(self):
                self.metrics = {
                    'total_events': 0,
                    'processing_times': [],
                    'event_types': {},
                    'errors': 0
                }
            
            def can_handle(self, event: DomainEvent) -> bool:
                return True
            
            def handle(self, event: DomainEvent) -> None:
                start_time = datetime.now()
                
                try:
                    # Simulate event processing
                    import time
                    time.sleep(0.001)  # 1ms processing
                    
                    # Update metrics
                    self.metrics['total_events'] += 1
                    
                    event_type = type(event).__name__
                    self.metrics['event_types'][event_type] = (
                        self.metrics['event_types'].get(event_type, 0) + 1
                    )
                    
                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds() * 1000  # ms
                    self.metrics['processing_times'].append(processing_time)
                    
                except Exception:
                    self.metrics['errors'] += 1
        
        metrics_handler = MetricsCollectingHandler()
        event_publisher.register_domain_handler(metrics_handler)
        
        # Generate diverse events
        events = [
            TaskScheduled(
                task_id=uuid4(),
                job_id=uuid4(),
                machine_id=uuid4(),
                operator_ids=[],
                planned_start=datetime.now(),
                planned_end=datetime.now() + timedelta(hours=1)
            ),
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[]
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_end=datetime.now(),
                actual_duration=Duration(minutes=60)
            )
        ]
        
        # Publish events
        for event in events:
            event_publisher.publish_domain_event(event)
        
        # Verify metrics collection
        metrics = metrics_handler.metrics
        
        assert metrics['total_events'] == 3
        assert len(metrics['processing_times']) == 3
        assert metrics['errors'] == 0
        
        # Verify event type tracking
        assert 'TaskScheduled' in metrics['event_types']
        assert 'TaskStarted' in metrics['event_types']
        assert 'TaskCompleted' in metrics['event_types']
        
        # Verify processing times are reasonable (> 0 and < 100ms)
        assert all(0 < time < 100 for time in metrics['processing_times'])


class TestEventHandlerIntegrationScenarios:
    """Test realistic integration scenarios with multiple handlers."""
    
    @pytest.fixture
    def integrated_event_system(self):
        """Set up integrated event system with multiple handlers."""
        event_bus = InMemoryEventBus()
        event_publisher = DomainEventPublisher(event_bus)
        
        # Create and register all handlers
        handlers = {
            'progress_tracker': TaskProgressTracker(),
            'resource_tracker': ResourceUtilizationTracker(),
            'quality_monitor': ScheduleQualityMonitor(),
            'workflow_orchestrator': WorkflowOrchestrator()
        }
        
        for handler in handlers.values():
            event_publisher.register_domain_handler(handler)
        
        return {
            'event_publisher': event_publisher,
            'handlers': handlers,
            'event_bus': event_bus
        }
    
    def test_complete_job_lifecycle_event_flow(self, integrated_event_system):
        """Test complete job lifecycle with all handlers processing events."""
        publisher = integrated_event_system['event_publisher']
        handlers = integrated_event_system['handlers']
        
        job_id = uuid4()
        task_id = uuid4()
        machine_id = uuid4()
        operator_id = uuid4()
        
        # Complete job lifecycle events
        lifecycle_events = [
            # Job creation
            JobCreated(
                job_id=job_id,
                job_number="LIFECYCLE-001",
                priority=1,
                due_date=datetime.now() + timedelta(days=3),
                release_date=datetime.now(),
                task_count=1
            ),
            
            # Task scheduling
            TaskScheduled(
                task_id=task_id,
                job_id=job_id,
                machine_id=machine_id,
                operator_ids=[operator_id],
                planned_start=datetime.now() + timedelta(hours=1),
                planned_end=datetime.now() + timedelta(hours=3)
            ),
            
            # Resource allocation
            MachineAllocated(
                machine_id=machine_id,
                task_id=task_id,
                job_id=job_id,
                allocation_start=datetime.now() + timedelta(hours=1),
                allocation_end=datetime.now() + timedelta(hours=3)
            ),
            
            OperatorAssigned(
                operator_id=operator_id,
                task_id=task_id,
                assignment_type="full_duration"
            ),
            
            # Task execution
            TaskStarted(
                task_id=task_id,
                job_id=job_id,
                actual_start=datetime.now() + timedelta(hours=1, minutes=5),
                machine_id=machine_id,
                operator_ids=[operator_id]
            ),
            
            # Task completion
            TaskCompleted(
                task_id=task_id,
                job_id=job_id,
                actual_end=datetime.now() + timedelta(hours=3, minutes=10),
                actual_duration=Duration(minutes=125)
            ),
            
            # Resource release
            MachineReleased(
                machine_id=machine_id,
                task_id=task_id,
                job_id=job_id,
                release_time=datetime.now() + timedelta(hours=3, minutes=10),
                utilization_hours=2.0
            ),
            
            OperatorReleased(
                operator_id=operator_id,
                task_id=task_id
            )
        ]
        
        # Publish all events
        for event in lifecycle_events:
            publisher.publish_domain_event(event)
        
        # Verify all handlers processed relevant events
        
        # Progress tracker should track task progress
        progress = handlers['progress_tracker'].get_task_progress(task_id)
        assert progress is not None
        assert progress['status'] == 'completed'
        
        timeline = handlers['progress_tracker'].get_timeline_for_task(task_id)
        assert len(timeline) >= 3  # scheduled, started, completed
        
        # Resource tracker should track utilization
        machine_util = handlers['resource_tracker'].get_machine_utilization(machine_id)
        assert machine_util['total_allocations'] == 1
        assert machine_util['total_utilized_hours'] == 2.0
        
        operator_workload = handlers['resource_tracker'].get_operator_workload(operator_id)
        assert operator_workload['total_assignments'] == 1
        
        # Quality monitor should have metrics
        quality_report = handlers['quality_monitor'].get_quality_report()
        assert 'quality_score' in quality_report
        
        # Workflow orchestrator should have active workflow
        workflows = handlers['workflow_orchestrator'].get_active_workflows()
        assert len(workflows) >= 1
    
    def test_error_propagation_and_recovery(self, integrated_event_system):
        """Test error propagation and recovery in event handling."""
        publisher = integrated_event_system['event_publisher']
        handlers = integrated_event_system['handlers']
        
        # Add a failing handler
        class FailingHandler(DomainEventHandler):
            def __init__(self):
                self.failure_count = 0
            
            def can_handle(self, event: DomainEvent) -> bool:
                return isinstance(event, TaskStarted)
            
            def handle(self, event: DomainEvent) -> None:
                self.failure_count += 1
                raise RuntimeError("Simulated handler failure")
        
        failing_handler = FailingHandler()
        publisher.register_domain_handler(failing_handler)
        
        # Create events that trigger the failing handler
        error_events = [
            TaskStarted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_start=datetime.now(),
                machine_id=uuid4(),
                operator_ids=[]
            ),
            TaskCompleted(
                task_id=uuid4(),
                job_id=uuid4(),
                actual_end=datetime.now(),
                actual_duration=Duration(minutes=60)
            )
        ]
        
        # Publish events - should not fail despite handler errors
        for event in error_events:
            publisher.publish_domain_event(event)
        
        # Verify failing handler was called but other handlers still worked
        assert failing_handler.failure_count == 1  # Only called for TaskStarted
        
        # Verify other handlers still processed events
        quality_report = handlers['quality_monitor'].get_quality_report()
        assert 'quality_score' in quality_report  # Handler still functional


<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Create domain event unit tests - test event creation, validation, and domain event dispatcher functionality", "status": "completed"}, {"id": "2", "content": "Create domain event integration tests - test event publishing, handling, and propagation through the infrastructure event bus", "status": "completed"}, {"id": "3", "content": "Create integration tests for complex scheduling workflows - test end-to-end scheduling scenarios with multiple jobs, tasks, and resource allocations", "status": "completed"}, {"id": "4", "content": "Create property-based tests for critical business rules - test scheduling constraints, resource allocation rules, and timing invariants using hypothesis", "status": "completed"}, {"id": "5", "content": "Create fixtures and test factories for scheduling domain entities - reusable test data for jobs, tasks, operators, machines, and schedules", "status": "completed"}, {"id": "6", "content": "Create event handler mock implementations for testing event propagation and side effects", "status": "completed"}]