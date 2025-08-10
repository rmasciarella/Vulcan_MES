"""
Repository validation tests.

Tests cover:
- Repository validation mixins
- Constraint validation
- Foreign key validation
- Uniqueness constraints
- Data integrity checks
"""

from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.repositories.validation_mixins import (
    ConstraintValidationMixin,
    JobRepositoryValidationMixin,
    MachineRepositoryValidationMixin,
    OperatorRepositoryValidationMixin,
    TaskRepositoryValidationMixin,
    validate_foreign_key_reference,
    validate_unique_constraint,
)
from app.domain.scheduling.value_objects.common import (
    ContactInfo,
    Quantity,
)
from app.domain.scheduling.value_objects.enums import (
    MachineAutomationLevel,
)
from app.domain.shared.exceptions import (
    ValidationError,
)


class MockJobRepository(JobRepositoryValidationMixin):
    """Mock job repository with validation."""

    def __init__(self):
        self.existing_job_numbers = set()
        self.existing_jobs = {}

    def _check_job_number_exists(
        self, job_number: str, exclude_id: UUID = None
    ) -> bool:
        """Mock check for existing job number."""
        return job_number in self.existing_job_numbers

    def add_existing_job_number(self, job_number: str):
        """Add job number to existing set."""
        self.existing_job_numbers.add(job_number)


class MockTaskRepository(TaskRepositoryValidationMixin):
    """Mock task repository with validation."""

    def __init__(self):
        self.existing_sequences = {}  # job_id -> set of sequences
        self.existing_jobs = set()
        self.existing_operations = set()
        self.existing_machines = set()

    def _check_task_sequence_exists(
        self, job_id: UUID, sequence: int, exclude_id: UUID = None
    ) -> bool:
        """Mock check for existing task sequence."""
        if job_id not in self.existing_sequences:
            return False
        return sequence in self.existing_sequences[job_id]

    def _check_job_exists(self, job_id: UUID) -> bool:
        """Mock check for job existence."""
        return job_id in self.existing_jobs

    def _check_operation_exists(self, operation_id: UUID) -> bool:
        """Mock check for operation existence."""
        return operation_id in self.existing_operations

    def _check_machine_exists(self, machine_id: UUID) -> bool:
        """Mock check for machine existence."""
        return machine_id in self.existing_machines

    def add_existing_sequence(self, job_id: UUID, sequence: int):
        """Add sequence to existing set."""
        if job_id not in self.existing_sequences:
            self.existing_sequences[job_id] = set()
        self.existing_sequences[job_id].add(sequence)

    def add_existing_job(self, job_id: UUID):
        """Add job to existing set."""
        self.existing_jobs.add(job_id)

    def add_existing_operation(self, operation_id: UUID):
        """Add operation to existing set."""
        self.existing_operations.add(operation_id)

    def add_existing_machine(self, machine_id: UUID):
        """Add machine to existing set."""
        self.existing_machines.add(machine_id)


class MockMachineRepository(MachineRepositoryValidationMixin):
    """Mock machine repository with validation."""

    def __init__(self):
        self.existing_machine_codes = set()
        self.existing_zones = set()

    def _check_machine_code_exists(
        self, machine_code: str, exclude_id: UUID = None
    ) -> bool:
        """Mock check for existing machine code."""
        return machine_code in self.existing_machine_codes

    def _check_production_zone_exists(self, zone_id: UUID) -> bool:
        """Mock check for production zone existence."""
        return zone_id in self.existing_zones

    def add_existing_machine_code(self, machine_code: str):
        """Add machine code to existing set."""
        self.existing_machine_codes.add(machine_code)

    def add_existing_zone(self, zone_id: UUID):
        """Add zone to existing set."""
        self.existing_zones.add(zone_id)


class MockOperatorRepository(OperatorRepositoryValidationMixin):
    """Mock operator repository with validation."""

    def __init__(self):
        self.existing_employee_ids = set()

    def _check_employee_id_exists(
        self, employee_id: str, exclude_id: UUID = None
    ) -> bool:
        """Mock check for existing employee ID."""
        return employee_id in self.existing_employee_ids

    def add_existing_employee_id(self, employee_id: str):
        """Add employee ID to existing set."""
        self.existing_employee_ids.add(employee_id)


class TestJobRepositoryValidation:
    """Test job repository validation."""

    def test_validate_valid_job(self):
        """Test validating a valid job."""
        repo = MockJobRepository()
        future_date = datetime.utcnow() + timedelta(days=7)

        job = Job.create(
            job_number="TEST-JOB-001",
            due_date=future_date,
            customer_name="Test Customer",
        )

        context = repo.validate_before_save(job)

        assert not context.has_errors
        assert not context.has_warnings

    def test_validate_duplicate_job_number(self):
        """Test validation fails for duplicate job number."""
        repo = MockJobRepository()
        repo.add_existing_job_number("EXISTING-JOB-001")

        future_date = datetime.utcnow() + timedelta(days=7)
        job = Job.create(job_number="EXISTING-JOB-001", due_date=future_date)

        context = repo.validate_before_save(job)

        assert context.has_errors
        assert len(context.errors) == 1
        assert "DUPLICATE_JOB_NUMBER" in context.errors[0].error_code

    def test_validate_past_due_date(self):
        """Test validation fails for past due date."""
        repo = MockJobRepository()
        past_date = datetime.utcnow() - timedelta(days=1)

        # Create job with past due date by bypassing normal validation
        job = Job(
            job_number="TEST-JOB-001", due_date=past_date, quantity=Quantity(value=1)
        )

        context = repo.validate_before_save(job)

        assert context.has_errors
        assert any("INVALID_DUE_DATE" in error.error_code for error in context.errors)

    def test_validate_invalid_planned_dates(self):
        """Test validation fails for invalid planned date range."""
        repo = MockJobRepository()
        base_date = datetime.utcnow() + timedelta(days=1)

        job = Job.create(
            job_number="TEST-JOB-001", due_date=base_date + timedelta(days=7)
        )
        # Set invalid planned dates
        job.planned_start_date = base_date + timedelta(hours=2)
        job.planned_end_date = base_date + timedelta(hours=1)  # Earlier than start

        context = repo.validate_before_save(job)

        assert context.has_errors
        assert any("INVALID_DATE_RANGE" in error.error_code for error in context.errors)


class TestTaskRepositoryValidation:
    """Test task repository validation."""

    def test_validate_valid_task(self):
        """Test validating a valid task."""
        repo = MockTaskRepository()
        job_id = uuid4()
        operation_id = uuid4()

        # Set up existing references
        repo.add_existing_job(job_id)
        repo.add_existing_operation(operation_id)

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
        )

        context = repo.validate_before_save(task)

        assert not context.has_errors
        assert not context.has_warnings

    def test_validate_duplicate_sequence(self):
        """Test validation fails for duplicate task sequence."""
        repo = MockTaskRepository()
        job_id = uuid4()
        operation_id = uuid4()

        # Set up existing references
        repo.add_existing_job(job_id)
        repo.add_existing_operation(operation_id)
        repo.add_existing_sequence(job_id, 10)  # Existing sequence

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,  # Duplicate sequence
            planned_duration_minutes=120,
        )

        context = repo.validate_before_save(task)

        assert context.has_errors
        assert any(
            "DUPLICATE_TASK_SEQUENCE" in error.error_code for error in context.errors
        )

    def test_validate_invalid_job_reference(self):
        """Test validation fails for invalid job reference."""
        repo = MockTaskRepository()
        job_id = uuid4()  # Non-existent job
        operation_id = uuid4()

        # Only add operation, not job
        repo.add_existing_operation(operation_id)

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
        )

        context = repo.validate_before_save(task)

        assert context.has_errors
        assert any(
            "INVALID_JOB_REFERENCE" in error.error_code for error in context.errors
        )

    def test_validate_invalid_machine_reference(self):
        """Test validation fails for invalid machine reference."""
        repo = MockTaskRepository()
        job_id = uuid4()
        operation_id = uuid4()
        machine_id = uuid4()  # Non-existent machine

        # Set up existing references except machine
        repo.add_existing_job(job_id)
        repo.add_existing_operation(operation_id)

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
        )
        task.assigned_machine_id = machine_id  # Invalid machine reference

        context = repo.validate_before_save(task)

        assert context.has_errors
        assert any(
            "INVALID_MACHINE_REFERENCE" in error.error_code for error in context.errors
        )


class TestMachineRepositoryValidation:
    """Test machine repository validation."""

    def test_validate_valid_machine(self):
        """Test validating a valid machine."""
        repo = MockMachineRepository()

        machine = Machine.create(
            machine_code="CNC-001",
            machine_name="CNC Machine #1",
            automation_level=MachineAutomationLevel.SEMI_AUTOMATED,
        )

        context = repo.validate_before_save(machine)

        assert not context.has_errors
        assert not context.has_warnings

    def test_validate_duplicate_machine_code(self):
        """Test validation fails for duplicate machine code."""
        repo = MockMachineRepository()
        repo.add_existing_machine_code("CNC-001")

        machine = Machine.create(
            machine_code="CNC-001",  # Duplicate code
            machine_name="CNC Machine #1",
            automation_level=MachineAutomationLevel.SEMI_AUTOMATED,
        )

        context = repo.validate_before_save(machine)

        assert context.has_errors
        assert any(
            "DUPLICATE_MACHINE_CODE" in error.error_code for error in context.errors
        )

    def test_validate_invalid_zone_reference(self):
        """Test validation fails for invalid production zone reference."""
        repo = MockMachineRepository()
        zone_id = uuid4()  # Non-existent zone

        machine = Machine.create(
            machine_code="CNC-001",
            machine_name="CNC Machine #1",
            automation_level=MachineAutomationLevel.SEMI_AUTOMATED,
            production_zone_id=zone_id,  # Invalid zone reference
        )

        context = repo.validate_before_save(machine)

        assert context.has_errors
        assert any(
            "INVALID_ZONE_REFERENCE" in error.error_code for error in context.errors
        )


class TestOperatorRepositoryValidation:
    """Test operator repository validation."""

    def test_validate_valid_operator(self):
        """Test validating a valid operator."""
        repo = MockOperatorRepository()

        operator = Operator.create(
            employee_id="EMP-001", first_name="John", last_name="Doe"
        )

        context = repo.validate_before_save(operator)

        assert not context.has_errors
        assert not context.has_warnings

    def test_validate_duplicate_employee_id(self):
        """Test validation fails for duplicate employee ID."""
        repo = MockOperatorRepository()
        repo.add_existing_employee_id("EMP-001")

        operator = Operator.create(
            employee_id="EMP-001",  # Duplicate employee ID
            first_name="John",
            last_name="Doe",
        )

        context = repo.validate_before_save(operator)

        assert context.has_errors
        assert any(
            "DUPLICATE_EMPLOYEE_ID" in error.error_code for error in context.errors
        )

    def test_validate_invalid_email(self):
        """Test validation fails for invalid email."""
        repo = MockOperatorRepository()

        contact_info = ContactInfo(
            email="invalid-email-format"  # Invalid email
        )

        operator = Operator.create(
            employee_id="EMP-001",
            first_name="John",
            last_name="Doe",
            contact_info=contact_info,
        )

        context = repo.validate_before_save(operator)

        assert context.has_errors
        assert any("INVALID_EMAIL" in error.error_code for error in context.errors)


class TestConstraintValidation:
    """Test constraint validation across entities."""

    def test_validate_no_resource_conflicts(self):
        """Test validation passes with no resource conflicts."""
        validator = ConstraintValidationMixin()

        # Create non-conflicting tasks
        job_id = uuid4()
        machine_id = uuid4()

        task1 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=1)
        task1.assigned_machine_id = machine_id
        task1.planned_start_time = datetime.utcnow() + timedelta(hours=1)
        task1.planned_end_time = datetime.utcnow() + timedelta(hours=3)

        task2 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=2)
        task2.assigned_machine_id = machine_id
        task2.planned_start_time = datetime.utcnow() + timedelta(hours=4)  # No conflict
        task2.planned_end_time = datetime.utcnow() + timedelta(hours=6)

        context = validator.validate_scheduling_constraints([task1, task2])

        assert not context.has_errors

    def test_validate_resource_conflicts(self):
        """Test validation fails with resource conflicts."""
        validator = ConstraintValidationMixin()

        # Create conflicting tasks
        job_id = uuid4()
        machine_id = uuid4()

        task1 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=1)
        task1.assigned_machine_id = machine_id
        task1.planned_start_time = datetime.utcnow() + timedelta(hours=1)
        task1.planned_end_time = datetime.utcnow() + timedelta(hours=3)

        task2 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=2)
        task2.assigned_machine_id = machine_id  # Same machine
        task2.planned_start_time = datetime.utcnow() + timedelta(
            hours=2
        )  # Overlapping time
        task2.planned_end_time = datetime.utcnow() + timedelta(hours=4)

        context = validator.validate_scheduling_constraints([task1, task2])

        assert context.has_errors
        assert any("RESOURCE_CONFLICT" in error.error_code for error in context.errors)

    def test_validate_precedence_violations(self):
        """Test validation fails with precedence violations."""
        validator = ConstraintValidationMixin()

        # Create tasks with precedence violation
        job_id = uuid4()

        task1 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=1)
        task1.planned_start_time = datetime.utcnow() + timedelta(hours=3)
        task1.planned_end_time = datetime.utcnow() + timedelta(hours=5)

        task2 = Task.create(job_id=job_id, operation_id=uuid4(), sequence_in_job=2)
        task2.planned_start_time = datetime.utcnow() + timedelta(
            hours=1
        )  # Starts before task1
        task2.planned_end_time = datetime.utcnow() + timedelta(hours=2)

        context = validator.validate_scheduling_constraints([task1, task2])

        assert context.has_errors
        assert any(
            "PRECEDENCE_VIOLATION" in error.error_code for error in context.errors
        )


class TestValidationUtilities:
    """Test validation utility functions."""

    def test_validate_foreign_key_reference_valid(self):
        """Test valid foreign key reference validation."""
        mock_method = Mock(return_value=True)
        entity_id = uuid4()

        # Should not raise exception
        result = validate_foreign_key_reference(mock_method, entity_id, "TestEntity")

        assert result is True
        mock_method.assert_called_once_with(entity_id)

    def test_validate_foreign_key_reference_invalid(self):
        """Test invalid foreign key reference validation."""
        mock_method = Mock(return_value=False)
        entity_id = uuid4()

        with pytest.raises(ValidationError) as exc_info:
            validate_foreign_key_reference(mock_method, entity_id, "TestEntity")

        assert "INVALID_REFERENCE" in exc_info.value.error_code
        mock_method.assert_called_once_with(entity_id)

    def test_validate_unique_constraint_valid(self):
        """Test valid uniqueness constraint validation."""
        mock_method = Mock(return_value=[])  # No existing records
        field_value = "unique_value"

        # Should not raise exception
        result = validate_unique_constraint(mock_method, field_value, "test_field")

        assert result is True
        mock_method.assert_called_once_with(field_value)

    def test_validate_unique_constraint_violation(self):
        """Test uniqueness constraint violation."""
        existing_record = Mock()
        existing_record.id = uuid4()
        mock_method = Mock(return_value=[existing_record])  # Existing record found
        field_value = "duplicate_value"

        with pytest.raises(ValidationError) as exc_info:
            validate_unique_constraint(mock_method, field_value, "test_field")

        assert "DUPLICATE_VALUE" in exc_info.value.error_code
        mock_method.assert_called_once_with(field_value)

    def test_validate_unique_constraint_with_exclusion(self):
        """Test uniqueness constraint with exclusion for updates."""
        existing_record = Mock()
        existing_record.id = uuid4()
        mock_method = Mock(return_value=[existing_record])
        field_value = "value"

        # Should not raise exception when excluding the same record
        result = validate_unique_constraint(
            mock_method, field_value, "test_field", exclude_id=existing_record.id
        )

        assert result is True
        mock_method.assert_called_once_with(field_value)


if __name__ == "__main__":
    pytest.main([__file__])
