"""
Comprehensive Test Fixtures and Utilities

Centralized fixtures for all test types including unit tests, integration tests,
performance tests, and security tests. Provides consistent test data and
mock objects across the entire test suite.
"""

import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db_test import test_engine
from app.core.security import create_access_token
from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.entities.schedule import Schedule, ScheduleAssignment
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.common import (
    Duration,
    EfficiencyFactor,
    OperatorSkill,
    Skill,
    TimeWindow,
)
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
    SkillLevel,
    TaskStatus,
)
from app.domain.scheduling.value_objects.machine_option import MachineOption
from app.domain.scheduling.value_objects.skill_requirement import SkillRequirement
from app.infrastructure.database.repositories.job_repository import JobRepository
from app.infrastructure.database.repositories.task_repository import TaskRepository
from app.main import app

# ============================================================================
# Basic Fixtures
# ============================================================================


@pytest.fixture
def test_client():
    """Create a test client for API testing."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Authentication and Authorization Fixtures
# ============================================================================


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = False
    user.full_name = "Test User"
    user.role = "operator"
    return user


@pytest.fixture
def mock_superuser():
    """Create a mock superuser for testing."""
    user = Mock()
    user.id = uuid4()
    user.email = "admin@example.com"
    user.is_active = True
    user.is_superuser = True
    user.full_name = "Admin User"
    user.role = "admin"
    return user


@pytest.fixture
def auth_token(mock_user):
    """Create an authentication token for testing."""
    return create_access_token(subject=str(mock_user.id))


@pytest.fixture
def auth_headers(auth_token):
    """Create authentication headers for API testing."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def superuser_token(mock_superuser):
    """Create a superuser authentication token."""
    return create_access_token(subject=str(mock_superuser.id))


@pytest.fixture
def superuser_headers(superuser_token):
    """Create superuser authentication headers."""
    return {"Authorization": f"Bearer {superuser_token}"}


# ============================================================================
# Domain Entity Fixtures
# ============================================================================


@pytest.fixture
def sample_duration():
    """Create a sample duration for testing."""
    return Duration(minutes=120)


@pytest.fixture
def sample_time_window():
    """Create a sample time window for testing."""
    start = datetime(2024, 1, 1, 9, 0)
    end = datetime(2024, 1, 1, 17, 0)
    return TimeWindow(start_time=start, end_time=end)


@pytest.fixture
def sample_skill():
    """Create a sample skill for testing."""
    return Skill(
        skill_code="WELD_001",
        skill_name="Basic Welding",
        skill_category="Welding",
        description="Basic welding operations",
    )


@pytest.fixture
def sample_operator_skill(sample_skill):
    """Create a sample operator skill for testing."""
    return OperatorSkill(
        skill=sample_skill,
        proficiency_level=SkillLevel.PROFICIENT,
        certified_date=datetime.utcnow() - timedelta(days=30),
        expiry_date=datetime.utcnow() + timedelta(days=365),
    )


@pytest.fixture
def sample_skill_requirement():
    """Create a sample skill requirement for testing."""
    return SkillRequirement(
        skill_code="MACH_001",
        skill_name="Machine Operation",
        minimum_level=SkillLevel.BASIC,
        is_required=True,
    )


@pytest.fixture
def sample_machine_option():
    """Create a sample machine option for testing."""
    return MachineOption(
        machine_id=uuid4(),
        machine_name="CNC Mill 001",
        efficiency_factor=1.2,
        setup_time_minutes=15,
        is_preferred=True,
    )


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return Job.create(
        job_number="TEST-JOB-001",
        due_date=datetime.utcnow() + timedelta(days=7),
        customer_name="Test Customer Corp",
        part_number="PART-TEST-001",
        quantity=10,
        priority=PriorityLevel.NORMAL,
        created_by="test_user",
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    job_id = uuid4()
    operation_id = uuid4()
    return Task.create(
        job_id=job_id,
        operation_id=operation_id,
        sequence_in_job=10,
        planned_duration_minutes=120,
        setup_duration_minutes=15,
    )


@pytest.fixture
def sample_machine():
    """Create a sample machine for testing."""
    machine = Mock(spec=Machine)
    machine.id = uuid4()
    machine.machine_code = "MILL-001"
    machine.machine_name = "CNC Mill 001"
    machine.machine_type = "CNC_MILL"
    machine.is_available = True
    machine.efficiency_factor = EfficiencyFactor(factor=1.0)

    def can_perform_task_type(task_type):
        compatible_types = ["MACHINING", "DRILLING", "MILLING"]
        return task_type in compatible_types

    machine.can_perform_task_type = can_perform_task_type
    return machine


@pytest.fixture
def sample_operator():
    """Create a sample operator for testing."""
    operator = Mock(spec=Operator)
    operator.id = uuid4()
    operator.employee_id = "EMP001"
    operator.full_name = "John Smith"
    operator.is_available = True
    operator.shift = "DAY"

    # Mock skills
    operator.skills = {
        "MACHINING": SkillLevel.PROFICIENT,
        "WELDING": SkillLevel.BASIC,
        "INSPECTION": SkillLevel.EXPERT,
    }

    def has_skill(skill_type, min_level):
        operator_level = operator.skills.get(skill_type, SkillLevel.NONE)
        return operator_level.value >= min_level.value

    operator.has_skill = has_skill
    return operator


@pytest.fixture
def sample_schedule():
    """Create a sample schedule for testing."""
    schedule = Mock(spec=Schedule)
    schedule.id = uuid4()
    schedule.name = "Test Schedule"
    schedule.created_at = datetime.utcnow()
    schedule.job_ids = {uuid4(), uuid4(), uuid4()}
    schedule.assignments = {}

    def get_assignment(task_id):
        return schedule.assignments.get(task_id)

    schedule.get_assignment = get_assignment
    return schedule


@pytest.fixture
def sample_schedule_assignment():
    """Create a sample schedule assignment for testing."""
    assignment = Mock(spec=ScheduleAssignment)
    assignment.id = uuid4()
    assignment.task_id = uuid4()
    assignment.machine_id = uuid4()
    assignment.operator_ids = [uuid4()]
    assignment.start_time = datetime(2024, 1, 1, 9, 0)
    assignment.end_time = datetime(2024, 1, 1, 11, 0)
    assignment.planned_duration = Duration(minutes=120)
    return assignment


# ============================================================================
# Repository Fixtures
# ============================================================================


@pytest.fixture
def job_repository(db_session):
    """Create a job repository for testing."""
    return JobRepository(session=db_session)


@pytest.fixture
def mock_job_repository():
    """Create a mock job repository for testing."""
    repo = Mock(spec=JobRepository)
    repo.create = Mock()
    repo.get = Mock()
    repo.update = Mock()
    repo.delete = Mock()
    repo.list = Mock()
    repo.find_by_job_number = Mock()
    repo.find_by_status = Mock()
    repo.find_by_customer = Mock()
    repo.find_overdue_jobs = Mock()
    repo.find_active_jobs = Mock()
    repo.get_completion_percentage = Mock()
    return repo


@pytest.fixture
def mock_task_repository():
    """Create a mock task repository for testing."""
    repo = Mock(spec=TaskRepository)
    repo.create = Mock()
    repo.get = Mock()
    repo.update = Mock()
    repo.delete = Mock()
    repo.list = Mock()
    repo.find_by_job_id = Mock()
    repo.find_ready_tasks = Mock()
    repo.find_scheduled_tasks = Mock()
    repo.find_active_tasks = Mock()
    repo.find_critical_path_tasks = Mock()
    repo.find_delayed_tasks = Mock()
    return repo


@pytest.fixture
def mock_repository_container(mock_job_repository, mock_task_repository):
    """Create a mock repository container."""
    container = Mock()
    container.jobs = mock_job_repository
    container.tasks = mock_task_repository
    container.machines = Mock()
    container.operators = Mock()
    container.resources = Mock()
    return container


# ============================================================================
# Data Generation Fixtures
# ============================================================================


@pytest.fixture
def job_factory():
    """Job factory for creating test jobs."""

    class JobFactory:
        @staticmethod
        def create(
            job_number: str | None = None,
            customer_name: str | None = None,
            part_number: str | None = None,
            quantity: int = 1,
            priority: PriorityLevel = PriorityLevel.NORMAL,
            status: JobStatus = JobStatus.PLANNED,
            due_date: datetime | None = None,
            notes: str | None = None,
            created_by: str | None = None,
            **kwargs,
        ) -> Job:
            """Create a Job instance with optional parameters."""
            if job_number is None:
                job_number = f"J{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            if customer_name is None:
                customers = [
                    "Acme Corp",
                    "Global Industries",
                    "Tech Solutions",
                    "Manufacturing Co",
                ]
                customer_name = random.choice(customers)

            if part_number is None:
                part_number = (
                    f"PART-{random.randint(100, 999)}{random.choice(['A', 'B', 'C'])}"
                )

            if due_date is None:
                due_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))

            if created_by is None:
                created_by = f"user_{random.randint(1, 100)}"

            return Job.create(
                job_number=job_number,
                due_date=due_date,
                customer_name=customer_name,
                part_number=part_number,
                quantity=quantity,
                priority=priority,
                created_by=created_by,
                **kwargs,
            )

        @staticmethod
        def create_batch(count: int, **kwargs) -> list[Job]:
            """Create a batch of jobs."""
            return [JobFactory.create(**kwargs) for _ in range(count)]

        @staticmethod
        def create_overdue(days_overdue: int = 1) -> Job:
            """Create an overdue job."""
            return JobFactory.create(
                due_date=datetime.utcnow() - timedelta(days=days_overdue),
                status=JobStatus.IN_PROGRESS,
            )

        @staticmethod
        def create_with_tasks(task_count: int = 3, **job_kwargs) -> Job:
            """Create a job with associated tasks."""
            job = JobFactory.create(**job_kwargs)

            for i in range(task_count):
                task = Task.create(
                    job_id=job.id,
                    operation_id=uuid4(),
                    sequence_in_job=(i + 1) * 10,
                    planned_duration_minutes=60 + (i * 30),
                )
                job.add_task(task)

            return job

    return JobFactory


@pytest.fixture
def task_factory():
    """Task factory for creating test tasks."""

    class TaskFactory:
        @staticmethod
        def create(
            job_id: UUID | None = None,
            operation_id: UUID | None = None,
            sequence_in_job: int = 10,
            status: TaskStatus = TaskStatus.PENDING,
            planned_duration_minutes: int | None = None,
            setup_duration_minutes: int = 0,
            **kwargs,
        ) -> Task:
            """Create a Task instance with optional parameters."""
            if job_id is None:
                job_id = uuid4()

            if operation_id is None:
                operation_id = uuid4()

            if planned_duration_minutes is None:
                planned_duration_minutes = random.randint(30, 180)

            task = Task.create(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=sequence_in_job,
                planned_duration_minutes=planned_duration_minutes,
                setup_duration_minutes=setup_duration_minutes,
            )

            task.status = status
            return task

        @staticmethod
        def create_critical_path(job_id: UUID | None = None) -> Task:
            """Create a critical path task."""
            task = TaskFactory.create(job_id=job_id)
            task.is_critical_path = True
            return task

        @staticmethod
        def create_with_requirements(
            skill_requirements: list[str] | None = None,
            machine_requirements: list[str] | None = None,
            **kwargs,
        ) -> Task:
            """Create a task with specific requirements."""
            task = TaskFactory.create(**kwargs)

            if skill_requirements:
                for skill in skill_requirements:
                    req = SkillRequirement(
                        skill_code=skill,
                        skill_name=f"{skill} Skill",
                        minimum_level=SkillLevel.BASIC,
                    )
                    task.skill_requirements.append(req)

            if machine_requirements:
                for machine_type in machine_requirements:
                    option = MachineOption(
                        machine_id=uuid4(),
                        machine_name=f"{machine_type} Machine",
                        efficiency_factor=1.0,
                    )
                    task.machine_options.append(option)

            return task

    return TaskFactory


@pytest.fixture
def random_generator():
    """Random data generator for tests."""

    class RandomGenerator:
        @staticmethod
        def string(length: int = 10) -> str:
            """Generate a random string."""
            return "".join(
                random.choices(string.ascii_letters + string.digits, k=length)
            )

        @staticmethod
        def email() -> str:
            """Generate a random email."""
            username = RandomGenerator.string(8).lower()
            domain = random.choice(["example.com", "test.org", "sample.net"])
            return f"{username}@{domain}"

        @staticmethod
        def phone() -> str:
            """Generate a random phone number."""
            return f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"

        @staticmethod
        def datetime_range(
            start: datetime | None = None, end: datetime | None = None
        ) -> datetime:
            """Generate a random datetime within range."""
            if start is None:
                start = datetime.utcnow()
            if end is None:
                end = start + timedelta(days=30)

            time_diff = end - start
            random_seconds = random.randint(0, int(time_diff.total_seconds()))
            return start + timedelta(seconds=random_seconds)

        @staticmethod
        def choice_from_enum(enum_class):
            """Choose a random value from an enum."""
            return random.choice(list(enum_class))

    return RandomGenerator


# ============================================================================
# Performance Testing Fixtures
# ============================================================================


@pytest.fixture
def performance_data():
    """Generate performance test data."""

    class PerformanceData:
        @staticmethod
        def large_job_dataset(size: int = 1000) -> list[dict[str, Any]]:
            """Generate a large dataset of job data."""
            jobs = []
            for i in range(size):
                jobs.append(
                    {
                        "job_number": f"PERF-JOB-{i:06d}",
                        "customer_name": f"Customer {i % 100}",
                        "part_number": f"PART-{i % 50:03d}",
                        "quantity": random.randint(1, 100),
                        "priority": random.choice(list(PriorityLevel)),
                        "due_date": datetime.utcnow()
                        + timedelta(days=random.randint(1, 60)),
                        "created_by": f"user_{i % 10}",
                    }
                )
            return jobs

        @staticmethod
        def complex_scheduling_scenario(
            job_count: int = 10,
            tasks_per_job: int = 5,
            operators: int = 8,
            machines: int = 6,
        ) -> dict[str, Any]:
            """Generate a complex scheduling scenario."""
            return {
                "jobs": PerformanceData.large_job_dataset(job_count),
                "tasks_per_job": tasks_per_job,
                "available_operators": operators,
                "available_machines": machines,
                "time_horizon_days": 30,
            }

    return PerformanceData


# ============================================================================
# Security Testing Fixtures
# ============================================================================


@pytest.fixture
def security_payloads():
    """Common security test payloads."""

    class SecurityPayloads:
        SQL_INJECTION = [
            "'; DROP TABLE jobs; --",
            "' OR '1'='1",
            "'; INSERT INTO jobs (job_number) VALUES ('hacked'); --",
            "' UNION SELECT * FROM users --",
            "'; UPDATE users SET is_superuser=true; --",
        ]

        XSS_PAYLOADS = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src='data:text/html,<script>alert(1)</script>'></iframe>",
        ]

        COMMAND_INJECTION = [
            "; ls -la",
            "| cat /etc/passwd",
            "& whoami",
            "`id`",
            "$(cat /etc/hosts)",
            "; rm -rf /",
        ]

        PATH_TRAVERSAL = [
            "../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
        ]

        BUFFER_OVERFLOW = ["A" * 1000, "A" * 10000, "A" * 100000]

        INVALID_FORMATS = {
            "emails": [
                "not-an-email",
                "@example.com",
                "user@",
                "user@.com",
                "user space@example.com",
            ],
            "dates": [
                "not-a-date",
                "2024-13-01",
                "2024-02-30",
                "32/01/2024",
                "2024-01-01 25:00:00",
            ],
            "uuids": [
                "not-a-uuid",
                "12345",
                "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "00000000-0000-0000-0000-000000000000",
            ],
        }

    return SecurityPayloads


# ============================================================================
# Mock Service Fixtures
# ============================================================================


@pytest.fixture
def mock_solver():
    """Mock OR-Tools solver for testing."""
    from app.core.solver import HFFSScheduler

    solver = Mock(spec=HFFSScheduler)
    solver.num_jobs = 5
    solver.num_tasks = 100
    solver.num_operators = 10
    solver.horizon_days = 30

    def mock_solve():
        return {
            "status": "OPTIMAL",
            "objective_value": 1000,
            "makespan": 2880,
            "solve_time": 2.5,
            "assignments": [
                {
                    "job": 0,
                    "task": 10,
                    "operator": 1,
                    "start_time": 420,
                    "end_time": 480,
                }
            ],
        }

    solver.solve = mock_solve
    return solver


@pytest.fixture
def mock_constraint_validator():
    """Mock constraint validation service."""
    from app.domain.scheduling.services.constraint_validation_service import (
        ConstraintValidationService,
    )

    validator = Mock(spec=ConstraintValidationService)
    validator.validate_schedule = AsyncMock(return_value=[])
    validator.validate_task_assignment = AsyncMock(return_value=[])
    validator.validate_precedence_for_job = AsyncMock(return_value=[])
    validator.validate_wip_limits = AsyncMock(return_value=[])
    return validator


# ============================================================================
# Test Data Cleanup Fixtures
# ============================================================================


@pytest.fixture
def cleanup_test_data():
    """Fixture to clean up test data after tests."""
    created_resources = []

    def register_for_cleanup(resource):
        created_resources.append(resource)

    yield register_for_cleanup

    # Cleanup after test
    for resource in created_resources:
        try:
            if hasattr(resource, "delete"):
                resource.delete()
            elif hasattr(resource, "cleanup"):
                resource.cleanup()
        except Exception:
            pass  # Ignore cleanup errors in tests


# ============================================================================
# Parametrized Test Fixtures
# ============================================================================


@pytest.fixture(params=[JobStatus.PLANNED, JobStatus.RELEASED, JobStatus.IN_PROGRESS])
def job_status(request):
    """Parametrized job status for testing multiple states."""
    return request.param


@pytest.fixture(
    params=[
        TaskStatus.PENDING,
        TaskStatus.READY,
        TaskStatus.SCHEDULED,
        TaskStatus.IN_PROGRESS,
    ]
)
def task_status(request):
    """Parametrized task status for testing multiple states."""
    return request.param


@pytest.fixture(
    params=[
        PriorityLevel.LOW,
        PriorityLevel.NORMAL,
        PriorityLevel.HIGH,
        PriorityLevel.URGENT,
    ]
)
def priority_level(request):
    """Parametrized priority level for testing."""
    return request.param


@pytest.fixture(params=[1, 5, 10, 50, 100])
def batch_size(request):
    """Parametrized batch sizes for performance testing."""
    return request.param
