"""
Repository Interfaces

Repository interfaces matching DOMAIN.md specification exactly.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.job import Job
from ..entities.machine import Machine
from ..entities.operator import Operator
from ..entities.schedule import Schedule
from ..entities.task import Task
from ..value_objects.enums import TaskStatus
from ..value_objects.skill_proficiency import SkillRequirement, SkillType
from ..value_objects.time_window import TimeWindow


class Repository(ABC):
    """Base repository interface - matches DOMAIN.md specification exactly."""

    @abstractmethod
    def save(self, entity) -> None:
        """Save an entity."""
        ...

    @abstractmethod
    def find_by_id(self, entity_id: UUID) -> object | None:
        """Find entity by ID."""
        ...

    @abstractmethod
    def find_all(self) -> list[object]:
        """Find all entities."""
        ...

    @abstractmethod
    def delete(self, entity_id: UUID) -> None:
        """Delete an entity."""
        ...


class JobRepository(ABC):
    """
    Repository interface for Job aggregate.
    Matches DOMAIN.md specification exactly.
    """

    @abstractmethod
    def save(self, job: Job) -> None:
        """Save job with all tasks."""
        ...

    @abstractmethod
    def find_by_id(self, job_id: UUID) -> Job | None:
        """Find job by ID with all tasks loaded."""
        ...

    @abstractmethod
    def find_by_job_number(self, job_number: str) -> Job | None:
        """Find job by job number."""
        ...

    @abstractmethod
    def find_by_status(self, status: TaskStatus) -> list[Job]:
        """Find jobs containing tasks with given status."""
        ...

    @abstractmethod
    def find_overdue(self, as_of: datetime) -> list[Job]:
        """Find jobs past their due date."""
        ...

    @abstractmethod
    def find_all(self) -> list[Job]:
        """Find all jobs."""
        ...

    @abstractmethod
    def delete(self, job_id: UUID) -> None:
        """Delete a job."""
        ...


class MachineRepository(ABC):
    """
    Repository interface for Machine entities.
    Matches DOMAIN.md specification exactly.
    """

    @abstractmethod
    def save(self, machine: Machine) -> None:
        """Save machine."""
        ...

    @abstractmethod
    def find_by_id(self, machine_id: UUID) -> Machine | None:
        """Find machine by ID."""
        ...

    @abstractmethod
    def find_by_zone(self, zone: str) -> list[Machine]:
        """Find machines in a zone."""
        ...

    @abstractmethod
    def find_available(self, time_window: TimeWindow) -> list[Machine]:
        """Find machines available during time window."""
        ...

    @abstractmethod
    def find_by_skill_requirement(self, skill: SkillRequirement) -> list[Machine]:
        """Find machines requiring specific skill."""
        ...

    @abstractmethod
    def find_all(self) -> list[Machine]:
        """Find all machines."""
        ...

    @abstractmethod
    def delete(self, machine_id: UUID) -> None:
        """Delete a machine."""
        ...


class OperatorRepository(ABC):
    """
    Repository interface for Operator aggregate.
    Matches DOMAIN.md specification exactly.
    """

    @abstractmethod
    def save(self, operator: Operator) -> None:
        """Save operator with skills."""
        ...

    @abstractmethod
    def find_by_id(self, operator_id: UUID) -> Operator | None:
        """Find operator by ID."""
        ...

    @abstractmethod
    def find_by_employee_id(self, employee_id: str) -> Operator | None:
        """Find operator by employee ID."""
        ...

    @abstractmethod
    def find_by_skill(self, skill_type: SkillType, min_level: int) -> list[Operator]:
        """Find operators with skill at minimum level."""
        ...

    @abstractmethod
    def find_available(self, time_window: TimeWindow) -> list[Operator]:
        """Find operators available during time window."""
        ...

    @abstractmethod
    def find_all(self) -> list[Operator]:
        """Find all operators."""
        ...

    @abstractmethod
    def delete(self, operator_id: UUID) -> None:
        """Delete an operator."""
        ...


class ScheduleRepository(ABC):
    """
    Repository interface for Schedule aggregate.
    Matches DOMAIN.md specification exactly.
    """

    @abstractmethod
    def save(self, schedule: Schedule) -> None:
        """Save schedule with all assignments."""
        ...

    @abstractmethod
    def find_by_id(self, schedule_id: UUID) -> Schedule | None:
        """Find schedule by ID."""
        ...

    @abstractmethod
    def find_by_version(self, version: int) -> Schedule | None:
        """Find schedule by version number."""
        ...

    @abstractmethod
    def find_active(self, as_of: datetime) -> Schedule | None:
        """Find active schedule for given date."""
        ...

    @abstractmethod
    def create_new_version(self, base_schedule: Schedule) -> Schedule:
        """Create new version from existing schedule."""
        ...

    @abstractmethod
    def find_all(self) -> list[Schedule]:
        """Find all schedules."""
        ...

    @abstractmethod
    def delete(self, schedule_id: UUID) -> None:
        """Delete a schedule."""
        ...


class TaskRepository(ABC):
    """
    Repository interface for Task entities.
    Extends base functionality with task-specific queries.
    """

    @abstractmethod
    def save(self, task: Task) -> None:
        """Save task."""
        ...

    @abstractmethod
    def find_by_id(self, task_id: UUID) -> Task | None:
        """Find task by ID."""
        ...

    @abstractmethod
    def find_by_job_id(self, job_id: UUID) -> list[Task]:
        """Find all tasks for a job."""
        ...

    @abstractmethod
    def find_by_status(self, status: TaskStatus) -> list[Task]:
        """Find tasks by status."""
        ...

    @abstractmethod
    def find_ready_to_schedule(self) -> list[Task]:
        """Find tasks ready to be scheduled."""
        ...

    @abstractmethod
    def find_critical_tasks(self) -> list[Task]:
        """Find all critical path tasks."""
        ...

    @abstractmethod
    def find_overdue_tasks(self, as_of: datetime) -> list[Task]:
        """Find tasks that are overdue."""
        ...

    @abstractmethod
    def find_by_machine(self, machine_id: UUID) -> list[Task]:
        """Find tasks assigned to a machine."""
        ...

    @abstractmethod
    def find_by_operator(self, operator_id: UUID) -> list[Task]:
        """Find tasks assigned to an operator."""
        ...

    @abstractmethod
    def find_predecessors(self, task_id: UUID) -> list[Task]:
        """Find predecessor tasks for a given task."""
        ...

    @abstractmethod
    def find_successors(self, task_id: UUID) -> list[Task]:
        """Find successor tasks for a given task."""
        ...

    @abstractmethod
    def find_all(self) -> list[Task]:
        """Find all tasks."""
        ...

    @abstractmethod
    def delete(self, task_id: UUID) -> None:
        """Delete a task."""
        ...
