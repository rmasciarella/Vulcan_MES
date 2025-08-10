"""
Repository validation mixins for data operations and constraint validation.

Provides validation capabilities for repository implementations including:
- Pre-save validation
- Constraint checking
- Referential integrity validation
- Business rule enforcement at data layer
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from ...shared.exceptions import (
    MultipleValidationError,
    ValidationError,
)
from ...shared.validation import ValidationContext, validate_entity

T = TypeVar("T")


class ValidationMixin(ABC):
    """Base mixin for repository validation capabilities."""

    def validate_before_save(
        self, entity: Any, context: ValidationContext = None
    ) -> ValidationContext:
        """
        Validate entity before saving to repository.

        Args:
            entity: Entity to validate
            context: Existing validation context

        Returns:
            ValidationContext with any validation errors
        """
        if context is None:
            context = ValidationContext()

        # Run entity-level validation
        validate_entity(entity, context)

        # Run repository-specific validation
        self._validate_repository_constraints(entity, context)

        return context

    @abstractmethod
    def _validate_repository_constraints(
        self, entity: Any, context: ValidationContext
    ) -> None:
        """Validate repository-specific constraints."""
        pass


class JobRepositoryValidationMixin(ValidationMixin):
    """Validation mixin for Job repository operations."""

    def _validate_repository_constraints(
        self, job: Any, context: ValidationContext
    ) -> None:
        """Validate job-specific repository constraints."""
        from ..entities.job import Job

        if not isinstance(job, Job):
            context.add_error(
                "entity", job, "Entity must be a Job instance", "INVALID_ENTITY_TYPE"
            )
            return

        # Validate job number uniqueness (would need to check against existing records)
        if hasattr(self, "_check_job_number_exists"):
            if self._check_job_number_exists(job.job_number, exclude_id=job.id):
                context.add_error(
                    "job_number",
                    job.job_number,
                    f"Job number '{job.job_number}' already exists",
                    "DUPLICATE_JOB_NUMBER",
                )

        # Validate due date constraints
        if job.due_date <= datetime.utcnow():
            context.add_error(
                "due_date",
                job.due_date,
                "Due date must be in the future",
                "INVALID_DUE_DATE",
            )

        # Validate planned dates consistency
        if job.planned_start_date and job.planned_end_date:
            if job.planned_start_date >= job.planned_end_date:
                context.add_error(
                    "planned_end_date",
                    job.planned_end_date,
                    "Planned end date must be after planned start date",
                    "INVALID_DATE_RANGE",
                )

        # Validate actual dates consistency
        if job.actual_start_date and job.actual_end_date:
            if job.actual_start_date >= job.actual_end_date:
                context.add_error(
                    "actual_end_date",
                    job.actual_end_date,
                    "Actual end date must be after actual start date",
                    "INVALID_DATE_RANGE",
                )

        # Validate status transitions
        if hasattr(job, "_original_status") and job._original_status != job.status:
            if not self._is_valid_status_transition(job._original_status, job.status):
                context.add_error(
                    "status",
                    job.status,
                    f"Invalid status transition from {job._original_status} to {job.status}",
                    "INVALID_STATUS_TRANSITION",
                )

    def _is_valid_status_transition(self, from_status: Any, to_status: Any) -> bool:
        """Check if status transition is valid."""
        # This would contain the actual business logic for valid transitions
        # For now, we'll assume all transitions are valid unless specifically restricted
        return True


class TaskRepositoryValidationMixin(ValidationMixin):
    """Validation mixin for Task repository operations."""

    def _validate_repository_constraints(
        self, task: Any, context: ValidationContext
    ) -> None:
        """Validate task-specific repository constraints."""
        from ..entities.task import Task

        if not isinstance(task, Task):
            context.add_error(
                "entity", task, "Entity must be a Task instance", "INVALID_ENTITY_TYPE"
            )
            return

        # Validate sequence uniqueness within job
        if hasattr(self, "_check_task_sequence_exists"):
            if self._check_task_sequence_exists(
                task.job_id, task.sequence_in_job, exclude_id=task.id
            ):
                context.add_error(
                    "sequence_in_job",
                    task.sequence_in_job,
                    f"Task sequence {task.sequence_in_job} already exists in job",
                    "DUPLICATE_TASK_SEQUENCE",
                )

        # Validate job exists
        if hasattr(self, "_check_job_exists"):
            if not self._check_job_exists(task.job_id):
                context.add_error(
                    "job_id",
                    task.job_id,
                    f"Job {task.job_id} does not exist",
                    "INVALID_JOB_REFERENCE",
                )

        # Validate operation exists
        if hasattr(self, "_check_operation_exists"):
            if not self._check_operation_exists(task.operation_id):
                context.add_error(
                    "operation_id",
                    task.operation_id,
                    f"Operation {task.operation_id} does not exist",
                    "INVALID_OPERATION_REFERENCE",
                )

        # Validate machine assignment
        if task.assigned_machine_id and hasattr(self, "_check_machine_exists"):
            if not self._check_machine_exists(task.assigned_machine_id):
                context.add_error(
                    "assigned_machine_id",
                    task.assigned_machine_id,
                    f"Machine {task.assigned_machine_id} does not exist",
                    "INVALID_MACHINE_REFERENCE",
                )

        # Validate planned time consistency
        if task.planned_start_time and task.planned_end_time:
            if task.planned_start_time >= task.planned_end_time:
                context.add_error(
                    "planned_end_time",
                    task.planned_end_time,
                    "Planned end time must be after planned start time",
                    "INVALID_TIME_RANGE",
                )

        # Validate actual time consistency
        if task.actual_start_time and task.actual_end_time:
            if task.actual_start_time >= task.actual_end_time:
                context.add_error(
                    "actual_end_time",
                    task.actual_end_time,
                    "Actual end time must be after actual start time",
                    "INVALID_TIME_RANGE",
                )


class MachineRepositoryValidationMixin(ValidationMixin):
    """Validation mixin for Machine repository operations."""

    def _validate_repository_constraints(
        self, machine: Any, context: ValidationContext
    ) -> None:
        """Validate machine-specific repository constraints."""
        from ..entities.machine import Machine

        if not isinstance(machine, Machine):
            context.add_error(
                "entity",
                machine,
                "Entity must be a Machine instance",
                "INVALID_ENTITY_TYPE",
            )
            return

        # Validate machine code uniqueness
        if hasattr(self, "_check_machine_code_exists"):
            if self._check_machine_code_exists(
                machine.machine_code, exclude_id=machine.id
            ):
                context.add_error(
                    "machine_code",
                    machine.machine_code,
                    f"Machine code '{machine.machine_code}' already exists",
                    "DUPLICATE_MACHINE_CODE",
                )

        # Validate production zone exists
        if machine.production_zone_id and hasattr(
            self, "_check_production_zone_exists"
        ):
            if not self._check_production_zone_exists(machine.production_zone_id):
                context.add_error(
                    "production_zone_id",
                    machine.production_zone_id,
                    f"Production zone {machine.production_zone_id} does not exist",
                    "INVALID_ZONE_REFERENCE",
                )

        # Validate efficiency factor range
        if hasattr(machine, "efficiency_factor"):
            factor_value = float(machine.efficiency_factor.factor)
            if not (0.1 <= factor_value <= 2.0):
                context.add_error(
                    "efficiency_factor",
                    factor_value,
                    "Efficiency factor must be between 0.1 and 2.0",
                    "INVALID_EFFICIENCY_FACTOR",
                )


class OperatorRepositoryValidationMixin(ValidationMixin):
    """Validation mixin for Operator repository operations."""

    def _validate_repository_constraints(
        self, operator: Any, context: ValidationContext
    ) -> None:
        """Validate operator-specific repository constraints."""
        from ..entities.operator import Operator

        if not isinstance(operator, Operator):
            context.add_error(
                "entity",
                operator,
                "Entity must be an Operator instance",
                "INVALID_ENTITY_TYPE",
            )
            return

        # Validate employee ID uniqueness
        if hasattr(self, "_check_employee_id_exists"):
            if self._check_employee_id_exists(
                operator.employee_id, exclude_id=operator.id
            ):
                context.add_error(
                    "employee_id",
                    operator.employee_id,
                    f"Employee ID '{operator.employee_id}' already exists",
                    "DUPLICATE_EMPLOYEE_ID",
                )

        # Validate contact info if present
        if operator.contact_info:
            if operator.contact_info.email:
                # Basic email validation (enhanced validation would be in the value object)
                if "@" not in operator.contact_info.email:
                    context.add_error(
                        "contact_info.email",
                        operator.contact_info.email,
                        "Invalid email format",
                        "INVALID_EMAIL",
                    )

        # Validate working hours
        if operator.default_working_hours:
            if (
                operator.default_working_hours.start_time
                >= operator.default_working_hours.end_time
            ):
                context.add_error(
                    "default_working_hours",
                    operator.default_working_hours,
                    "End time must be after start time",
                    "INVALID_WORKING_HOURS",
                )


class ConstraintValidationMixin:
    """Mixin for validating domain constraints across entities."""

    def validate_scheduling_constraints(
        self, tasks: list[Any], context: ValidationContext = None
    ) -> ValidationContext:
        """
        Validate scheduling constraints across multiple tasks.

        Args:
            tasks: List of tasks to validate
            context: Existing validation context

        Returns:
            ValidationContext with constraint violations
        """
        if context is None:
            context = ValidationContext()

        # Check for resource conflicts
        self._validate_resource_conflicts(tasks, context)

        # Check for precedence violations
        self._validate_precedence_constraints(tasks, context)

        # Check for capacity constraints
        self._validate_capacity_constraints(tasks, context)

        return context

    def _validate_resource_conflicts(
        self, tasks: list[Any], context: ValidationContext
    ) -> None:
        """Check for resource double-booking."""
        machine_bookings = {}

        for task in tasks:
            if not hasattr(task, "planned_start_time") or not task.planned_start_time:
                continue

            # Check machine conflicts
            if task.assigned_machine_id:
                machine_id = task.assigned_machine_id
                task_window = (task.planned_start_time, task.planned_end_time)

                if machine_id in machine_bookings:
                    for existing_window in machine_bookings[machine_id]:
                        if self._time_windows_overlap(task_window, existing_window):
                            context.add_error(
                                "assigned_machine_id",
                                machine_id,
                                f"Machine {machine_id} is double-booked",
                                "RESOURCE_CONFLICT",
                            )
                    machine_bookings[machine_id].append(task_window)
                else:
                    machine_bookings[machine_id] = [task_window]

        # Similar logic would apply for operator conflicts

    def _validate_precedence_constraints(
        self, tasks: list[Any], context: ValidationContext
    ) -> None:
        """Validate task precedence constraints."""
        # Group tasks by job
        job_tasks = {}
        for task in tasks:
            job_id = task.job_id
            if job_id not in job_tasks:
                job_tasks[job_id] = []
            job_tasks[job_id].append(task)

        # Check precedence within each job
        for job_id, tasks_in_job in job_tasks.items():
            sorted_tasks = sorted(tasks_in_job, key=lambda t: t.sequence_in_job)

            for i in range(1, len(sorted_tasks)):
                current_task = sorted_tasks[i]
                previous_task = sorted_tasks[i - 1]

                if (
                    current_task.planned_start_time
                    and previous_task.planned_end_time
                    and current_task.planned_start_time < previous_task.planned_end_time
                ):
                    context.add_error(
                        "planned_start_time",
                        current_task.planned_start_time,
                        f"Task {current_task.sequence_in_job} cannot start before task {previous_task.sequence_in_job} ends",
                        "PRECEDENCE_VIOLATION",
                    )

    def _validate_capacity_constraints(
        self, tasks: list[Any], context: ValidationContext
    ) -> None:
        """Validate resource capacity constraints."""
        # This would implement work-in-progress limits, machine capacity, etc.
        # Implementation depends on specific business rules
        pass

    def _time_windows_overlap(self, window1: tuple, window2: tuple) -> bool:
        """Check if two time windows overlap."""
        start1, end1 = window1
        start2, end2 = window2

        if not all([start1, end1, start2, end2]):
            return False

        return start1 < end2 and end1 > start2


class RepositoryValidationDecorator:
    """Decorator for adding validation to repository methods."""

    def __init__(self, validation_mixin: type[ValidationMixin]):
        self.validation_mixin = validation_mixin

    def validate_save(self, func):
        """Decorator for save operations."""

        def wrapper(self, entity: Any, *args, **kwargs):
            # Create validation context
            context = ValidationContext()

            # Run validation if mixin is available
            if hasattr(self, "_validate_repository_constraints"):
                context = self.validate_before_save(entity, context)

            # Raise errors if validation failed
            if context.has_errors:
                if len(context.errors) == 1:
                    raise context.errors[0]
                else:
                    raise MultipleValidationError(context.errors)

            # Proceed with save if validation passed
            return func(self, entity, *args, **kwargs)

        return wrapper

    def validate_update(self, func):
        """Decorator for update operations."""

        def wrapper(self, entity: Any, *args, **kwargs):
            # Similar to save but may have different validation rules
            context = ValidationContext()

            if hasattr(self, "_validate_repository_constraints"):
                context = self.validate_before_save(entity, context)

            if context.has_errors:
                if len(context.errors) == 1:
                    raise context.errors[0]
                else:
                    raise MultipleValidationError(context.errors)

            return func(self, entity, *args, **kwargs)

        return wrapper


# Utility functions for repository validation
def validate_foreign_key_reference(
    repository_method: callable, entity_id: UUID, entity_type: str
) -> bool:
    """
    Validate that a foreign key reference exists.

    Args:
        repository_method: Method to check existence (e.g., repo.exists)
        entity_id: ID to validate
        entity_type: Type of entity for error messages

    Returns:
        True if reference is valid

    Raises:
        ValidationError: If reference is invalid
    """
    try:
        if not repository_method(entity_id):
            raise ValidationError(
                f"{entity_type.lower()}_id",
                entity_id,
                f"{entity_type} {entity_id} does not exist",
                "INVALID_REFERENCE",
            )
        return True
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(
            f"{entity_type.lower()}_id",
            entity_id,
            f"Failed to validate {entity_type} reference: {str(e)}",
            "REFERENCE_CHECK_FAILED",
        )


def validate_unique_constraint(
    repository_method: callable,
    field_value: Any,
    field_name: str,
    exclude_id: UUID = None,
) -> bool:
    """
    Validate uniqueness constraint.

    Args:
        repository_method: Method to check for existing records
        field_value: Value to check for uniqueness
        field_name: Name of the field
        exclude_id: ID to exclude from uniqueness check (for updates)

    Returns:
        True if constraint is satisfied

    Raises:
        ValidationError: If uniqueness is violated
    """
    try:
        existing_records = repository_method(field_value)

        if exclude_id:
            existing_records = [r for r in existing_records if r.id != exclude_id]

        if existing_records:
            raise ValidationError(
                field_name,
                field_value,
                f"{field_name} '{field_value}' already exists",
                "DUPLICATE_VALUE",
            )
        return True
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(
            field_name,
            field_value,
            f"Failed to validate uniqueness: {str(e)}",
            "UNIQUENESS_CHECK_FAILED",
        )
