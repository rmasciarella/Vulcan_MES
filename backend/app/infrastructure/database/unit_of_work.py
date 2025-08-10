"""
Unit of Work implementation for managing transactions across repositories.

The Unit of Work pattern maintains a list of objects affected by a business transaction
and coordinates writing out changes and resolving concurrency problems.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, create_engine

from app.core.config import get_settings
from app.infrastructure.database.repositories.job_repository import JobRepository
from app.infrastructure.database.repositories.resource_repository import (
    MachineRepository,
    OperatorRepository,
)
from app.infrastructure.database.repositories.schedule_repository import ScheduleRepository
from app.infrastructure.database.repositories.task_repository import TaskRepository

from .repositories.base import DatabaseError


class UnitOfWorkInterface(ABC):
    """
    Abstract base class for Unit of Work pattern.

    Defines the interface for coordinating transactions across multiple repositories.
    """

    # Repository properties
    jobs: JobRepository
    tasks: TaskRepository
    machines: MachineRepository
    operators: OperatorRepository
    schedules: ScheduleRepository

    @abstractmethod
    def __enter__(self):
        """Enter the runtime context for the unit of work."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context for the unit of work."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit all changes in the current transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback all changes in the current transaction."""
        pass


class SqlModelUnitOfWork(UnitOfWorkInterface):
    """
    SQLModel-based implementation of Unit of Work pattern.

    Manages database transactions using SQLModel/SQLAlchemy sessions and provides
    access to all repositories within a single transactional boundary.
    """

    def __init__(self, session_factory: Any | None = None):
        """
        Initialize the unit of work.

        Args:
            session_factory: Optional session factory. If None, creates default engine.
        """
        self._session_factory = session_factory
        self._session: Session | None = None
        self._repositories_initialized = False

        # Repository instances
        self.jobs: JobRepository | None = None
        self.tasks: TaskRepository | None = None
        self.machines: MachineRepository | None = None
        self.operators: OperatorRepository | None = None
        self.schedules: ScheduleRepository | None = None

    def __enter__(self):
        """
        Enter the runtime context and create database session.

        Returns:
            Self for context manager usage
        """
        if self._session_factory:
            self._session = self._session_factory()
        else:
            # Create session from default engine
            settings = get_settings()
            engine = create_engine(settings.database_url, echo=settings.debug)
            self._session = Session(engine)

        self._init_repositories()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the runtime context and cleanup resources.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        try:
            if exc_type is not None:
                self.rollback()
            else:
                try:
                    self.commit()
                except Exception:
                    self.rollback()
                    raise
        finally:
            if self._session:
                self._session.close()
                self._session = None
            self._repositories_initialized = False

    def commit(self) -> None:
        """
        Commit the current transaction.

        Raises:
            DatabaseError: If commit fails
        """
        if not self._session:
            raise DatabaseError("No active session to commit")

        try:
            self._session.commit()
        except SQLAlchemyError as e:
            self.rollback()
            raise DatabaseError(f"Failed to commit transaction: {str(e)}") from e

    def rollback(self) -> None:
        """
        Rollback the current transaction.

        Raises:
            DatabaseError: If rollback fails
        """
        if not self._session:
            raise DatabaseError("No active session to rollback")

        try:
            self._session.rollback()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to rollback transaction: {str(e)}") from e

    def flush(self) -> None:
        """
        Flush pending changes to the database without committing.

        Useful for getting generated IDs before commit.

        Raises:
            DatabaseError: If flush fails
        """
        if not self._session:
            raise DatabaseError("No active session to flush")

        try:
            self._session.flush()
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to flush session: {str(e)}") from e

    def refresh(self, instance: Any) -> None:
        """
        Refresh an instance from the database.

        Args:
            instance: Database instance to refresh

        Raises:
            DatabaseError: If refresh fails
        """
        if not self._session:
            raise DatabaseError("No active session for refresh")

        try:
            self._session.refresh(instance)
        except SQLAlchemyError as e:
            raise DatabaseError(f"Failed to refresh instance: {str(e)}") from e

    def expunge(self, instance: Any) -> None:
        """
        Remove an instance from the session.

        Args:
            instance: Database instance to expunge
        """
        if self._session:
            self._session.expunge(instance)

    def expunge_all(self) -> None:
        """Remove all instances from the session."""
        if self._session:
            self._session.expunge_all()

    def _init_repositories(self) -> None:
        """Initialize all repository instances with the current session."""
        if not self._session:
            raise DatabaseError("Cannot initialize repositories without active session")

        if not self._repositories_initialized:
            self.jobs = JobRepository(self._session)
            self.tasks = TaskRepository(self._session)
            self.machines = MachineRepository(self._session)
            self.operators = OperatorRepository(self._session)
            self.schedules = ScheduleRepository(self._session)
            self._repositories_initialized = True

    @property
    def session(self) -> Session:
        """
        Get the current database session.

        Returns:
            Active database session

        Raises:
            DatabaseError: If no active session
        """
        if not self._session:
            raise DatabaseError("No active database session")
        return self._session


class UnitOfWorkManager:
    """
    Manager for creating and configuring Unit of Work instances.

    Provides factory methods and configuration for different Unit of Work
    implementations and database backends.
    """

    def __init__(self, session_factory: Any | None = None):
        """
        Initialize the manager.

        Args:
            session_factory: Optional session factory for database connections
        """
        self._session_factory = session_factory
        self._default_uow_class = SqlModelUnitOfWork

    def create_unit_of_work(self) -> UnitOfWorkInterface:
        """
        Create a new Unit of Work instance.

        Returns:
            New Unit of Work instance
        """
        return self._default_uow_class(self._session_factory)

    @contextmanager
    def transaction(self):
        """
        Context manager for executing code within a transaction.

        Usage:
            with uow_manager.transaction() as uow:
                job = uow.jobs.find_by_id(job_id)
                job.update_status(new_status)
                uow.jobs.save(job)

        Yields:
            Unit of Work instance
        """
        uow = self.create_unit_of_work()
        with uow:
            yield uow

    def set_default_uow_class(self, uow_class: type) -> None:
        """
        Set the default Unit of Work implementation class.

        Args:
            uow_class: Class to use for creating Unit of Work instances
        """
        self._default_uow_class = uow_class


# Global unit of work manager instance
_uow_manager: UnitOfWorkManager | None = None


def get_unit_of_work_manager() -> UnitOfWorkManager:
    """
    Get the global Unit of Work manager instance.

    Returns:
        Unit of Work manager instance
    """
    global _uow_manager
    if _uow_manager is None:
        _uow_manager = UnitOfWorkManager()
    return _uow_manager


def configure_unit_of_work(session_factory: Any | None = None) -> None:
    """
    Configure the global Unit of Work manager.

    Args:
        session_factory: Session factory for database connections
    """
    global _uow_manager
    _uow_manager = UnitOfWorkManager(session_factory)


@contextmanager
def transaction():
    """
    Convenience context manager for database transactions.

    Usage:
        from app.infrastructure.database.unit_of_work import transaction

        with transaction() as uow:
            job = uow.jobs.find_by_id(job_id)
            job.update_status(new_status)

    Yields:
        Unit of Work instance
    """
    uow_manager = get_unit_of_work_manager()
    with uow_manager.transaction() as uow:
        yield uow
