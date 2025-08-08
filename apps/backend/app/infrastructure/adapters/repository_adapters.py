"""
Repository Adapters

Adapts infrastructure repository implementations to domain repository interfaces
for use with the optimization service and other domain services.
"""

from datetime import datetime
from uuid import UUID

from app.domain.scheduling.entities.job import Job as DomainJob
from app.domain.scheduling.entities.machine import Machine as DomainMachine
from app.domain.scheduling.entities.operator import Operator as DomainOperator
from app.domain.scheduling.entities.task import Task as DomainTask
from app.domain.scheduling.repositories.job_repository import (
    JobRepository as DomainJobRepository,
)
from app.domain.scheduling.repositories.machine_repository import (
    MachineRepository as DomainMachineRepository,
)
from app.domain.scheduling.repositories.operator_repository import (
    OperatorRepository as DomainOperatorRepository,
)
from app.domain.scheduling.repositories.task_repository import (
    TaskRepository as DomainTaskRepository,
)
from app.infrastructure.database.repositories import (
    JobRepository as InfraJobRepository,
)
from app.infrastructure.database.repositories import (
    MachineRepository as InfraMachineRepository,
)
from app.infrastructure.database.repositories import (
    OperatorRepository as InfraOperatorRepository,
)
from app.infrastructure.database.repositories import (
    TaskRepository as InfraTaskRepository,
)


class JobRepositoryAdapter(DomainJobRepository):
    """Adapter that bridges infrastructure JobRepository to domain interface."""

    def __init__(self, infra_repo: InfraJobRepository):
        self._infra_repo = infra_repo

    async def save(self, job: DomainJob) -> DomainJob:
        # Convert domain entity to infrastructure model
        # This is simplified - would need proper mapping
        saved = await self._infra_repo.save(job)  # type: ignore
        return saved  # type: ignore

    async def get_by_id(self, job_id: UUID) -> DomainJob | None:
        job = await self._infra_repo.get_by_id(job_id)
        # Convert infrastructure model to domain entity
        return job  # type: ignore - simplified

    async def get_all(self) -> list[DomainJob]:
        jobs = await self._infra_repo.get_all()
        return jobs  # type: ignore - simplified

    async def get_by_customer_id(self, customer_id: UUID) -> list[DomainJob]:
        # Infrastructure might not have this method - implement as needed
        jobs = await self._infra_repo.get_all()
        return [
            job
            for job in jobs
            if hasattr(job, "customer_id") and job.customer_id == customer_id
        ]  # type: ignore

    async def get_active_jobs(self) -> list[DomainJob]:
        jobs = await self._infra_repo.find_active_jobs()
        return jobs  # type: ignore - simplified

    async def get_jobs_due_before(self, due_date: datetime) -> list[DomainJob]:
        # Infrastructure might not have this method - implement filter
        all_jobs = await self._infra_repo.get_all()
        return [
            job
            for job in all_jobs
            if hasattr(job, "due_date") and job.due_date and job.due_date < due_date
        ]  # type: ignore

    async def get_jobs_by_priority(self, priority: int) -> list[DomainJob]:
        # Infrastructure might not have this method - implement filter
        all_jobs = await self._infra_repo.get_all()
        return [
            job
            for job in all_jobs
            if hasattr(job, "priority") and job.priority == priority
        ]  # type: ignore

    async def update(self, job: DomainJob) -> DomainJob:
        updated = await self._infra_repo.update(job.id, job)  # type: ignore
        return updated  # type: ignore

    async def delete(self, job_id: UUID) -> bool:
        return await self._infra_repo.delete(job_id)

    async def exists(self, job_id: UUID) -> bool:
        job = await self._infra_repo.get_by_id(job_id)
        return job is not None

    async def count(self) -> int:
        jobs = await self._infra_repo.get_all()
        return len(jobs)

    async def count_by_status(self, is_active: bool) -> int:
        if is_active:
            jobs = await self._infra_repo.find_active_jobs()
        else:
            # Get all jobs and filter inactive
            all_jobs = await self._infra_repo.get_all()
            jobs = [job for job in all_jobs if not getattr(job, "is_active", True)]
        return len(jobs)


class TaskRepositoryAdapter(DomainTaskRepository):
    """Adapter that bridges infrastructure TaskRepository to domain interface."""

    def __init__(self, infra_repo: InfraTaskRepository):
        self._infra_repo = infra_repo

    async def save(self, task: DomainTask) -> DomainTask:
        saved = await self._infra_repo.save(task)  # type: ignore
        return saved  # type: ignore

    async def get_by_id(self, task_id: UUID) -> DomainTask | None:
        task = await self._infra_repo.get_by_id(task_id)
        return task  # type: ignore

    async def get_all(self) -> list[DomainTask]:
        tasks = await self._infra_repo.get_all()
        return tasks  # type: ignore

    async def get_by_job_id(self, job_id: UUID) -> list[DomainTask]:
        tasks = await self._infra_repo.find_by_job_id(job_id)
        return tasks  # type: ignore

    async def get_ready_tasks(self) -> list[DomainTask]:
        tasks = await self._infra_repo.find_ready_tasks()
        return tasks  # type: ignore

    async def get_scheduled_tasks(self) -> list[DomainTask]:
        tasks = await self._infra_repo.find_scheduled_tasks()
        return tasks  # type: ignore

    async def get_active_tasks(self) -> list[DomainTask]:
        tasks = await self._infra_repo.find_active_tasks()
        return tasks  # type: ignore

    async def get_tasks_by_status(self, status: str) -> list[DomainTask]:
        # Filter by status - simplified implementation
        all_tasks = await self._infra_repo.get_all()
        return [task for task in all_tasks if getattr(task, "status", None) == status]  # type: ignore

    async def get_tasks_in_sequence_range(
        self, start_seq: int, end_seq: int
    ) -> list[DomainTask]:
        all_tasks = await self._infra_repo.get_all()
        return [
            task
            for task in all_tasks
            if hasattr(task, "sequence_in_job")
            and start_seq <= task.sequence_in_job <= end_seq  # type: ignore
        ]

    async def update(self, task: DomainTask) -> DomainTask:
        updated = await self._infra_repo.update(task.id, task)  # type: ignore
        return updated  # type: ignore

    async def delete(self, task_id: UUID) -> bool:
        return await self._infra_repo.delete(task_id)

    async def exists(self, task_id: UUID) -> bool:
        task = await self._infra_repo.get_by_id(task_id)
        return task is not None

    async def count(self) -> int:
        tasks = await self._infra_repo.get_all()
        return len(tasks)

    async def count_by_job(self, job_id: UUID) -> int:
        tasks = await self._infra_repo.find_by_job_id(job_id)
        return len(tasks)


class MachineRepositoryAdapter(DomainMachineRepository):
    """Adapter that bridges infrastructure MachineRepository to domain interface."""

    def __init__(self, infra_repo: InfraMachineRepository):
        self._infra_repo = infra_repo

    async def save(self, machine: DomainMachine) -> DomainMachine:
        saved = await self._infra_repo.save(machine)  # type: ignore
        return saved  # type: ignore

    async def get_by_id(self, machine_id: UUID) -> DomainMachine | None:
        machine = await self._infra_repo.get_by_id(machine_id)
        return machine  # type: ignore

    async def get_all(self) -> list[DomainMachine]:
        machines = await self._infra_repo.get_all()
        return machines  # type: ignore

    async def get_available_machines(self) -> list[DomainMachine]:
        machines = await self._infra_repo.find_available()
        return machines  # type: ignore

    async def get_machines_by_capability(self, capability: str) -> list[DomainMachine]:
        # Filter by capability - simplified
        all_machines = await self._infra_repo.get_all()
        return [
            machine
            for machine in all_machines
            if hasattr(machine, "capabilities")
            and capability in getattr(machine, "capabilities", [])  # type: ignore
        ]

    async def get_machines_in_zone(self, zone_id: UUID) -> list[DomainMachine]:
        all_machines = await self._infra_repo.get_all()
        return [
            machine
            for machine in all_machines
            if hasattr(machine, "production_zone_id")
            and machine.production_zone_id == zone_id  # type: ignore
        ]

    async def update(self, machine: DomainMachine) -> DomainMachine:
        updated = await self._infra_repo.update(machine.id, machine)  # type: ignore
        return updated  # type: ignore

    async def delete(self, machine_id: UUID) -> bool:
        return await self._infra_repo.delete(machine_id)

    async def exists(self, machine_id: UUID) -> bool:
        machine = await self._infra_repo.get_by_id(machine_id)
        return machine is not None

    async def count(self) -> int:
        machines = await self._infra_repo.get_all()
        return len(machines)


class OperatorRepositoryAdapter(DomainOperatorRepository):
    """Adapter that bridges infrastructure OperatorRepository to domain interface."""

    def __init__(self, infra_repo: InfraOperatorRepository):
        self._infra_repo = infra_repo

    async def save(self, operator: DomainOperator) -> DomainOperator:
        saved = await self._infra_repo.save(operator)  # type: ignore
        return saved  # type: ignore

    async def get_by_id(self, operator_id: UUID) -> DomainOperator | None:
        operator = await self._infra_repo.get_by_id(operator_id)
        return operator  # type: ignore

    async def get_all(self) -> list[DomainOperator]:
        operators = await self._infra_repo.get_all()
        return operators  # type: ignore

    async def get_available_operators(self) -> list[DomainOperator]:
        operators = await self._infra_repo.find_available()
        return operators  # type: ignore

    async def get_operators_by_skill(
        self, skill_id: UUID, min_level: int = 1
    ) -> list[DomainOperator]:
        # Filter by skill - simplified
        all_operators = await self._infra_repo.get_all()
        return [
            operator
            for operator in all_operators
            if hasattr(operator, "skills")
            and any(
                skill.skill_id == skill_id and skill.level >= min_level
                for skill in getattr(operator, "skills", [])  # type: ignore
            )
        ]

    async def get_operators_on_shift(
        self, shift_start: datetime, shift_end: datetime
    ) -> list[DomainOperator]:
        # Simplified - would need proper shift logic
        available_operators = await self._infra_repo.find_available()
        return available_operators  # type: ignore

    async def update(self, operator: DomainOperator) -> DomainOperator:
        updated = await self._infra_repo.update(operator.id, operator)  # type: ignore
        return updated  # type: ignore

    async def delete(self, operator_id: UUID) -> bool:
        return await self._infra_repo.delete(operator_id)

    async def exists(self, operator_id: UUID) -> bool:
        operator = await self._infra_repo.get_by_id(operator_id)
        return operator is not None

    async def count(self) -> int:
        operators = await self._infra_repo.get_all()
        return len(operators)


def create_domain_repositories(
    job_repo: InfraJobRepository,
    task_repo: InfraTaskRepository,
    machine_repo: InfraMachineRepository,
    operator_repo: InfraOperatorRepository,
) -> tuple[
    DomainJobRepository,
    DomainTaskRepository,
    DomainMachineRepository,
    DomainOperatorRepository,
]:
    """
    Create domain repository adapters from infrastructure repositories.

    Args:
        job_repo: Infrastructure job repository
        task_repo: Infrastructure task repository
        machine_repo: Infrastructure machine repository
        operator_repo: Infrastructure operator repository

    Returns:
        Tuple of domain repository adapters
    """
    return (
        JobRepositoryAdapter(job_repo),
        TaskRepositoryAdapter(task_repo),
        MachineRepositoryAdapter(machine_repo),
        OperatorRepositoryAdapter(operator_repo),
    )
