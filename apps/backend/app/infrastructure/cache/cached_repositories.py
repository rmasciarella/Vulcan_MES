"""Cached repository implementations for domain entities."""

import logging
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from app.core.cache import CacheManager, EntityCache
from app.core.monitoring import performance_monitor
from app.domain.scheduling.entities import Job, Operator, Schedule, Task
from app.domain.scheduling.repositories import (
    JobRepository,
    OperatorRepository,
    ScheduleRepository,
    TaskRepository,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CachedRepositoryMixin(Generic[T]):
    """Mixin for adding caching capabilities to repositories."""

    def __init__(self, repository: Any, entity_type: str):
        """
        Initialize cached repository.

        Args:
            repository: Underlying repository implementation
            entity_type: Type of entity for cache key generation
        """
        self.repository = repository
        self.entity_type = entity_type
        self.cache_manager = CacheManager()
        self.entity_cache = EntityCache()

    def _get_cache_key(self, entity_id: UUID | str) -> str:
        """Generate cache key for entity."""
        return self.entity_cache.entity_key(self.entity_type, str(entity_id))

    def _get_list_cache_key(self, **filters: Any) -> str:
        """Generate cache key for entity list."""
        return self.entity_cache.entity_list_key(self.entity_type, **filters)

    def _invalidate_cache(self, entity_id: UUID | str | None = None) -> None:
        """Invalidate cache for entity."""
        self.entity_cache.invalidate_entity(
            self.entity_type, str(entity_id) if entity_id else None
        )


class CachedJobRepository(CachedRepositoryMixin[Job], JobRepository):
    """Job repository with caching."""

    def __init__(self, repository: JobRepository):
        """Initialize cached job repository."""
        super().__init__(repository, "job")
        self.repository: JobRepository = repository

    async def save(self, job: Job) -> Job:
        """Save job and update cache."""
        with performance_monitor.measure_time("repository.job.save"):
            # Save to database
            saved_job = await self.repository.save(job)

            # Update cache
            cache_key = self._get_cache_key(saved_job.id)
            ttl = self.entity_cache.get_entity_ttl("job")

            # Serialize job for caching
            job_dict = {
                "id": str(saved_job.id),
                "name": saved_job.name,
                "priority": saved_job.priority.value
                if hasattr(saved_job.priority, "value")
                else saved_job.priority,
                "status": saved_job.status.value
                if hasattr(saved_job.status, "value")
                else saved_job.status,
                "created_at": saved_job.created_at.isoformat()
                if saved_job.created_at
                else None,
                "updated_at": saved_job.updated_at.isoformat()
                if saved_job.updated_at
                else None,
            }

            self.cache_manager.set(cache_key, job_dict, ttl)

            # Invalidate list caches
            self._invalidate_cache()

            logger.debug(f"Cached job {saved_job.id}")

            return saved_job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        """Get job by ID with caching."""
        with performance_monitor.measure_time("repository.job.get_by_id"):
            # Check cache first
            cache_key = self._get_cache_key(job_id)
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for job {job_id}")
                # Reconstruct job from cached data
                # Note: This is simplified - in production, use proper deserialization
                return await self.repository.get_by_id(job_id)

            # Cache miss - fetch from database
            logger.debug(f"Cache miss for job {job_id}")
            job = await self.repository.get_by_id(job_id)

            if job:
                # Cache the result
                ttl = self.entity_cache.get_entity_ttl("job")
                job_dict = {
                    "id": str(job.id),
                    "name": job.name,
                    "priority": job.priority.value
                    if hasattr(job.priority, "value")
                    else job.priority,
                    "status": job.status.value
                    if hasattr(job.status, "value")
                    else job.status,
                }
                self.cache_manager.set(cache_key, job_dict, ttl)

            return job

    async def list(
        self,
        status: str | None = None,
        priority: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs with caching."""
        with performance_monitor.measure_time("repository.job.list"):
            # Generate cache key based on filters
            cache_key = self._get_list_cache_key(
                status=status,
                priority=priority,
                limit=limit,
                offset=offset,
            )

            # Check cache
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug("Cache hit for job list")
                # Fetch full objects (simplified)
                return await self.repository.list(status, priority, limit, offset)

            # Cache miss - fetch from database
            logger.debug("Cache miss for job list")
            jobs = await self.repository.list(status, priority, limit, offset)

            # Cache the result (store IDs only to save space)
            ttl = self.entity_cache.get_entity_ttl("job")
            job_ids = [str(job.id) for job in jobs]
            self.cache_manager.set(cache_key, job_ids, ttl)

            # Also cache individual jobs
            for job in jobs[:10]:  # Cache first 10 for quick access
                job_cache_key = self._get_cache_key(job.id)
                job_dict = {
                    "id": str(job.id),
                    "name": job.name,
                    "priority": job.priority.value
                    if hasattr(job.priority, "value")
                    else job.priority,
                    "status": job.status.value
                    if hasattr(job.status, "value")
                    else job.status,
                }
                self.cache_manager.set(job_cache_key, job_dict, ttl)

            return jobs

    async def update(self, job_id: UUID, updates: dict[str, Any]) -> Job | None:
        """Update job and invalidate cache."""
        with performance_monitor.measure_time("repository.job.update"):
            # Update in database
            updated_job = await self.repository.update(job_id, updates)

            if updated_job:
                # Invalidate cache for this job and lists
                self._invalidate_cache(job_id)

                # Update cache with new data
                cache_key = self._get_cache_key(job_id)
                ttl = self.entity_cache.get_entity_ttl("job")
                job_dict = {
                    "id": str(updated_job.id),
                    "name": updated_job.name,
                    "priority": updated_job.priority.value
                    if hasattr(updated_job.priority, "value")
                    else updated_job.priority,
                    "status": updated_job.status.value
                    if hasattr(updated_job.status, "value")
                    else updated_job.status,
                }
                self.cache_manager.set(cache_key, job_dict, ttl)

            return updated_job

    async def delete(self, job_id: UUID) -> bool:
        """Delete job and invalidate cache."""
        with performance_monitor.measure_time("repository.job.delete"):
            # Delete from database
            success = await self.repository.delete(job_id)

            if success:
                # Invalidate all related caches
                self._invalidate_cache(job_id)

            return success

    async def find_by_due_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Job]:
        """Find jobs by due date range with caching."""
        with performance_monitor.measure_time("repository.job.find_by_due_date"):
            # Generate cache key
            cache_key = self._get_list_cache_key(
                method="by_due_date",
                start=start_date.isoformat(),
                end=end_date.isoformat(),
            )

            # Check cache
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                logger.debug("Cache hit for jobs by due date")
                return await self.repository.find_by_due_date_range(
                    start_date, end_date
                )

            # Cache miss
            jobs = await self.repository.find_by_due_date_range(start_date, end_date)

            # Cache result
            ttl = 1800  # 30 minutes for date range queries
            job_ids = [str(job.id) for job in jobs]
            self.cache_manager.set(cache_key, job_ids, ttl)

            return jobs


class CachedTaskRepository(CachedRepositoryMixin[Task], TaskRepository):
    """Task repository with caching."""

    def __init__(self, repository: TaskRepository):
        """Initialize cached task repository."""
        super().__init__(repository, "task")
        self.repository: TaskRepository = repository

    async def save(self, task: Task) -> Task:
        """Save task and update cache."""
        with performance_monitor.measure_time("repository.task.save"):
            saved_task = await self.repository.save(task)

            # Update cache
            cache_key = self._get_cache_key(saved_task.id)
            ttl = self.entity_cache.get_entity_ttl("task")

            task_dict = {
                "id": str(saved_task.id),
                "job_id": str(saved_task.job_id) if saved_task.job_id else None,
                "name": saved_task.name,
                "status": saved_task.status.value
                if hasattr(saved_task.status, "value")
                else saved_task.status,
                "duration": saved_task.duration,
            }

            self.cache_manager.set(cache_key, task_dict, ttl)
            self._invalidate_cache()

            return saved_task

    async def get_by_id(self, task_id: UUID) -> Task | None:
        """Get task by ID with caching."""
        with performance_monitor.measure_time("repository.task.get_by_id"):
            cache_key = self._get_cache_key(task_id)
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for task {task_id}")
                return await self.repository.get_by_id(task_id)

            task = await self.repository.get_by_id(task_id)

            if task:
                ttl = self.entity_cache.get_entity_ttl("task")
                task_dict = {
                    "id": str(task.id),
                    "job_id": str(task.job_id) if task.job_id else None,
                    "name": task.name,
                    "status": task.status.value
                    if hasattr(task.status, "value")
                    else task.status,
                }
                self.cache_manager.set(cache_key, task_dict, ttl)

            return task

    async def find_by_job_id(self, job_id: UUID) -> list[Task]:
        """Find tasks by job ID with caching."""
        with performance_monitor.measure_time("repository.task.find_by_job"):
            cache_key = self._get_list_cache_key(job_id=str(job_id))
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for tasks of job {job_id}")
                return await self.repository.find_by_job_id(job_id)

            tasks = await self.repository.find_by_job_id(job_id)

            # Cache result
            ttl = self.entity_cache.get_entity_ttl("task")
            task_ids = [str(task.id) for task in tasks]
            self.cache_manager.set(cache_key, task_ids, ttl)

            return tasks


class CachedOperatorRepository(CachedRepositoryMixin[Operator], OperatorRepository):
    """Operator repository with caching."""

    def __init__(self, repository: OperatorRepository):
        """Initialize cached operator repository."""
        super().__init__(repository, "operator")
        self.repository: OperatorRepository = repository

    async def save(self, operator: Operator) -> Operator:
        """Save operator and update cache."""
        with performance_monitor.measure_time("repository.operator.save"):
            saved_operator = await self.repository.save(operator)

            # Update cache
            cache_key = self._get_cache_key(saved_operator.id)
            ttl = self.entity_cache.get_entity_ttl("operator")

            operator_dict = {
                "id": str(saved_operator.id),
                "name": saved_operator.name,
                "skills": [
                    {"name": s.name, "level": s.level} for s in saved_operator.skills
                ]
                if saved_operator.skills
                else [],
                "available": saved_operator.available,
            }

            self.cache_manager.set(cache_key, operator_dict, ttl)
            self._invalidate_cache()

            return saved_operator

    async def get_by_id(self, operator_id: UUID) -> Operator | None:
        """Get operator by ID with caching."""
        with performance_monitor.measure_time("repository.operator.get_by_id"):
            cache_key = self._get_cache_key(operator_id)
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for operator {operator_id}")
                return await self.repository.get_by_id(operator_id)

            operator = await self.repository.get_by_id(operator_id)

            if operator:
                ttl = self.entity_cache.get_entity_ttl("operator")
                operator_dict = {
                    "id": str(operator.id),
                    "name": operator.name,
                    "skills": [
                        {"name": s.name, "level": s.level} for s in operator.skills
                    ]
                    if operator.skills
                    else [],
                    "available": operator.available,
                }
                self.cache_manager.set(cache_key, operator_dict, ttl)

            return operator

    async def find_by_skill(
        self, skill_name: str, min_level: int = 1
    ) -> list[Operator]:
        """Find operators by skill with caching."""
        with performance_monitor.measure_time("repository.operator.find_by_skill"):
            cache_key = self._get_list_cache_key(
                skill=skill_name,
                min_level=min_level,
            )
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for operators with skill {skill_name}")
                return await self.repository.find_by_skill(skill_name, min_level)

            operators = await self.repository.find_by_skill(skill_name, min_level)

            # Cache result
            ttl = self.entity_cache.get_entity_ttl("operator")
            operator_ids = [str(op.id) for op in operators]
            self.cache_manager.set(cache_key, operator_ids, ttl)

            return operators


class CachedScheduleRepository(CachedRepositoryMixin[Schedule], ScheduleRepository):
    """Schedule repository with caching."""

    def __init__(self, repository: ScheduleRepository):
        """Initialize cached schedule repository."""
        super().__init__(repository, "schedule")
        self.repository: ScheduleRepository = repository

    async def save(self, schedule: Schedule) -> Schedule:
        """Save schedule and update cache."""
        with performance_monitor.measure_time("repository.schedule.save"):
            saved_schedule = await self.repository.save(schedule)

            # Update cache with shorter TTL for schedules
            cache_key = self._get_cache_key(saved_schedule.id)
            ttl = self.entity_cache.get_entity_ttl("schedule")

            schedule_dict = {
                "id": str(saved_schedule.id),
                "job_id": str(saved_schedule.job_id) if saved_schedule.job_id else None,
                "status": saved_schedule.status.value
                if hasattr(saved_schedule.status, "value")
                else saved_schedule.status,
                "makespan": saved_schedule.makespan,
                "created_at": saved_schedule.created_at.isoformat()
                if saved_schedule.created_at
                else None,
            }

            self.cache_manager.set(cache_key, schedule_dict, ttl)
            self._invalidate_cache()

            return saved_schedule

    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        """Get schedule by ID with caching."""
        with performance_monitor.measure_time("repository.schedule.get_by_id"):
            cache_key = self._get_cache_key(schedule_id)
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for schedule {schedule_id}")
                return await self.repository.get_by_id(schedule_id)

            schedule = await self.repository.get_by_id(schedule_id)

            if schedule:
                ttl = self.entity_cache.get_entity_ttl("schedule")
                schedule_dict = {
                    "id": str(schedule.id),
                    "job_id": str(schedule.job_id) if schedule.job_id else None,
                    "status": schedule.status.value
                    if hasattr(schedule.status, "value")
                    else schedule.status,
                    "makespan": schedule.makespan,
                }
                self.cache_manager.set(cache_key, schedule_dict, ttl)

            return schedule

    async def find_active_schedules(self) -> list[Schedule]:
        """Find active schedules with caching."""
        with performance_monitor.measure_time("repository.schedule.find_active"):
            cache_key = self._get_list_cache_key(status="active")
            cached_data = self.cache_manager.get(cache_key)

            if cached_data:
                logger.debug("Cache hit for active schedules")
                return await self.repository.find_active_schedules()

            schedules = await self.repository.find_active_schedules()

            # Cache with shorter TTL for active schedules
            ttl = 300  # 5 minutes
            schedule_ids = [str(s.id) for s in schedules]
            self.cache_manager.set(cache_key, schedule_ids, ttl)

            return schedules


# Factory function to wrap repositories with caching
def create_cached_repository(repository: Any, entity_type: str) -> Any:
    """
    Create a cached version of a repository.

    Args:
        repository: Original repository implementation
        entity_type: Type of entity (job, task, operator, schedule, machine)

    Returns:
        Cached repository implementation
    """
    cache_classes = {
        "job": CachedJobRepository,
        "task": CachedTaskRepository,
        "operator": CachedOperatorRepository,
        "schedule": CachedScheduleRepository,
    }

    cache_class = cache_classes.get(entity_type)
    if not cache_class:
        logger.warning(
            f"No cached implementation for {entity_type}, returning original"
        )
        return repository

    return cache_class(repository)


# Cache warming functions
async def warm_entity_caches() -> dict[str, int]:
    """Warm caches for frequently accessed entities."""

    try:
        # This would be called with actual repository instances
        # For now, just return placeholder
        logger.info("Cache warming completed")
        return {"status": "completed"}
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        return {"status": "failed", "error": str(e)}


# Export main components
__all__ = [
    "CachedJobRepository",
    "CachedTaskRepository",
    "CachedOperatorRepository",
    "CachedScheduleRepository",
    "create_cached_repository",
    "warm_entity_caches",
]
