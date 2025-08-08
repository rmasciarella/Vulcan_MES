"""
Base query service providing common query functionality.

This module provides a base class for all query services,
including common patterns for data access and result processing.
"""

from abc import ABC
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from app.domain.shared.exceptions import ValidationError

T = TypeVar("T")


class BaseQueryService(ABC):
    """
    Base class for query services.

    Provides common functionality for data access, result processing,
    and query optimization across all query services.
    """

    def validate_date_range(
        self, start_date: datetime | None, end_date: datetime | None
    ) -> None:
        """
        Validate date range parameters.

        Args:
            start_date: Start date of range
            end_date: End date of range

        Raises:
            ValidationError: If date range is invalid
        """
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("Start date must be before end date")

            # Validate reasonable range (e.g., not more than 5 years)
            max_range_days = 365 * 5
            if (end_date - start_date).days > max_range_days:
                raise ValidationError(f"Date range cannot exceed {max_range_days} days")

    def validate_pagination(self, limit: int | None, offset: int | None) -> None:
        """
        Validate pagination parameters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Raises:
            ValidationError: If pagination parameters are invalid
        """
        if limit is not None and (limit <= 0 or limit > 10000):
            raise ValidationError("Limit must be between 1 and 10000")

        if offset is not None and offset < 0:
            raise ValidationError("Offset must be non-negative")

    def validate_uuid_list(self, ids: list[Any], field_name: str) -> list[UUID]:
        """
        Validate and convert a list of values to UUIDs.

        Args:
            ids: List of values to convert
            field_name: Name of the field for error messages

        Returns:
            List of UUID objects

        Raises:
            ValidationError: If any value is not a valid UUID
        """
        if not ids:
            return []

        try:
            return [UUID(str(id_val)) for id_val in ids]
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name} contains invalid UUID: {str(e)}")

    def apply_filters(
        self, query, filters: dict[str, Any], model_class: type[T]
    ) -> Any:
        """
        Apply common filters to a query.

        Args:
            query: SQLAlchemy query object
            filters: Dictionary of filters to apply
            model_class: SQLModel class to filter

        Returns:
            Modified query object
        """
        for field_name, value in filters.items():
            if value is not None and hasattr(model_class, field_name):
                field = getattr(model_class, field_name)

                if isinstance(value, list):
                    query = query.where(field.in_(value))
                elif isinstance(value, str) and field_name.endswith("_like"):
                    # Handle LIKE queries
                    actual_field_name = field_name.replace("_like", "")
                    if hasattr(model_class, actual_field_name):
                        actual_field = getattr(model_class, actual_field_name)
                        query = query.where(actual_field.ilike(f"%{value}%"))
                else:
                    query = query.where(field == value)

        return query

    def apply_sorting(
        self, query, sort_by: str | None, sort_order: str | None, model_class: type[T]
    ) -> Any:
        """
        Apply sorting to a query.

        Args:
            query: SQLAlchemy query object
            sort_by: Field name to sort by
            sort_order: Sort order ('asc' or 'desc')
            model_class: SQLModel class being queried

        Returns:
            Modified query object
        """
        if not sort_by:
            return query

        if not hasattr(model_class, sort_by):
            return query

        field = getattr(model_class, sort_by)

        if sort_order and sort_order.lower() == "desc":
            query = query.order_by(field.desc())
        else:
            query = query.order_by(field.asc())

        return query

    def apply_pagination(self, query, limit: int | None, offset: int | None) -> Any:
        """
        Apply pagination to a query.

        Args:
            query: SQLAlchemy query object
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Modified query object
        """
        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query

    def format_currency(self, amount: float, currency: str = "USD") -> str:
        """
        Format a currency amount for display.

        Args:
            amount: Amount to format
            currency: Currency code

        Returns:
            Formatted currency string
        """
        if currency == "USD":
            return f"${amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"

    def format_duration(self, minutes: float) -> str:
        """
        Format duration in minutes to human-readable string.

        Args:
            minutes: Duration in minutes

        Returns:
            Formatted duration string
        """
        if minutes < 60:
            return f"{minutes:.0f} min"
        elif minutes < 1440:  # Less than a day
            hours = minutes / 60
            return f"{hours:.1f} hrs"
        else:
            days = minutes / 1440
            return f"{days:.1f} days"

    def calculate_percentage(self, numerator: float, denominator: float) -> float:
        """
        Calculate percentage with safe division.

        Args:
            numerator: Numerator value
            denominator: Denominator value

        Returns:
            Percentage value (0-100)
        """
        if denominator == 0:
            return 0.0
        return (numerator / denominator) * 100

    def group_by_period(
        self, data: list[dict[str, Any]], date_field: str, period: str
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group data by time period.

        Args:
            data: List of data dictionaries
            date_field: Name of date field to group by
            period: Period to group by ('day', 'week', 'month', 'quarter', 'year')

        Returns:
            Dictionary with period keys and data lists
        """
        groups = {}

        for item in data:
            date_value = item.get(date_field)
            if not isinstance(date_value, datetime):
                continue

            if period == "day":
                key = date_value.strftime("%Y-%m-%d")
            elif period == "week":
                key = date_value.strftime("%Y-W%U")
            elif period == "month":
                key = date_value.strftime("%Y-%m")
            elif period == "quarter":
                quarter = (date_value.month - 1) // 3 + 1
                key = f"{date_value.year}-Q{quarter}"
            elif period == "year":
                key = date_value.strftime("%Y")
            else:
                key = date_value.strftime("%Y-%m-%d")

            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        return groups
