"""
Circuit Breaker Implementation

Provides resilience patterns for external service calls and system stability
with configurable failure thresholds and recovery mechanisms.
"""

import asyncio
import functools
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from circuitbreaker import circuit
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings
from .observability import CIRCUIT_BREAKER_STATE, get_logger

F = TypeVar("F", bound=Callable[..., Any])


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
    recovery_timeout: int = settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
    expected_exception: tuple[type[Exception], ...] = (Exception,)
    name: str = "default"


class CircuitBreakerRegistry:
    """Registry for managing circuit breakers."""

    def __init__(self):
        self._breakers: dict[str, Any] = {}
        self._configs: dict[str, CircuitBreakerConfig] = {}
        self.logger = get_logger("circuit_breaker")

    def get_breaker(self, name: str, config: CircuitBreakerConfig | None = None) -> Any:
        """Get or create a circuit breaker."""
        if name not in self._breakers:
            if config is None:
                config = CircuitBreakerConfig(name=name)

            self._configs[name] = config

            # Create circuit breaker with custom listeners
            breaker = circuit(
                failure_threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout,
                expected_exception=config.expected_exception,
            )

            # Add state change listeners
            self._add_listeners(breaker, name)
            self._breakers[name] = breaker

        return self._breakers[name]

    def _add_listeners(self, breaker: Any, name: str) -> None:
        """Add listeners for circuit breaker state changes."""

        def on_failure(exception: Exception) -> None:
            self.logger.warning(
                "Circuit breaker failure recorded",
                service=name,
                error=str(exception),
                error_type=type(exception).__name__,
            )

        def on_success() -> None:
            self.logger.info("Circuit breaker success recorded", service=name)

        def on_circuit_open() -> None:
            CIRCUIT_BREAKER_STATE.labels(service=name).set(1)  # Open = 1
            self.logger.error("Circuit breaker opened", service=name)

        def on_circuit_close() -> None:
            CIRCUIT_BREAKER_STATE.labels(service=name).set(0)  # Closed = 0
            self.logger.info("Circuit breaker closed", service=name)

        def on_circuit_half_open() -> None:
            CIRCUIT_BREAKER_STATE.labels(service=name).set(0.5)  # Half-open = 0.5
            self.logger.info("Circuit breaker half-open", service=name)

        # Register listeners
        breaker.add_failure_listener(on_failure)
        breaker.add_success_listener(on_success)
        breaker.add_circuit_open_listener(on_circuit_open)
        breaker.add_circuit_close_listener(on_circuit_close)
        breaker.add_circuit_half_open_listener(on_circuit_half_open)


# Global registry
_circuit_breaker_registry = CircuitBreakerRegistry()


def with_circuit_breaker(
    service_name: str,
    config: CircuitBreakerConfig | None = None,
):
    """Decorator to add circuit breaker protection to a function."""

    def decorator(func: F) -> F:
        breaker = _circuit_breaker_registry.get_breaker(service_name, config)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker(func)(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return breaker(func)(*args, **kwargs)

        # Return appropriate wrapper
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exponential_base: int = 2,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator to add retry logic with exponential backoff."""

    def decorator(func: F) -> F:
        logger = get_logger("retry")

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=min_wait, max=max_wait, exp_base=exponential_base
            ),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        )
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Retry attempt failed",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=min_wait, max=max_wait, exp_base=exponential_base
            ),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        )
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Retry attempt failed",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        # Return appropriate wrapper
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_resilience(
    service_name: str,
    circuit_config: CircuitBreakerConfig | None = None,
    max_retry_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Combined decorator for circuit breaker + retry pattern."""

    def decorator(func: F) -> F:
        # Apply retry first, then circuit breaker
        func_with_retry = with_retry(
            max_attempts=max_retry_attempts,
            min_wait=min_wait,
            max_wait=max_wait,
            retry_exceptions=retry_exceptions,
        )(func)

        return with_circuit_breaker(service_name, circuit_config)(func_with_retry)

    return decorator


class TimeoutError(Exception):
    """Exception raised when operation times out."""

    pass


def with_timeout(timeout_seconds: float):
    """Decorator to add timeout protection to async functions."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger = get_logger("timeout")
                logger.error(
                    "Function timeout",
                    function=func.__name__,
                    timeout_seconds=timeout_seconds,
                )
                raise TimeoutError(
                    f"Function {func.__name__} timed out after {timeout_seconds}s"
                )

        return wrapper

    return decorator


# Predefined configurations for common services
DATABASE_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=(ConnectionError, OSError, TimeoutError),
    name="database",
)

EXTERNAL_API_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=(ConnectionError, OSError, TimeoutError),
    name="external_api",
)

SOLVER_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=2,
    recovery_timeout=120,
    expected_exception=(Exception,),
    name="solver",
)

# Enhanced solver-specific circuit breaker configurations
SOLVER_OPTIMIZATION_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=2,
    recovery_timeout=300,  # 5 minutes for optimization recovery
    expected_exception=(
        Exception,  # Catch all solver-related exceptions
    ),
    name="solver_optimization",
)

SOLVER_MEMORY_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=1,  # Fail fast on memory issues
    recovery_timeout=600,  # 10 minutes to allow system recovery
    expected_exception=(
        MemoryError,
        OSError,  # System resource errors
    ),
    name="solver_memory",
)

SOLVER_MODEL_CREATION_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=60,  # Quick recovery for model creation
    expected_exception=(
        ValueError,
        TypeError,
        AttributeError,
    ),
    name="solver_model_creation",
)


def get_circuit_breaker_status() -> dict[str, dict[str, Any]]:
    """Get status of all registered circuit breakers."""
    status = {}

    for name, breaker in _circuit_breaker_registry._breakers.items():
        status[name] = {
            "state": breaker.current_state,
            "failure_count": breaker.failure_count,
            "last_failure_time": breaker.last_failure_time,
            "config": {
                "failure_threshold": _circuit_breaker_registry._configs[
                    name
                ].failure_threshold,
                "recovery_timeout": _circuit_breaker_registry._configs[
                    name
                ].recovery_timeout,
            },
        }

    return status


async def health_check_with_circuit_breaker(
    service_name: str,
    health_check_func: Callable[[], bool],
    timeout_seconds: float = 5.0,
) -> bool:
    """Perform health check with circuit breaker protection."""

    @with_timeout(timeout_seconds)
    @with_circuit_breaker(f"{service_name}_health")
    async def protected_health_check():
        return health_check_func()

    try:
        return await protected_health_check()
    except Exception:
        return False
