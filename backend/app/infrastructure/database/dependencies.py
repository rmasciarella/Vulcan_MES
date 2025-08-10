"""
Database dependency injection for FastAPI.

This module provides dependency injection functions for database sessions
and repository instances to be used in FastAPI route handlers.
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.db import engine

from .repositories import (
    JobRepository,
    MachineRepository,
    OperatorRepository,
    ResourceRepository,
    ScheduleRepository,
    TaskRepository,
)


def get_session() -> Generator[Session, None, None]:
    """
    Create a database session for dependency injection.

    This function creates a new SQLModel session that will be automatically
    closed when the request is complete. Use this as a FastAPI dependency.

    Yields:
        Session: SQLModel database session
    """
    with Session(engine) as session:
        yield session


# Type aliases for dependency injection
SessionDep = Annotated[Session, Depends(get_session)]


def get_job_repository(session: SessionDep) -> JobRepository:
    """
    Get JobRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        JobRepository: Repository instance
    """
    return JobRepository(session)


def get_task_repository(session: SessionDep) -> TaskRepository:
    """
    Get TaskRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        TaskRepository: Repository instance
    """
    return TaskRepository(session)


def get_machine_repository(session: SessionDep) -> MachineRepository:
    """
    Get MachineRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        MachineRepository: Repository instance
    """
    return MachineRepository(session)


def get_operator_repository(session: SessionDep) -> OperatorRepository:
    """
    Get OperatorRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        OperatorRepository: Repository instance
    """
    return OperatorRepository(session)


def get_resource_repository(session: SessionDep) -> ResourceRepository:
    """
    Get ResourceRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        ResourceRepository: Repository instance
    """
    return ResourceRepository(session)


def get_schedule_repository(session: SessionDep) -> ScheduleRepository:
    """
    Get ScheduleRepository instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        ScheduleRepository: Repository instance
    """
    return ScheduleRepository(session)


# Type aliases for repository dependency injection
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]
MachineRepositoryDep = Annotated[MachineRepository, Depends(get_machine_repository)]
OperatorRepositoryDep = Annotated[OperatorRepository, Depends(get_operator_repository)]
ResourceRepositoryDep = Annotated[ResourceRepository, Depends(get_resource_repository)]
ScheduleRepositoryDep = Annotated[ScheduleRepository, Depends(get_schedule_repository)]


class RepositoryContainer:
    """
    Container class that provides access to all repositories with a single dependency.

    This is useful when you need multiple repositories in a single endpoint
    without having to inject them individually.
    """

    def __init__(self, session: Session):
        """Initialize container with database session."""
        self._session = session
        self._job_repo: JobRepository | None = None
        self._task_repo: TaskRepository | None = None
        self._machine_repo: MachineRepository | None = None
        self._operator_repo: OperatorRepository | None = None
        self._resource_repo: ResourceRepository | None = None
        self._schedule_repo: ScheduleRepository | None = None

    @property
    def jobs(self) -> JobRepository:
        """Get or create JobRepository instance."""
        if self._job_repo is None:
            self._job_repo = JobRepository(self._session)
        return self._job_repo

    @property
    def tasks(self) -> TaskRepository:
        """Get or create TaskRepository instance."""
        if self._task_repo is None:
            self._task_repo = TaskRepository(self._session)
        return self._task_repo

    @property
    def machines(self) -> MachineRepository:
        """Get or create MachineRepository instance."""
        if self._machine_repo is None:
            self._machine_repo = MachineRepository(self._session)
        return self._machine_repo

    @property
    def operators(self) -> OperatorRepository:
        """Get or create OperatorRepository instance."""
        if self._operator_repo is None:
            self._operator_repo = OperatorRepository(self._session)
        return self._operator_repo

    @property
    def resources(self) -> ResourceRepository:
        """Get or create ResourceRepository instance."""
        if self._resource_repo is None:
            self._resource_repo = ResourceRepository(self._session)
        return self._resource_repo

    @property
    def schedules(self) -> ScheduleRepository:
        """Get or create ScheduleRepository instance."""
        if self._schedule_repo is None:
            self._schedule_repo = ScheduleRepository(self._session)
        return self._schedule_repo


def get_repository_container(session: SessionDep) -> RepositoryContainer:
    """
    Get RepositoryContainer instance for dependency injection.

    Args:
        session: Database session from dependency injection

    Returns:
        RepositoryContainer: Container with all repositories
    """
    return RepositoryContainer(session)


# Type alias for container dependency injection
RepositoryContainerDep = Annotated[
    RepositoryContainer, Depends(get_repository_container)
]


# Example usage in FastAPI route handlers:
"""
from fastapi import APIRouter
from app.infrastructure.database.dependencies import JobRepositoryDep, TaskRepositoryDep

router = APIRouter()

@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, job_repo: JobRepositoryDep):
    job = job_repo.get_by_id_required(job_id)
    return job

@router.get("/jobs/{job_id}/tasks")
async def get_job_tasks(job_id: UUID, task_repo: TaskRepositoryDep):
    tasks = task_repo.find_by_job_id(job_id)
    return tasks

# Or use container for multiple repos
@router.get("/solve")
async def solve_schedule(repos: RepositoryContainerDep):
    jobs = repos.jobs.find_active_jobs()
    machines = repos.machines.find_available()
    operators = repos.operators.find_available()
    # ... scheduling logic
    return {"jobs": len(jobs), "machines": len(machines), "operators": len(operators)}
"""
