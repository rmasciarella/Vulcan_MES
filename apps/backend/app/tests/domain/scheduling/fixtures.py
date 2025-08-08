"""
Test fixtures and factories for scheduling domain entities.

Provides reusable test data for jobs, tasks, operators, machines, schedules,
and related domain objects. Includes both simple fixtures and configurable
factory functions for complex test scenarios.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine, MachineStatus
from app.domain.scheduling.entities.operation import Operation
from app.domain.scheduling.entities.operator import Operator, OperatorStatus
from app.domain.scheduling.entities.schedule import Schedule, ScheduleStatus
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.common import Duration, TimeWindow
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    Priority,
    TaskStatus,
)
from app.domain.scheduling.value_objects.machine_option import MachineOption
from app.domain.scheduling.value_objects.role_requirement import (
    AttendanceRequirement,
    RoleRequirement,
)
from app.domain.scheduling.value_objects.skill import Skill
from app.domain.scheduling.value_objects.skill_proficiency import (
    SkillProficiency,
    SkillRequirement,
)
from app.infrastructure.events.domain_event_publisher import DomainEventPublisher
from app.infrastructure.events.event_bus import InMemoryEventBus


# Basic UUID fixtures
@pytest.fixture
def job_id():
    """Generate a job ID for testing."""
    return uuid4()


@pytest.fixture
def task_id():
    """Generate a task ID for testing."""
    return uuid4()


@pytest.fixture
def operator_id():
    """Generate an operator ID for testing."""
    return uuid4()


@pytest.fixture
def machine_id():
    """Generate a machine ID for testing."""
    return uuid4()


@pytest.fixture
def operation_id():
    """Generate an operation ID for testing."""
    return uuid4()


@pytest.fixture
def schedule_id():
    """Generate a schedule ID for testing."""
    return uuid4()


# Time fixtures
@pytest.fixture
def base_time():
    """Base time for test scenarios."""
    return datetime(2024, 1, 15, 8, 0, 0)  # Monday 8:00 AM


@pytest.fixture
def time_window(base_time):
    """A standard 8-hour work time window."""
    return TimeWindow(
        start_time=base_time,
        end_time=base_time + timedelta(hours=8)
    )


# Skill fixtures
@pytest.fixture
def welding_skill():
    """Welding skill definition."""
    return Skill(name="welding", description="Metal welding operations")


@pytest.fixture
def machining_skill():
    """Machining skill definition."""
    return Skill(name="machining", description="CNC machining operations")


@pytest.fixture
def assembly_skill():
    """Assembly skill definition."""
    return Skill(name="assembly", description="Product assembly operations")


@pytest.fixture
def basic_skills(welding_skill, machining_skill, assembly_skill):
    """Collection of basic skills."""
    return [welding_skill, machining_skill, assembly_skill]


# Skill proficiency fixtures
@pytest.fixture
def expert_welding_proficiency(welding_skill):
    """Expert level welding proficiency."""
    return SkillProficiency(skill=welding_skill, level=5)


@pytest.fixture
def intermediate_machining_proficiency(machining_skill):
    """Intermediate level machining proficiency."""
    return SkillProficiency(skill=machining_skill, level=3)


@pytest.fixture
def basic_assembly_proficiency(assembly_skill):
    """Basic level assembly proficiency."""
    return SkillProficiency(skill=assembly_skill, level=2)


# Operation fixtures
@pytest.fixture
def welding_operation(operation_id, welding_skill):
    """Standard welding operation."""
    return Operation(
        id=operation_id,
        name="Steel Welding",
        description="Weld steel components together",
        standard_duration=Duration(minutes=120),
        setup_duration=Duration(minutes=15),
        required_skills=[SkillRequirement(skill=welding_skill.name, level=3)],
        department="fabrication"
    )


@pytest.fixture
def machining_operation(machining_skill):
    """Standard machining operation."""
    return Operation(
        id=uuid4(),
        name="CNC Milling",
        description="Mill component to specifications",
        standard_duration=Duration(minutes=90),
        setup_duration=Duration(minutes=20),
        required_skills=[SkillRequirement(skill=machining_skill.name, level=4)],
        department="machining"
    )


@pytest.fixture
def assembly_operation(assembly_skill):
    """Standard assembly operation."""
    return Operation(
        id=uuid4(),
        name="Final Assembly",
        description="Assemble components into final product",
        standard_duration=Duration(minutes=60),
        setup_duration=Duration(minutes=5),
        required_skills=[SkillRequirement(skill=assembly_skill.name, level=2)],
        department="assembly"
    )


# Machine fixtures
@pytest.fixture
def welding_machine(machine_id):
    """Standard welding machine."""
    return Machine(
        id=machine_id,
        name="Welder-01",
        machine_type="welding_station",
        department="fabrication",
        status=MachineStatus.AVAILABLE,
        capabilities=["mig_welding", "tig_welding"],
        hourly_cost=Decimal("45.00")
    )


@pytest.fixture
def cnc_machine():
    """CNC milling machine."""
    return Machine(
        id=uuid4(),
        name="CNC-Mill-01",
        machine_type="cnc_mill",
        department="machining",
        status=MachineStatus.AVAILABLE,
        capabilities=["3_axis_milling", "drilling", "tapping"],
        hourly_cost=Decimal("75.00")
    )


@pytest.fixture
def assembly_station():
    """Manual assembly station."""
    return Machine(
        id=uuid4(),
        name="Assembly-Station-01",
        machine_type="assembly_station",
        department="assembly",
        status=MachineStatus.AVAILABLE,
        capabilities=["manual_assembly", "torque_tools"],
        hourly_cost=Decimal("25.00")
    )


@pytest.fixture
def basic_machines(welding_machine, cnc_machine, assembly_station):
    """Collection of basic machines."""
    return [welding_machine, cnc_machine, assembly_station]


# Operator fixtures
@pytest.fixture
def expert_welder(operator_id, expert_welding_proficiency):
    """Expert welder operator."""
    return Operator(
        id=operator_id,
        name="John Smith",
        employee_id="EMP-001",
        status=OperatorStatus.AVAILABLE,
        department="fabrication",
        shift_start=datetime(2024, 1, 15, 7, 0, 0),
        shift_end=datetime(2024, 1, 15, 15, 30, 0),
        skill_proficiencies=[expert_welding_proficiency],
        hourly_rate=Decimal("28.50")
    )


@pytest.fixture
def machinist(intermediate_machining_proficiency):
    """Experienced machinist."""
    return Operator(
        id=uuid4(),
        name="Alice Johnson",
        employee_id="EMP-002",
        status=OperatorStatus.AVAILABLE,
        department="machining",
        shift_start=datetime(2024, 1, 15, 6, 0, 0),
        shift_end=datetime(2024, 1, 15, 14, 30, 0),
        skill_proficiencies=[intermediate_machining_proficiency],
        hourly_rate=Decimal("32.00")
    )


@pytest.fixture
def assembler(basic_assembly_proficiency):
    """Assembly line worker."""
    return Operator(
        id=uuid4(),
        name="Bob Wilson",
        employee_id="EMP-003",
        status=OperatorStatus.AVAILABLE,
        department="assembly",
        shift_start=datetime(2024, 1, 15, 8, 0, 0),
        shift_end=datetime(2024, 1, 15, 16, 30, 0),
        skill_proficiencies=[basic_assembly_proficiency],
        hourly_rate=Decimal("22.00")
    )


@pytest.fixture
def multi_skilled_operator(expert_welding_proficiency, intermediate_machining_proficiency):
    """Multi-skilled operator."""
    return Operator(
        id=uuid4(),
        name="Sarah Davis",
        employee_id="EMP-004",
        status=OperatorStatus.AVAILABLE,
        department="fabrication",
        shift_start=datetime(2024, 1, 15, 7, 0, 0),
        shift_end=datetime(2024, 1, 15, 15, 30, 0),
        skill_proficiencies=[expert_welding_proficiency, intermediate_machining_proficiency],
        hourly_rate=Decimal("35.00")
    )


@pytest.fixture
def basic_operators(expert_welder, machinist, assembler, multi_skilled_operator):
    """Collection of basic operators."""
    return [expert_welder, machinist, assembler, multi_skilled_operator]


# Task fixtures
@pytest.fixture
def welding_task(job_id, welding_operation, welding_machine):
    """Standard welding task."""
    machine_option = MachineOption(
        machine_id=welding_machine.id,
        setup_duration=Duration(minutes=15),
        processing_duration=Duration(minutes=120),
        requires_operator_full_duration=True
    )
    
    role_requirement = RoleRequirement(
        role="welder",
        count=1,
        attendance=AttendanceRequirement.FULL_DURATION
    )
    
    return Task(
        job_id=job_id,
        operation_id=welding_operation.id,
        sequence_in_job=1,
        machine_options=[machine_option],
        role_requirements=[role_requirement],
        planned_duration=Duration(minutes=135)  # Setup + processing
    )


@pytest.fixture
def machining_task(job_id, machining_operation, cnc_machine):
    """Standard machining task."""
    machine_option = MachineOption(
        machine_id=cnc_machine.id,
        setup_duration=Duration(minutes=20),
        processing_duration=Duration(minutes=90),
        requires_operator_full_duration=False  # Operator only for setup
    )
    
    role_requirement = RoleRequirement(
        role="machinist",
        count=1,
        attendance=AttendanceRequirement.SETUP_ONLY
    )
    
    return Task(
        job_id=job_id,
        operation_id=machining_operation.id,
        sequence_in_job=2,
        machine_options=[machine_option],
        role_requirements=[role_requirement],
        planned_duration=Duration(minutes=110),
        predecessor_ids=[uuid4()]  # Depends on previous task
    )


@pytest.fixture
def assembly_task(job_id, assembly_operation, assembly_station):
    """Standard assembly task."""
    machine_option = MachineOption(
        machine_id=assembly_station.id,
        setup_duration=Duration(minutes=5),
        processing_duration=Duration(minutes=60),
        requires_operator_full_duration=True
    )
    
    role_requirement = RoleRequirement(
        role="assembler",
        count=2,  # Requires 2 operators
        attendance=AttendanceRequirement.FULL_DURATION
    )
    
    return Task(
        job_id=job_id,
        operation_id=assembly_operation.id,
        sequence_in_job=3,
        machine_options=[machine_option],
        role_requirements=[role_requirement],
        planned_duration=Duration(minutes=65),
        predecessor_ids=[uuid4()]  # Depends on previous task
    )


@pytest.fixture
def basic_tasks(welding_task, machining_task, assembly_task):
    """Collection of basic tasks."""
    return [welding_task, machining_task, assembly_task]


# Job fixtures
@pytest.fixture
def standard_job(job_id, basic_tasks, base_time):
    """Standard 3-operation job."""
    job = Job(
        id=job_id,
        job_number="JOB-2024-001",
        customer_name="ABC Manufacturing",
        product_name="Steel Bracket",
        priority=Priority.NORMAL,
        due_date=base_time + timedelta(days=7),
        release_date=base_time,
        task_ids=[task.id for task in basic_tasks],
        status=JobStatus.ACTIVE
    )
    return job


@pytest.fixture
def urgent_job(base_time):
    """High priority urgent job."""
    return Job(
        id=uuid4(),
        job_number="JOB-2024-002",
        customer_name="XYZ Corp",
        product_name="Emergency Part",
        priority=Priority.HIGH,
        due_date=base_time + timedelta(days=2),  # Shorter deadline
        release_date=base_time,
        task_ids=[uuid4(), uuid4()],  # 2 tasks
        status=JobStatus.ACTIVE
    )


@pytest.fixture
def complex_job(base_time):
    """Complex job with many tasks."""
    task_ids = [uuid4() for _ in range(8)]  # 8 tasks
    return Job(
        id=uuid4(),
        job_number="JOB-2024-003",
        customer_name="Complex Industries",
        product_name="Multi-Component Assembly",
        priority=Priority.NORMAL,
        due_date=base_time + timedelta(days=14),
        release_date=base_time,
        task_ids=task_ids,
        status=JobStatus.ACTIVE
    )


@pytest.fixture
def basic_jobs(standard_job, urgent_job, complex_job):
    """Collection of basic jobs."""
    return [standard_job, urgent_job, complex_job]


# Schedule fixtures
@pytest.fixture
def empty_schedule(schedule_id):
    """Empty schedule for testing."""
    return Schedule(
        id=schedule_id,
        name="Test Schedule",
        planning_horizon=Duration(days=7),
        status=ScheduleStatus.DRAFT
    )


@pytest.fixture
def published_schedule():
    """Published schedule with some assignments."""
    schedule = Schedule(
        id=uuid4(),
        name="Published Schedule",
        planning_horizon=Duration(days=14),
        status=ScheduleStatus.PUBLISHED
    )
    
    # Add some mock assignments
    schedule.job_ids.extend([uuid4(), uuid4(), uuid4()])
    
    return schedule


# Event bus fixtures
@pytest.fixture
def event_bus():
    """Fresh event bus for each test."""
    bus = InMemoryEventBus()
    bus.clear_handlers()
    bus.clear_event_history()
    return bus


@pytest.fixture
def event_publisher(event_bus):
    """Domain event publisher with fresh event bus."""
    return DomainEventPublisher(event_bus)


# Factory functions
class OperatorFactory:
    """Factory for creating test operators with various configurations."""
    
    @staticmethod
    def create_operator(
        name: str = "Test Operator",
        employee_id: str = None,
        department: str = "production",
        skills: List[SkillProficiency] = None,
        shift_start: datetime = None,
        shift_end: datetime = None,
        status: OperatorStatus = OperatorStatus.AVAILABLE,
        hourly_rate: Decimal = Decimal("25.00")
    ) -> Operator:
        """Create an operator with specified parameters."""
        if employee_id is None:
            employee_id = f"EMP-{uuid4().hex[:6].upper()}"
        
        if skills is None:
            skills = []
        
        if shift_start is None:
            shift_start = datetime(2024, 1, 15, 8, 0, 0)
        
        if shift_end is None:
            shift_end = shift_start + timedelta(hours=8)
        
        return Operator(
            id=uuid4(),
            name=name,
            employee_id=employee_id,
            status=status,
            department=department,
            shift_start=shift_start,
            shift_end=shift_end,
            skill_proficiencies=skills,
            hourly_rate=hourly_rate
        )
    
    @staticmethod
    def create_skilled_operator(skill_name: str, skill_level: int) -> Operator:
        """Create an operator with a specific skill."""
        skill = Skill(name=skill_name, description=f"{skill_name.title()} operations")
        proficiency = SkillProficiency(skill=skill, level=skill_level)
        
        return OperatorFactory.create_operator(
            name=f"{skill_name.title()} Expert",
            department=skill_name.lower(),
            skills=[proficiency]
        )


class MachineFactory:
    """Factory for creating test machines with various configurations."""
    
    @staticmethod
    def create_machine(
        name: str = "Test Machine",
        machine_type: str = "generic",
        department: str = "production",
        capabilities: List[str] = None,
        status: MachineStatus = MachineStatus.AVAILABLE,
        hourly_cost: Decimal = Decimal("50.00")
    ) -> Machine:
        """Create a machine with specified parameters."""
        if capabilities is None:
            capabilities = ["basic_operation"]
        
        return Machine(
            id=uuid4(),
            name=name,
            machine_type=machine_type,
            department=department,
            status=status,
            capabilities=capabilities,
            hourly_cost=hourly_cost
        )
    
    @staticmethod
    def create_department_machines(department: str, count: int) -> List[Machine]:
        """Create multiple machines for a specific department."""
        machines = []
        for i in range(count):
            machine = MachineFactory.create_machine(
                name=f"{department.title()}-Machine-{i+1:02d}",
                machine_type=f"{department}_station",
                department=department
            )
            machines.append(machine)
        return machines


class TaskFactory:
    """Factory for creating test tasks with various configurations."""
    
    @staticmethod
    def create_task(
        job_id: UUID = None,
        operation_id: UUID = None,
        sequence: int = 1,
        duration_minutes: int = 60,
        setup_minutes: int = 10,
        machine_options: List[MachineOption] = None,
        role_requirements: List[RoleRequirement] = None,
        status: TaskStatus = TaskStatus.PENDING,
        predecessors: List[UUID] = None
    ) -> Task:
        """Create a task with specified parameters."""
        if job_id is None:
            job_id = uuid4()
        
        if operation_id is None:
            operation_id = uuid4()
        
        if machine_options is None:
            machine_options = [
                MachineOption(
                    machine_id=uuid4(),
                    setup_duration=Duration(minutes=setup_minutes),
                    processing_duration=Duration(minutes=duration_minutes),
                    requires_operator_full_duration=True
                )
            ]
        
        if role_requirements is None:
            role_requirements = [
                RoleRequirement(
                    role="operator",
                    count=1,
                    attendance=AttendanceRequirement.FULL_DURATION
                )
            ]
        
        if predecessors is None:
            predecessors = []
        
        return Task(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=sequence,
            machine_options=machine_options,
            role_requirements=role_requirements,
            planned_duration=Duration(minutes=duration_minutes + setup_minutes),
            status=status,
            predecessor_ids=predecessors
        )
    
    @staticmethod
    def create_task_sequence(
        job_id: UUID,
        count: int,
        base_duration: int = 60
    ) -> List[Task]:
        """Create a sequence of dependent tasks."""
        tasks = []
        for i in range(count):
            predecessors = [tasks[i-1].id] if i > 0 else []
            
            task = TaskFactory.create_task(
                job_id=job_id,
                sequence=i + 1,
                duration_minutes=base_duration + (i * 10),  # Increasing duration
                predecessors=predecessors
            )
            tasks.append(task)
        
        return tasks


class JobFactory:
    """Factory for creating test jobs with various configurations."""
    
    @staticmethod
    def create_job(
        job_number: str = None,
        customer_name: str = "Test Customer",
        product_name: str = "Test Product",
        priority: Priority = Priority.NORMAL,
        task_count: int = 3,
        due_date: datetime = None,
        release_date: datetime = None,
        status: JobStatus = JobStatus.ACTIVE
    ) -> Job:
        """Create a job with specified parameters."""
        if job_number is None:
            job_number = f"JOB-TEST-{uuid4().hex[:6].upper()}"
        
        if release_date is None:
            release_date = datetime.now()
        
        if due_date is None:
            due_date = release_date + timedelta(days=7)
        
        # Create task IDs
        task_ids = [uuid4() for _ in range(task_count)]
        
        return Job(
            id=uuid4(),
            job_number=job_number,
            customer_name=customer_name,
            product_name=product_name,
            priority=priority,
            due_date=due_date,
            release_date=release_date,
            task_ids=task_ids,
            status=status
        )
    
    @staticmethod
    def create_job_with_tasks(
        task_count: int = 3,
        base_duration: int = 60,
        **job_kwargs
    ) -> tuple[Job, List[Task]]:
        """Create a job with its associated tasks."""
        job = JobFactory.create_job(task_count=task_count, **job_kwargs)
        tasks = TaskFactory.create_task_sequence(
            job_id=job.id,
            count=task_count,
            base_duration=base_duration
        )
        
        # Update job with actual task IDs
        job.task_ids = [task.id for task in tasks]
        
        return job, tasks


class ScheduleFactory:
    """Factory for creating test schedules with various configurations."""
    
    @staticmethod
    def create_schedule(
        name: str = "Test Schedule",
        planning_days: int = 7,
        status: ScheduleStatus = ScheduleStatus.DRAFT,
        job_count: int = 0
    ) -> Schedule:
        """Create a schedule with specified parameters."""
        schedule = Schedule(
            id=uuid4(),
            name=name,
            planning_horizon=Duration(days=planning_days),
            status=status
        )
        
        # Add job IDs if requested
        for _ in range(job_count):
            schedule.job_ids.append(uuid4())
        
        return schedule


# Scenario fixtures for complex testing
@pytest.fixture
def production_scenario():
    """Complete production scenario with jobs, tasks, operators, and machines."""
    
    # Create skills
    welding_skill = Skill(name="welding", description="Metal welding")
    machining_skill = Skill(name="machining", description="CNC operations")
    
    # Create operators with skills
    operators = [
        OperatorFactory.create_skilled_operator("welding", 4),
        OperatorFactory.create_skilled_operator("machining", 3),
        OperatorFactory.create_operator(name="General Operator"),
    ]
    
    # Create machines
    machines = [
        MachineFactory.create_machine("Welder-01", "welding_station", "fabrication"),
        MachineFactory.create_machine("CNC-01", "cnc_mill", "machining"),
        MachineFactory.create_machine("Assembly-01", "assembly_station", "assembly"),
    ]
    
    # Create jobs with tasks
    jobs_with_tasks = []
    for i in range(3):
        job, tasks = JobFactory.create_job_with_tasks(
            task_count=2 + i,  # Varying task counts
            job_number=f"PROD-{i+1:03d}"
        )
        jobs_with_tasks.append((job, tasks))
    
    return {
        'operators': operators,
        'machines': machines,
        'jobs_with_tasks': jobs_with_tasks,
        'skills': [welding_skill, machining_skill]
    }


@pytest.fixture
def resource_constrained_scenario():
    """Scenario with limited resources to test constraint handling."""
    
    # Limited operators
    operators = [OperatorFactory.create_operator(f"Operator-{i}") for i in range(2)]
    
    # Limited machines
    machines = [MachineFactory.create_machine(f"Machine-{i}") for i in range(2)]
    
    # Many jobs competing for resources
    jobs_with_tasks = []
    for i in range(5):  # 5 jobs, but only 2 operators/machines
        job, tasks = JobFactory.create_job_with_tasks(
            task_count=3,
            priority=Priority.HIGH if i < 2 else Priority.NORMAL
        )
        jobs_with_tasks.append((job, tasks))
    
    return {
        'operators': operators,
        'machines': machines,
        'jobs_with_tasks': jobs_with_tasks
    }