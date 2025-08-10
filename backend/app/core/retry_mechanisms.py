"""
Advanced Retry Mechanisms with Exponential Backoff

Provides sophisticated retry patterns for optimization operations with
configurable strategies, circuit breaker integration, and comprehensive monitoring.
"""

import asyncio
import functools
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar
from uuid import uuid4

from ..domain.shared.exceptions import (
    CircuitBreakerOpenError as DomainCircuitBreakerOpenError,
)
from ..domain.shared.exceptions import (
    OptimizationTimeoutError,
    RetryExhaustedError,
    SolverCrashError,
    SolverError,
    SolverMemoryError,
    SystemResourceError,
)
from .circuit_breaker import CircuitBreakerOpenError
from .observability import (
    ERROR_RECOVERY_TIME,
    OPTIMIZATION_FAILURES,
    get_correlation_id,
    get_logger,
    log_error_with_context,
)

F = TypeVar("F", bound=Callable[..., Any])


class RetryStrategy(Enum):
    """Available retry strategies."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    CUSTOM = "custom"


class RetryCondition(Enum):
    """Conditions that determine if a retry should be attempted."""

    ALWAYS = "always"
    ON_TIMEOUT = "on_timeout"
    ON_SOLVER_ERROR = "on_solver_error"
    ON_RESOURCE_ERROR = "on_resource_error"
    ON_TRANSIENT_ERROR = "on_transient_error"
    NEVER = "never"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_max_seconds: float = 1.0

    # Conditions
    retry_on_exceptions: tuple[type[Exception], ...] = (
        SolverError,
        OptimizationTimeoutError,
        SystemResourceError,
    )

    stop_on_exceptions: tuple[type[Exception], ...] = (
        SolverMemoryError,  # Don't retry on memory exhaustion
        CircuitBreakerOpenError,  # Don't retry when circuit breaker is open
    )

    # Circuit breaker integration
    respect_circuit_breaker: bool = True
    backoff_on_circuit_breaker: bool = True

    # Monitoring
    track_metrics: bool = True
    log_attempts: bool = True


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""

    attempt_number: int
    delay_seconds: float
    error: Exception | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_seconds: float = 0.0
    success: bool = False

    def complete(self, success: bool = False, error: Exception | None = None) -> None:
        """Mark the attempt as completed."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.success = success
        self.error = error


@dataclass
class RetrySession:
    """Tracks a complete retry session."""

    session_id: str = field(default_factory=lambda: str(uuid4())[:8])
    operation_name: str = ""
    config: RetryConfig = field(default_factory=RetryConfig)
    attempts: list[RetryAttempt] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    final_success: bool = False
    final_error: Exception | None = None

    @property
    def total_duration_seconds(self) -> float:
        """Get total session duration."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def total_attempts(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)

    @property
    def successful_attempts(self) -> int:
        """Get number of successful attempts."""
        return sum(1 for attempt in self.attempts if attempt.success)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for logging."""
        return {
            "session_id": self.session_id,
            "operation_name": self.operation_name,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "total_duration_seconds": self.total_duration_seconds,
            "final_success": self.final_success,
            "final_error": str(self.final_error) if self.final_error else None,
            "final_error_type": type(self.final_error).__name__
            if self.final_error
            else None,
            "config": {
                "max_attempts": self.config.max_attempts,
                "strategy": self.config.strategy.value,
                "base_delay_seconds": self.config.base_delay_seconds,
                "max_delay_seconds": self.config.max_delay_seconds,
            },
        }


class RetryDelayCalculator:
    """Calculates retry delays based on different strategies."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self._fibonacci_cache = [1, 1]  # For Fibonacci sequence

    def calculate_delay(self, attempt_number: int) -> float:
        """Calculate delay for the given attempt number (1-based)."""
        base_delay = self._calculate_base_delay(attempt_number)

        # Apply jitter if enabled
        if self.config.jitter:
            jitter = random.uniform(0, self.config.jitter_max_seconds)
            base_delay += jitter

        # Respect maximum delay
        return min(base_delay, self.config.max_delay_seconds)

    def _calculate_base_delay(self, attempt_number: int) -> float:
        """Calculate base delay without jitter."""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            return self.config.base_delay_seconds

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return self.config.base_delay_seconds * (
                self.config.exponential_base ** (attempt_number - 1)
            )

        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            return self.config.base_delay_seconds * attempt_number

        elif self.config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            return self.config.base_delay_seconds * self._get_fibonacci(attempt_number)

        else:  # CUSTOM or unknown
            return self.config.base_delay_seconds

    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number (1-based)."""
        # Extend cache if necessary
        while len(self._fibonacci_cache) < n:
            next_fib = self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            self._fibonacci_cache.append(next_fib)

        return self._fibonacci_cache[n - 1]


class RetryManager:
    """
    Advanced retry manager with comprehensive monitoring and strategy support.

    Provides sophisticated retry patterns with circuit breaker integration,
    exponential backoff, jitter, and detailed observability.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._active_sessions: dict[str, RetrySession] = {}
        self._session_history: list[RetrySession] = []

    async def execute_with_retry(
        self,
        operation: Callable[..., Any],
        operation_name: str,
        config: RetryConfig | None = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute operation with retry logic.

        Args:
            operation: The async function to execute
            operation_name: Name for logging and metrics
            config: Retry configuration (uses default if None)
            *args, **kwargs: Arguments to pass to the operation

        Returns:
            Result from the operation

        Raises:
            RetryExhaustedError: If all retry attempts are exhausted
        """
        config = config or RetryConfig()
        session = RetrySession(operation_name=operation_name, config=config)

        self._active_sessions[session.session_id] = session
        delay_calculator = RetryDelayCalculator(config)

        self.logger.info(
            "Starting retry session",
            session_id=session.session_id,
            operation=operation_name,
            max_attempts=config.max_attempts,
            strategy=config.strategy.value,
            correlation_id=get_correlation_id(),
        )

        try:
            for attempt_num in range(1, config.max_attempts + 1):
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    delay_seconds=0.0
                    if attempt_num == 1
                    else delay_calculator.calculate_delay(attempt_num - 1),
                )
                session.attempts.append(attempt)

                # Apply delay for retry attempts (not first attempt)
                if attempt_num > 1:
                    self.logger.info(
                        "Retrying after delay",
                        session_id=session.session_id,
                        attempt=attempt_num,
                        delay_seconds=attempt.delay_seconds,
                    )
                    await asyncio.sleep(attempt.delay_seconds)

                try:
                    # Execute the operation
                    result = await operation(*args, **kwargs)

                    # Success!
                    attempt.complete(success=True)
                    session.final_success = True
                    session.end_time = time.time()

                    self.logger.info(
                        "Operation succeeded",
                        session_id=session.session_id,
                        attempt=attempt_num,
                        total_duration=session.total_duration_seconds,
                    )

                    # Record success metrics
                    if config.track_metrics:
                        ERROR_RECOVERY_TIME.labels(
                            error_type="retry_success", recovery_method="retry"
                        ).observe(session.total_duration_seconds)

                    return result

                except Exception as e:
                    attempt.complete(success=False, error=e)
                    session.final_error = e

                    # Check if we should stop retrying
                    if self._should_stop_retrying(e, config, attempt_num):
                        self.logger.error(
                            "Stopping retry due to non-retryable error",
                            session_id=session.session_id,
                            attempt=attempt_num,
                            error_type=type(e).__name__,
                            error=str(e),
                        )
                        break

                    # Log the failed attempt
                    if config.log_attempts:
                        log_error_with_context(
                            error=e,
                            operation=f"{operation_name}_retry_attempt_{attempt_num}",
                            context={
                                "session_id": session.session_id,
                                "attempt_number": attempt_num,
                                "max_attempts": config.max_attempts,
                                "will_retry": attempt_num < config.max_attempts,
                            },
                            severity="warning",
                            include_traceback=False,
                        )

                    # Check if we have more attempts
                    if attempt_num >= config.max_attempts:
                        self.logger.error(
                            "All retry attempts exhausted",
                            session_id=session.session_id,
                            total_attempts=attempt_num,
                            total_duration=session.total_duration_seconds,
                        )
                        break

            # All attempts failed
            session.end_time = time.time()

            # Record failure metrics
            if config.track_metrics:
                OPTIMIZATION_FAILURES.labels(
                    failure_reason="retry_exhausted", fallback_used="false"
                ).inc()

                ERROR_RECOVERY_TIME.labels(
                    error_type="retry_failure", recovery_method="retry"
                ).observe(session.total_duration_seconds)

            raise RetryExhaustedError(
                operation=operation_name,
                max_attempts=config.max_attempts,
                last_error=session.final_error or Exception("Unknown error"),
            )

        finally:
            # Clean up and record session history
            if session.session_id in self._active_sessions:
                del self._active_sessions[session.session_id]

            self._session_history.append(session)

            # Keep history limited
            if len(self._session_history) > 1000:
                self._session_history = self._session_history[-500:]  # Keep last 500

    def _should_stop_retrying(
        self, error: Exception, config: RetryConfig, attempt_number: int
    ) -> bool:
        """Determine if retrying should stop based on error type and config."""

        # Check if error type is in stop list
        if any(isinstance(error, stop_type) for stop_type in config.stop_on_exceptions):
            return True

        # Check if error type is not in retry list
        if config.retry_on_exceptions and not any(
            isinstance(error, retry_type) for retry_type in config.retry_on_exceptions
        ):
            return True

        # Circuit breaker handling
        if isinstance(error, CircuitBreakerOpenError | DomainCircuitBreakerOpenError):
            if not config.respect_circuit_breaker:
                return False  # Ignore circuit breaker
            return True  # Stop retrying when circuit breaker is open

        return False  # Continue retrying

    def get_active_sessions(self) -> dict[str, dict[str, Any]]:
        """Get information about currently active retry sessions."""
        return {
            session_id: session.to_dict()
            for session_id, session in self._active_sessions.items()
        }

    def get_session_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent retry session history."""
        recent_sessions = self._session_history[-limit:]
        return [session.to_dict() for session in recent_sessions]

    def get_retry_statistics(self) -> dict[str, int | float]:
        """Get retry statistics across all sessions."""
        if not self._session_history:
            return {
                "total_sessions": 0,
                "success_rate": 0.0,
                "average_attempts": 0.0,
                "average_duration": 0.0,
            }

        total_sessions = len(self._session_history)
        successful_sessions = sum(1 for s in self._session_history if s.final_success)
        total_attempts = sum(s.total_attempts for s in self._session_history)
        total_duration = sum(s.total_duration_seconds for s in self._session_history)

        return {
            "total_sessions": total_sessions,
            "success_rate": successful_sessions / total_sessions
            if total_sessions > 0
            else 0.0,
            "average_attempts": total_attempts / total_sessions
            if total_sessions > 0
            else 0.0,
            "average_duration": total_duration / total_sessions
            if total_sessions > 0
            else 0.0,
            "successful_sessions": successful_sessions,
            "failed_sessions": total_sessions - successful_sessions,
        }


# Global retry manager instance
_retry_manager = RetryManager()


def with_retry(
    operation_name: str | None = None,
    config: RetryConfig | None = None,
):
    """
    Decorator to add retry behavior to async functions.

    Args:
        operation_name: Name for logging (defaults to function name)
        config: Retry configuration (uses default if None)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            return await _retry_manager.execute_with_retry(
                func, name, config, *args, **kwargs
            )

        return wrapper

    return decorator


# Predefined retry configurations
SOLVER_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay_seconds=2.0,
    max_delay_seconds=30.0,
    exponential_base=2.0,
    jitter=True,
    retry_on_exceptions=(
        SolverError,
        SolverCrashError,
        OptimizationTimeoutError,
    ),
    stop_on_exceptions=(
        SolverMemoryError,
        CircuitBreakerOpenError,
    ),
)

QUICK_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    strategy=RetryStrategy.FIXED_DELAY,
    base_delay_seconds=1.0,
    max_delay_seconds=5.0,
    jitter=True,
    retry_on_exceptions=(Exception,),
    stop_on_exceptions=(
        SolverMemoryError,
        CircuitBreakerOpenError,
    ),
)

PERSISTENT_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    strategy=RetryStrategy.FIBONACCI_BACKOFF,
    base_delay_seconds=1.0,
    max_delay_seconds=120.0,  # 2 minutes max
    jitter=True,
    retry_on_exceptions=(
        SolverError,
        SystemResourceError,
        OptimizationTimeoutError,
    ),
    stop_on_exceptions=(
        SolverMemoryError,
        CircuitBreakerOpenError,
    ),
)


async def execute_with_retry(
    operation: Callable[..., Any],
    operation_name: str,
    config: RetryConfig | None = None,
    *args,
    **kwargs,
) -> Any:
    """
    Execute operation with retry logic (functional interface).

    Args:
        operation: The async function to execute
        operation_name: Name for logging and metrics
        config: Retry configuration (uses default if None)
        *args, **kwargs: Arguments to pass to the operation

    Returns:
        Result from the operation
    """
    return await _retry_manager.execute_with_retry(
        operation, operation_name, config, *args, **kwargs
    )


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance."""
    return _retry_manager
