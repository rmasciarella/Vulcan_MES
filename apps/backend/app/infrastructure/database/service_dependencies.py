"""
Service Dependencies for Domain Service Injection.

This module provides dependency injection for domain services, ensuring proper
repository and service wiring for FastAPI endpoints.
"""

from typing import Annotated

from fastapi import Depends

from app.application.services.job_service import JobService
from app.domain.scheduling.services.optimization_service import OptimizationService
from app.domain.scheduling.services.scheduling_service import SchedulingService
from app.infrastructure.adapters.repository_adapters import create_domain_repositories
from app.infrastructure.database.dependencies import (
    JobRepositoryDep,
    MachineRepositoryDep,
    OperatorRepositoryDep,
    ScheduleRepositoryDep,
    TaskRepositoryDep,
)


def get_job_service(
    job_repo: JobRepositoryDep,
    task_repo: TaskRepositoryDep,
) -> JobService:
    """Get Job Service with proper repository injection."""
    return JobService(
        job_repository=job_repo,
        task_repository=task_repo,
    )


def get_scheduling_service(
    job_repo: JobRepositoryDep,
    task_repo: TaskRepositoryDep,
    schedule_repo: ScheduleRepositoryDep,
    machine_repo: MachineRepositoryDep,
    operator_repo: OperatorRepositoryDep,
) -> SchedulingService:
    """Get Scheduling Service with proper repository injection."""
    # Create domain repository adapters
    domain_job_repo, domain_task_repo, domain_machine_repo, domain_operator_repo = (
        create_domain_repositories(job_repo, task_repo, machine_repo, operator_repo)
    )

    return SchedulingService(
        job_repository=domain_job_repo,
        task_repository=domain_task_repo,
        schedule_repository=schedule_repo,
        machine_repository=domain_machine_repo,
        operator_repository=domain_operator_repo,
    )


def get_optimization_service(
    job_repo: JobRepositoryDep,
    task_repo: TaskRepositoryDep,
    machine_repo: MachineRepositoryDep,
    operator_repo: OperatorRepositoryDep,
) -> OptimizationService:
    """Get Optimization Service with proper repository injection."""
    # Create domain repository adapters
    domain_job_repo, domain_task_repo, domain_machine_repo, domain_operator_repo = (
        create_domain_repositories(job_repo, task_repo, machine_repo, operator_repo)
    )

    return OptimizationService(
        job_repository=domain_job_repo,
        task_repository=domain_task_repo,
        machine_repository=domain_machine_repo,
        operator_repository=domain_operator_repo,
    )


# Type annotations for dependency injection
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
SchedulingServiceDep = Annotated[SchedulingService, Depends(get_scheduling_service)]
OptimizationServiceDep = Annotated[
    OptimizationService, Depends(get_optimization_service)
]
