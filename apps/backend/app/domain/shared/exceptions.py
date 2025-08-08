"""
Domain Exceptions with Enterprise-Grade Type Safety

Defines custom exceptions for domain-specific errors with discriminated unions.
These exceptions represent business rule violations and domain constraints.
Implements proper error type discrimination for enterprise-grade error handling.
"""

from enum import Enum
from uuid import UUID


class ErrorType(str, Enum):
    """Error type enumeration for discriminated unions."""

    VALIDATION = "validation"
    BUSINESS_RULE = "business_rule"
    RESOURCE_CONFLICT = "resource_conflict"
    CONSTRAINT_VIOLATION = "constraint_violation"
    NOT_FOUND = "not_found"
    OPTIMIZATION = "optimization"
    REPOSITORY = "repository"
    CONCURRENCY = "concurrency"


class DomainError(Exception):
    """Base class for all domain errors with type discrimination."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}

    def to_dict(self) -> dict[str, str | dict[str, str | int | bool | None]]:
        """Convert error to dictionary for API responses."""
        return {
            "type": self.error_type.value,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(DomainError):
    """Raised when domain validation rules are violated."""

    def __init__(
        self,
        field_name: str,
        value: str | int | float | bool | None,
        message: str,
        error_code: str | None = None,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        self.field_name = field_name
        self.value = value
        self.error_code = error_code or "VALIDATION_ERROR"

        full_message = f"Validation failed for field '{field_name}': {message}"
        details = details or {}
        details.update(
            {
                "field": field_name,
                "value": str(value) if value is not None else None,
                "error_code": self.error_code,
            }
        )

        super().__init__(full_message, ErrorType.VALIDATION, details)

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary for API responses."""
        return {
            "type": self.error_type.value,
            "field": self.field_name,
            "value": str(self.value) if self.value is not None else None,
            "message": self.message,
            "error_code": self.error_code,
        }


class MultipleValidationError(ValidationError):
    """Raised when multiple validation errors occur."""

    def __init__(self, validation_errors: list[ValidationError]) -> None:
        self.validation_errors = validation_errors
        messages = [error.message for error in validation_errors]
        combined_message = "Multiple validation errors: " + "; ".join(messages)

        details: dict[str, str | int | bool | None] = {
            "error_count": len(validation_errors),
            "errors": str(
                [error.to_dict() for error in validation_errors]
            ),  # Convert to string for union type compatibility
        }

        super().__init__(
            "multiple_fields",
            None,
            combined_message,
            "MULTIPLE_VALIDATION_ERRORS",
            details,
        )

    @property
    def error_count(self) -> int:
        """Get the number of validation errors."""
        return len(self.validation_errors)


class BusinessRuleError(DomainError):
    """Raised when business rules are violated."""

    def __init__(
        self, message: str, details: dict[str, str | int | bool | None] | None = None
    ) -> None:
        super().__init__(message, ErrorType.BUSINESS_RULE, details)


class ResourceConflictError(DomainError):
    """Raised when resource conflicts occur (double booking, etc.)."""

    def __init__(
        self, message: str, details: dict[str, str | int | bool | None] | None = None
    ) -> None:
        super().__init__(message, ErrorType.RESOURCE_CONFLICT, details)


class ConstraintViolationError(DomainError):
    """Raised when scheduling constraints are violated."""

    def __init__(
        self,
        message: str,
        violations: list[str] | None = None,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        constraint_details = details or {}
        if violations:
            constraint_details["violations"] = str(
                violations
            )  # Convert to string for union type compatibility
        super().__init__(message, ErrorType.CONSTRAINT_VIOLATION, constraint_details)
        self.violations = violations or []


# Job-related exceptions
class JobError(DomainError):
    """Base class for job-related errors."""

    def __init__(
        self, message: str, details: dict[str, str | int | bool | None] | None = None
    ) -> None:
        super().__init__(message, ErrorType.NOT_FOUND, details)


class JobNotFoundError(JobError):
    """Raised when a job is not found."""

    def __init__(self, job_id: UUID) -> None:
        details = {"job_id": str(job_id), "entity_type": "job"}
        super().__init__(f"Job not found: {job_id}", details)
        self.job_id = job_id


class JobAlreadyCompletedError(JobError):
    """Raised when attempting to modify a completed job."""

    def __init__(self, job_id: UUID) -> None:
        details = {"job_id": str(job_id), "status": "completed"}
        super().__init__(f"Job {job_id} is already completed", details)
        self.job_id = job_id


class JobCancellationError(JobError):
    """Raised when job cannot be cancelled."""

    def __init__(self, message: str, job_id: UUID | None = None) -> None:
        details = {"job_id": str(job_id) if job_id else None}
        super().__init__(message, details)


# Task-related exceptions
class TaskError(DomainError):
    """Base class for task-related errors."""

    def __init__(
        self, message: str, details: dict[str, str | int | bool | None] | None = None
    ) -> None:
        super().__init__(message, ErrorType.BUSINESS_RULE, details)


class TaskNotFoundError(TaskError):
    """Raised when a task is not found."""

    def __init__(self, task_id: UUID) -> None:
        details = {"task_id": str(task_id), "entity_type": "task"}
        super().__init__(f"Task not found: {task_id}", details)
        self.task_id = task_id


class TaskSchedulingError(TaskError):
    """Raised when task cannot be scheduled."""

    def __init__(self, message: str, task_id: UUID | None = None) -> None:
        details = {"task_id": str(task_id) if task_id else None}
        super().__init__(message, details)


class TaskStatusError(TaskError):
    """Raised when task status transition is invalid."""

    def __init__(
        self, task_id: UUID, current_status: str, attempted_status: str
    ) -> None:
        details = {
            "task_id": str(task_id),
            "current_status": current_status,
            "attempted_status": attempted_status,
        }
        super().__init__(
            f"Cannot change task {task_id} from {current_status} to {attempted_status}",
            details,
        )
        self.task_id = task_id
        self.current_status = current_status
        self.attempted_status = attempted_status


# Operator-related exceptions
class OperatorError(DomainError):
    """Base class for operator-related errors."""

    pass


class OperatorNotFoundError(OperatorError):
    """Raised when an operator is not found."""

    def __init__(self, operator_id: UUID) -> None:
        super().__init__(f"Operator not found: {operator_id}")
        self.operator_id = operator_id


class OperatorUnavailableError(OperatorError):
    """Raised when operator is not available for assignment."""

    def __init__(self, operator_id: UUID, reason: str = "") -> None:
        message = f"Operator {operator_id} is unavailable"
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.operator_id = operator_id
        self.reason = reason


class InsufficientSkillError(OperatorError):
    """Raised when operator doesn't have required skills."""

    def __init__(
        self,
        operator_id: UUID,
        required_skill: str,
        required_level: int,
        actual_level: int | None = None,
    ) -> None:
        message = f"Operator {operator_id} lacks required skill: {required_skill} (level {required_level})"
        if actual_level is not None:
            message += f" - has level {actual_level}"
        super().__init__(message)
        self.operator_id = operator_id
        self.required_skill = required_skill
        self.required_level = required_level
        self.actual_level = actual_level


# Machine-related exceptions
class MachineError(DomainError):
    """Base class for machine-related errors."""

    pass


class MachineNotFoundError(MachineError):
    """Raised when a machine is not found."""

    def __init__(self, machine_id: UUID) -> None:
        super().__init__(f"Machine not found: {machine_id}")
        self.machine_id = machine_id


class MachineUnavailableError(MachineError):
    """Raised when machine is not available for assignment."""

    def __init__(self, machine_id: UUID, reason: str = "") -> None:
        message = f"Machine {machine_id} is unavailable"
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.machine_id = machine_id
        self.reason = reason


class MachineCapabilityError(MachineError):
    """Raised when machine cannot perform required task."""

    def __init__(self, machine_id: UUID, task_type: str) -> None:
        super().__init__(f"Machine {machine_id} cannot perform task type: {task_type}")
        self.machine_id = machine_id
        self.task_type = task_type


# Schedule-related exceptions
class ScheduleError(DomainError):
    """Base class for schedule-related errors."""

    pass


class ScheduleNotFoundError(ScheduleError):
    """Raised when a schedule is not found."""

    def __init__(self, schedule_id: UUID) -> None:
        super().__init__(f"Schedule not found: {schedule_id}")
        self.schedule_id = schedule_id


class SchedulePublishError(ScheduleError):
    """Raised when schedule cannot be published."""

    pass


class ScheduleModificationError(ScheduleError):
    """Raised when published schedule cannot be modified."""

    def __init__(self, schedule_id: UUID, status: str) -> None:
        super().__init__(f"Cannot modify schedule {schedule_id} in status: {status}")
        self.schedule_id = schedule_id
        self.status = status


# Scheduling constraint exceptions
class PrecedenceConstraintError(ConstraintViolationError):
    """Raised when task precedence constraints are violated."""

    def __init__(self, task_id: UUID, predecessor_id: UUID) -> None:
        super().__init__(
            f"Task {task_id} cannot start before predecessor {predecessor_id}"
        )
        self.task_id = task_id
        self.predecessor_id = predecessor_id


class WorkInProgressLimitError(ConstraintViolationError):
    """Raised when WIP limits are exceeded."""

    def __init__(self, zone: str, current_wip: int, limit: int) -> None:
        super().__init__(f"WIP limit exceeded in zone {zone}: {current_wip} > {limit}")
        self.zone = zone
        self.current_wip = current_wip
        self.limit = limit


class BusinessHoursConstraintError(ConstraintViolationError):
    """Raised when tasks are scheduled outside business hours."""

    def __init__(self, task_id: UUID, scheduled_time: str) -> None:
        super().__init__(
            f"Task {task_id} scheduled outside business hours: {scheduled_time}"
        )
        self.task_id = task_id
        self.scheduled_time = scheduled_time


class ResourceDoubleBookingError(ResourceConflictError):
    """Raised when resources are double-booked."""

    def __init__(
        self, resource_type: str, resource_id: UUID, time_conflict: str
    ) -> None:
        super().__init__(
            f"{resource_type} {resource_id} is double-booked at {time_conflict}"
        )
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.time_conflict = time_conflict


# Repository exceptions
class RepositoryError(DomainError):
    """Base class for repository-related errors."""

    pass


class EntityNotFoundError(RepositoryError):
    """Raised when entity is not found in repository."""

    def __init__(self, entity_type: str, entity_id: UUID) -> None:
        super().__init__(f"{entity_type} not found: {entity_id}")
        self.entity_type = entity_type
        self.entity_id = entity_id


class DataIntegrityError(RepositoryError):
    """Raised when data integrity constraints are violated."""

    pass


class ConcurrencyError(RepositoryError):
    """Raised when concurrent modification conflicts occur."""

    def __init__(self, entity_type: str, entity_id: UUID) -> None:
        super().__init__(f"Concurrent modification of {entity_type}: {entity_id}")
        self.entity_type = entity_type
        self.entity_id = entity_id


# Optimization exceptions
class OptimizationError(DomainError):
    """Base class for optimization-related errors."""

    def __init__(
        self, message: str, details: dict[str, str | int | bool | None] | None = None
    ) -> None:
        super().__init__(message, ErrorType.OPTIMIZATION, details)


class NoFeasibleSolutionError(OptimizationError):
    """Raised when no feasible solution can be found."""

    def __init__(
        self,
        reason: str = "",
        problem_stats: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        message = "No feasible solution found"
        if reason:
            message += f": {reason}"

        details = problem_stats or {}
        details.update({"reason": reason, "feasibility": "infeasible"})

        super().__init__(message, details)
        self.reason = reason


class OptimizationTimeoutError(OptimizationError):
    """Raised when optimization times out."""

    def __init__(
        self,
        timeout_seconds: int,
        partial_solution: bool = False,
        solver_stats: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        message = f"Optimization timed out after {timeout_seconds} seconds"
        if partial_solution:
            message += " (partial solution available)"

        details = solver_stats or {}
        details.update(
            {
                "timeout_seconds": timeout_seconds,
                "partial_solution": partial_solution,
                "termination_reason": "timeout",
            }
        )

        super().__init__(message, details)
        self.timeout_seconds = timeout_seconds
        self.partial_solution = partial_solution


class SolverError(OptimizationError):
    """Raised when solver encounters an error."""

    def __init__(
        self,
        message: str,
        solver_status: str = "UNKNOWN",
        solver_stats: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        details = solver_stats or {}
        details.update({"solver_status": solver_status, "error_category": "solver"})

        super().__init__(message, details)
        self.solver_status = solver_status


class SolverMemoryError(SolverError):
    """Raised when solver runs out of memory."""

    def __init__(self, memory_limit_mb: int = 0, peak_memory_mb: int = 0) -> None:
        message = "Solver exceeded memory limit"
        if memory_limit_mb > 0:
            message += f" (limit: {memory_limit_mb}MB"
            if peak_memory_mb > 0:
                message += f", peak: {peak_memory_mb}MB"
            message += ")"

        details = {
            "memory_limit_mb": memory_limit_mb,
            "peak_memory_mb": peak_memory_mb,
            "error_type": "memory_exhaustion",
        }

        super().__init__(message, "MEMORY_ERROR", details)
        self.memory_limit_mb = memory_limit_mb
        self.peak_memory_mb = peak_memory_mb


class SolverCrashError(SolverError):
    """Raised when solver process crashes unexpectedly."""

    def __init__(self, exit_code: int = -1, signal: str | None = None) -> None:
        message = "Solver process crashed unexpectedly"
        if exit_code != -1:
            message += f" (exit code: {exit_code})"
        if signal:
            message += f" (signal: {signal})"

        details = {
            "exit_code": exit_code,
            "signal": signal,
            "error_type": "process_crash",
        }

        super().__init__(message, "CRASH", details)
        self.exit_code = exit_code
        self.signal = signal


class SolverConfigurationError(SolverError):
    """Raised when solver configuration is invalid."""

    def __init__(
        self, parameter: str, value: str | int | float, reason: str = ""
    ) -> None:
        message = f"Invalid solver configuration: {parameter}={value}"
        if reason:
            message += f" ({reason})"

        details = {
            "parameter": parameter,
            "value": str(value),
            "reason": reason,
            "error_type": "configuration",
        }

        super().__init__(message, "CONFIGURATION_ERROR", details)
        self.parameter = parameter
        self.value = value


# Circuit breaker and resilience exceptions
class CircuitBreakerError(DomainError):
    """Base class for circuit breaker errors."""

    def __init__(
        self,
        message: str,
        service_name: str,
        state: str,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        circuit_details = details or {}
        circuit_details.update(
            {
                "service_name": service_name,
                "circuit_state": state,
                "error_category": "circuit_breaker",
            }
        )

        super().__init__(message, ErrorType.REPOSITORY, circuit_details)
        self.service_name = service_name
        self.state = state


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open."""

    def __init__(
        self, service_name: str, failure_count: int, recovery_timeout: int
    ) -> None:
        message = f"Circuit breaker open for {service_name} (failures: {failure_count})"
        details = {
            "failure_count": failure_count,
            "recovery_timeout_seconds": recovery_timeout,
            "action": "rejecting_requests",
        }

        super().__init__(message, service_name, "OPEN", details)
        self.failure_count = failure_count
        self.recovery_timeout = recovery_timeout


# Retry and resilience exceptions
class RetryExhaustedError(DomainError):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self, operation: str, max_attempts: int, last_error: Exception
    ) -> None:
        message = f"Retry exhausted for {operation} after {max_attempts} attempts"
        details = {
            "operation": operation,
            "max_attempts": max_attempts,
            "last_error": str(last_error),
            "last_error_type": type(last_error).__name__,
            "error_category": "retry_exhausted",
        }

        super().__init__(message, ErrorType.REPOSITORY, details)
        self.operation = operation
        self.max_attempts = max_attempts
        self.last_error = last_error


# System resource exceptions
class SystemResourceError(DomainError):
    """Base class for system resource errors."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        resource_details = details or {}
        resource_details.update(
            {"resource_type": resource_type, "error_category": "system_resource"}
        )

        super().__init__(message, ErrorType.REPOSITORY, resource_details)
        self.resource_type = resource_type


class MemoryExhaustionError(SystemResourceError):
    """Raised when system runs out of memory."""

    def __init__(self, available_mb: int = 0, required_mb: int = 0) -> None:
        message = "System memory exhaustion"
        if available_mb > 0 and required_mb > 0:
            message += f" (available: {available_mb}MB, required: {required_mb}MB)"

        details = {
            "available_memory_mb": available_mb,
            "required_memory_mb": required_mb,
            "resource_exhausted": "memory",
        }

        super().__init__(message, "memory", details)
        self.available_mb = available_mb
        self.required_mb = required_mb


class DiskSpaceExhaustionError(SystemResourceError):
    """Raised when system runs out of disk space."""

    def __init__(self, available_gb: float = 0, required_gb: float = 0) -> None:
        message = "Disk space exhaustion"
        if available_gb > 0 and required_gb > 0:
            message += (
                f" (available: {available_gb:.1f}GB, required: {required_gb:.1f}GB)"
            )

        details = {
            "available_disk_gb": available_gb,
            "required_disk_gb": required_gb,
            "resource_exhausted": "disk_space",
        }

        super().__init__(message, "disk", details)
        self.available_gb = available_gb
        self.required_gb = required_gb


# External service exceptions
class ExternalServiceError(DomainError):
    """Base class for external service errors."""

    def __init__(
        self,
        message: str,
        service_name: str,
        details: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        service_details = details or {}
        service_details.update(
            {"service_name": service_name, "error_category": "external_service"}
        )

        super().__init__(message, ErrorType.REPOSITORY, service_details)
        self.service_name = service_name


class ServiceUnavailableError(ExternalServiceError):
    """Raised when external service is unavailable."""

    def __init__(
        self,
        service_name: str,
        status_code: int | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        message = f"Service unavailable: {service_name}"
        if status_code:
            message += f" (HTTP {status_code})"

        details = {
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "availability": "unavailable",
        }

        super().__init__(message, service_name, details)
        self.status_code = status_code
        self.response_time_ms = response_time_ms
