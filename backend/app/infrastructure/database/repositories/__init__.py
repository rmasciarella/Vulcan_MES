"""
Repository Implementations

Contains concrete implementations of repository interfaces defined in the
domain layer. These implementations handle the actual database operations
using SQLModel and provide the persistence layer for domain entities.

Repository implementations translate between domain objects and database
records, ensuring proper mapping and data consistency.
"""

from .base import (
    BaseRepository,
    DatabaseError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    RepositoryException,
)
from .job_repository import JobRepository
from .resource_repository import (
    MachineRepository,
    OperatorRepository,
    ResourceRepository,
)
from .schedule_repository import ScheduleRepository
from .task_repository import TaskRepository

__all__ = [
    # Base classes
    "BaseRepository",
    "RepositoryException",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "DatabaseError",
    # Repository implementations
    "JobRepository",
    "TaskRepository",
    "MachineRepository",
    "OperatorRepository",
    "ResourceRepository",
    "ScheduleRepository",
]
