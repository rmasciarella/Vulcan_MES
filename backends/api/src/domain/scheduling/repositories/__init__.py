"""
Repository Interfaces

Contains abstract interfaces for data persistence operations.
These interfaces define the contract for data access without specifying
the implementation details, following the Dependency Inversion Principle.

The actual implementations are provided in the infrastructure layer,
allowing the domain to remain independent of persistence technology.
"""

from .job_repository import JobRepository
from .machine_repository import MachineRepository
from .operator_repository import OperatorRepository
from .schedule_repository import ScheduleRepository
from .task_repository import TaskRepository

__all__ = [
    "JobRepository",
    "TaskRepository",
    "OperatorRepository",
    "MachineRepository",
    "ScheduleRepository",
]
