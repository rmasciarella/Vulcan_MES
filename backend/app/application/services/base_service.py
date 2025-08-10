"""
Base application service providing common functionality.

This module provides a base class for all application services,
including common validation, error handling, and transaction management.
"""

from abc import ABC
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.shared.exceptions import (
    BusinessRuleViolation,
    EntityNotFoundError,
    ValidationError,
)
from app.infrastructure.database.repositories.base import DatabaseError


class ApplicationServiceBase(ABC):
    """
    Base class for application services.

    Provides common functionality for validation, error handling,
    and transaction coordination across all application services.
    """

    def __init__(self, unit_of_work_factory):
        """
        Initialize the application service.

        Args:
            unit_of_work_factory: Factory for creating unit of work instances
        """
        self._uow_factory = unit_of_work_factory

    def validate_request(self, request: BaseModel) -> None:
        """
        Validate a request DTO.

        Args:
            request: Request DTO to validate

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Pydantic models automatically validate on creation
            # This method can be extended for additional validation
            if hasattr(request, "dict"):
                request.dict()  # Trigger validation
        except Exception as e:
            raise ValidationError(f"Request validation failed: {str(e)}")

    def validate_non_empty_string(self, value: str | None, field_name: str) -> None:
        """
        Validate that a string field is not empty.

        Args:
            value: String value to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If string is None or empty
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty")

    def validate_positive_number(self, value: float | None, field_name: str) -> None:
        """
        Validate that a number is positive.

        Args:
            value: Number to validate
            field_name: Name of the field for error messages

        Raises:
            ValidationError: If number is not positive
        """
        if value is None or value <= 0:
            raise ValidationError(f"{field_name} must be a positive number")

    def validate_uuid(self, value: Any, field_name: str) -> UUID:
        """
        Validate and convert a value to UUID.

        Args:
            value: Value to convert to UUID
            field_name: Name of the field for error messages

        Returns:
            UUID object

        Raises:
            ValidationError: If value is not a valid UUID
        """
        if isinstance(value, UUID):
            return value

        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a valid UUID")

    def validation_error(self, message: str) -> ValidationError:
        """
        Create a validation error.

        Args:
            message: Error message

        Returns:
            ValidationError instance
        """
        return ValidationError(message)

    def business_rule_violation(self, message: str) -> BusinessRuleViolation:
        """
        Create a business rule violation error.

        Args:
            message: Error message

        Returns:
            BusinessRuleViolation instance
        """
        return BusinessRuleViolation(message)

    def entity_not_found_error(self, message: str) -> EntityNotFoundError:
        """
        Create an entity not found error.

        Args:
            message: Error message

        Returns:
            EntityNotFoundError instance
        """
        return EntityNotFoundError(message)

    def database_error(self, message: str) -> DatabaseError:
        """
        Create a database error.

        Args:
            message: Error message

        Returns:
            DatabaseError instance
        """
        return DatabaseError(message)
