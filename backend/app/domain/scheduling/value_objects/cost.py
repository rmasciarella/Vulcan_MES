"""
Cost Value Object

Represents a monetary cost with currency and amount.
Used for operator rates, task costs, and schedule cost calculations.
"""


class Cost:
    """
    A cost value object representing a monetary amount with currency.

    Provides operations for cost calculations while maintaining
    currency consistency.
    """

    def __init__(self, amount: float, currency: str = "USD") -> None:
        """
        Initialize a Cost.

        Args:
            amount: Cost amount (can be negative for credits)
            currency: Currency code (e.g., 'USD', 'EUR')

        Raises:
            ValueError: If currency is empty
        """
        if not currency.strip():
            raise ValueError("Currency cannot be empty")

        self._amount = float(amount)
        self._currency = currency.strip().upper()

    @classmethod
    def zero(cls, currency: str = "USD") -> "Cost":
        """
        Create a zero cost.

        Args:
            currency: Currency code

        Returns:
            Zero cost in specified currency
        """
        return cls(0.0, currency)

    @classmethod
    def from_hourly_rate(
        cls, hourly_rate: float, hours: float, currency: str = "USD"
    ) -> "Cost":
        """
        Create cost from hourly rate and hours.

        Args:
            hourly_rate: Cost per hour
            hours: Number of hours
            currency: Currency code

        Returns:
            Total cost
        """
        return cls(hourly_rate * hours, currency)

    @classmethod
    def from_daily_rate(
        cls, daily_rate: float, days: float, currency: str = "USD"
    ) -> "Cost":
        """
        Create cost from daily rate and days.

        Args:
            daily_rate: Cost per day
            days: Number of days
            currency: Currency code

        Returns:
            Total cost
        """
        return cls(daily_rate * days, currency)

    @property
    def amount(self) -> float:
        """Get cost amount."""
        return self._amount

    @property
    def currency(self) -> str:
        """Get currency code."""
        return self._currency

    @property
    def is_zero(self) -> bool:
        """Check if cost is zero."""
        return abs(self._amount) < 1e-10

    @property
    def is_positive(self) -> bool:
        """Check if cost is positive."""
        return self._amount > 1e-10

    @property
    def is_negative(self) -> bool:
        """Check if cost is negative."""
        return self._amount < -1e-10

    def abs(self) -> "Cost":
        """
        Get absolute value of cost.

        Returns:
            New Cost with absolute amount
        """
        return Cost(abs(self._amount), self._currency)

    def round_to_cents(self) -> "Cost":
        """
        Round cost to nearest cent.

        Returns:
            New Cost rounded to 2 decimal places
        """
        return Cost(round(self._amount, 2), self._currency)

    def per_hour(self, hours: float) -> "Cost":
        """
        Calculate cost per hour.

        Args:
            hours: Number of hours

        Returns:
            Cost per hour

        Raises:
            ZeroDivisionError: If hours is zero
        """
        if hours == 0:
            raise ZeroDivisionError("Cannot divide by zero hours")
        return Cost(self._amount / hours, self._currency)

    def per_unit(self, units: float) -> "Cost":
        """
        Calculate cost per unit.

        Args:
            units: Number of units

        Returns:
            Cost per unit

        Raises:
            ZeroDivisionError: If units is zero
        """
        if units == 0:
            raise ZeroDivisionError("Cannot divide by zero units")
        return Cost(self._amount / units, self._currency)

    def multiply_by(self, multiplier: float) -> "Cost":
        """
        Multiply cost by a factor.

        Args:
            multiplier: Factor to multiply by

        Returns:
            New Cost with multiplied amount
        """
        return Cost(self._amount * multiplier, self._currency)

    def add_percentage(self, percentage: float) -> "Cost":
        """
        Add a percentage to the cost.

        Args:
            percentage: Percentage to add (e.g., 10 for 10%)

        Returns:
            New Cost with percentage added
        """
        multiplier = 1.0 + (percentage / 100.0)
        return Cost(self._amount * multiplier, self._currency)

    def subtract_percentage(self, percentage: float) -> "Cost":
        """
        Subtract a percentage from the cost.

        Args:
            percentage: Percentage to subtract (e.g., 10 for 10%)

        Returns:
            New Cost with percentage subtracted
        """
        multiplier = 1.0 - (percentage / 100.0)
        return Cost(self._amount * multiplier, self._currency)

    def __add__(self, other: "Cost") -> "Cost":
        """Add two costs."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot add Cost and {type(other)}")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot add costs with different currencies: {self._currency} and {other._currency}"
            )

        return Cost(self._amount + other._amount, self._currency)

    def __sub__(self, other: "Cost") -> "Cost":
        """Subtract two costs."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot subtract {type(other)} from Cost")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot subtract costs with different currencies: {self._currency} and {other._currency}"
            )

        return Cost(self._amount - other._amount, self._currency)

    def __mul__(self, factor: float) -> "Cost":
        """Multiply cost by a factor."""
        if not isinstance(factor, int | float):
            raise TypeError(f"Cannot multiply Cost by {type(factor)}")

        return Cost(self._amount * factor, self._currency)

    def __rmul__(self, factor: float) -> "Cost":
        """Right multiplication (factor * cost)."""
        return self.__mul__(factor)

    def __truediv__(self, divisor) -> "Cost":
        """Divide cost by a factor."""
        if isinstance(divisor, int | float):
            if divisor == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            return Cost(self._amount / divisor, self._currency)
        else:
            raise TypeError(f"Cannot divide Cost by {type(divisor)}")

    def __floordiv__(self, divisor: float) -> "Cost":
        """Floor division of cost."""
        if not isinstance(divisor, int | float):
            raise TypeError(f"Cannot floor divide Cost by {type(divisor)}")
        if divisor == 0:
            raise ZeroDivisionError("Cannot divide by zero")

        return Cost(self._amount // divisor, self._currency)

    def __neg__(self) -> "Cost":
        """Negate cost."""
        return Cost(-self._amount, self._currency)

    def __pos__(self) -> "Cost":
        """Positive cost (no-op)."""
        return Cost(self._amount, self._currency)

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Cost):
            return False

        return (
            abs(self._amount - other._amount) < 1e-10
            and self._currency == other._currency
        )

    def __ne__(self, other: object) -> bool:
        """Check inequality."""
        return not self.__eq__(other)

    def __lt__(self, other: "Cost") -> bool:
        """Check if less than."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot compare Cost and {type(other)}")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot compare costs with different currencies: {self._currency} and {other._currency}"
            )

        return self._amount < other._amount

    def __le__(self, other: "Cost") -> bool:
        """Check if less than or equal."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot compare Cost and {type(other)}")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot compare costs with different currencies: {self._currency} and {other._currency}"
            )

        return self._amount <= other._amount

    def __gt__(self, other: "Cost") -> bool:
        """Check if greater than."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot compare Cost and {type(other)}")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot compare costs with different currencies: {self._currency} and {other._currency}"
            )

        return self._amount > other._amount

    def __ge__(self, other: "Cost") -> bool:
        """Check if greater than or equal."""
        if not isinstance(other, Cost):
            raise TypeError(f"Cannot compare Cost and {type(other)}")

        if self._currency != other._currency:
            raise ValueError(
                f"Cannot compare costs with different currencies: {self._currency} and {other._currency}"
            )

        return self._amount >= other._amount

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash((round(self._amount, 10), self._currency))

    def __str__(self) -> str:
        """String representation."""
        if self._currency == "USD":
            return f"${self._amount:.2f}"
        elif self._currency == "EUR":
            return f"€{self._amount:.2f}"
        elif self._currency == "GBP":
            return f"£{self._amount:.2f}"
        else:
            return f"{self._amount:.2f} {self._currency}"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Cost(amount={self._amount:.2f}, currency='{self._currency}')"

    def format_detailed(self, show_currency: bool = True) -> str:
        """
        Format cost with detailed formatting.

        Args:
            show_currency: Whether to show currency symbol/code

        Returns:
            Formatted cost string
        """
        if not show_currency:
            return f"{self._amount:.2f}"

        # Use appropriate currency formatting
        currency_symbols = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥"}

        if self._currency in currency_symbols:
            symbol = currency_symbols[self._currency]
            return f"{symbol}{self._amount:.2f}"
        else:
            return f"{self._amount:.2f} {self._currency}"
