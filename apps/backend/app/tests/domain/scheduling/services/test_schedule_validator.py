"""
Comprehensive Unit Tests for ScheduleValidator Domain Service

Tests all validation methods including precedence, calendar, resource conflicts,
skill requirements, and business rule validation with proper mocking and edge cases.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from freezegun import freeze_time

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.entities.schedule import Schedule, ScheduleAssignment
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.services.schedule_validator import ScheduleValidator
from app.domain.scheduling.value_objects.business_calendar import BusinessCalendar
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import TaskStatus
from app.domain.scheduling.value_objects.time_window import TimeWindow
from app.tests.database.factories import JobFactory, TaskFactory


@pytest.fixture
def business_calendar():
    """Create a standard business calendar."""
    return BusinessCalendar.standard_calendar()


@pytest.fixture
def schedule_validator(business_calendar):
    """Create ScheduleValidator with standard business calendar."""
    return ScheduleValidator(business_calendar)


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    job = JobFactory.create(
        job_number="TEST-001",
        due_date=datetime(2024, 1, 15, 16, 0),  # 4 PM deadline
        priority=1,
    )
    return job


@pytest.fixture
def sample_tasks():
    """Create sample tasks with dependencies."""
    job_id = uuid4()
    
    task1 = Mock(spec=Task)
    task1.id = uuid4()
    task1.predecessor_ids = []
    task1.status = TaskStatus.READY
    
    task2 = Mock(spec=Task)
    task2.id = uuid4()
    task2.predecessor_ids = [task1.id]
    task2.status = TaskStatus.PENDING
    
    task3 = Mock(spec=Task)
    task3.id = uuid4()
    task3.predecessor_ids = [task2.id]
    task3.status = TaskStatus.PENDING
    
    return [task1, task2, task3]


@pytest.fixture
def sample_schedule():
    """Create a sample schedule for testing."""
    schedule = Mock(spec=Schedule)
    schedule.id = uuid4()
    schedule._assignments = {}
    schedule._machine_timeline = {}
    schedule._operator_timeline = {}
    
    def get_assignment(task_id):
        return schedule._assignments.get(task_id)
    
    schedule.get_assignment = get_assignment
    return schedule


@pytest.fixture
def sample_machines():
    """Create sample machines."""
    machine1 = Mock(spec=Machine)
    machine1.id = uuid4()
    machine1.name = "CNC-001"
    
    machine2 = Mock(spec=Machine)
    machine2.id = uuid4()
    machine2.name = "MILL-002"
    
    return {str(machine1.id): machine1, str(machine2.id): machine2}


@pytest.fixture
def sample_operators():
    """Create sample operators."""
    operator1 = Mock(spec=Operator)
    operator1.id = uuid4()
    operator1.name = "John Doe"
    
    operator2 = Mock(spec=Operator)
    operator2.id = uuid4()
    operator2.name = "Jane Smith"
    
    # Mock can_operate_machine method
    def can_operate_machine(machine):
        return True  # Assume all operators can operate all machines for basic tests
    
    operator1.can_operate_machine = can_operate_machine
    operator2.can_operate_machine = can_operate_machine
    
    return {str(operator1.id): operator1, str(operator2.id): operator2}


class TestScheduleValidator:
    """Test the main ScheduleValidator functionality."""

    def test_initialization(self, business_calendar):
        """Test validator initialization."""
        validator = ScheduleValidator(business_calendar)
        assert validator._calendar == business_calendar

    def test_validate_precedence_constraints_valid_sequence(
        self, schedule_validator, sample_tasks, sample_schedule
    ):
        """Test precedence validation with valid sequence."""
        task1, task2, task3 = sample_tasks
        
        # Create job mock
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        # Create valid schedule assignments (task1 -> task2 -> task3)
        window1 = TimeWindow(
            datetime(2024, 1, 10, 8, 0),
            datetime(2024, 1, 10, 10, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),  # Starts when task1 ends
            datetime(2024, 1, 10, 12, 0)
        )
        window3 = TimeWindow(
            datetime(2024, 1, 10, 13, 0),  # Starts after lunch
            datetime(2024, 1, 10, 15, 0)
        )
        
        sample_schedule._assignments = {
            task1.id: (uuid4(), [uuid4()], window1),
            task2.id: (uuid4(), [uuid4()], window2),
            task3.id: (uuid4(), [uuid4()], window3),
        }
        
        violations = schedule_validator.validate_precedence_constraints(job, sample_schedule)
        assert violations == []

    def test_validate_precedence_constraints_violation(
        self, schedule_validator, sample_tasks, sample_schedule
    ):
        """Test precedence validation with violations."""
        task1, task2, task3 = sample_tasks
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        # Create schedule with precedence violation (task2 starts before task1 ends)
        window1 = TimeWindow(
            datetime(2024, 1, 10, 8, 0),
            datetime(2024, 1, 10, 10, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),  # Starts before task1 ends!
            datetime(2024, 1, 10, 11, 0)
        )
        
        sample_schedule._assignments = {
            task1.id: (uuid4(), [uuid4()], window1),
            task2.id: (uuid4(), [uuid4()], window2),
        }
        
        violations = schedule_validator.validate_precedence_constraints(job, sample_schedule)
        assert len(violations) == 1
        assert "starts before predecessor" in violations[0]
        assert str(task2.id) in violations[0]
        assert str(task1.id) in violations[0]

    def test_validate_precedence_constraints_missing_predecessor(
        self, schedule_validator, sample_tasks, sample_schedule
    ):
        """Test precedence validation with missing predecessor."""
        task1, task2, task3 = sample_tasks
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        # Only schedule task2, but not its predecessor task1
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),
            datetime(2024, 1, 10, 12, 0)
        )
        
        sample_schedule._assignments = {
            task2.id: (uuid4(), [uuid4()], window2),
        }
        
        violations = schedule_validator.validate_precedence_constraints(job, sample_schedule)
        assert len(violations) == 1
        assert "not scheduled" in violations[0]
        assert str(task1.id) in violations[0]

    @freeze_time("2024-01-10 12:00:00")  # Freeze at noon on Wednesday
    def test_validate_calendar_constraints_valid_time(
        self, schedule_validator, sample_schedule
    ):
        """Test calendar validation during valid business hours."""
        task_id = uuid4()
        
        # Schedule task during business hours (9 AM to 11 AM)
        window = TimeWindow(
            datetime(2024, 1, 10, 9, 0),   # 9 AM
            datetime(2024, 1, 10, 11, 0)   # 11 AM
        )
        
        sample_schedule._assignments = {
            task_id: (uuid4(), [uuid4()], window)
        }
        
        violations = schedule_validator.validate_calendar_constraints(sample_schedule)
        assert violations == []

    @freeze_time("2024-01-10 12:00:00")  # Wednesday
    def test_validate_calendar_constraints_outside_hours(
        self, schedule_validator, sample_schedule
    ):
        """Test calendar validation outside business hours."""
        task_id = uuid4()
        
        # Schedule task outside business hours (6 PM to 8 PM)
        window = TimeWindow(
            datetime(2024, 1, 10, 18, 0),  # 6 PM (after 4 PM business end)
            datetime(2024, 1, 10, 20, 0)   # 8 PM
        )
        
        sample_schedule._assignments = {
            task_id: (uuid4(), [uuid4()], window)
        }
        
        violations = schedule_validator.validate_calendar_constraints(sample_schedule)
        assert len(violations) >= 1
        assert any("outside business hours" in v for v in violations)

    def test_validate_resource_conflicts_machine_overlap(
        self, schedule_validator, sample_schedule
    ):
        """Test machine resource conflict detection."""
        machine_id = uuid4()
        task1_id = uuid4()
        task2_id = uuid4()
        
        # Create overlapping time windows on same machine
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),  # Overlaps with window1
            datetime(2024, 1, 10, 12, 0)
        )
        
        # Mock machine timeline with overlapping windows
        sample_schedule._machine_timeline = {
            machine_id: [window1, window2]
        }
        
        violations = schedule_validator.validate_resource_conflicts(sample_schedule)
        assert len(violations) == 1
        assert "overlapping assignments" in violations[0]
        assert str(machine_id) in violations[0]

    def test_validate_resource_conflicts_operator_overlap(
        self, schedule_validator, sample_schedule
    ):
        """Test operator resource conflict detection."""
        operator_id = uuid4()
        
        # Create overlapping time windows for same operator
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 30),  # Overlaps with window1
            datetime(2024, 1, 10, 12, 30)
        )
        
        sample_schedule._operator_timeline = {
            operator_id: [window1, window2]
        }
        
        violations = schedule_validator.validate_resource_conflicts(sample_schedule)
        assert len(violations) == 1
        assert "overlapping assignments" in violations[0]
        assert str(operator_id) in violations[0]

    def test_validate_resource_conflicts_no_overlaps(
        self, schedule_validator, sample_schedule
    ):
        """Test resource conflict validation with no overlaps."""
        machine_id = uuid4()
        operator_id = uuid4()
        
        # Create non-overlapping time windows
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 10, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),  # Starts when window1 ends
            datetime(2024, 1, 10, 11, 0)
        )
        
        sample_schedule._machine_timeline = {machine_id: [window1, window2]}
        sample_schedule._operator_timeline = {operator_id: [window1, window2]}
        
        violations = schedule_validator.validate_resource_conflicts(sample_schedule)
        assert violations == []

    def test_validate_skill_requirements_valid(
        self, schedule_validator, sample_schedule, sample_machines, sample_operators
    ):
        """Test skill requirement validation with valid assignments."""
        task_id = uuid4()
        machine_id = list(sample_machines.keys())[0]
        operator_id = list(sample_operators.keys())[0]
        
        sample_schedule._assignments = {
            task_id: (machine_id, [operator_id], None)
        }
        
        violations = schedule_validator.validate_skill_requirements(
            sample_schedule, sample_machines, sample_operators
        )
        assert violations == []

    def test_validate_skill_requirements_missing_machine(
        self, schedule_validator, sample_schedule, sample_machines, sample_operators
    ):
        """Test skill validation with missing machine."""
        task_id = uuid4()
        missing_machine_id = "missing-machine-id"
        operator_id = list(sample_operators.keys())[0]
        
        sample_schedule._assignments = {
            task_id: (missing_machine_id, [operator_id], None)
        }
        
        violations = schedule_validator.validate_skill_requirements(
            sample_schedule, sample_machines, sample_operators
        )
        assert len(violations) == 1
        assert "Machine" in violations[0] and "not found" in violations[0]

    def test_validate_skill_requirements_missing_operator(
        self, schedule_validator, sample_schedule, sample_machines, sample_operators
    ):
        """Test skill validation with missing operator."""
        task_id = uuid4()
        machine_id = list(sample_machines.keys())[0]
        missing_operator_id = "missing-operator-id"
        
        sample_schedule._assignments = {
            task_id: (machine_id, [missing_operator_id], None)
        }
        
        violations = schedule_validator.validate_skill_requirements(
            sample_schedule, sample_machines, sample_operators
        )
        assert len(violations) == 1
        assert "Operator" in violations[0] and "not found" in violations[0]

    def test_validate_skill_requirements_operator_lacks_skill(
        self, schedule_validator, sample_schedule, sample_machines, sample_operators
    ):
        """Test skill validation when operator lacks required skills."""
        task_id = uuid4()
        machine_id = list(sample_machines.keys())[0]
        operator_id = list(sample_operators.keys())[0]
        
        # Mock operator to not be able to operate the machine
        operator = sample_operators[operator_id]
        operator.can_operate_machine = Mock(return_value=False)
        
        sample_schedule._assignments = {
            task_id: (machine_id, [operator_id], None)
        }
        
        violations = schedule_validator.validate_skill_requirements(
            sample_schedule, sample_machines, sample_operators
        )
        assert len(violations) == 1
        assert "lacks required skills" in violations[0]

    def test_validate_capacity_constraints_within_limits(
        self, schedule_validator, sample_schedule
    ):
        """Test capacity validation within machine limits."""
        machine_id = uuid4()
        
        # Two non-overlapping tasks on machine with capacity 2
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 10, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        
        sample_schedule._assignments = {
            uuid4(): (machine_id, [uuid4()], window1),
            uuid4(): (machine_id, [uuid4()], window2),
        }
        
        machine_capacities = {str(machine_id): 2}
        
        violations = schedule_validator.validate_capacity_constraints(
            sample_schedule, machine_capacities
        )
        assert violations == []

    def test_validate_capacity_constraints_exceeded(
        self, schedule_validator, sample_schedule
    ):
        """Test capacity validation when limits are exceeded."""
        machine_id = uuid4()
        
        # Three overlapping tasks on machine with capacity 2
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 9, 30),  # Overlaps with window1
            datetime(2024, 1, 10, 11, 30)
        )
        window3 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),  # Overlaps with both
            datetime(2024, 1, 10, 12, 0)
        )
        
        task1, task2, task3 = uuid4(), uuid4(), uuid4()
        
        sample_schedule._assignments = {
            task1: (machine_id, [uuid4()], window1),
            task2: (machine_id, [uuid4()], window2),
            task3: (machine_id, [uuid4()], window3),
        }
        
        machine_capacities = {str(machine_id): 2}  # Capacity of 2, but 3 concurrent
        
        violations = schedule_validator.validate_capacity_constraints(
            sample_schedule, machine_capacities
        )
        assert len(violations) == 1
        assert "capacity exceeded" in violations[0]
        assert "3 concurrent tasks" in violations[0]
        assert "capacity is 2" in violations[0]

    def test_validate_complete_valid_schedule(
        self, schedule_validator, sample_job, sample_schedule
    ):
        """Test complete validation of valid schedule."""
        # Mock job to return empty tasks for simplicity
        sample_job.get_tasks_in_sequence = Mock(return_value=[])
        
        is_valid, violations = schedule_validator.validate_complete(sample_job, sample_schedule)
        assert is_valid is True
        assert violations == []

    def test_validate_complete_invalid_schedule(
        self, schedule_validator, sample_tasks, sample_schedule
    ):
        """Test complete validation of invalid schedule."""
        task1, task2, task3 = sample_tasks
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        # Create schedule with precedence violation
        window1 = TimeWindow(
            datetime(2024, 1, 10, 8, 0),
            datetime(2024, 1, 10, 10, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),  # Starts before task1 ends
            datetime(2024, 1, 10, 11, 0)
        )
        
        sample_schedule._assignments = {
            task1.id: (uuid4(), [uuid4()], window1),
            task2.id: (uuid4(), [uuid4()], window2),
        }
        
        is_valid, violations = schedule_validator.validate_complete(job, sample_schedule)
        assert is_valid is False
        assert len(violations) >= 1

    def test_validate_task_readiness_valid(
        self, schedule_validator, sample_tasks
    ):
        """Test task readiness validation with valid states."""
        task1, task2, task3 = sample_tasks
        
        # Set up valid states: task1 ready, task2 and task3 pending
        task1.status = TaskStatus.READY
        task2.status = TaskStatus.PENDING
        task3.status = TaskStatus.PENDING
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        # Mock get_task method
        def get_task(task_id):
            for task in sample_tasks:
                if task.id == task_id:
                    return task
            return None
        
        job.get_task = get_task
        
        # Mock can_start method to return True for task1
        task1.can_start = Mock(return_value=True)
        
        violations = schedule_validator.validate_task_readiness(job)
        assert violations == []

    def test_validate_task_readiness_violation(
        self, schedule_validator, sample_tasks
    ):
        """Test task readiness validation with violations."""
        task1, task2, task3 = sample_tasks
        
        # Set task2 as ready but its predecessor (task1) is still pending
        task1.status = TaskStatus.PENDING  # Not completed
        task2.status = TaskStatus.READY  # But marked as ready
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = sample_tasks
        
        def get_task(task_id):
            for task in sample_tasks:
                if task.id == task_id:
                    return task
            return None
        
        job.get_task = get_task
        
        # Mock can_start to return False (predecessor not complete)
        task2.can_start = Mock(return_value=False)
        
        violations = schedule_validator.validate_task_readiness(job)
        assert len(violations) == 1
        assert "ready but predecessors are not completed" in violations[0]

    def test_validate_due_date_feasibility_on_time(
        self, schedule_validator, sample_job, sample_schedule
    ):
        """Test due date validation when schedule meets deadline."""
        # Job due at 4 PM
        sample_job.due_date = datetime(2024, 1, 10, 16, 0)
        
        # Create task that completes by 3 PM
        task = Mock(spec=Task)
        task.id = uuid4()
        
        window = TimeWindow(
            datetime(2024, 1, 10, 13, 0),
            datetime(2024, 1, 10, 15, 0)  # Ends at 3 PM
        )
        
        sample_schedule._assignments = {task.id: (uuid4(), [uuid4()], window)}
        sample_job.get_tasks_in_sequence = Mock(return_value=[task])
        
        violations = schedule_validator.validate_due_date_feasibility(sample_job, sample_schedule)
        assert violations == []

    def test_validate_due_date_feasibility_late(
        self, schedule_validator, sample_job, sample_schedule
    ):
        """Test due date validation when schedule misses deadline."""
        # Job due at 4 PM
        sample_job.due_date = datetime(2024, 1, 10, 16, 0)
        
        # Create task that completes at 6 PM (2 hours late)
        task = Mock(spec=Task)
        task.id = uuid4()
        
        window = TimeWindow(
            datetime(2024, 1, 10, 16, 0),
            datetime(2024, 1, 10, 18, 0)  # Ends at 6 PM
        )
        
        sample_schedule._assignments = {task.id: (uuid4(), [uuid4()], window)}
        sample_job.get_tasks_in_sequence = Mock(return_value=[task])
        
        violations = schedule_validator.validate_due_date_feasibility(sample_job, sample_schedule)
        assert len(violations) == 1
        assert "will miss due date by 2.0 hours" in violations[0]

    def test_validate_due_date_feasibility_no_due_date(
        self, schedule_validator, sample_schedule
    ):
        """Test due date validation with no due date set."""
        job = Mock(spec=Job)
        job.due_date = None
        job.get_tasks_in_sequence = Mock(return_value=[])
        
        violations = schedule_validator.validate_due_date_feasibility(job, sample_schedule)
        assert violations == []

    def test_validate_work_in_progress_limits_placeholder(
        self, schedule_validator, sample_schedule
    ):
        """Test WIP limits validation (placeholder implementation)."""
        wip_limits = {"zone1": 5, "zone2": 3}
        
        violations = schedule_validator.validate_work_in_progress_limits(
            sample_schedule, wip_limits
        )
        # Current implementation returns empty list
        assert violations == []


class TestScheduleValidatorEdgeCases:
    """Test edge cases and error conditions."""

    def test_validate_empty_schedule(self, schedule_validator):
        """Test validation of empty schedule."""
        job = Mock(spec=Job)
        job.get_tasks_in_sequence = Mock(return_value=[])
        
        schedule = Mock(spec=Schedule)
        schedule._assignments = {}
        schedule._machine_timeline = {}
        schedule._operator_timeline = {}
        
        is_valid, violations = schedule_validator.validate_complete(job, schedule)
        assert is_valid is True
        assert violations == []

    def test_validate_precedence_missing_task_in_job(
        self, schedule_validator, sample_schedule
    ):
        """Test precedence validation when task is missing from job."""
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        task1.predecessor_ids = [uuid4()]  # References non-existent task
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = [task1]
        job.get_task = Mock(return_value=None)  # Task not found
        
        violations = schedule_validator.validate_task_readiness(job)
        assert len(violations) >= 1
        assert "not found" in violations[0]

    def test_calendar_constraints_weekend_business_calendar(self):
        """Test calendar validation with weekend working hours."""
        # Create calendar that works on weekends
        weekend_calendar = BusinessCalendar.create_24_7()
        validator = ScheduleValidator(weekend_calendar)
        
        schedule = Mock(spec=Schedule)
        task_id = uuid4()
        
        # Schedule on Saturday
        window = TimeWindow(
            datetime(2024, 1, 13, 10, 0),  # Saturday
            datetime(2024, 1, 13, 12, 0)
        )
        
        schedule._assignments = {task_id: (uuid4(), [uuid4()], window)}
        
        violations = validator.validate_calendar_constraints(schedule)
        assert violations == []  # Should be valid for 24/7 calendar

    def test_resource_conflicts_same_time_different_resources(
        self, schedule_validator, sample_schedule
    ):
        """Test that same time windows on different resources don't conflict."""
        machine1 = uuid4()
        machine2 = uuid4()
        operator1 = uuid4()
        operator2 = uuid4()
        
        # Same time window, different resources
        window = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        
        sample_schedule._machine_timeline = {
            machine1: [window],
            machine2: [window]  # Same time, different machine - OK
        }
        sample_schedule._operator_timeline = {
            operator1: [window],
            operator2: [window]  # Same time, different operator - OK
        }
        
        violations = schedule_validator.validate_resource_conflicts(sample_schedule)
        assert violations == []

    def test_capacity_constraints_default_capacity(
        self, schedule_validator, sample_schedule
    ):
        """Test capacity validation with default capacity (1)."""
        machine_id = uuid4()
        
        # Two overlapping tasks, no capacity specified (defaults to 1)
        window1 = TimeWindow(
            datetime(2024, 1, 10, 9, 0),
            datetime(2024, 1, 10, 11, 0)
        )
        window2 = TimeWindow(
            datetime(2024, 1, 10, 10, 0),  # Overlaps
            datetime(2024, 1, 10, 12, 0)
        )
        
        sample_schedule._assignments = {
            uuid4(): (machine_id, [uuid4()], window1),
            uuid4(): (machine_id, [uuid4()], window2),
        }
        
        machine_capacities = {}  # No capacity specified
        
        violations = schedule_validator.validate_capacity_constraints(
            sample_schedule, machine_capacities
        )
        assert len(violations) == 1
        assert "capacity exceeded" in violations[0]
        assert "capacity is 1" in violations[0]


class TestScheduleValidatorIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_manufacturing_workflow_validation(
        self, schedule_validator, sample_machines, sample_operators
    ):
        """Test complete manufacturing workflow validation."""
        # Create a realistic job with sequential tasks
        job = JobFactory.create_with_tasks(task_count=3)
        tasks = list(job._tasks.values())
        
        # Set up task dependencies
        tasks[1].predecessor_ids = [tasks[0].id]
        tasks[2].predecessor_ids = [tasks[1].id]
        
        # Create schedule with proper sequencing
        schedule = Mock(spec=Schedule)
        schedule._assignments = {}
        schedule._machine_timeline = {}
        schedule._operator_timeline = {}
        
        # Sequential non-overlapping assignments
        base_time = datetime(2024, 1, 10, 8, 0)
        for i, task in enumerate(tasks):
            start_time = base_time + timedelta(hours=i * 2)
            end_time = start_time + timedelta(hours=1.5)
            window = TimeWindow(start_time, end_time)
            
            schedule._assignments[task.id] = (
                uuid4(),  # machine_id
                [uuid4()],  # operator_ids
                window
            )
        
        def get_assignment(task_id):
            return schedule._assignments.get(task_id)
        
        schedule.get_assignment = get_assignment
        
        is_valid, violations = schedule_validator.validate_complete(job, schedule)
        assert is_valid is True
        assert violations == []

    def test_rush_order_validation(self, schedule_validator):
        """Test validation of rush order with tight constraints."""
        # Create urgent job
        job = JobFactory.create_urgent()
        task1 = TaskFactory.create(job_id=job.id, sequence_in_job=10)
        task2 = TaskFactory.create(job_id=job.id, sequence_in_job=20)
        task2.predecessor_ids = [task1.id]
        
        job._tasks = {task1.id: task1, task2.id: task2}
        
        # Create tight schedule that might violate due date
        schedule = Mock(spec=Schedule)
        
        # Task 1: 8 AM - 12 PM (4 hours)
        window1 = TimeWindow(
            datetime(2024, 1, 10, 8, 0),
            datetime(2024, 1, 10, 12, 0)
        )
        
        # Task 2: 1 PM - 6 PM (5 hours) - extends beyond business hours
        window2 = TimeWindow(
            datetime(2024, 1, 10, 13, 0),
            datetime(2024, 1, 10, 18, 0)  # 6 PM - after business hours
        )
        
        schedule._assignments = {
            task1.id: (uuid4(), [uuid4()], window1),
            task2.id: (uuid4(), [uuid4()], window2),
        }
        
        def get_assignment(task_id):
            return schedule._assignments.get(task_id)
        
        schedule.get_assignment = get_assignment
        
        violations = schedule_validator.validate_calendar_constraints(schedule)
        assert len(violations) >= 1  # Should detect business hours violation

    def test_complex_precedence_network(self, schedule_validator):
        """Test validation of complex precedence network."""
        job_id = uuid4()
        
        # Create complex precedence network:
        # T1 -> T3
        # T2 -> T3
        # T3 -> T4
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        task1.predecessor_ids = []
        
        task2 = Mock(spec=Task)
        task2.id = uuid4()
        task2.predecessor_ids = []
        
        task3 = Mock(spec=Task)
        task3.id = uuid4()
        task3.predecessor_ids = [task1.id, task2.id]  # Depends on both T1 and T2
        
        task4 = Mock(spec=Task)
        task4.id = uuid4()
        task4.predecessor_ids = [task3.id]
        
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = [task1, task2, task3, task4]
        
        # Create valid schedule: T1 and T2 in parallel, then T3, then T4
        schedule = Mock(spec=Schedule)
        
        window1 = TimeWindow(datetime(2024, 1, 10, 8, 0), datetime(2024, 1, 10, 10, 0))
        window2 = TimeWindow(datetime(2024, 1, 10, 8, 0), datetime(2024, 1, 10, 9, 0))  # Parallel with T1
        window3 = TimeWindow(datetime(2024, 1, 10, 10, 0), datetime(2024, 1, 10, 12, 0))  # After T1 and T2
        window4 = TimeWindow(datetime(2024, 1, 10, 13, 0), datetime(2024, 1, 10, 15, 0))  # After T3
        
        schedule._assignments = {
            task1.id: (uuid4(), [uuid4()], window1),
            task2.id: (uuid4(), [uuid4()], window2),
            task3.id: (uuid4(), [uuid4()], window3),
            task4.id: (uuid4(), [uuid4()], window4),
        }
        
        violations = schedule_validator.validate_precedence_constraints(job, schedule)
        assert violations == []  # Should be valid