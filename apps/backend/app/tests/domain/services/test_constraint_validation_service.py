"""
Comprehensive Unit Tests for Constraint Validation Service

Tests all constraint validation logic including precedence, WIP limits,
resource conflicts, skill requirements, and business rules.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.entities.schedule import Schedule, ScheduleAssignment
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.services.constraint_validation_service import (
    ConstraintValidationService,
    WIPZone,
)
from app.domain.scheduling.value_objects.enums import SkillLevel
from app.domain.scheduling.value_objects.skill_requirement import SkillRequirement


class TestWIPZone:
    """Test WIP Zone constraints."""

    def test_create_wip_zone(self):
        """Test creating a WIP zone."""
        zone = WIPZone(start_position=10, end_position=30, max_jobs=5, name="Test Zone")

        assert zone.start_position == 10
        assert zone.end_position == 30
        assert zone.max_jobs == 5
        assert zone.name == "Test Zone"

    def test_create_wip_zone_default_name(self):
        """Test creating WIP zone with default name."""
        zone = WIPZone(start_position=10, end_position=30, max_jobs=5)
        assert zone.name == "Zone_10_30"

    def test_wip_zone_contains_position(self):
        """Test position containment in WIP zone."""
        zone = WIPZone(start_position=20, end_position=40, max_jobs=3)

        assert zone.contains_position(20)  # Start boundary
        assert zone.contains_position(30)  # Middle
        assert zone.contains_position(40)  # End boundary
        assert not zone.contains_position(19)  # Before
        assert not zone.contains_position(41)  # After


@pytest.fixture
def mock_repositories():
    """Create mock repositories for testing."""
    return {
        "job_repository": Mock(),
        "task_repository": AsyncMock(),
        "operator_repository": AsyncMock(),
        "machine_repository": AsyncMock(),
    }


@pytest.fixture
def constraint_service(mock_repositories):
    """Create constraint validation service with mock repositories."""
    return ConstraintValidationService(
        job_repository=mock_repositories["job_repository"],
        task_repository=mock_repositories["task_repository"],
        operator_repository=mock_repositories["operator_repository"],
        machine_repository=mock_repositories["machine_repository"],
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    task = Mock(spec=Task)
    task.id = uuid4()
    task.position_in_job = 20
    task.is_attended = True
    task.skill_requirements = []
    task.task_type = Mock()
    task.task_type.value = "MACHINING"

    def requires_multiple_operators():
        return False

    task.requires_multiple_operators = requires_multiple_operators
    return task


@pytest.fixture
def sample_machine():
    """Create a sample machine for testing."""
    machine = Mock(spec=Machine)
    machine.id = uuid4()

    def can_perform_task_type(task_type):
        return task_type in ["MACHINING", "ASSEMBLY"]

    machine.can_perform_task_type = can_perform_task_type
    return machine


@pytest.fixture
def sample_operator():
    """Create a sample operator for testing."""
    operator = Mock(spec=Operator)
    operator.id = uuid4()

    def has_skill(skill_type, min_level):
        return skill_type == "MACHINING" and min_level <= SkillLevel.PROFICIENT

    operator.has_skill = has_skill
    return operator


@pytest.fixture
def sample_schedule():
    """Create a sample schedule for testing."""
    schedule = Mock(spec=Schedule)
    schedule.assignments = {}
    schedule.job_ids = {uuid4(), uuid4()}

    def get_assignment(task_id):
        return schedule.assignments.get(task_id)

    schedule.get_assignment = get_assignment
    return schedule


class TestConstraintValidationService:
    """Test the main constraint validation service."""

    def test_service_initialization(self, mock_repositories):
        """Test service initialization with repositories."""
        service = ConstraintValidationService(
            job_repository=mock_repositories["job_repository"],
            task_repository=mock_repositories["task_repository"],
            operator_repository=mock_repositories["operator_repository"],
            machine_repository=mock_repositories["machine_repository"],
        )

        assert service._job_repository == mock_repositories["job_repository"]
        assert service._task_repository == mock_repositories["task_repository"]
        assert service._operator_repository == mock_repositories["operator_repository"]
        assert service._machine_repository == mock_repositories["machine_repository"]

    def test_default_configuration(self, constraint_service):
        """Test default business rules configuration."""
        # Business hours
        assert constraint_service._work_start_minutes == 7 * 60  # 7 AM
        assert constraint_service._work_end_minutes == 16 * 60  # 4 PM
        assert constraint_service._lunch_start_minutes == 12 * 60  # Noon
        assert constraint_service._lunch_end_minutes == 12 * 60 + 45  # 12:45 PM

        # Holiday days
        assert constraint_service._holiday_days == {5, 12, 26}

        # WIP zones
        assert len(constraint_service._wip_zones) == 3
        assert constraint_service._wip_zones[0].start_position == 0
        assert constraint_service._wip_zones[0].end_position == 30
        assert constraint_service._wip_zones[0].max_jobs == 3

        # Critical sequences
        assert len(constraint_service._critical_sequences) == 4
        assert (20, 28, "Critical Welding") in constraint_service._critical_sequences

    @pytest.mark.asyncio
    async def test_validate_empty_schedule(self, constraint_service, sample_schedule):
        """Test validating empty schedule."""
        sample_schedule.assignments = {}
        violations = await constraint_service.validate_schedule(sample_schedule)
        assert violations == []

    @pytest.mark.asyncio
    async def test_validate_schedule_with_assignments(
        self, constraint_service, sample_schedule, mock_repositories
    ):
        """Test validating schedule with assignments."""
        # Create test assignment
        task_id = uuid4()
        assignment = Mock(spec=ScheduleAssignment)
        assignment.task_id = task_id
        assignment.machine_id = uuid4()
        assignment.operator_ids = [uuid4()]
        assignment.start_time = datetime(2024, 1, 1, 9, 0)
        assignment.end_time = datetime(2024, 1, 1, 11, 0)

        sample_schedule.assignments = {task_id: assignment}

        # Mock repository responses
        task = Mock(spec=Task)
        task.id = task_id
        task.is_attended = False
        task.skill_requirements = []
        task.task_type = Mock()
        task.task_type.value = "MACHINING"
        task.requires_multiple_operators = lambda: False

        machine = Mock(spec=Machine)
        machine.id = assignment.machine_id
        machine.can_perform_task_type = lambda x: True

        operator = Mock(spec=Operator)
        operator.id = assignment.operator_ids[0]

        mock_repositories["task_repository"].get_by_id.return_value = task
        mock_repositories["machine_repository"].get_by_id.return_value = machine
        mock_repositories["operator_repository"].get_by_id.return_value = operator
        mock_repositories["task_repository"].get_by_job_id.return_value = []

        violations = await constraint_service.validate_schedule(sample_schedule)
        assert isinstance(violations, list)

    def test_validate_machine_capability_valid(
        self, constraint_service, sample_task, sample_machine
    ):
        """Test machine capability validation - valid case."""
        sample_task.task_type.value = "MACHINING"
        violations = constraint_service._validate_machine_capability(
            sample_task, sample_machine
        )
        assert violations == []

    def test_validate_machine_capability_invalid(
        self, constraint_service, sample_task, sample_machine
    ):
        """Test machine capability validation - invalid case."""
        sample_task.task_type.value = "WELDING"  # Machine can't do welding
        violations = constraint_service._validate_machine_capability(
            sample_task, sample_machine
        )
        assert len(violations) == 1
        assert "cannot perform task type WELDING" in violations[0]

    def test_validate_operator_skills_valid(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test operator skills validation - valid case."""
        skill_req = Mock(spec=SkillRequirement)
        skill_req.skill_type = "MACHINING"
        skill_req.minimum_level = SkillLevel.BASIC
        sample_task.skill_requirements = [skill_req]

        violations = constraint_service._validate_operator_skills(
            sample_task, [sample_operator]
        )
        assert violations == []

    def test_validate_operator_skills_missing_skill(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test operator skills validation - missing skill."""
        skill_req = Mock(spec=SkillRequirement)
        skill_req.skill_type = "WELDING"  # Operator doesn't have this skill
        skill_req.minimum_level = SkillLevel.BASIC
        sample_task.skill_requirements = [skill_req]

        violations = constraint_service._validate_operator_skills(
            sample_task, [sample_operator]
        )
        assert len(violations) == 1
        assert "No operator has required skill WELDING" in violations[0]

    def test_validate_operator_skills_insufficient_level(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test operator skills validation - insufficient skill level."""
        skill_req = Mock(spec=SkillRequirement)
        skill_req.skill_type = "MACHINING"
        skill_req.minimum_level = SkillLevel.EXPERT  # Operator only has PROFICIENT
        sample_task.skill_requirements = [skill_req]

        violations = constraint_service._validate_operator_skills(
            sample_task, [sample_operator]
        )
        assert len(violations) == 1
        assert "No operator has required skill MACHINING (level" in violations[0]

    def test_validate_business_hours_unattended_task(
        self, constraint_service, sample_task
    ):
        """Test business hours validation for unattended task."""
        sample_task.is_attended = False
        start_time = datetime(2024, 1, 1, 2, 0)  # 2 AM
        end_time = datetime(2024, 1, 1, 6, 0)  # 6 AM

        violations = constraint_service._validate_business_hours(
            sample_task, start_time, end_time
        )
        assert violations == []  # Unattended tasks can run anytime

    def test_validate_business_hours_valid_hours(self, constraint_service, sample_task):
        """Test business hours validation - valid hours."""
        start_time = datetime(2024, 1, 1, 9, 0)  # 9 AM
        end_time = datetime(2024, 1, 1, 11, 0)  # 11 AM

        violations = constraint_service._validate_business_hours(
            sample_task, start_time, end_time
        )
        assert violations == []

    def test_validate_business_hours_outside_hours(
        self, constraint_service, sample_task
    ):
        """Test business hours validation - outside hours."""
        start_time = datetime(2024, 1, 1, 6, 0)  # 6 AM (before work hours)
        end_time = datetime(2024, 1, 1, 8, 0)  # 8 AM

        violations = constraint_service._validate_business_hours(
            sample_task, start_time, end_time
        )
        assert len(violations) == 1
        assert "scheduled outside business hours" in violations[0]

    def test_validate_business_hours_during_lunch(
        self, constraint_service, sample_task
    ):
        """Test business hours validation - during lunch."""
        start_time = datetime(2024, 1, 1, 11, 30)  # 11:30 AM
        end_time = datetime(2024, 1, 1, 13, 0)  # 1:00 PM (overlaps lunch)

        violations = constraint_service._validate_business_hours(
            sample_task, start_time, end_time
        )
        assert len(violations) == 1
        assert "overlaps lunch break" in violations[0]

    def test_validate_business_hours_holiday(self, constraint_service, sample_task):
        """Test business hours validation - holiday."""
        # Day 5 is configured as holiday
        start_time = datetime(2024, 1, 5, 9, 0)
        end_time = datetime(2024, 1, 5, 11, 0)

        violations = constraint_service._validate_business_hours(
            sample_task, start_time, end_time
        )
        assert len(violations) == 1
        assert "scheduled on holiday" in violations[0]

    def test_validate_operator_count_single_operator_valid(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test operator count validation - single operator valid."""
        violations = constraint_service._validate_operator_count(
            sample_task, [sample_operator]
        )
        assert violations == []

    def test_validate_operator_count_wrong_count(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test operator count validation - wrong count."""
        # Task requires 1 operator, but 2 provided
        operator2 = Mock(spec=Operator)
        operator2.id = uuid4()

        violations = constraint_service._validate_operator_count(
            sample_task, [sample_operator, operator2]
        )
        assert len(violations) == 1
        assert "requires 1 operators, but 2 assigned" in violations[0]

    def test_validate_operator_count_multi_operator_task(
        self, constraint_service, sample_operator
    ):
        """Test operator count validation - multi-operator task."""
        # Task requires multiple operators
        task = Mock(spec=Task)
        task.id = uuid4()
        task.requires_multiple_operators = lambda: True

        operator2 = Mock(spec=Operator)
        operator2.id = uuid4()

        violations = constraint_service._validate_operator_count(
            task, [sample_operator, operator2]
        )
        assert violations == []

    def test_validate_operator_count_duplicate_operators(
        self, constraint_service, sample_operator
    ):
        """Test operator count validation - duplicate operators."""
        task = Mock(spec=Task)
        task.id = uuid4()
        task.requires_multiple_operators = lambda: True

        # Same operator assigned twice
        violations = constraint_service._validate_operator_count(
            task, [sample_operator, sample_operator]
        )
        assert len(violations) == 1
        assert "duplicate operator assignments" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_task_assignment_all_valid(
        self, constraint_service, sample_task, sample_machine, sample_operator
    ):
        """Test complete task assignment validation - all constraints valid."""
        start_time = datetime(2024, 1, 1, 9, 0)
        end_time = datetime(2024, 1, 1, 11, 0)

        violations = await constraint_service.validate_task_assignment(
            sample_task, sample_machine, [sample_operator], start_time, end_time
        )
        assert violations == []

    @pytest.mark.asyncio
    async def test_validate_task_assignment_multiple_violations(
        self, constraint_service, sample_operator
    ):
        """Test task assignment with multiple violations."""
        # Create task with unsupported type
        task = Mock(spec=Task)
        task.id = uuid4()
        task.position_in_job = 20
        task.is_attended = True
        task.task_type = Mock()
        task.task_type.value = "WELDING"  # Machine can't do this
        task.skill_requirements = []
        task.requires_multiple_operators = lambda: False

        # Create machine that can't do welding
        machine = Mock(spec=Machine)
        machine.id = uuid4()
        machine.can_perform_task_type = lambda x: x == "MACHINING"

        # Schedule outside business hours
        start_time = datetime(2024, 1, 1, 18, 0)  # 6 PM
        end_time = datetime(2024, 1, 1, 20, 0)  # 8 PM

        violations = await constraint_service.validate_task_assignment(
            task, machine, [sample_operator], start_time, end_time
        )

        # Should have both machine capability and business hours violations
        assert len(violations) >= 2
        assert any("cannot perform task type" in v for v in violations)
        assert any("outside business hours" in v for v in violations)

    @pytest.mark.asyncio
    async def test_validate_resource_conflicts_machine(self, constraint_service):
        """Test machine resource conflict validation."""
        schedule = Mock(spec=Schedule)
        machine_id = uuid4()
        task_id1 = uuid4()
        task_id2 = uuid4()

        # Overlapping assignments on same machine
        assignment1 = Mock(spec=ScheduleAssignment)
        assignment1.task_id = task_id1
        assignment1.machine_id = machine_id
        assignment1.operator_ids = [uuid4()]
        assignment1.start_time = datetime(2024, 1, 1, 9, 0)
        assignment1.end_time = datetime(2024, 1, 1, 11, 0)

        assignment2 = Mock(spec=ScheduleAssignment)
        assignment2.task_id = task_id2
        assignment2.machine_id = machine_id  # Same machine
        assignment2.operator_ids = [uuid4()]
        assignment2.start_time = datetime(
            2024, 1, 1, 10, 30
        )  # Overlaps with assignment1
        assignment2.end_time = datetime(2024, 1, 1, 12, 30)

        schedule.assignments = {task_id1: assignment1, task_id2: assignment2}

        violations = await constraint_service._validate_resource_conflicts(schedule)
        assert len(violations) == 1
        assert "Machine" in violations[0] and "double-booked" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_resource_conflicts_operator(self, constraint_service):
        """Test operator resource conflict validation."""
        schedule = Mock(spec=Schedule)
        operator_id = uuid4()
        task_id1 = uuid4()
        task_id2 = uuid4()

        # Overlapping assignments with same operator
        assignment1 = Mock(spec=ScheduleAssignment)
        assignment1.task_id = task_id1
        assignment1.machine_id = uuid4()
        assignment1.operator_ids = [operator_id]
        assignment1.start_time = datetime(2024, 1, 1, 9, 0)
        assignment1.end_time = datetime(2024, 1, 1, 11, 0)

        assignment2 = Mock(spec=ScheduleAssignment)
        assignment2.task_id = task_id2
        assignment2.machine_id = uuid4()
        assignment2.operator_ids = [operator_id]  # Same operator
        assignment2.start_time = datetime(2024, 1, 1, 10, 30)  # Overlaps
        assignment2.end_time = datetime(2024, 1, 1, 12, 30)

        schedule.assignments = {task_id1: assignment1, task_id2: assignment2}

        violations = await constraint_service._validate_resource_conflicts(schedule)
        assert len(violations) == 1
        assert "Operator" in violations[0] and "double-booked" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_precedence_constraints(
        self, constraint_service, mock_repositories
    ):
        """Test precedence constraint validation."""
        job_id = uuid4()

        # Create tasks with precedence
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        task1.position_in_job = 10

        task2 = Mock(spec=Task)
        task2.id = uuid4()
        task2.position_in_job = 20

        mock_repositories["task_repository"].get_by_job_id.return_value = [task1, task2]

        # Create schedule with precedence violation
        schedule = Mock(spec=Schedule)
        schedule.job_ids = {job_id}

        assignment1 = Mock(spec=ScheduleAssignment)
        assignment1.start_time = datetime(2024, 1, 1, 10, 0)
        assignment1.end_time = datetime(2024, 1, 1, 12, 0)

        assignment2 = Mock(spec=ScheduleAssignment)
        assignment2.start_time = datetime(2024, 1, 1, 11, 0)  # Starts before task1 ends
        assignment2.end_time = datetime(2024, 1, 1, 13, 0)

        def get_assignment(task_id):
            if task_id == task1.id:
                return assignment1
            elif task_id == task2.id:
                return assignment2
            return None

        schedule.get_assignment = get_assignment

        violations = await constraint_service.validate_precedence_for_job(
            job_id, schedule
        )
        assert len(violations) == 1
        assert "starts before predecessor" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_wip_constraints(
        self, constraint_service, mock_repositories
    ):
        """Test WIP constraint validation."""
        job_ids = [uuid4(), uuid4(), uuid4(), uuid4()]  # 4 jobs

        schedule = Mock(spec=Schedule)
        schedule.job_ids = set(job_ids)

        # Mock that all jobs overlap the first WIP zone (max 3 jobs allowed)
        async def mock_job_overlaps_zone(job_id, zone, schedule):
            return zone.start_position == 0  # All jobs overlap first zone

        constraint_service._job_overlaps_zone = mock_job_overlaps_zone

        violations = await constraint_service._validate_wip_constraints(schedule)
        assert len(violations) == 1
        assert "WIP limit exceeded" in violations[0]
        assert "4 > 3" in violations[0]

    @pytest.mark.asyncio
    async def test_job_overlaps_zone(self, constraint_service, mock_repositories):
        """Test job-zone overlap detection."""
        job_id = uuid4()
        zone = WIPZone(start_position=20, end_position=40, max_jobs=3)

        # Create task in the zone
        task = Mock(spec=Task)
        task.id = uuid4()
        task.position_in_job = 25  # Within zone

        mock_repositories["task_repository"].get_by_job_id.return_value = [task]

        schedule = Mock(spec=Schedule)
        assignment = Mock(spec=ScheduleAssignment)
        schedule.get_assignment = lambda t_id: assignment if t_id == task.id else None

        result = await constraint_service._job_overlaps_zone(job_id, zone, schedule)
        assert result is True

    @pytest.mark.asyncio
    async def test_job_does_not_overlap_zone(
        self, constraint_service, mock_repositories
    ):
        """Test job does not overlap zone."""
        job_id = uuid4()
        zone = WIPZone(start_position=20, end_position=40, max_jobs=3)

        # Create task outside the zone
        task = Mock(spec=Task)
        task.id = uuid4()
        task.position_in_job = 50  # Outside zone

        mock_repositories["task_repository"].get_by_job_id.return_value = [task]

        schedule = Mock(spec=Schedule)
        schedule.get_assignment = lambda t_id: None

        result = await constraint_service._job_overlaps_zone(job_id, zone, schedule)
        assert result is False


class TestConstraintServiceConfiguration:
    """Test constraint service configuration methods."""

    def test_set_business_hours(self, constraint_service):
        """Test setting business hours."""
        constraint_service.set_business_hours(8, 17)  # 8 AM to 5 PM

        assert constraint_service._work_start_minutes == 8 * 60
        assert constraint_service._work_end_minutes == 17 * 60

    def test_set_lunch_break(self, constraint_service):
        """Test setting lunch break."""
        constraint_service.set_lunch_break(12, 60)  # Noon, 1 hour

        assert constraint_service._lunch_start_minutes == 12 * 60
        assert constraint_service._lunch_end_minutes == 13 * 60  # 12:00 + 60 min

    def test_add_wip_zone(self, constraint_service):
        """Test adding WIP zone."""
        initial_count = len(constraint_service._wip_zones)

        constraint_service.add_wip_zone(50, 60, 2, "Test Zone")

        assert len(constraint_service._wip_zones) == initial_count + 1
        new_zone = constraint_service._wip_zones[-1]
        assert new_zone.start_position == 50
        assert new_zone.end_position == 60
        assert new_zone.max_jobs == 2
        assert new_zone.name == "Test Zone"

    def test_add_critical_sequence(self, constraint_service):
        """Test adding critical sequence."""
        initial_count = len(constraint_service._critical_sequences)

        constraint_service.add_critical_sequence(70, 80, "Test Critical Sequence")

        assert len(constraint_service._critical_sequences) == initial_count + 1
        assert (
            70,
            80,
            "Test Critical Sequence",
        ) in constraint_service._critical_sequences

    def test_set_holiday_days(self, constraint_service):
        """Test setting holiday days."""
        new_holidays = {1, 10, 25, 31}
        constraint_service.set_holiday_days(new_holidays)

        assert constraint_service._holiday_days == new_holidays


class TestConstraintValidationEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_validate_assignment_missing_task(
        self, constraint_service, mock_repositories
    ):
        """Test validation when task is not found."""
        assignment = Mock(spec=ScheduleAssignment)
        assignment.task_id = uuid4()
        assignment.machine_id = uuid4()
        assignment.operator_ids = []

        mock_repositories["task_repository"].get_by_id.return_value = None
        mock_repositories["machine_repository"].get_by_id.return_value = Mock()

        schedule = Mock(spec=Schedule)
        violations = await constraint_service._validate_assignment(assignment, schedule)

        assert len(violations) == 1
        assert "not found" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_assignment_missing_machine(
        self, constraint_service, mock_repositories
    ):
        """Test validation when machine is not found."""
        assignment = Mock(spec=ScheduleAssignment)
        assignment.task_id = uuid4()
        assignment.machine_id = uuid4()
        assignment.operator_ids = []

        mock_repositories["task_repository"].get_by_id.return_value = Mock()
        mock_repositories["machine_repository"].get_by_id.return_value = None

        schedule = Mock(spec=Schedule)
        violations = await constraint_service._validate_assignment(assignment, schedule)

        assert len(violations) == 1
        assert "not found" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_assignment_repository_error(
        self, constraint_service, mock_repositories
    ):
        """Test validation when repository raises exception."""
        assignment = Mock(spec=ScheduleAssignment)
        assignment.task_id = uuid4()
        assignment.machine_id = uuid4()
        assignment.operator_ids = []

        mock_repositories["task_repository"].get_by_id.side_effect = Exception(
            "Database error"
        )

        schedule = Mock(spec=Schedule)
        violations = await constraint_service._validate_assignment(assignment, schedule)

        assert len(violations) == 1
        assert "Error validating assignment" in violations[0]
        assert "Database error" in violations[0]

    def test_validate_operator_skills_empty_requirements(
        self, constraint_service, sample_task, sample_operator
    ):
        """Test validation with no skill requirements."""
        sample_task.skill_requirements = []
        violations = constraint_service._validate_operator_skills(
            sample_task, [sample_operator]
        )
        assert violations == []

    def test_validate_operator_skills_no_operators(
        self, constraint_service, sample_task
    ):
        """Test validation with skill requirements but no operators."""
        skill_req = Mock(spec=SkillRequirement)
        skill_req.skill_type = "MACHINING"
        skill_req.minimum_level = SkillLevel.BASIC
        sample_task.skill_requirements = [skill_req]

        violations = constraint_service._validate_operator_skills(sample_task, [])
        assert len(violations) == 1
        assert "No operator has required skill" in violations[0]

    @pytest.mark.asyncio
    async def test_validate_precedence_empty_tasks(
        self, constraint_service, mock_repositories
    ):
        """Test precedence validation with no tasks."""
        job_id = uuid4()
        mock_repositories["task_repository"].get_by_job_id.return_value = []

        schedule = Mock(spec=Schedule)
        violations = await constraint_service.validate_precedence_for_job(
            job_id, schedule
        )
        assert violations == []

    @pytest.mark.asyncio
    async def test_validate_precedence_single_task(
        self, constraint_service, mock_repositories
    ):
        """Test precedence validation with single task."""
        job_id = uuid4()
        task = Mock(spec=Task)
        task.id = uuid4()
        task.position_in_job = 10

        mock_repositories["task_repository"].get_by_job_id.return_value = [task]

        schedule = Mock(spec=Schedule)
        violations = await constraint_service.validate_precedence_for_job(
            job_id, schedule
        )
        assert violations == []  # Single task has no precedence constraints


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_manufacturing_workflow_validation(
        self, constraint_service, mock_repositories
    ):
        """Test complete manufacturing workflow validation."""
        # Setup a realistic manufacturing scenario
        job_id = uuid4()

        # Three sequential tasks: Setup -> Machining -> Inspection
        setup_task = Mock(spec=Task)
        setup_task.id = uuid4()
        setup_task.position_in_job = 10

        machining_task = Mock(spec=Task)
        machining_task.id = uuid4()
        machining_task.position_in_job = 20

        inspection_task = Mock(spec=Task)
        inspection_task.id = uuid4()
        inspection_task.position_in_job = 30

        mock_repositories["task_repository"].get_by_job_id.return_value = [
            setup_task,
            machining_task,
            inspection_task,
        ]

        # Create schedule with proper sequencing
        schedule = Mock(spec=Schedule)
        schedule.job_ids = {job_id}
        schedule.assignments = {}

        # Properly sequenced assignments
        setup_assignment = Mock(spec=ScheduleAssignment)
        setup_assignment.start_time = datetime(2024, 1, 1, 8, 0)
        setup_assignment.end_time = datetime(2024, 1, 1, 9, 0)

        machining_assignment = Mock(spec=ScheduleAssignment)
        machining_assignment.start_time = datetime(
            2024, 1, 1, 9, 0
        )  # Starts when setup ends
        machining_assignment.end_time = datetime(2024, 1, 1, 12, 0)

        inspection_assignment = Mock(spec=ScheduleAssignment)
        inspection_assignment.start_time = datetime(2024, 1, 1, 13, 0)  # After lunch
        inspection_assignment.end_time = datetime(2024, 1, 1, 14, 0)

        def get_assignment(task_id):
            if task_id == setup_task.id:
                return setup_assignment
            elif task_id == machining_task.id:
                return machining_assignment
            elif task_id == inspection_task.id:
                return inspection_assignment
            return None

        schedule.get_assignment = get_assignment

        violations = await constraint_service.validate_precedence_for_job(
            job_id, schedule
        )
        assert violations == []  # Should be valid

    @pytest.mark.asyncio
    async def test_rush_order_validation(self, constraint_service, mock_repositories):
        """Test validation of rush order scenario."""
        # Rush orders might have constraints relaxed or different rules
        job_ids = [uuid4() for _ in range(5)]  # 5 rush jobs

        schedule = Mock(spec=Schedule)
        schedule.job_ids = set(job_ids)

        # All jobs need to go through bottleneck zone (positions 31-60, max 2 jobs)
        async def mock_job_overlaps_zone(job_id, zone, schedule):
            # All jobs overlap bottleneck zone
            return zone.start_position == 31 and zone.end_position == 60

        constraint_service._job_overlaps_zone = mock_job_overlaps_zone

        violations = await constraint_service._validate_wip_constraints(schedule)

        # Should detect WIP violation
        assert len(violations) == 1
        assert "WIP limit exceeded" in violations[0]
        assert "Bottleneck Zone" in violations[0]
        assert "5 > 2" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
