"""
Application layer validators for request validation and business rule checking.

This module provides validation classes that handle application-level validation
requirements, including input validation, business rule validation, and
cross-cutting validation concerns.
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError


class ValidationResult:
    """Result of a validation operation."""

    def __init__(self, is_valid: bool = True, errors: list[str] | None = None):
        """
        Initialize validation result.

        Args:
            is_valid: Whether validation passed
            errors: List of validation error messages
        """
        self.is_valid = is_valid
        self.errors = errors or []

    def add_error(self, error_message: str) -> None:
        """Add an error message and mark as invalid."""
        self.errors.append(error_message)
        self.is_valid = False

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
            self.errors.extend(other.errors)


class ApplicationValidator(ABC):
    """
    Abstract base class for application validators.

    Provides common validation utilities and defines the interface
    for application-level validation operations.
    """

    @abstractmethod
    def validate(self, data: Any) -> ValidationResult:
        """
        Validate the provided data.

        Args:
            data: Data to validate

        Returns:
            ValidationResult with success/failure and error messages
        """
        pass

    def validate_pydantic_model(
        self, model_class: type, data: dict
    ) -> ValidationResult:
        """
        Validate data against a Pydantic model.

        Args:
            model_class: Pydantic model class
            data: Data to validate

        Returns:
            ValidationResult
        """
        try:
            model_class(**data)
            return ValidationResult(True)
        except PydanticValidationError as e:
            result = ValidationResult(False)
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                result.add_error(f"{field}: {error['msg']}")
            return result

    def validate_required_field(self, value: Any, field_name: str) -> ValidationResult:
        """Validate that a required field has a value."""
        result = ValidationResult()
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(f"{field_name} is required")
        return result

    def validate_string_length(
        self,
        value: str | None,
        field_name: str,
        min_length: int = 0,
        max_length: int | None = None,
    ) -> ValidationResult:
        """Validate string length constraints."""
        result = ValidationResult()
        if value is not None:
            length = len(value)
            if length < min_length:
                result.add_error(
                    f"{field_name} must be at least {min_length} characters"
                )
            if max_length and length > max_length:
                result.add_error(
                    f"{field_name} must not exceed {max_length} characters"
                )
        return result

    def validate_numeric_range(
        self,
        value: float | None,
        field_name: str,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> ValidationResult:
        """Validate numeric value is within acceptable range."""
        result = ValidationResult()
        if value is not None:
            if min_value is not None and value < min_value:
                result.add_error(f"{field_name} must be at least {min_value}")
            if max_value is not None and value > max_value:
                result.add_error(f"{field_name} must not exceed {max_value}")
        return result

    def validate_enum_value(
        self, value: str | None, field_name: str, valid_values: list[str]
    ) -> ValidationResult:
        """Validate value is one of the allowed enum values."""
        result = ValidationResult()
        if value is not None and value not in valid_values:
            result.add_error(f"{field_name} must be one of: {', '.join(valid_values)}")
        return result

    def validate_datetime_future(
        self, value: datetime | None, field_name: str
    ) -> ValidationResult:
        """Validate datetime is in the future."""
        result = ValidationResult()
        if value is not None and value <= datetime.utcnow():
            result.add_error(f"{field_name} must be in the future")
        return result

    def validate_datetime_range(
        self,
        start: datetime | None,
        end: datetime | None,
        start_field: str,
        end_field: str,
    ) -> ValidationResult:
        """Validate datetime range (start before end)."""
        result = ValidationResult()
        if start is not None and end is not None and start >= end:
            result.add_error(f"{start_field} must be before {end_field}")
        return result

    def validate_email(self, email: str | None, field_name: str) -> ValidationResult:
        """Validate email format."""
        result = ValidationResult()
        if email is not None:
            email_pattern = re.compile(
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            )
            if not email_pattern.match(email):
                result.add_error(f"{field_name} must be a valid email address")
        return result

    def validate_uuid(self, value: str | None, field_name: str) -> ValidationResult:
        """Validate UUID format."""
        result = ValidationResult()
        if value is not None:
            try:
                UUID(value)
            except ValueError:
                result.add_error(f"{field_name} must be a valid UUID")
        return result


class JobValidator(ApplicationValidator):
    """
    Validator for job-related operations.

    Handles validation of job creation, updates, and status changes.
    """

    VALID_STATUSES = [
        "planned",
        "released",
        "in_progress",
        "completed",
        "on_hold",
        "cancelled",
    ]
    VALID_PRIORITIES = ["low", "normal", "high", "critical"]

    def validate(self, data: Any) -> ValidationResult:
        """Validate job data."""
        if isinstance(data, dict):
            return self.validate_job_dict(data)
        else:
            result = ValidationResult(False)
            result.add_error("Job data must be a dictionary")
            return result

    def validate_job_dict(self, job_data: dict) -> ValidationResult:
        """Validate job dictionary data."""
        result = ValidationResult()

        # Validate job number
        job_number = job_data.get("job_number")
        result.merge(self.validate_required_field(job_number, "job_number"))
        result.merge(
            self.validate_string_length(
                job_number, "job_number", min_length=1, max_length=50
            )
        )
        if job_number:
            result.merge(self.validate_job_number_format(job_number))

        # Validate customer name
        customer_name = job_data.get("customer_name")
        result.merge(
            self.validate_string_length(customer_name, "customer_name", max_length=100)
        )

        # Validate part number
        part_number = job_data.get("part_number")
        result.merge(
            self.validate_string_length(part_number, "part_number", max_length=50)
        )

        # Validate quantity
        quantity = job_data.get("quantity", 1)
        result.merge(self.validate_numeric_range(quantity, "quantity", min_value=1))

        # Validate priority
        priority = job_data.get("priority")
        if priority:
            result.merge(
                self.validate_enum_value(priority, "priority", self.VALID_PRIORITIES)
            )

        # Validate status
        status = job_data.get("status")
        if status:
            result.merge(
                self.validate_enum_value(status, "status", self.VALID_STATUSES)
            )

        # Validate due date
        due_date = job_data.get("due_date")
        if due_date:
            result.merge(self.validate_datetime_future(due_date, "due_date"))

        # Validate date ranges
        planned_start = job_data.get("planned_start_date")
        planned_end = job_data.get("planned_end_date")
        result.merge(
            self.validate_datetime_range(
                planned_start, planned_end, "planned_start_date", "planned_end_date"
            )
        )

        actual_start = job_data.get("actual_start_date")
        actual_end = job_data.get("actual_end_date")
        result.merge(
            self.validate_datetime_range(
                actual_start, actual_end, "actual_start_date", "actual_end_date"
            )
        )

        # Validate operation sequence
        sequence = job_data.get("current_operation_sequence")
        if sequence is not None:
            result.merge(
                self.validate_numeric_range(
                    sequence, "current_operation_sequence", min_value=0, max_value=100
                )
            )

        # Validate notes length
        notes = job_data.get("notes")
        result.merge(self.validate_string_length(notes, "notes", max_length=1000))

        return result

    def validate_job_number_format(self, job_number: str) -> ValidationResult:
        """Validate job number format."""
        result = ValidationResult()
        # Job number should contain only alphanumeric characters, hyphens, and underscores
        if not re.match(r"^[A-Za-z0-9\-_]+$", job_number):
            result.add_error(
                "Job number can only contain letters, numbers, hyphens, and underscores"
            )
        return result

    def validate_status_transition(
        self, current_status: str, new_status: str
    ) -> ValidationResult:
        """Validate job status transition is allowed."""
        result = ValidationResult()

        # Define valid transitions
        valid_transitions = {
            "planned": ["released", "on_hold", "cancelled"],
            "released": ["in_progress", "on_hold", "cancelled"],
            "in_progress": ["completed", "on_hold", "cancelled"],
            "on_hold": ["released", "cancelled"],
            "completed": [],  # No transitions from completed
            "cancelled": [],  # No transitions from cancelled
        }

        if new_status not in valid_transitions.get(current_status, []):
            result.add_error(f"Cannot transition from {current_status} to {new_status}")

        return result


class TaskValidator(ApplicationValidator):
    """
    Validator for task-related operations.

    Handles validation of task creation, updates, and assignments.
    """

    VALID_STATUSES = [
        "pending",
        "ready",
        "scheduled",
        "in_progress",
        "completed",
        "cancelled",
        "failed",
    ]

    def validate(self, data: Any) -> ValidationResult:
        """Validate task data."""
        if isinstance(data, dict):
            return self.validate_task_dict(data)
        else:
            result = ValidationResult(False)
            result.add_error("Task data must be a dictionary")
            return result

    def validate_task_dict(self, task_data: dict) -> ValidationResult:
        """Validate task dictionary data."""
        result = ValidationResult()

        # Validate job ID
        job_id = task_data.get("job_id")
        result.merge(self.validate_required_field(job_id, "job_id"))
        if job_id:
            result.merge(self.validate_uuid(str(job_id), "job_id"))

        # Validate sequence in job
        sequence = task_data.get("sequence_in_job")
        result.merge(self.validate_required_field(sequence, "sequence_in_job"))
        result.merge(
            self.validate_numeric_range(
                sequence, "sequence_in_job", min_value=1, max_value=100
            )
        )

        # Validate status
        status = task_data.get("status")
        if status:
            result.merge(
                self.validate_enum_value(status, "status", self.VALID_STATUSES)
            )

        # Validate durations
        planned_duration = task_data.get("planned_duration_minutes")
        if planned_duration is not None:
            result.merge(
                self.validate_numeric_range(
                    planned_duration, "planned_duration_minutes", min_value=0
                )
            )

        setup_duration = task_data.get("planned_setup_duration_minutes", 0)
        result.merge(
            self.validate_numeric_range(
                setup_duration, "planned_setup_duration_minutes", min_value=0
            )
        )

        # Validate time ranges
        planned_start = task_data.get("planned_start_time")
        planned_end = task_data.get("planned_end_time")
        result.merge(
            self.validate_datetime_range(
                planned_start, planned_end, "planned_start_time", "planned_end_time"
            )
        )

        actual_start = task_data.get("actual_start_time")
        actual_end = task_data.get("actual_end_time")
        result.merge(
            self.validate_datetime_range(
                actual_start, actual_end, "actual_start_time", "actual_end_time"
            )
        )

        return result


class SchedulingValidator(ApplicationValidator):
    """
    Validator for scheduling-related operations.

    Handles validation of scheduling requests and optimization parameters.
    """

    def validate(self, data: Any) -> ValidationResult:
        """Validate scheduling data."""
        if isinstance(data, dict):
            return self.validate_scheduling_dict(data)
        else:
            result = ValidationResult(False)
            result.add_error("Scheduling data must be a dictionary")
            return result

    def validate_scheduling_dict(self, scheduling_data: dict) -> ValidationResult:
        """Validate scheduling dictionary data."""
        result = ValidationResult()

        # Validate time horizon
        start_date = scheduling_data.get("start_date")
        end_date = scheduling_data.get("end_date")

        if start_date:
            result.merge(self.validate_datetime_future(start_date, "start_date"))

        if start_date and end_date:
            result.merge(
                self.validate_datetime_range(
                    start_date, end_date, "start_date", "end_date"
                )
            )

            # Validate reasonable time horizon
            if end_date - start_date > timedelta(days=365):
                result.add_error("Scheduling horizon cannot exceed 365 days")

        # Validate job IDs if provided
        job_ids = scheduling_data.get("job_ids", [])
        if job_ids:
            for i, job_id in enumerate(job_ids):
                result.merge(self.validate_uuid(str(job_id), f"job_ids[{i}]"))

        # Validate optimization parameters
        max_iterations = scheduling_data.get("max_iterations")
        if max_iterations is not None:
            result.merge(
                self.validate_numeric_range(
                    max_iterations, "max_iterations", min_value=1, max_value=10000
                )
            )

        time_limit = scheduling_data.get("time_limit_seconds")
        if time_limit is not None:
            result.merge(
                self.validate_numeric_range(
                    time_limit, "time_limit_seconds", min_value=1, max_value=3600
                )
            )

        return result

    def validate_resource_constraints(self, constraints: dict) -> ValidationResult:
        """Validate resource constraints for scheduling."""
        result = ValidationResult()

        # Validate machine constraints
        machine_constraints = constraints.get("machine_constraints", {})
        for machine_id, constraint in machine_constraints.items():
            result.merge(
                self.validate_uuid(str(machine_id), f"machine_constraints.{machine_id}")
            )

            if isinstance(constraint, dict):
                max_concurrent = constraint.get("max_concurrent_tasks")
                if max_concurrent is not None:
                    result.merge(
                        self.validate_numeric_range(
                            max_concurrent, "max_concurrent_tasks", min_value=1
                        )
                    )

        # Validate operator constraints
        operator_constraints = constraints.get("operator_constraints", {})
        for operator_id, constraint in operator_constraints.items():
            result.merge(
                self.validate_uuid(
                    str(operator_id), f"operator_constraints.{operator_id}"
                )
            )

            if isinstance(constraint, dict):
                max_hours_per_day = constraint.get("max_hours_per_day")
                if max_hours_per_day is not None:
                    result.merge(
                        self.validate_numeric_range(
                            max_hours_per_day,
                            "max_hours_per_day",
                            min_value=1,
                            max_value=24,
                        )
                    )

        return result
