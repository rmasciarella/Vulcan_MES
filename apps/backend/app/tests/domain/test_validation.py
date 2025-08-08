"""
Comprehensive validation tests for domain entities and business rules.

Tests cover:
- Field-level validation
- Business rule validation
- Input sanitization
- Repository validation
- Constraint validation
- Error handling and messaging
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.machine import Machine
from app.domain.scheduling.entities.operator import Operator
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.common import (
    ContactInfo,
    WorkingHours,
)
from app.domain.scheduling.value_objects.enums import (
    MachineAutomationLevel,
    PriorityLevel,
)
from app.domain.shared.exceptions import (
    MultipleValidationError,
)
from app.domain.shared.validation import (
    BusinessRuleValidators,
    DataSanitizer,
    SchedulingValidators,
    ValidationContext,
    ValidationContextManager,
    ValidationError,
)


class TestDataSanitizer:
    """Test data sanitization utilities."""

    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        result = DataSanitizer.sanitize_string("  Hello World  ")
        assert result == "Hello World"

    def test_sanitize_string_max_length(self):
        """Test string length validation."""
        with pytest.raises(ValidationError) as exc_info:
            DataSanitizer.sanitize_string("A" * 100, max_length=50)

        assert "TOO_LONG" in str(exc_info.value.error_code)

    def test_sanitize_string_empty_not_allowed(self):
        """Test empty string validation."""
        with pytest.raises(ValidationError) as exc_info:
            DataSanitizer.sanitize_string("", allow_empty=False)

        assert "EMPTY_VALUE" in str(exc_info.value.error_code)

    def test_sanitize_code_valid(self):
        """Test valid code sanitization."""
        result = DataSanitizer.sanitize_code("abc-123_def")
        assert result == "ABC-123_DEF"

    def test_sanitize_code_invalid_chars(self):
        """Test code with invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            DataSanitizer.sanitize_code("abc@123")

        assert "INVALID_FORMAT" in str(exc_info.value.error_code)

    def test_sanitize_email_valid(self):
        """Test valid email sanitization."""
        result = DataSanitizer.sanitize_email("  Test.User@Example.COM  ")
        assert result == "test.user@example.com"

    def test_sanitize_email_invalid(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            DataSanitizer.sanitize_email("invalid-email")

        assert "INVALID_EMAIL" in str(exc_info.value.error_code)

    def test_sanitize_phone_valid(self):
        """Test valid phone sanitization."""
        result = DataSanitizer.sanitize_phone("(555) 123-4567")
        assert result == "5551234567"

    def test_sanitize_phone_invalid_length(self):
        """Test invalid phone length."""
        with pytest.raises(ValidationError) as exc_info:
            DataSanitizer.sanitize_phone("123")

        assert "INVALID_PHONE" in str(exc_info.value.error_code)


class TestBusinessRuleValidators:
    """Test business rule validation functions."""

    def test_validate_future_date_valid(self):
        """Test future date validation with valid date."""
        future_date = datetime.utcnow() + timedelta(days=1)
        # Should not raise exception
        BusinessRuleValidators.validate_future_date("test_date", future_date)

    def test_validate_future_date_invalid(self):
        """Test future date validation with past date."""
        past_date = datetime.utcnow() - timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            BusinessRuleValidators.validate_future_date("test_date", past_date)

        assert "DATE_NOT_FUTURE" in str(exc_info.value.error_code)

    def test_validate_date_range_valid(self):
        """Test valid date range."""
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(hours=2)

        # Should not raise exception
        BusinessRuleValidators.validate_date_range("start", start_date, "end", end_date)

    def test_validate_date_range_invalid(self):
        """Test invalid date range."""
        start_date = datetime.utcnow()
        end_date = start_date - timedelta(hours=1)

        with pytest.raises(ValidationError) as exc_info:
            BusinessRuleValidators.validate_date_range(
                "start", start_date, "end", end_date
            )

        assert "INVALID_DATE_RANGE" in str(exc_info.value.error_code)

    def test_validate_positive_number_valid(self):
        """Test positive number validation."""
        BusinessRuleValidators.validate_positive_number("test", 10)
        BusinessRuleValidators.validate_positive_number("test", 0.5)
        BusinessRuleValidators.validate_positive_number("test", Decimal("1.5"))

    def test_validate_positive_number_invalid(self):
        """Test negative number validation."""
        with pytest.raises(ValidationError) as exc_info:
            BusinessRuleValidators.validate_positive_number("test", -1)

        assert "NOT_POSITIVE" in str(exc_info.value.error_code)

    def test_validate_range_valid(self):
        """Test range validation."""
        BusinessRuleValidators.validate_range("test", 5, 1, 10)
        BusinessRuleValidators.validate_range("test", 1, 1, 10)
        BusinessRuleValidators.validate_range("test", 10, 1, 10)

    def test_validate_range_below_minimum(self):
        """Test value below minimum."""
        with pytest.raises(ValidationError) as exc_info:
            BusinessRuleValidators.validate_range("test", 0, 1, 10)

        assert "BELOW_MINIMUM" in str(exc_info.value.error_code)

    def test_validate_range_above_maximum(self):
        """Test value above maximum."""
        with pytest.raises(ValidationError) as exc_info:
            BusinessRuleValidators.validate_range("test", 11, 1, 10)

        assert "ABOVE_MAXIMUM" in str(exc_info.value.error_code)


class TestSchedulingValidators:
    """Test scheduling domain-specific validators."""

    def test_validate_job_number_format_valid(self):
        """Test valid job number formats."""
        valid_numbers = ["JOB-123", "ABC_DEF", "12345", "TEST-JOB-001"]

        for number in valid_numbers:
            result = SchedulingValidators.validate_job_number_format(number)
            assert result.isupper()
            assert len(result) >= 3

    def test_validate_job_number_format_invalid(self):
        """Test invalid job number formats."""
        invalid_numbers = ["AB", "job@123", "test job", ""]

        for number in invalid_numbers:
            with pytest.raises(ValidationError):
                SchedulingValidators.validate_job_number_format(number)

    def test_validate_task_sequence_valid(self):
        """Test valid task sequences."""
        valid_sequences = [1, 50, 100]

        for seq in valid_sequences:
            # Should not raise exception
            SchedulingValidators.validate_task_sequence(seq)

    def test_validate_task_sequence_invalid(self):
        """Test invalid task sequences."""
        invalid_sequences = [0, -1, 101, 1000]

        for seq in invalid_sequences:
            with pytest.raises(ValidationError):
                SchedulingValidators.validate_task_sequence(seq)

    def test_validate_efficiency_factor_valid(self):
        """Test valid efficiency factors."""
        valid_factors = [0.1, 1.0, 2.0, Decimal("1.5")]

        for factor in valid_factors:
            # Should not raise exception
            SchedulingValidators.validate_efficiency_factor(factor)

    def test_validate_efficiency_factor_invalid(self):
        """Test invalid efficiency factors."""
        invalid_factors = [0.05, 2.5, -0.5]

        for factor in invalid_factors:
            with pytest.raises(ValidationError):
                SchedulingValidators.validate_efficiency_factor(factor)


class TestJobValidation:
    """Test Job entity validation."""

    def test_job_creation_valid(self):
        """Test creating valid job."""
        future_date = datetime.utcnow() + timedelta(days=7)

        job = Job.create(
            job_number="TEST-JOB-001",
            due_date=future_date,
            customer_name="Test Customer",
            part_number="PART-123",
            quantity=10,
            priority=PriorityLevel.HIGH,
        )

        assert job.job_number == "TEST-JOB-001"
        assert job.customer_name == "Test Customer"
        assert job.part_number == "PART-123"
        assert job.quantity.value == 10
        assert job.priority == PriorityLevel.HIGH
        assert job.is_valid()

    def test_job_invalid_job_number(self):
        """Test job with invalid job number."""
        future_date = datetime.utcnow() + timedelta(days=7)

        with pytest.raises(ValueError):
            Job(
                job_number="",  # Empty job number
                due_date=future_date,
            )

    def test_job_invalid_due_date(self):
        """Test job with past due date."""
        past_date = datetime.utcnow() - timedelta(days=1)

        with pytest.raises(ValueError):
            Job(
                job_number="TEST-001",
                due_date=past_date,  # Past due date
            )

    def test_job_sanitized_fields(self):
        """Test field sanitization in job."""
        future_date = datetime.utcnow() + timedelta(days=7)

        job = Job(
            job_number="  test-job-001  ",  # Should be sanitized
            due_date=future_date,
            customer_name="  Test Customer  ",  # Should be sanitized
            part_number="  PART-123  ",  # Should be sanitized
            notes="  Test notes  ",  # Should be sanitized
        )

        assert job.job_number == "TEST-JOB-001"
        assert job.customer_name == "Test Customer"
        assert job.part_number == "PART-123"
        assert job.notes == "Test notes"


class TestTaskValidation:
    """Test Task entity validation."""

    def test_task_creation_valid(self):
        """Test creating valid task."""
        job_id = uuid4()
        operation_id = uuid4()

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=10,
            planned_duration_minutes=120,
            setup_duration_minutes=30,
        )

        assert task.job_id == job_id
        assert task.operation_id == operation_id
        assert task.sequence_in_job == 10
        assert task.planned_duration.minutes == 120
        assert task.planned_setup_duration.minutes == 30
        assert task.is_valid()

    def test_task_invalid_sequence(self):
        """Test task with invalid sequence."""
        with pytest.raises(ValueError):
            Task(
                job_id=uuid4(),
                operation_id=uuid4(),
                sequence_in_job=0,  # Invalid sequence
            )

        with pytest.raises(ValueError):
            Task(
                job_id=uuid4(),
                operation_id=uuid4(),
                sequence_in_job=101,  # Invalid sequence
            )

    def test_task_negative_values(self):
        """Test task with negative values."""
        job_id = uuid4()
        operation_id = uuid4()

        with pytest.raises(ValueError):
            Task(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=10,
                delay_minutes=-10,  # Negative delay not allowed
            )

        with pytest.raises(ValueError):
            Task(
                job_id=job_id,
                operation_id=operation_id,
                sequence_in_job=10,
                rework_count=-1,  # Negative rework not allowed
            )


class TestMachineValidation:
    """Test Machine entity validation."""

    def test_machine_creation_valid(self):
        """Test creating valid machine."""
        machine = Machine.create(
            machine_code="CNC-001",
            machine_name="CNC Machining Center #1",
            automation_level=MachineAutomationLevel.SEMI_AUTOMATED,
            efficiency_factor=1.2,
        )

        assert machine.machine_code == "CNC-001"
        assert machine.machine_name == "CNC Machining Center #1"
        assert machine.automation_level == MachineAutomationLevel.SEMI_AUTOMATED
        assert float(machine.efficiency_factor.factor) == 1.2
        assert machine.is_valid()

    def test_machine_invalid_code(self):
        """Test machine with invalid code."""
        with pytest.raises(ValueError):
            Machine(
                machine_code="cnc@001",  # Invalid characters
                machine_name="Test Machine",
                automation_level=MachineAutomationLevel.MANUAL,
            )

    def test_machine_sanitized_name(self):
        """Test machine name sanitization."""
        machine = Machine(
            machine_code="CNC-001",
            machine_name="  CNC Machine  ",  # Should be sanitized
            automation_level=MachineAutomationLevel.MANUAL,
        )

        assert machine.machine_name == "CNC Machine"


class TestOperatorValidation:
    """Test Operator entity validation."""

    def test_operator_creation_valid(self):
        """Test creating valid operator."""
        working_hours = WorkingHours(start_time=time(8, 0), end_time=time(17, 0))

        contact_info = ContactInfo(email="john.doe@company.com", phone="5551234567")

        operator = Operator.create(
            employee_id="EMP-001",
            first_name="John",
            last_name="Doe",
            working_hours=working_hours,
            contact_info=contact_info,
            hire_date=date(2023, 1, 15),
        )

        assert operator.employee_id == "EMP-001"
        assert operator.first_name == "John"
        assert operator.last_name == "Doe"
        assert operator.full_name == "John Doe"
        assert operator.is_valid()

    def test_operator_invalid_employee_id(self):
        """Test operator with invalid employee ID."""
        with pytest.raises(ValueError):
            Operator(
                employee_id="emp@001",  # Invalid characters
                first_name="John",
                last_name="Doe",
            )

    def test_operator_sanitized_names(self):
        """Test operator name sanitization."""
        operator = Operator(
            employee_id="EMP-001",
            first_name="  John  ",  # Should be sanitized
            last_name="  Doe  ",  # Should be sanitized
        )

        assert operator.first_name == "John"
        assert operator.last_name == "Doe"


class TestValidationContext:
    """Test validation context functionality."""

    def test_validation_context_empty(self):
        """Test empty validation context."""
        context = ValidationContext()

        assert not context.has_errors
        assert not context.has_warnings
        assert len(context.errors) == 0
        assert len(context.warnings) == 0

    def test_validation_context_with_errors(self):
        """Test validation context with errors."""
        context = ValidationContext()

        context.add_error("field1", "value1", "Error message 1", "ERROR_CODE_1")
        context.add_error("field2", "value2", "Error message 2", "ERROR_CODE_2")

        assert context.has_errors
        assert len(context.errors) == 2
        assert context.errors[0].field_name == "field1"
        assert context.errors[1].field_name == "field2"

    def test_validation_context_with_warnings(self):
        """Test validation context with warnings."""
        context = ValidationContext()

        context.add_warning("Warning message 1")
        context.add_warning("Warning message 2")

        assert context.has_warnings
        assert len(context.warnings) == 2
        assert "Warning message 1" in context.warnings
        assert "Warning message 2" in context.warnings

    def test_validation_context_manager(self):
        """Test validation context manager."""
        with pytest.raises(ValidationError):
            with ValidationContextManager() as context:
                context.add_error(
                    "test_field", "test_value", "Test error", "TEST_ERROR"
                )


class TestMultipleValidationError:
    """Test multiple validation error handling."""

    def test_multiple_validation_error_creation(self):
        """Test creating multiple validation error."""
        errors = [
            ValidationError("field1", "value1", "Error 1", "ERROR_1"),
            ValidationError("field2", "value2", "Error 2", "ERROR_2"),
        ]

        multi_error = MultipleValidationError(errors)

        assert multi_error.error_count == 2
        assert len(multi_error.validation_errors) == 2
        assert "Multiple validation errors" in str(multi_error)


if __name__ == "__main__":
    pytest.main([__file__])
