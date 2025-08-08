"""
Comprehensive Unit Tests for ResourceAllocationService Domain Service

Tests all resource allocation methods including machine selection, operator assignment,
alternative allocation, availability validation, and utilization statistics with proper mocking.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine, MachineStatus
from app.domain.scheduling.entities.operator import Operator, OperatorStatus
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.services.resource_allocation_service import (
    ResourceAllocation,
    ResourceAllocationService,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import SkillLevel, TaskType
from app.domain.scheduling.value_objects.skill_requirement import SkillRequirement
from app.shared.exceptions import MachineUnavailableError, OperatorUnavailableError
from app.tests.database.factories import JobFactory, TaskFactory


@pytest.fixture
def mock_repositories():
    """Create mock repositories for testing."""
    return {
        "job_repository": AsyncMock(),
        "task_repository": AsyncMock(),
        "operator_repository": AsyncMock(),
        "machine_repository": AsyncMock(),
    }


@pytest.fixture
def resource_allocation_service(mock_repositories):
    """Create ResourceAllocationService with mock repositories."""
    return ResourceAllocationService(
        job_repository=mock_repositories["job_repository"],
        task_repository=mock_repositories["task_repository"],
        operator_repository=mock_repositories["operator_repository"],
        machine_repository=mock_repositories["machine_repository"],
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    task = TaskFactory.create(
        planned_duration_minutes=120,
        setup_duration_minutes=30,
    )
    
    # Add additional properties needed for resource allocation
    task.task_type = Mock()
    task.task_type.value = "MACHINING"
    task.is_attended = True
    task.department = "PRODUCTION"
    
    # Mock machine options
    machine_option = Mock()
    machine_option.total_duration.return_value = Duration.from_minutes(120)
    task.machine_options = [machine_option]
    
    # Mock skill requirements
    skill_req = Mock(spec=SkillRequirement)
    skill_req.skill_type = "MACHINING"
    skill_req.minimum_level = SkillLevel.PROFICIENT
    task.skill_requirements = [skill_req]
    task.role_requirements = None
    
    # Mock methods
    def required_operator_count():
        return 1
    
    def get_machine_option_for(machine_id):
        return machine_option
    
    def operator_required_duration_minutes(option, role):
        return 120
    
    task.required_operator_count = required_operator_count
    task.get_machine_option_for = get_machine_option_for
    task.operator_required_duration_minutes = operator_required_duration_minutes
    
    return task


@pytest.fixture
def sample_machines():
    """Create sample machines for testing."""
    machine1 = Mock(spec=Machine)
    machine1.id = uuid4()
    machine1.name = "CNC-001"
    machine1.is_available = True
    machine1.status = MachineStatus.AVAILABLE
    machine1.processing_speed_multiplier = 1.0
    machine1.requires_operator = True
    
    machine2 = Mock(spec=Machine)
    machine2.id = uuid4()
    machine2.name = "MILL-002"
    machine2.is_available = True
    machine2.status = MachineStatus.AVAILABLE
    machine2.processing_speed_multiplier = 1.5  # Faster machine
    machine2.requires_operator = True
    
    machine3 = Mock(spec=Machine)
    machine3.id = uuid4()
    machine3.name = "DRILL-003"
    machine3.is_available = False  # Unavailable machine
    machine3.status = MachineStatus.MAINTENANCE
    machine3.processing_speed_multiplier = 1.0
    machine3.requires_operator = True
    
    # Mock can_perform_task_type method
    def can_perform_machining(task_type):
        return task_type in ["MACHINING", "DRILLING"]
    
    def can_perform_limited(task_type):
        return task_type == "DRILLING"
    
    machine1.can_perform_task_type = can_perform_machining
    machine2.can_perform_task_type = can_perform_machining
    machine3.can_perform_task_type = can_perform_limited
    
    # Mock utilization method
    def get_utilization_window(start, end):
        return 0.6  # 60% utilization
    
    machine1.get_utilization_window = get_utilization_window
    machine2.get_utilization_window = get_utilization_window
    machine3.get_utilization_window = get_utilization_window
    
    return [machine1, machine2, machine3]


@pytest.fixture
def sample_operators():
    """Create sample operators for testing."""
    operator1 = Mock(spec=Operator)
    operator1.id = uuid4()
    operator1.name = "John Doe"
    operator1.status = OperatorStatus.AVAILABLE
    operator1.department = "PRODUCTION"
    operator1.current_task_assignments = []
    
    operator2 = Mock(spec=Operator)
    operator2.id = uuid4()
    operator2.name = "Jane Smith" 
    operator2.status = OperatorStatus.AVAILABLE
    operator2.department = "PRODUCTION"
    operator2.current_task_assignments = []
    
    operator3 = Mock(spec=Operator)
    operator3.id = uuid4()
    operator3.name = "Bob Wilson"
    operator3.status = OperatorStatus.BUSY  # Unavailable operator
    operator3.department = "PRODUCTION"
    operator3.current_task_assignments = [uuid4()]
    
    # Mock skill-related methods
    def has_machining_skill(skill_type, min_level):
        return skill_type == "MACHINING" and min_level <= SkillLevel.PROFICIENT
    
    def has_limited_skill(skill_type, min_level):
        return skill_type == "MACHINING" and min_level <= SkillLevel.BASIC
    
    def get_skill_level(skill_type):
        if skill_type == "MACHINING":
            return SkillLevel.PROFICIENT
        return None
    
    def get_highest_skill_level():
        return SkillLevel.PROFICIENT
    
    def calculate_cost_per_minute():
        return 1.5  # $1.50 per minute
    
    def is_available_on_date(check_date):
        return True
    
    def is_available_at_time(minutes):
        return 420 <= minutes <= 960  # 7 AM to 4 PM
    
    operator1.has_skill = has_machining_skill
    operator1.get_skill_level = get_skill_level
    operator1.get_highest_skill_level = get_highest_skill_level
    operator1.calculate_cost_per_minute = calculate_cost_per_minute
    operator1.is_available_on_date = is_available_on_date
    operator1.is_available_at_time = is_available_at_time
    
    operator2.has_skill = has_machining_skill
    operator2.get_skill_level = get_skill_level
    operator2.get_highest_skill_level = get_highest_skill_level
    operator2.calculate_cost_per_minute = calculate_cost_per_minute
    operator2.is_available_on_date = is_available_on_date
    operator2.is_available_at_time = is_available_at_time
    
    operator3.has_skill = has_limited_skill
    operator3.get_skill_level = get_skill_level
    operator3.get_highest_skill_level = lambda: SkillLevel.BASIC
    operator3.calculate_cost_per_minute = lambda: 1.2
    operator3.is_available_on_date = is_available_on_date
    operator3.is_available_at_time = is_available_at_time
    
    return [operator1, operator2, operator3]


class TestResourceAllocation:
    """Test the ResourceAllocation data class."""

    def test_resource_allocation_creation(self):
        """Test creating a ResourceAllocation instance."""
        task_id = uuid4()
        machine_id = uuid4()
        operator_ids = [uuid4(), uuid4()]
        
        allocation = ResourceAllocation(
            task_id=task_id,
            machine_id=machine_id,
            operator_ids=operator_ids,
            allocation_score=85.5,
            reasoning="High skill match and low cost"
        )
        
        assert allocation.task_id == task_id
        assert allocation.machine_id == machine_id
        assert allocation.operator_ids == operator_ids
        assert allocation.allocation_score == 85.5
        assert allocation.reasoning == "High skill match and low cost"

    def test_resource_allocation_default_values(self):
        """Test ResourceAllocation with default values."""
        task_id = uuid4()
        machine_id = uuid4()
        operator_ids = [uuid4()]
        
        allocation = ResourceAllocation(
            task_id=task_id,
            machine_id=machine_id,
            operator_ids=operator_ids
        )
        
        assert allocation.allocation_score == 0.0
        assert allocation.reasoning == ""

    def test_resource_allocation_operator_ids_copy(self):
        """Test that operator_ids are copied to prevent mutation."""
        original_ids = [uuid4(), uuid4()]
        
        allocation = ResourceAllocation(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=original_ids
        )
        
        # Modify original list
        original_ids.append(uuid4())
        
        # Allocation should be unaffected
        assert len(allocation.operator_ids) == 2


class TestResourceAllocationService:
    """Test the main ResourceAllocationService functionality."""

    def test_service_initialization(self, mock_repositories):
        """Test service initialization with repositories."""
        service = ResourceAllocationService(
            job_repository=mock_repositories["job_repository"],
            task_repository=mock_repositories["task_repository"],
            operator_repository=mock_repositories["operator_repository"],
            machine_repository=mock_repositories["machine_repository"],
        )
        
        assert service._job_repository == mock_repositories["job_repository"]
        assert service._task_repository == mock_repositories["task_repository"]
        assert service._operator_repository == mock_repositories["operator_repository"]
        assert service._machine_repository == mock_repositories["machine_repository"]

    def test_default_configuration(self, resource_allocation_service):
        """Test default allocation preferences."""
        assert resource_allocation_service._prefer_lowest_cost is True
        assert resource_allocation_service._prefer_highest_skill is False
        assert resource_allocation_service._load_balancing_enabled is True

    @pytest.mark.asyncio
    async def test_allocate_resources_for_task_success(
        self, resource_allocation_service, sample_task, sample_machines, sample_operators, mock_repositories
    ):
        """Test successful resource allocation for a task."""
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Mock repository responses
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:2]  # Available machines
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]  # Available operators
        
        allocation = await resource_allocation_service.allocate_resources_for_task(
            sample_task, start_time
        )
        
        assert isinstance(allocation, ResourceAllocation)
        assert allocation.task_id == sample_task.id
        assert allocation.machine_id in [m.id for m in sample_machines[:2]]
        assert len(allocation.operator_ids) >= 1
        assert allocation.allocation_score > 0
        assert len(allocation.reasoning) > 0

    @pytest.mark.asyncio
    async def test_allocate_resources_for_task_no_machine(
        self, resource_allocation_service, sample_task, mock_repositories
    ):
        """Test resource allocation when no suitable machine is available."""
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Mock no available machines
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = []
        
        with pytest.raises(MachineUnavailableError):
            await resource_allocation_service.allocate_resources_for_task(sample_task, start_time)

    @pytest.mark.asyncio
    async def test_allocate_resources_for_task_insufficient_operators(
        self, resource_allocation_service, sample_task, sample_machines, mock_repositories
    ):
        """Test resource allocation when insufficient operators are available."""
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Mock task requiring 2 operators but only 1 available
        sample_task.required_operator_count = Mock(return_value=2)
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:1]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = []  # No operators
        
        with pytest.raises(OperatorUnavailableError):
            await resource_allocation_service.allocate_resources_for_task(sample_task, start_time)

    @pytest.mark.asyncio
    async def test_allocate_resources_for_task_with_exclusions(
        self, resource_allocation_service, sample_task, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource allocation with excluded resources."""
        start_time = datetime(2024, 1, 10, 9, 0)
        excluded_machine_ids = {sample_machines[0].id}
        excluded_operator_ids = {sample_operators[0].id}
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        allocation = await resource_allocation_service.allocate_resources_for_task(
            sample_task, start_time, excluded_machine_ids, excluded_operator_ids
        )
        
        # Should not allocate excluded resources
        assert allocation.machine_id != sample_machines[0].id
        assert sample_operators[0].id not in allocation.operator_ids

    @pytest.mark.asyncio
    async def test_allocate_resources_for_job(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource allocation for an entire job."""
        job = JobFactory.create_with_tasks(task_count=3)
        tasks = list(job._tasks.values())
        
        # Set up task properties for all tasks
        for task in tasks:
            task.task_type = Mock()
            task.task_type.value = "MACHINING"
            task.is_attended = True
            task.department = "PRODUCTION"
            task.skill_requirements = []
            task.role_requirements = None
            task.required_operator_count = Mock(return_value=1)
            task.total_duration = Duration.from_minutes(120)
        
        start_time = datetime(2024, 1, 10, 8, 0)
        
        # Mock repository responses
        mock_repositories["task_repository"].get_by_job_id.return_value = tasks
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:2]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        allocations = await resource_allocation_service.allocate_resources_for_job(job, start_time)
        
        assert len(allocations) == 3
        assert all(isinstance(a, ResourceAllocation) for a in allocations)
        assert all(a.task_id in [t.id for t in tasks] for a in allocations)

    @pytest.mark.asyncio
    async def test_find_alternative_allocation(
        self, resource_allocation_service, sample_task, sample_machines, sample_operators, mock_repositories
    ):
        """Test finding alternative resource allocation."""
        original_allocation = ResourceAllocation(
            task_id=sample_task.id,
            machine_id=sample_machines[0].id,
            operator_ids=[sample_operators[0].id]
        )
        
        mock_repositories["task_repository"].get_by_id.return_value = sample_task
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:2]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        alternative = await resource_allocation_service.find_alternative_allocation(original_allocation)
        
        assert alternative is not None
        assert alternative.task_id == sample_task.id
        assert alternative.machine_id != original_allocation.machine_id  # Should be different
        assert set(alternative.operator_ids).isdisjoint(set(original_allocation.operator_ids))  # Should be different

    @pytest.mark.asyncio
    async def test_find_alternative_allocation_no_alternatives(
        self, resource_allocation_service, sample_task, sample_machines, mock_repositories
    ):
        """Test finding alternative allocation when none are available."""
        original_allocation = ResourceAllocation(
            task_id=sample_task.id,
            machine_id=sample_machines[0].id,
            operator_ids=[sample_operators[0].id]
        )
        
        mock_repositories["task_repository"].get_by_id.return_value = sample_task
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = []  # No alternatives
        
        alternative = await resource_allocation_service.find_alternative_allocation(original_allocation)
        
        assert alternative is None

    @pytest.mark.asyncio
    async def test_find_alternative_allocation_task_not_found(
        self, resource_allocation_service, mock_repositories
    ):
        """Test alternative allocation when task is not found."""
        original_allocation = ResourceAllocation(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()]
        )
        
        mock_repositories["task_repository"].get_by_id.return_value = None
        
        alternative = await resource_allocation_service.find_alternative_allocation(original_allocation)
        
        assert alternative is None

    @pytest.mark.asyncio
    async def test_validate_resource_availability_all_available(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource availability validation when all resources are available."""
        machine_id = sample_machines[0].id
        operator_ids = [sample_operators[0].id, sample_operators[1].id]
        start_time = datetime(2024, 1, 10, 9, 0)
        end_time = datetime(2024, 1, 10, 11, 0)
        
        mock_repositories["machine_repository"].get_by_id.return_value = sample_machines[0]
        mock_repositories["operator_repository"].get_by_id.side_effect = lambda op_id: next(
            (op for op in sample_operators if op.id == op_id), None
        )
        
        availability = await resource_allocation_service.validate_resource_availability(
            machine_id, operator_ids, start_time, end_time
        )
        
        assert availability[f"machine_{machine_id}"] is True
        assert all(availability[f"operator_{op_id}"] for op_id in operator_ids)

    @pytest.mark.asyncio
    async def test_validate_resource_availability_machine_unavailable(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource availability validation with unavailable machine."""
        unavailable_machine = sample_machines[2]  # This one is unavailable
        machine_id = unavailable_machine.id
        operator_ids = [sample_operators[0].id]
        start_time = datetime(2024, 1, 10, 9, 0)
        end_time = datetime(2024, 1, 10, 11, 0)
        
        mock_repositories["machine_repository"].get_by_id.return_value = unavailable_machine
        mock_repositories["operator_repository"].get_by_id.return_value = sample_operators[0]
        
        availability = await resource_allocation_service.validate_resource_availability(
            machine_id, operator_ids, start_time, end_time
        )
        
        assert availability[f"machine_{machine_id}"] is False
        assert availability[f"operator_{operator_ids[0]}"] is True

    @pytest.mark.asyncio
    async def test_validate_resource_availability_operator_busy(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource availability validation with busy operator."""
        machine_id = sample_machines[0].id
        busy_operator = sample_operators[2]  # This one is busy
        operator_ids = [busy_operator.id]
        start_time = datetime(2024, 1, 10, 9, 0)
        end_time = datetime(2024, 1, 10, 11, 0)
        
        mock_repositories["machine_repository"].get_by_id.return_value = sample_machines[0]
        mock_repositories["operator_repository"].get_by_id.return_value = busy_operator
        
        availability = await resource_allocation_service.validate_resource_availability(
            machine_id, operator_ids, start_time, end_time
        )
        
        assert availability[f"machine_{machine_id}"] is True
        assert availability[f"operator_{operator_ids[0]}"] is False

    @pytest.mark.asyncio
    async def test_get_resource_utilization_stats(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test getting resource utilization statistics."""
        start_time = datetime(2024, 1, 10, 8, 0)
        end_time = datetime(2024, 1, 10, 16, 0)
        
        mock_repositories["machine_repository"].get_all.return_value = sample_machines
        mock_repositories["operator_repository"].get_all.return_value = sample_operators
        
        stats = await resource_allocation_service.get_resource_utilization_stats(start_time, end_time)
        
        # Should have utilization stats for all machines
        for machine in sample_machines:
            assert f"machine_{machine.id}_utilization" in stats
        
        # Should have utilization stats for all operators
        for operator in sample_operators:
            assert f"operator_{operator.id}_utilization" in stats

    def test_score_machine_for_task_basic(self, resource_allocation_service, sample_task, sample_machines):
        """Test machine scoring for task assignment."""
        machine = sample_machines[0]  # Basic machine
        
        score = resource_allocation_service._score_machine_for_task(sample_task, machine)
        
        assert score > 0
        # Should get base score for capability
        assert score >= 10.0

    def test_score_machine_for_task_fast_machine(self, resource_allocation_service, sample_task, sample_machines):
        """Test machine scoring for fast machine."""
        fast_machine = sample_machines[1]  # This one has speed multiplier 1.5
        
        score = resource_allocation_service._score_machine_for_task(sample_task, fast_machine)
        
        # Should get bonus for speed
        assert score > 10.0  # More than base capability score

    def test_score_operator_for_task(self, resource_allocation_service, sample_task, sample_operators):
        """Test operator scoring for task assignment."""
        operator = sample_operators[0]
        
        score = resource_allocation_service._score_operator_for_task(sample_task, operator)
        
        assert score > 0
        # Should get points for skill matching

    def test_is_operator_available_at_time_valid(self, resource_allocation_service, sample_operators):
        """Test operator time availability check."""
        operator = sample_operators[0]
        start_time = datetime(2024, 1, 10, 9, 0)  # 9 AM - within business hours
        end_time = datetime(2024, 1, 10, 11, 0)   # 11 AM
        
        is_available = resource_allocation_service._is_operator_available_at_time(
            operator, start_time, end_time
        )
        
        assert is_available is True

    def test_is_operator_available_at_time_invalid(self, resource_allocation_service, sample_operators):
        """Test operator time availability check outside business hours."""
        operator = sample_operators[0]
        start_time = datetime(2024, 1, 10, 6, 0)  # 6 AM - before business hours
        end_time = datetime(2024, 1, 10, 8, 0)    # 8 AM
        
        is_available = resource_allocation_service._is_operator_available_at_time(
            operator, start_time, end_time
        )
        
        assert is_available is False

    @pytest.mark.asyncio
    async def test_calculate_allocation_score(
        self, resource_allocation_service, sample_task, sample_machines, sample_operators
    ):
        """Test allocation score calculation."""
        machine = sample_machines[0]
        operators = sample_operators[:2]
        
        score = await resource_allocation_service._calculate_allocation_score(
            sample_task, machine, operators
        )
        
        assert score > 0
        # Score should be combination of machine and operator scores

    @pytest.mark.asyncio
    async def test_generate_allocation_reasoning(
        self, resource_allocation_service, sample_task, sample_machines, sample_operators
    ):
        """Test allocation reasoning generation."""
        machine = sample_machines[0]
        operators = sample_operators[:1]
        
        reasoning = await resource_allocation_service._generate_allocation_reasoning(
            sample_task, machine, operators
        )
        
        assert len(reasoning) > 0
        assert machine.name in reasoning
        assert "MACHINING capability" in reasoning

    def test_set_allocation_preferences(self, resource_allocation_service):
        """Test setting allocation preferences."""
        resource_allocation_service.set_allocation_preferences(
            prefer_lowest_cost=False,
            prefer_highest_skill=True,
            load_balancing_enabled=False
        )
        
        assert resource_allocation_service._prefer_lowest_cost is False
        assert resource_allocation_service._prefer_highest_skill is True
        assert resource_allocation_service._load_balancing_enabled is False


class TestResourceAllocationServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_find_best_machine_no_capable_machines(
        self, resource_allocation_service, sample_task, mock_repositories
    ):
        """Test machine selection when no machines can perform the task."""
        sample_task.task_type.value = "WELDING"  # No machines can do welding
        
        # Mock repository to return machines that can't do welding
        machines = [Mock() for _ in range(3)]
        for machine in machines:
            machine.can_perform_task_type = Mock(return_value=False)
            machine.is_available = True
            machine.status = MachineStatus.AVAILABLE
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = machines
        
        result = await resource_allocation_service._find_best_machine_for_task(sample_task, set())
        assert result is None

    @pytest.mark.asyncio
    async def test_find_best_machine_all_unavailable(
        self, resource_allocation_service, sample_task, mock_repositories
    ):
        """Test machine selection when all machines are unavailable."""
        # Mock machines that are all unavailable
        machines = [Mock() for _ in range(3)]
        for machine in machines:
            machine.can_perform_task_type = Mock(return_value=True)
            machine.is_available = False
            machine.status = MachineStatus.MAINTENANCE
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = machines
        
        result = await resource_allocation_service._find_best_machine_for_task(sample_task, set())
        assert result is None

    @pytest.mark.asyncio
    async def test_find_best_operators_no_skill_match(
        self, resource_allocation_service, sample_task, sample_machines, mock_repositories
    ):
        """Test operator selection when no operators have required skills."""
        machine = sample_machines[0]
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Mock operators without required skills
        operators = [Mock() for _ in range(3)]
        for operator in operators:
            operator.id = uuid4()
            operator.status = OperatorStatus.AVAILABLE
            operator.department = "PRODUCTION"
        
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = operators
        
        result = await resource_allocation_service._find_best_operators_for_task(
            sample_task, start_time, machine, set()
        )
        
        # Should return all operators even if they don't have perfect skills
        assert len(result) == len(operators)

    @pytest.mark.asyncio
    async def test_allocate_resources_with_role_requirements(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource allocation with role requirements instead of skill requirements."""
        task = Mock(spec=Task)
        task.id = uuid4()
        task.task_type = Mock()
        task.task_type.value = "MACHINING"
        task.department = "PRODUCTION"
        task.required_operator_count = Mock(return_value=2)
        
        # Mock role requirements
        role_requirement = Mock()
        role_requirement.skill_type = "MACHINING"
        role_requirement.minimum_level = SkillLevel.BASIC
        role_requirement.count = 2
        
        task.role_requirements = [role_requirement]
        task.skill_requirements = []
        
        # Mock machine option
        machine_option = Mock()
        task.get_machine_option_for = Mock(return_value=machine_option)
        task.operator_required_duration_minutes = Mock(return_value=120)
        
        start_time = datetime(2024, 1, 10, 9, 0)
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:1]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        allocation = await resource_allocation_service.allocate_resources_for_task(task, start_time)
        
        assert allocation is not None
        assert len(allocation.operator_ids) <= 2  # Based on role requirements

    def test_score_machine_attendance_mismatch(self, resource_allocation_service, sample_task, sample_machines):
        """Test machine scoring when attendance requirements don't match."""
        machine = sample_machines[0]
        machine.requires_operator = False  # Machine doesn't require operator
        sample_task.is_attended = True     # But task is attended
        
        score = resource_allocation_service._score_machine_for_task(sample_task, machine)
        
        # Should still get base capability score but no attendance bonus
        assert score >= 10.0

    def test_score_operator_no_skill_requirements(self, resource_allocation_service, sample_operators):
        """Test operator scoring when task has no skill requirements."""
        task = Mock()
        task.skill_requirements = []
        
        operator = sample_operators[0]
        
        score = resource_allocation_service._score_operator_for_task(task, operator)
        
        # Should still get some score from other factors (cost, experience, etc.)
        assert score >= 0


class TestResourceAllocationServiceIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_high_priority_job_allocation(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test resource allocation for high-priority job."""
        # Create urgent job
        job = JobFactory.create_urgent()
        tasks = [TaskFactory.create(job_id=job.id) for _ in range(2)]
        
        # Set up tasks
        for task in tasks:
            task.task_type = Mock()
            task.task_type.value = "MACHINING"
            task.is_attended = True
            task.department = "PRODUCTION"
            task.skill_requirements = []
            task.role_requirements = None
            task.required_operator_count = Mock(return_value=1)
            task.total_duration = Duration.from_minutes(60)  # Shorter for urgent job
        
        start_time = datetime(2024, 1, 10, 8, 0)
        
        mock_repositories["task_repository"].get_by_job_id.return_value = tasks
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = sample_machines[:2]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        allocations = await resource_allocation_service.allocate_resources_for_job(job, start_time)
        
        assert len(allocations) == 2
        # All allocations should have high scores due to priority
        assert all(a.allocation_score > 0 for a in allocations)

    @pytest.mark.asyncio
    async def test_multi_skill_task_allocation(
        self, resource_allocation_service, sample_machines, sample_operators, mock_repositories
    ):
        """Test allocation for task requiring multiple skills."""
        task = Mock(spec=Task)
        task.id = uuid4()
        task.task_type = Mock()
        task.task_type.value = "ASSEMBLY"
        task.is_attended = True
        task.department = "PRODUCTION"
        task.required_operator_count = Mock(return_value=2)  # Needs 2 operators
        task.role_requirements = None
        
        # Multiple skill requirements
        skill1 = Mock(spec=SkillRequirement)
        skill1.skill_type = "MACHINING"
        skill1.minimum_level = SkillLevel.PROFICIENT
        
        skill2 = Mock(spec=SkillRequirement)
        skill2.skill_type = "ASSEMBLY"
        skill2.minimum_level = SkillLevel.BASIC
        
        task.skill_requirements = [skill1, skill2]
        
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Mock machines that can do assembly
        assembly_machines = [Mock() for _ in range(2)]
        for machine in assembly_machines:
            machine.id = uuid4()
            machine.is_available = True
            machine.status = MachineStatus.AVAILABLE
            machine.processing_speed_multiplier = 1.0
            machine.requires_operator = True
            machine.can_perform_task_type = lambda t: t == "ASSEMBLY"
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = assembly_machines
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = sample_operators[:2]
        
        allocation = await resource_allocation_service.allocate_resources_for_task(task, start_time)
        
        assert allocation is not None
        assert len(allocation.operator_ids) == 2  # Should allocate 2 operators

    @pytest.mark.asyncio
    async def test_resource_constraint_scenario(
        self, resource_allocation_service, sample_task, mock_repositories
    ):
        """Test allocation under resource constraints."""
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Only one machine available
        limited_machines = [Mock()]
        limited_machines[0].id = uuid4()
        limited_machines[0].is_available = True
        limited_machines[0].status = MachineStatus.AVAILABLE
        limited_machines[0].can_perform_task_type = Mock(return_value=True)
        limited_machines[0].processing_speed_multiplier = 1.0
        limited_machines[0].requires_operator = True
        
        # Only one operator available
        limited_operators = [Mock()]
        limited_operators[0].id = uuid4()
        limited_operators[0].status = OperatorStatus.AVAILABLE
        limited_operators[0].department = "PRODUCTION"
        limited_operators[0].has_skill = Mock(return_value=True)
        limited_operators[0].get_skill_level = Mock(return_value=SkillLevel.PROFICIENT)
        limited_operators[0].get_highest_skill_level = Mock(return_value=SkillLevel.PROFICIENT)
        limited_operators[0].calculate_cost_per_minute = Mock(return_value=1.5)
        limited_operators[0].is_available_on_date = Mock(return_value=True)
        limited_operators[0].is_available_at_time = Mock(return_value=True)
        limited_operators[0].current_task_assignments = []
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = limited_machines
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = limited_operators
        
        allocation = await resource_allocation_service.allocate_resources_for_task(sample_task, start_time)
        
        # Should successfully allocate with limited resources
        assert allocation is not None
        assert allocation.machine_id == limited_machines[0].id
        assert allocation.operator_ids == [limited_operators[0].id]

    @pytest.mark.asyncio
    async def test_cost_optimization_allocation(self, resource_allocation_service, mock_repositories):
        """Test allocation optimized for cost."""
        # Configure for cost optimization
        resource_allocation_service.set_allocation_preferences(
            prefer_lowest_cost=True,
            prefer_highest_skill=False,
            load_balancing_enabled=False
        )
        
        task = Mock(spec=Task)
        task.id = uuid4()
        task.task_type = Mock()
        task.task_type.value = "MACHINING"
        task.is_attended = True
        task.department = "PRODUCTION"
        task.skill_requirements = []
        task.role_requirements = None
        task.required_operator_count = Mock(return_value=1)
        
        start_time = datetime(2024, 1, 10, 9, 0)
        
        # Create operators with different costs
        expensive_operator = Mock()
        expensive_operator.id = uuid4()
        expensive_operator.status = OperatorStatus.AVAILABLE
        expensive_operator.department = "PRODUCTION"
        expensive_operator.calculate_cost_per_minute = Mock(return_value=3.0)  # Expensive
        expensive_operator.has_skill = Mock(return_value=True)
        expensive_operator.get_skill_level = Mock(return_value=SkillLevel.EXPERT)
        expensive_operator.get_highest_skill_level = Mock(return_value=SkillLevel.EXPERT)
        expensive_operator.is_available_on_date = Mock(return_value=True)
        expensive_operator.is_available_at_time = Mock(return_value=True)
        expensive_operator.current_task_assignments = []
        
        cheap_operator = Mock()
        cheap_operator.id = uuid4()
        cheap_operator.status = OperatorStatus.AVAILABLE
        cheap_operator.department = "PRODUCTION"
        cheap_operator.calculate_cost_per_minute = Mock(return_value=1.0)  # Cheap
        cheap_operator.has_skill = Mock(return_value=True)
        cheap_operator.get_skill_level = Mock(return_value=SkillLevel.BASIC)
        cheap_operator.get_highest_skill_level = Mock(return_value=SkillLevel.BASIC)
        cheap_operator.is_available_on_date = Mock(return_value=True)
        cheap_operator.is_available_at_time = Mock(return_value=True)
        cheap_operator.current_task_assignments = []
        
        machine = Mock()
        machine.id = uuid4()
        machine.is_available = True
        machine.status = MachineStatus.AVAILABLE
        machine.can_perform_task_type = Mock(return_value=True)
        machine.processing_speed_multiplier = 1.0
        machine.requires_operator = True
        
        mock_repositories["machine_repository"].get_machines_for_task_type.return_value = [machine]
        mock_repositories["operator_repository"].get_operators_with_skill.return_value = [expensive_operator, cheap_operator]
        
        allocation = await resource_allocation_service.allocate_resources_for_task(task, start_time)
        
        # Should prefer the cheaper operator
        assert allocation.operator_ids[0] == cheap_operator.id