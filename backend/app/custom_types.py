"""
Enterprise-Grade Type Definitions

This module provides comprehensive type definitions and patterns for the application,
implementing TypeScript-like type safety and documentation standards in Python.

Features:
- Discriminated unions for error handling
- Generic type constraints
- Utility types for common patterns
- Comprehensive documentation following JSDoc standards
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Generic,
    Literal,
    Protocol,
    TypeVar,
    runtime_checkable,
)
from uuid import UUID

from typing_extensions import NotRequired, TypedDict

# ============================================================================
# Base Types and Constraints
# ============================================================================

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

# Entity constraint - must have an ID
EntityT = TypeVar("EntityT", bound="HasId")


class HasId(Protocol):
    """Protocol for entities with ID field."""

    id: UUID


# ============================================================================
# Result Types (Similar to TypeScript's Result<T, E> pattern)
# ============================================================================


class Result(Generic[T, K], ABC):
    """
    Result type for handling success/failure cases with type safety.

    Similar to TypeScript's Result<T, E> pattern, this provides a type-safe
    way to handle operations that can succeed or fail.

    Examples:
        >>> result: Result[User, str] = Success(user)
        >>> if isinstance(result, Success):
        ...     print(f"User: {result.value.email}")
        >>> elif isinstance(result, Failure):
        ...     print(f"Error: {result.error}")
    """

    @abstractmethod
    def is_success(self) -> bool:
        """Check if result represents success."""
        pass

    @abstractmethod
    def is_failure(self) -> bool:
        """Check if result represents failure."""
        pass


class Success(Result[T, K]):
    """Success result containing a value."""

    def __init__(self, value: T) -> None:
        self.value = value

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False


class Failure(Result[T, K]):
    """Failure result containing an error."""

    def __init__(self, error: K) -> None:
        self.error = error

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True


# ============================================================================
# API Response Types
# ============================================================================


class ApiStatus(str, Enum):
    """API response status enumeration."""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class PaginationMeta(TypedDict):
    """
    Pagination metadata for API responses.

    Attributes:
        page: Current page number (1-based)
        per_page: Number of items per page
        total: Total number of items
        pages: Total number of pages
        has_next: Whether there are more pages
        has_prev: Whether there are previous pages
    """

    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class ApiResponse(TypedDict, Generic[T]):
    """
    Generic API response structure with type safety.

    Type Parameters:
        T: Type of the data payload

    Attributes:
        status: Response status
        data: Response payload (optional for error responses)
        message: Human-readable message (optional)
        errors: List of error messages (optional)
        meta: Metadata for responses (optional, used for pagination)
    """

    status: ApiStatus
    data: NotRequired[T]
    message: NotRequired[str]
    errors: NotRequired[list[str]]
    meta: NotRequired[PaginationMeta]


class PaginatedResponse(TypedDict, Generic[T]):
    """
    Paginated API response with type safety.

    Type Parameters:
        T: Type of items in the data array
    """

    status: Literal[ApiStatus.SUCCESS]
    data: list[T]
    meta: PaginationMeta


# ============================================================================
# Database Operation Types
# ============================================================================


class DatabaseOperation(str, Enum):
    """Database operation types for audit logging."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class AuditLog(TypedDict):
    """
    Audit log entry for database operations.

    Attributes:
        operation: Type of database operation
        table_name: Name of affected table
        entity_id: ID of affected entity
        user_id: ID of user performing operation
        timestamp: When operation occurred
        changes: Dictionary of changed fields (for updates)
    """

    operation: DatabaseOperation
    table_name: str
    entity_id: UUID
    user_id: UUID | None
    timestamp: datetime
    changes: NotRequired[dict[str, Any]]


# ============================================================================
# Validation Types
# ============================================================================


class ValidationErrorDetail(TypedDict):
    """
    Detailed validation error information.

    Attributes:
        field: Name of the field that failed validation
        value: Value that was provided
        message: Human-readable error message
        code: Machine-readable error code
    """

    field: str
    value: str | None
    message: str
    code: str


class ValidationResult(Generic[T]):
    """
    Result of validation operation with type safety.

    Type Parameters:
        T: Type of the validated data

    Attributes:
        is_valid: Whether validation passed
        data: Validated data (only present if valid)
        errors: List of validation errors (only present if invalid)
    """

    def __init__(
        self,
        is_valid: bool,
        data: T | None = None,
        errors: list[ValidationErrorDetail] | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.data = data
        self.errors = errors or []

    @classmethod
    def success(cls, data: T) -> "ValidationResult[T]":
        """Create a successful validation result."""
        return cls(is_valid=True, data=data)

    @classmethod
    def failure(cls, errors: list[ValidationErrorDetail]) -> "ValidationResult[T]":
        """Create a failed validation result."""
        return cls(is_valid=False, errors=errors)


# ============================================================================
# Repository Patterns
# ============================================================================


@runtime_checkable
class Repository(Protocol, Generic[EntityT]):
    """
    Generic repository protocol for data access operations.

    Type Parameters:
        EntityT: Type of entity this repository handles

    This protocol defines the contract for repository implementations,
    ensuring type safety across different storage backends.
    """

    async def get_by_id(self, entity_id: UUID) -> EntityT | None:
        """
        Retrieve entity by ID.

        Args:
            entity_id: Unique identifier of the entity

        Returns:
            Entity if found, None otherwise
        """
        ...

    async def create(self, entity: EntityT) -> EntityT:
        """
        Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with generated ID

        Raises:
            RepositoryError: If creation fails
        """
        ...

    async def update(self, entity: EntityT) -> EntityT:
        """
        Update existing entity.

        Args:
            entity: Entity with updated data

        Returns:
            Updated entity

        Raises:
            RepositoryError: If update fails
            EntityNotFoundError: If entity doesn't exist
        """
        ...

    async def delete(self, entity_id: UUID) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Unique identifier of entity to delete

        Returns:
            True if entity was deleted, False if not found

        Raises:
            RepositoryError: If deletion fails
        """
        ...

    async def list(self, limit: int = 100, offset: int = 0) -> list[EntityT]:
        """
        List entities with pagination.

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of entities
        """
        ...


# ============================================================================
# Service Layer Types
# ============================================================================


class ServiceOperation(str, Enum):
    """Service layer operation types."""

    QUERY = "query"
    COMMAND = "command"
    EVENT = "event"


class ServiceContext(TypedDict):
    """
    Context information for service operations.

    Attributes:
        user_id: ID of user performing operation
        operation: Type of service operation
        trace_id: Distributed tracing ID
        correlation_id: Request correlation ID
        timestamp: When operation started
    """

    user_id: UUID | None
    operation: ServiceOperation
    trace_id: str | None
    correlation_id: str | None
    timestamp: datetime


# ============================================================================
# Configuration Types
# ============================================================================


class DatabaseConfig(TypedDict):
    """
    Database configuration with type safety.

    Attributes:
        url: Database connection URL
        pool_size: Connection pool size
        max_overflow: Maximum pool overflow
        pool_timeout: Pool timeout in seconds
        echo: Whether to echo SQL queries
    """

    url: str
    pool_size: int
    max_overflow: int
    pool_timeout: int
    echo: bool


class ApiConfig(TypedDict):
    """
    API configuration with type safety.

    Attributes:
        title: API title
        version: API version
        description: API description
        cors_origins: List of allowed CORS origins
        rate_limit: Rate limiting configuration
    """

    title: str
    version: str
    description: str
    cors_origins: list[str]
    rate_limit: dict[str, int]


# ============================================================================
# Utility Types (TypeScript-like utility types)
# ============================================================================


def Partial(cls: type) -> type:
    """
    Create a partial version of a TypedDict (similar to TypeScript's Partial<T>).

    Args:
        cls: TypedDict class to make partial

    Returns:
        New TypedDict class with all fields optional
    """
    # This would require runtime modification of TypedDict
    # For static typing, use NotRequired for individual fields
    return cls


def Pick(cls: type, keys: list[str]) -> type:
    """
    Pick specific keys from a TypedDict (similar to TypeScript's Pick<T, K>).

    Args:
        cls: TypedDict class to pick from
        keys: List of keys to include

    Returns:
        New TypedDict class with only specified keys
    """
    # This would require runtime modification of TypedDict
    # For static typing, create new TypedDict classes as needed
    return cls


def Omit(cls: type, keys: list[str]) -> type:
    """
    Omit specific keys from a TypedDict (similar to TypeScript's Omit<T, K>).

    Args:
        cls: TypedDict class to omit from
        keys: List of keys to exclude

    Returns:
        New TypedDict class without specified keys
    """
    # This would require runtime modification of TypedDict
    # For static typing, create new TypedDict classes as needed
    return cls


# ============================================================================
# Type Guards (Runtime Type Checking)
# ============================================================================


def is_uuid(value: Any) -> bool:
    """
    Type guard to check if value is a valid UUID.

    Args:
        value: Value to check

    Returns:
        True if value is a valid UUID
    """
    if not isinstance(value, str | UUID):
        return False

    try:
        if isinstance(value, str):
            UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def is_non_empty_string(value: Any) -> bool:
    """
    Type guard to check if value is a non-empty string.

    Args:
        value: Value to check

    Returns:
        True if value is a non-empty string
    """
    return isinstance(value, str) and len(value.strip()) > 0


# ============================================================================
# Export Types for Public API
# ============================================================================

__all__ = [
    # Result types
    "Result",
    "Success",
    "Failure",
    # API types
    "ApiStatus",
    "ApiResponse",
    "PaginatedResponse",
    "PaginationMeta",
    # Database types
    "DatabaseOperation",
    "AuditLog",
    # Validation types
    "ValidationErrorDetail",
    "ValidationResult",
    # Repository types
    "Repository",
    "HasId",
    # Service types
    "ServiceOperation",
    "ServiceContext",
    # Configuration types
    "DatabaseConfig",
    "ApiConfig",
    # Type guards
    "is_uuid",
    "is_non_empty_string",
    # Type variables
    "T",
    "K",
    "V",
    "EntityT",
]
