"""
Property-Based Testing for Domain Entities

Using Hypothesis to generate comprehensive test cases that explore
the full range of possible inputs and edge cases for domain entities.
"""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, List
from uuid import UUID

import pytest
from hypothesis import assume, given, settings, strategies as st
from hypothesis.extra.datetime import datetimes

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import OperatorAssignment, Task
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    PriorityLevel,
    TaskStatus,
)


# Custom Hypothesis strategies for domain-specific types
@st.composite
def job_numbers(draw):
    """Generate realistic job numbers."""
    prefix = draw(st.sampled_from(["JOB", "AUTO", "AERO", "MED", "ELEC", "PROTO"]))
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    sequence = draw(st.integers(min_value=1, max_value=9999))
    
    return f"{prefix}-{year}{month:02d}-{sequence:04d}"


@st.composite
def customer_names(draw):
    """Generate realistic customer names."""
    companies = [
        "Acme Corp", "Global Industries", "Tech Solutions", "Manufacturing Co",
        "Precision Parts", "Quality Systems", "Advanced Materials", "Custom Fabrication",
        "Industrial Solutions", "Engineering Services"
    ]
    return draw(st.sampled_from(companies))


@st.composite
def part_numbers(draw):
    """Generate realistic part numbers."""
    prefix = draw(st.sampled_from(["PART", "ENG", "ASM", "CMP", "SUB"]))
    numeric = draw(st.integers(min_value=1000, max_value=9999))
    suffix = draw(st.sampled_from(["A", "B", "C", "X", "Y", "Z"]))
    revision = draw(st.integers(min_value=1, max_value=9))
    
    return f"{prefix}-{numeric}-{suffix}{revision}"


@st.composite
def valid_quantities(draw):
    """Generate realistic quantities (avoiding zero and negative)."""
    return draw(st.integers(min_value=1, max_value=100000))


@st.composite
def future_datetimes(draw):
    """Generate future datetime objects."""
    return draw(datetimes(
        min_value=datetime.utcnow() + timedelta(hours=1),
        max_value=datetime.utcnow() + timedelta(days=365)
    ))


@st.composite
def valid_durations_minutes(draw):
    """Generate realistic task durations in minutes."""
    return draw(st.integers(min_value=1, max_value=2880))  # 1 minute to 2 days


class TestJobEntityProperties:
    """Property-based tests for Job entity."""
    
    @given(
        job_number=job_numbers(),
        customer_name=customer_names(),
        part_number=part_numbers(),
        quantity=valid_quantities(),
        priority=st.sampled_from(PriorityLevel),
        due_date=future_datetimes()
    )
    @settings(max_examples=200, deadline=None)
    def test_job_creation_properties(self, job_number, customer_name, part_number, quantity, priority, due_date):
        """Test that Job creation maintains invariants across all valid inputs."""
        # Act
        job = Job.create(
            job_number=job_number,
            due_date=due_date,
            customer_name=customer_name,
            part_number=part_number,
            quantity=quantity,
            priority=priority,
            created_by="test_user"
        )
        
        # Assert properties that should always hold
        assert job.job_number == job_number
        assert job.customer_name == customer_name
        assert job.part_number == part_number
        assert job.quantity == quantity
        assert job.priority == priority
        assert job.due_date == due_date
        
        # Invariants
        assert job.id is not None
        assert isinstance(job.id, UUID)
        assert job.status == JobStatus.PLANNED
        assert job.created_at is not None
        assert job.created_by == "test_user"
        assert len(job.get_all_tasks()) == 0  # New job has no tasks
        
        # Business rules
        assert job.quantity > 0
        assert len(job.job_number.strip()) > 0
        assert len(job.customer_name.strip()) > 0
        assert len(job.part_number.strip()) > 0
    
    @given(
        job_number=job_numbers(),
        customer_name=customer_names(),
        part_number=part_numbers(),
        quantity=valid_quantities(),
        tasks_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, deadline=None)
    def test_job_task_management_properties(self, job_number, customer_name, part_number, quantity, tasks_count):
        """Test job-task relationship properties."""
        # Arrange
        job = Job.create(
            job_number=job_number,
            due_date=datetime.utcnow() + timedelta(days=30),
            customer_name=customer_name,
            part_number=part_number,
            quantity=quantity,
            priority=PriorityLevel.NORMAL,
            created_by="test_user"
        )
        
        tasks = []
        for i in range(tasks_count):
            task = Task.create(
                job_id=job.id,
                operation_id=st.uuids().example(),
                sequence_in_job=(i + 1) * 10,
                planned_duration_minutes=60 + (i * 30)
            )
            tasks.append(task)
            job.add_task(task)
        
        # Assert task management properties
        assert len(job.get_all_tasks()) == tasks_count
        assert job.task_count == tasks_count
        
        # Task sequence properties
        task_sequences = [task.sequence_in_job for task in job.get_all_tasks()]
        assert len(set(task_sequences)) == len(task_sequences)  # All sequences unique
        assert all(seq > 0 for seq in task_sequences)  # All sequences positive
        
        # Job-task relationship properties
        for task in job.get_all_tasks():
            assert task.job_id == job.id
            assert task in tasks
    
    @given(
        initial_priority=st.sampled_from(PriorityLevel),
        new_priority=st.sampled_from(PriorityLevel)
    )
    @settings(max_examples=50)
    def test_job_priority_changes_properties(self, initial_priority, new_priority):
        """Test that priority changes maintain system invariants."""
        # Arrange
        job = Job.create(
            job_number="TEST-001",
            due_date=datetime.utcnow() + timedelta(days=14),
            customer_name="Test Customer",
            part_number="TEST-PART",
            quantity=10,
            priority=initial_priority,
            created_by="test_user"
        )
        
        original_id = job.id
        original_created_at = job.created_at
        
        # Act
        job.update_priority(new_priority, "Priority change test")
        
        # Assert invariants maintained
        assert job.id == original_id  # Identity preserved
        assert job.created_at == original_created_at  # Creation time preserved
        assert job.priority == new_priority  # Priority updated
        
        # Additional properties
        assert job.updated_at is not None
        assert job.updated_at >= original_created_at
    
    @given(
        quantities=st.lists(
            valid_quantities(),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=30)
    def test_job_quantity_consistency_properties(self, quantities):
        """Test quantity handling across different scenarios."""
        jobs = []
        
        for i, qty in enumerate(quantities):
            job = Job.create(
                job_number=f"QTY-TEST-{i+1:03d}",
                due_date=datetime.utcnow() + timedelta(days=7),
                customer_name="Quantity Test Customer",
                part_number=f"QTY-PART-{i+1}",
                quantity=qty,
                priority=PriorityLevel.NORMAL,
                created_by="test_user"
            )
            jobs.append(job)
        
        # Properties that should hold for all jobs
        total_quantity = sum(job.quantity for job in jobs)
        assert total_quantity == sum(quantities)
        assert all(job.quantity > 0 for job in jobs)
        assert all(isinstance(job.quantity, int) for job in jobs)
        
        # Uniqueness properties
        job_numbers = [job.job_number for job in jobs]
        assert len(set(job_numbers)) == len(jobs)  # All job numbers unique


class TestTaskEntityProperties:
    """Property-based tests for Task entity."""
    
    @given(
        job_id=st.uuids(),
        operation_id=st.uuids(),
        sequence=st.integers(min_value=10, max_value=9999),
        duration=valid_durations_minutes(),
        setup_duration=st.integers(min_value=0, max_value=240)
    )
    @settings(max_examples=100, deadline=None)
    def test_task_creation_properties(self, job_id, operation_id, sequence, duration, setup_duration):
        """Test Task creation maintains invariants."""
        # Act
        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=sequence,
            planned_duration_minutes=duration,
            setup_duration_minutes=setup_duration
        )
        
        # Assert properties
        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == sequence
        assert task.planned_duration_minutes == duration
        assert task.setup_duration_minutes == setup_duration
        
        # Invariants
        assert task.id is not None
        assert isinstance(task.id, UUID)
        assert task.status == TaskStatus.PENDING
        assert task.created_at is not None
        
        # Business rules
        assert task.sequence_in_job > 0
        assert task.planned_duration_minutes > 0
        assert task.setup_duration_minutes >= 0
        
        # Total time calculation
        expected_total = duration + setup_duration
        assert task.total_planned_duration_minutes == expected_total
    
    @given(
        duration=valid_durations_minutes(),
        setup_duration=st.integers(min_value=0, max_value=240),
        start_offset_hours=st.integers(min_value=1, max_value=48),
        machine_id=st.uuids()
    )
    @settings(max_examples=50)
    def test_task_scheduling_properties(self, duration, setup_duration, start_offset_hours, machine_id):
        """Test task scheduling maintains time relationships."""
        # Arrange
        task = Task.create(
            job_id=st.uuids().example(),
            operation_id=st.uuids().example(),
            sequence_in_job=10,
            planned_duration_minutes=duration,
            setup_duration_minutes=setup_duration
        )
        
        start_time = datetime.utcnow() + timedelta(hours=start_offset_hours)
        total_duration_hours = (duration + setup_duration) / 60.0
        end_time = start_time + timedelta(hours=total_duration_hours)
        
        # Act
        task.schedule(start_time, end_time, machine_id)
        
        # Assert scheduling properties
        assert task.scheduled_start_time == start_time
        assert task.scheduled_end_time == end_time
        assert task.assigned_machine_id == machine_id
        assert task.status == TaskStatus.SCHEDULED
        
        # Time relationship properties
        assert task.scheduled_end_time > task.scheduled_start_time
        scheduled_duration = task.scheduled_end_time - task.scheduled_start_time
        expected_duration = timedelta(minutes=duration + setup_duration)
        
        # Allow small tolerance for floating point precision
        time_diff = abs(scheduled_duration.total_seconds() - expected_duration.total_seconds())
        assert time_diff < 60  # Less than 1 minute difference
    
    @given(
        sequences=st.lists(
            st.integers(min_value=10, max_value=1000),
            min_size=2,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=30)
    def test_task_sequence_ordering_properties(self, sequences):
        """Test task sequence ordering properties."""
        job_id = st.uuids().example()
        tasks = []
        
        # Create tasks with given sequences
        for seq in sequences:
            task = Task.create(
                job_id=job_id,
                operation_id=st.uuids().example(),
                sequence_in_job=seq,
                planned_duration_minutes=60
            )
            tasks.append(task)
        
        # Properties that should hold
        task_sequences = [task.sequence_in_job for task in tasks]
        assert len(set(task_sequences)) == len(tasks)  # All unique
        assert sorted(task_sequences) == sorted(sequences)  # Matches input
        assert all(seq > 0 for seq in task_sequences)  # All positive
        assert min(task_sequences) >= 10  # All meet minimum


class TestOperatorAssignmentProperties:
    """Property-based tests for OperatorAssignment entity."""
    
    @given(
        task_id=st.uuids(),
        operator_id=st.uuids(),
        assignment_type=st.sampled_from(AssignmentType),
        duration_hours=st.floats(min_value=0.5, max_value=12.0)
    )
    @settings(max_examples=50)
    def test_operator_assignment_properties(self, task_id, operator_id, assignment_type, duration_hours):
        """Test OperatorAssignment creation and properties."""
        # Arrange
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=duration_hours)
        
        # Act
        assignment = OperatorAssignment(
            task_id=task_id,
            operator_id=operator_id,
            assignment_type=assignment_type,
            planned_start_time=start_time,
            planned_end_time=end_time
        )
        
        # Assert properties
        assert assignment.task_id == task_id
        assert assignment.operator_id == operator_id
        assert assignment.assignment_type == assignment_type
        assert assignment.planned_start_time == start_time
        assert assignment.planned_end_time == end_time
        
        # Time relationship properties
        assert assignment.planned_end_time > assignment.planned_start_time
        planned_duration = assignment.planned_end_time - assignment.planned_start_time
        assert planned_duration.total_seconds() > 0
        
        # Duration consistency (within tolerance)
        expected_seconds = duration_hours * 3600
        actual_seconds = planned_duration.total_seconds()
        assert abs(actual_seconds - expected_seconds) < 60  # 1 minute tolerance


class TestDurationValueObjectProperties:
    """Property-based tests for Duration value object."""
    
    @given(
        minutes=st.integers(min_value=1, max_value=10080)  # 1 minute to 1 week
    )
    @settings(max_examples=100)
    def test_duration_minutes_properties(self, minutes):
        """Test Duration creation from minutes."""
        duration = Duration(minutes=minutes)
        
        # Basic properties
        assert duration.total_minutes == minutes
        assert duration.total_hours == minutes / 60.0
        assert duration.total_days == minutes / (60.0 * 24.0)
        
        # Consistency properties
        assert duration.total_minutes > 0
        assert duration.total_hours >= duration.total_minutes / 60.0
        assert duration.total_days >= duration.total_minutes / (60.0 * 24.0)
        
        # String representation properties
        str_repr = str(duration)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0
        assert "minute" in str_repr.lower() or "hour" in str_repr.lower() or "day" in str_repr.lower()
    
    @given(
        hours=st.floats(min_value=0.1, max_value=168.0)  # 6 minutes to 1 week
    )
    @settings(max_examples=50)
    def test_duration_hours_properties(self, hours):
        """Test Duration creation from hours."""
        duration = Duration(hours=hours)
        
        # Conversion properties
        expected_minutes = int(hours * 60)
        assert abs(duration.total_minutes - expected_minutes) <= 1  # Allow rounding
        assert abs(duration.total_hours - hours) < 0.01  # Floating point precision
        
        # Relationship properties
        assert duration.total_hours > 0
        assert duration.total_minutes > 0
        
        if hours >= 1.0:
            assert duration.total_hours >= 1.0
        if hours >= 24.0:
            assert duration.total_days >= 1.0
    
    @given(
        days=st.floats(min_value=0.1, max_value=30.0)  # 2.4 hours to 30 days
    )
    @settings(max_examples=30)
    def test_duration_days_properties(self, days):
        """Test Duration creation from days."""
        duration = Duration(days=days)
        
        # Conversion properties
        expected_hours = days * 24.0
        expected_minutes = int(days * 24.0 * 60.0)
        
        assert abs(duration.total_days - days) < 0.001
        assert abs(duration.total_hours - expected_hours) < 0.1
        assert abs(duration.total_minutes - expected_minutes) <= 60  # Allow some rounding
        
        # Magnitude properties
        if days >= 1.0:
            assert duration.total_hours >= 24.0
            assert duration.total_minutes >= 1440  # 24 * 60


class TestDomainInvariants:
    """Test domain-wide invariants that should hold across all entities."""
    
    @given(
        job_data=st.fixed_dictionaries({
            'job_number': job_numbers(),
            'customer_name': customer_names(),
            'part_number': part_numbers(),
            'quantity': valid_quantities(),
            'priority': st.sampled_from(PriorityLevel),
            'due_date': future_datetimes()
        }),
        task_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20)
    def test_job_task_entity_consistency(self, job_data, task_count):
        """Test consistency between related entities."""
        # Create job
        job = Job.create(
            created_by="test_user",
            **job_data
        )
        
        # Create and add tasks
        tasks = []
        for i in range(task_count):
            task = Task.create(
                job_id=job.id,
                operation_id=st.uuids().example(),
                sequence_in_job=(i + 1) * 10,
                planned_duration_minutes=60 * (i + 1)
            )
            tasks.append(task)
            job.add_task(task)
        
        # Entity relationship invariants
        assert len(job.get_all_tasks()) == task_count
        assert job.task_count == task_count
        
        # Cross-entity consistency
        for task in job.get_all_tasks():
            assert task.job_id == job.id
            assert task in tasks
        
        # Business rule invariants
        sequences = [task.sequence_in_job for task in job.get_all_tasks()]
        assert len(set(sequences)) == len(sequences)  # Unique sequences
        assert all(seq > 0 for seq in sequences)  # Positive sequences
        assert min(sequences) >= 10  # Minimum sequence value
        
        # Temporal consistency
        for task in job.get_all_tasks():
            assert task.created_at >= job.created_at  # Tasks created after job
    
    @given(
        entity_count=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=10)
    def test_uuid_uniqueness_properties(self, entity_count):
        """Test that UUIDs are unique across large numbers of entities."""
        job_ids = set()
        task_ids = set()
        
        for i in range(entity_count):
            # Create job
            job = Job.create(
                job_number=f"UUID-TEST-{i+1:04d}",
                due_date=datetime.utcnow() + timedelta(days=30),
                customer_name="UUID Test Customer",
                part_number=f"UUID-PART-{i+1}",
                quantity=10,
                priority=PriorityLevel.NORMAL,
                created_by="test_user"
            )
            job_ids.add(job.id)
            
            # Create task
            task = Task.create(
                job_id=job.id,
                operation_id=st.uuids().example(),
                sequence_in_job=10,
                planned_duration_minutes=60
            )
            task_ids.add(task.id)
        
        # UUID uniqueness properties
        assert len(job_ids) == entity_count  # All job IDs unique
        assert len(task_ids) == entity_count  # All task IDs unique
        assert job_ids.isdisjoint(task_ids)  # No overlap between job and task IDs
        
        # Type consistency
        assert all(isinstance(job_id, UUID) for job_id in job_ids)
        assert all(isinstance(task_id, UUID) for task_id in task_ids)


# Custom strategies for complex scenarios
@st.composite
def realistic_manufacturing_scenario(draw):
    """Generate realistic manufacturing scenarios."""
    job_count = draw(st.integers(min_value=5, max_value=20))
    industry = draw(st.sampled_from(["automotive", "aerospace", "medical", "electronics"]))
    
    jobs = []
    for i in range(job_count):
        job_number = draw(job_numbers())
        customer = draw(customer_names())
        part_number = draw(part_numbers())
        quantity = draw(valid_quantities())
        priority = draw(st.sampled_from(PriorityLevel))
        due_date = draw(future_datetimes())
        
        job = Job.create(
            job_number=job_number,
            due_date=due_date,
            customer_name=customer,
            part_number=part_number,
            quantity=quantity,
            priority=priority,
            created_by="scenario_user"
        )
        jobs.append(job)
    
    return {
        "industry": industry,
        "jobs": jobs,
        "job_count": job_count
    }


class TestManufacturingScenarios:
    """Property-based tests for complete manufacturing scenarios."""
    
    @given(scenario=realistic_manufacturing_scenario())
    @settings(max_examples=10, deadline=None)
    def test_manufacturing_scenario_properties(self, scenario):
        """Test properties that should hold for any manufacturing scenario."""
        jobs = scenario["jobs"]
        industry = scenario["industry"]
        job_count = scenario["job_count"]
        
        # Scenario consistency
        assert len(jobs) == job_count
        assert industry in ["automotive", "aerospace", "medical", "electronics"]
        
        # Job collection properties
        job_numbers = [job.job_number for job in jobs]
        assert len(set(job_numbers)) == len(jobs)  # Unique job numbers
        
        customer_names = [job.customer_name for job in jobs]
        assert all(len(name) > 2 for name in customer_names)  # Realistic customer names
        
        # Business rule properties
        assert all(job.quantity > 0 for job in jobs)  # Positive quantities
        assert all(job.due_date > datetime.utcnow() for job in jobs)  # Future due dates
        
        # Priority distribution properties (should have variety)
        priorities = [job.priority for job in jobs]
        if len(jobs) >= 10:
            # With enough jobs, should have some priority variety
            unique_priorities = set(priorities)
            assert len(unique_priorities) >= 2  # At least 2 different priorities


if __name__ == "__main__":
    # Run property-based tests with verbose output
    pytest.main(["-v", __file__, "--hypothesis-show-statistics"])
