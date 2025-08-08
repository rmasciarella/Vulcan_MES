"""
Type Testing Utilities for Enterprise-Grade Type Safety

This module provides utilities for testing type safety at runtime,
similar to TypeScript's type testing patterns. These utilities help
ensure that our type definitions work correctly in practice.

Features:
- Runtime type validation
- Mock data generation with proper types
- Type assertion helpers for tests
- Performance-optimized type checking
"""

from dataclasses import fields, is_dataclass
from typing import (
    Any,
    TypeVar,
    Union,
    get_args,
    get_origin,
)
from uuid import UUID

from ..types import (
    ApiResponse,
    ApiStatus,
    Failure,
    PaginationMeta,
    Success,
    ValidationErrorDetail,
)

T = TypeVar("T")


# ============================================================================
# Type Assertion Helpers
# ============================================================================


class TypeAssertionError(Exception):
    """Raised when type assertion fails."""

    def __init__(self, expected: type, actual: type, value: Any) -> None:
        self.expected = expected
        self.actual = actual
        self.value = value
        super().__init__(
            f"Expected {expected.__name__}, got {actual.__name__}: {value}"
        )


def assert_type(value: Any, expected_type: type[T]) -> T:
    """
    Assert that a value matches the expected type.

    Args:
        value: Value to check
        expected_type: Expected type

    Returns:
        The value, typed as expected_type

    Raises:
        TypeAssertionError: If type doesn't match

    Examples:
        >>> user = assert_type(data, User)
        >>> count = assert_type(result["count"], int)
    """
    if not isinstance(value, expected_type):
        raise TypeAssertionError(expected_type, type(value), value)
    return value


def assert_optional_type(value: Any, expected_type: type[T]) -> T | None:
    """
    Assert that a value is either None or matches the expected type.

    Args:
        value: Value to check
        expected_type: Expected type (excluding None)

    Returns:
        The value, typed as Optional[expected_type]

    Raises:
        TypeAssertionError: If type doesn't match and isn't None
    """
    if value is None:
        return None
    if not isinstance(value, expected_type):
        raise TypeAssertionError(expected_type, type(value), value)
    return value


def assert_list_type(value: Any, item_type: type[T]) -> list[T]:
    """
    Assert that a value is a list containing items of the expected type.

    Args:
        value: Value to check
        item_type: Expected type of list items

    Returns:
        The value, typed as List[item_type]

    Raises:
        TypeAssertionError: If not a list or items don't match type
    """
    if not isinstance(value, list):
        raise TypeAssertionError(list, type(value), value)

    for i, item in enumerate(value):
        if not isinstance(item, item_type):
            raise TypeAssertionError(item_type, type(item), f"Item {i}: {item}")

    return value


def assert_dict_type(value: Any, key_type: type[K], value_type: type[V]) -> dict[K, V]:
    """
    Assert that a value is a dict with keys and values of expected types.

    Args:
        value: Value to check
        key_type: Expected type of dictionary keys
        value_type: Expected type of dictionary values

    Returns:
        The value, typed as Dict[key_type, value_type]

    Raises:
        TypeAssertionError: If not a dict or items don't match types
    """
    if not isinstance(value, dict):
        raise TypeAssertionError(dict, type(value), value)

    for k, v in value.items():
        if not isinstance(k, key_type):
            raise TypeAssertionError(key_type, type(k), f"Key: {k}")
        if not isinstance(v, value_type):
            raise TypeAssertionError(value_type, type(v), f"Value for {k}: {v}")

    return value


# ============================================================================
# Runtime Type Validation
# ============================================================================


def validate_type_at_runtime(value: Any, expected_type: type) -> bool:
    """
    Validate that a value matches a type annotation at runtime.

    This function handles complex type annotations including:
    - Union types
    - Optional types
    - Generic types
    - Literal types

    Args:
        value: Value to validate
        expected_type: Type annotation to validate against

    Returns:
        True if value matches the type, False otherwise

    Examples:
        >>> validate_type_at_runtime("hello", str)  # True
        >>> validate_type_at_runtime(42, Union[str, int])  # True
        >>> validate_type_at_runtime(None, Optional[str])  # True
    """
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    # Handle Union types (including Optional)
    if origin is Union:
        return any(validate_type_at_runtime(value, arg) for arg in args)

    # Handle List types
    if origin is list:
        if not isinstance(value, list):
            return False
        if args:  # List[SomeType]
            return all(validate_type_at_runtime(item, args[0]) for item in value)
        return True  # Plain list

    # Handle Dict types
    if origin is dict:
        if not isinstance(value, dict):
            return False
        if len(args) == 2:  # Dict[KeyType, ValueType]
            key_type, value_type = args
            return all(
                validate_type_at_runtime(k, key_type) for k in value.keys()
            ) and all(validate_type_at_runtime(v, value_type) for v in value.values())
        return True  # Plain dict

    # Handle basic types
    if origin is None:
        return isinstance(value, expected_type)

    # Handle other generic types
    if hasattr(expected_type, "__origin__"):
        return isinstance(value, origin)

    return isinstance(value, expected_type)


def validate_dataclass_fields(obj: Any, expected_type: type[T]) -> list[str]:
    """
    Validate all fields of a dataclass instance.

    Args:
        obj: Dataclass instance to validate
        expected_type: Expected dataclass type

    Returns:
        List of validation error messages (empty if valid)

    Examples:
        >>> @dataclass
        ... class User:
        ...     name: str
        ...     age: int
        >>> user = User(name="John", age="not_a_number")
        >>> errors = validate_dataclass_fields(user, User)
        >>> assert "age" in errors[0]
    """
    if not is_dataclass(obj):
        return [f"Expected dataclass, got {type(obj).__name__}"]

    if not isinstance(obj, expected_type):
        return [f"Expected {expected_type.__name__}, got {type(obj).__name__}"]

    errors = []
    for field in fields(obj):
        value = getattr(obj, field.name)
        if not validate_type_at_runtime(value, field.type):
            errors.append(
                f"Field '{field.name}' expected {field.type}, got {type(value).__name__}: {value}"
            )

    return errors


# ============================================================================
# Mock Data Generation
# ============================================================================


class TypedMockGenerator:
    """
    Generate mock data with proper types for testing.

    This class provides type-safe mock data generation that respects
    the type annotations and produces realistic test data.
    """

    def __init__(self) -> None:
        self._uuid_counter = 0
        self._string_counter = 0

    def generate_uuid(self) -> UUID:
        """Generate a deterministic UUID for testing."""
        self._uuid_counter += 1
        # Create deterministic UUID for reproducible tests
        return UUID(f"00000000-0000-0000-0000-{self._uuid_counter:012d}")

    def generate_string(self, prefix: str = "test") -> str:
        """Generate a deterministic string for testing."""
        self._string_counter += 1
        return f"{prefix}_{self._string_counter}"

    def generate_api_response(
        self, data: T, status: ApiStatus = ApiStatus.SUCCESS
    ) -> ApiResponse[T]:
        """
        Generate a properly typed API response.

        Args:
            data: Response data
            status: Response status

        Returns:
            Typed API response
        """
        response: ApiResponse[T] = {"status": status}
        if data is not None:
            response["data"] = data
        return response

    def generate_pagination_meta(
        self, page: int = 1, per_page: int = 10, total: int = 100
    ) -> PaginationMeta:
        """
        Generate pagination metadata.

        Args:
            page: Current page number
            per_page: Items per page
            total: Total items

        Returns:
            Pagination metadata
        """
        pages = (total + per_page - 1) // per_page
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
        }

    def generate_validation_error(
        self,
        field: str = "test_field",
        value: str = "invalid_value",
        message: str = "Validation failed",
    ) -> ValidationErrorDetail:
        """
        Generate a validation error detail.

        Args:
            field: Field name that failed validation
            value: Invalid value
            message: Error message

        Returns:
            Validation error detail
        """
        return {
            "field": field,
            "value": value,
            "message": message,
            "code": f"{field.upper()}_INVALID",
        }

    def generate_success_result(self, data: T) -> Success[T, str]:
        """Generate a Success result."""
        return Success(data)

    def generate_failure_result(self, error: str = "Test error") -> Failure[Any, str]:
        """Generate a Failure result."""
        return Failure(error)


# ============================================================================
# Performance-Optimized Type Checking
# ============================================================================


class TypeChecker:
    """
    High-performance type checking with caching.

    This class provides optimized type checking for performance-critical
    code paths where type validation is needed frequently.
    """

    def __init__(self) -> None:
        self._cache: dict[str, bool] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def check_type_cached(self, value: Any, expected_type: type) -> bool:
        """
        Check type with caching for better performance.

        Args:
            value: Value to check
            expected_type: Expected type

        Returns:
            True if type matches
        """
        # Create cache key from value type and expected type
        cache_key = f"{type(value).__name__}::{expected_type.__name__}"

        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1
        result = isinstance(value, expected_type)
        self._cache[cache_key] = result
        return result

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0

        return {
            "cache_size": len(self._cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
        }

    def clear_cache(self) -> None:
        """Clear the type checking cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


# ============================================================================
# Test Helpers for Type Safety
# ============================================================================


def create_type_safe_test_fixture(fixture_type: type[T], **kwargs: Any) -> T:
    """
    Create a test fixture with proper typing.

    Args:
        fixture_type: Type of fixture to create
        **kwargs: Fixture data

    Returns:
        Properly typed test fixture

    Examples:
        >>> user = create_type_safe_test_fixture(User, name="John", age=30)
        >>> assert isinstance(user, User)
    """
    if is_dataclass(fixture_type):
        # For dataclasses, use constructor
        return fixture_type(**kwargs)

    # For other types, try to construct with kwargs
    try:
        return fixture_type(**kwargs)
    except TypeError:
        # If constructor doesn't accept kwargs, try without
        return fixture_type()


def assert_api_response_structure(
    response: dict[str, Any], expected_data_type: type | None = None
) -> None:
    """
    Assert that a dictionary has the correct API response structure.

    Args:
        response: Response dictionary to check
        expected_data_type: Expected type of data field

    Raises:
        TypeAssertionError: If structure is invalid
    """
    # Check required fields
    if "status" not in response:
        raise TypeAssertionError(dict, type(response), "Missing 'status' field")

    if not isinstance(response["status"], str):
        raise TypeAssertionError(
            str, type(response["status"]), f"Invalid status type: {response['status']}"
        )

    # Validate status value
    try:
        ApiStatus(response["status"])
    except ValueError:
        raise TypeAssertionError(
            ApiStatus, str, f"Invalid status value: {response['status']}"
        )

    # Check data field if expected
    if expected_data_type and "data" in response:
        if not isinstance(response["data"], expected_data_type):
            raise TypeAssertionError(
                expected_data_type, type(response["data"]), response["data"]
            )


# ============================================================================
# Export for Public API
# ============================================================================

# Global type checker instance for reuse
global_type_checker = TypeChecker()

# Global mock generator instance for reuse
global_mock_generator = TypedMockGenerator()

__all__ = [
    # Type assertions
    "TypeAssertionError",
    "assert_type",
    "assert_optional_type",
    "assert_list_type",
    "assert_dict_type",
    # Runtime validation
    "validate_type_at_runtime",
    "validate_dataclass_fields",
    # Mock generation
    "TypedMockGenerator",
    "global_mock_generator",
    # Performance optimization
    "TypeChecker",
    "global_type_checker",
    # Test helpers
    "create_type_safe_test_fixture",
    "assert_api_response_structure",
]
