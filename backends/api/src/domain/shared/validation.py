"""
Enhanced validation decorators, validators, and utilities for domain entities.

Provides comprehensive validation capabilities including:
- Custom field validators with business rules
- Data sanitization utilities
- Validation decorators for complex rules
- Clear error messages for validation failures
"""

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from functools import wraps
from typing import Any

try:
    from pydantic import Field, validator
    from pydantic.validators import str_validator
except ImportError:
    # Fallback for when pydantic is not available
    def validator(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def Field(*args, **kwargs):
        return None

    str_validator = str


class ValidationError(Exception):
    """Enhanced validation error with detailed context."""

    def __init__(
        self, field_name: str, value: Any, message: str, error_code: str = None
    ):
        self.field_name = field_name
        self.value = value
        self.message = message
        self.error_code = error_code or "VALIDATION_ERROR"
        super().__init__(f"{field_name}: {message}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "field": self.field_name,
            "value": str(self.value),
            "message": self.message,
            "error_code": self.error_code,
        }


class ValidationContext:
    """Context for validation operations."""

    def __init__(self):
        self.errors: list[ValidationError] = []
        self.warnings: list[str] = []

    def add_error(
        self, field_name: str, value: Any, message: str, error_code: str = None
    ):
        """Add validation error."""
        error = ValidationError(field_name, value, message, error_code)
        self.errors.append(error)

    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)

    @property
    def has_errors(self) -> bool:
        """Check if context has validation errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if context has warnings."""
        return len(self.warnings) > 0


# Input Sanitization Utilities
class DataSanitizer:
    """Utilities for cleaning and sanitizing input data."""

    @staticmethod
    def sanitize_string(
        value: str, max_length: int = None, strip: bool = True, allow_empty: bool = True
    ) -> str:
        """
        Sanitize string input.

        Args:
            value: Input string
            max_length: Maximum allowed length
            strip: Whether to strip whitespace
            allow_empty: Whether to allow empty strings

        Returns:
            Sanitized string

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError(
                "input", value, "Input must be a string", "INVALID_TYPE"
            )

        if strip:
            value = value.strip()

        if not allow_empty and not value:
            raise ValidationError(
                "input", value, "Value cannot be empty", "EMPTY_VALUE"
            )

        if max_length and len(value) > max_length:
            raise ValidationError(
                "input",
                value,
                f"Value exceeds maximum length of {max_length}",
                "TOO_LONG",
            )

        # Remove null bytes and control characters
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]", "", value)

        return value

    @staticmethod
    def sanitize_code(value: str, pattern: str = r"^[A-Z0-9_-]+$") -> str:
        """
        Sanitize code/identifier fields.

        Args:
            value: Input code
            pattern: Regex pattern for validation

        Returns:
            Sanitized code

        Raises:
            ValidationError: If validation fails
        """
        value = DataSanitizer.sanitize_string(value, strip=True, allow_empty=False)
        value = value.upper()

        if not re.match(pattern, value):
            raise ValidationError(
                "code", value, f"Code must match pattern: {pattern}", "INVALID_FORMAT"
            )

        return value

    @staticmethod
    def sanitize_email(value: str) -> str:
        """
        Sanitize email address.

        Args:
            value: Email address

        Returns:
            Sanitized email

        Raises:
            ValidationError: If validation fails
        """
        value = DataSanitizer.sanitize_string(value, strip=True, allow_empty=False)
        value = value.lower()

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, value):
            raise ValidationError(
                "email", value, "Invalid email format", "INVALID_EMAIL"
            )

        return value

    @staticmethod
    def sanitize_phone(value: str) -> str:
        """
        Sanitize phone number.

        Args:
            value: Phone number

        Returns:
            Sanitized phone number

        Raises:
            ValidationError: If validation fails
        """
        value = DataSanitizer.sanitize_string(value, strip=True, allow_empty=False)

        # Remove all non-digits
        digits_only = re.sub(r"[^\d]", "", value)

        # US phone number validation (10 or 11 digits)
        if len(digits_only) not in [10, 11]:
            raise ValidationError(
                "phone", value, "Phone number must be 10 or 11 digits", "INVALID_PHONE"
            )

        return digits_only


# Business Rule Validators
class BusinessRuleValidators:
    """Collection of business rule validation functions."""

    @staticmethod
    def validate_future_date(field_name: str, value: datetime) -> None:
        """Validate that date is in the future."""
        if value <= datetime.utcnow():
            raise ValidationError(
                field_name, value, "Date must be in the future", "DATE_NOT_FUTURE"
            )

    @staticmethod
    def validate_date_range(
        start_field: str, start_date: datetime, end_field: str, end_date: datetime
    ) -> None:
        """Validate date range (end after start)."""
        if end_date <= start_date:
            raise ValidationError(
                end_field,
                end_date,
                f"{end_field} must be after {start_field}",
                "INVALID_DATE_RANGE",
            )

    @staticmethod
    def validate_positive_number(field_name: str, value: int | float | Decimal) -> None:
        """Validate that number is positive."""
        if value <= 0:
            raise ValidationError(
                field_name, value, "Value must be positive", "NOT_POSITIVE"
            )

    @staticmethod
    def validate_range(
        field_name: str,
        value: int | float | Decimal,
        min_val: int | float | Decimal = None,
        max_val: int | float | Decimal = None,
    ) -> None:
        """Validate that value is within specified range."""
        if min_val is not None and value < min_val:
            raise ValidationError(
                field_name, value, f"Value must be at least {min_val}", "BELOW_MINIMUM"
            )

        if max_val is not None and value > max_val:
            raise ValidationError(
                field_name, value, f"Value must be at most {max_val}", "ABOVE_MAXIMUM"
            )

    @staticmethod
    def validate_unique_items(field_name: str, items: list[Any]) -> None:
        """Validate that all items in list are unique."""
        if len(items) != len(set(items)):
            raise ValidationError(
                field_name, items, "All items must be unique", "DUPLICATE_ITEMS"
            )

    @staticmethod
    def validate_required_field(field_name: str, value: Any) -> None:
        """Validate that required field is not empty."""
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(
                field_name, value, f"{field_name} is required", "REQUIRED_FIELD"
            )


# Domain-Specific Validators
class SchedulingValidators:
    """Validators specific to scheduling domain."""

    @staticmethod
    def validate_job_number_format(value: str) -> str:
        """
        Validate job number format (letters/numbers/hyphens/underscores).

        Args:
            value: Job number string

        Returns:
            Sanitized job number

        Raises:
            ValidationError: If format is invalid
        """
        try:
            value = DataSanitizer.sanitize_code(value, r"^[A-Z0-9_-]+$")
        except ValidationError:
            raise ValidationError(
                "job_number",
                value,
                "Job number must contain only letters, numbers, hyphens, and underscores",
                "INVALID_JOB_NUMBER_FORMAT",
            )

        if len(value) < 3:
            raise ValidationError(
                "job_number",
                value,
                "Job number must be at least 3 characters",
                "JOB_NUMBER_TOO_SHORT",
            )

        if len(value) > 50:
            raise ValidationError(
                "job_number",
                value,
                "Job number must be at most 50 characters",
                "JOB_NUMBER_TOO_LONG",
            )

        return value

    @staticmethod
    def validate_task_sequence(value: int) -> None:
        """Validate task sequence number (1-100)."""
        BusinessRuleValidators.validate_range("sequence_in_job", value, 1, 100)

    @staticmethod
    def validate_priority_level(value: int) -> None:
        """Validate priority level (1-10)."""
        BusinessRuleValidators.validate_range("priority", value, 1, 10)

    @staticmethod
    def validate_efficiency_factor(value: float | Decimal) -> None:
        """Validate efficiency factor (0.1-2.0)."""
        BusinessRuleValidators.validate_range(
            "efficiency_factor", value, Decimal("0.1"), Decimal("2.0")
        )

    @staticmethod
    def validate_duration_minutes(value: int) -> None:
        """Validate duration in minutes (non-negative)."""
        if value < 0:
            raise ValidationError(
                "duration", value, "Duration cannot be negative", "NEGATIVE_DURATION"
            )

    @staticmethod
    def validate_quantity(value: int) -> None:
        """Validate quantity (positive integer)."""
        if not isinstance(value, int):
            raise ValidationError(
                "quantity",
                value,
                "Quantity must be an integer",
                "INVALID_QUANTITY_TYPE",
            )

        if value < 1:
            raise ValidationError(
                "quantity",
                value,
                "Quantity must be at least 1",
                "INVALID_QUANTITY_VALUE",
            )


# Enhanced Validation Decorators
def validate_business_rules(validation_func: Callable) -> Callable:
    """
    Decorator for adding business rule validation to methods.

    Args:
        validation_func: Function to perform validation

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Run validation before method execution
            validation_func(self, *args, **kwargs)
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def sanitize_input(**field_sanitizers: Callable) -> Callable:
    """
    Decorator to sanitize input fields before validation.

    Args:
        field_sanitizers: Mapping of field names to sanitizer functions

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Sanitize kwargs based on field_sanitizers
            for field_name, sanitizer in field_sanitizers.items():
                if field_name in kwargs:
                    try:
                        kwargs[field_name] = sanitizer(kwargs[field_name])
                    except ValidationError:
                        raise
                    except Exception as e:
                        raise ValidationError(
                            field_name,
                            kwargs[field_name],
                            f"Sanitization failed: {str(e)}",
                            "SANITIZATION_ERROR",
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Validation Context Manager
class ValidationContextManager:
    """Context manager for collecting validation errors."""

    def __init__(self):
        self.context = ValidationContext()

    def __enter__(self) -> ValidationContext:
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context.has_errors:
            # Collect all error messages
            messages = [str(error) for error in self.context.errors]
            raise ValidationError(
                "validation", None, "; ".join(messages), "MULTIPLE_VALIDATION_ERRORS"
            )


# Utility Functions
def validate_entity(
    entity: Any, validation_context: ValidationContext = None
) -> ValidationContext:
    """
    Validate an entity and return validation context.

    Args:
        entity: Entity to validate
        validation_context: Existing context or None to create new

    Returns:
        ValidationContext with any errors/warnings
    """
    if validation_context is None:
        validation_context = ValidationContext()

    try:
        # Call entity's validation method if it exists
        if hasattr(entity, "is_valid") and callable(entity.is_valid):
            if not entity.is_valid():
                validation_context.add_error(
                    "entity",
                    entity,
                    "Entity failed business rule validation",
                    "BUSINESS_RULE_VIOLATION",
                )

        # Run Pydantic validation
        if hasattr(entity, "__pydantic_validate__"):
            entity.validate()

    except ValidationError as e:
        validation_context.add_error(e.field_name, e.value, e.message, e.error_code)
    except Exception as e:
        validation_context.add_error(
            "entity", entity, str(e), "UNEXPECTED_VALIDATION_ERROR"
        )

    return validation_context


def get_validation_summary(validation_context: ValidationContext) -> dict[str, Any]:
    """
    Get a summary of validation results.

    Args:
        validation_context: Context with validation results

    Returns:
        Dictionary with validation summary
    """
    return {
        "is_valid": not validation_context.has_errors,
        "error_count": len(validation_context.errors),
        "warning_count": len(validation_context.warnings),
        "errors": [error.to_dict() for error in validation_context.errors],
        "warnings": validation_context.warnings,
    }
