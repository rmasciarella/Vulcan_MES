"""
Schedule repository implementation providing CRUD and domain-specific operations.

This module implements the ScheduleRepository interface defined in the domain layer,
providing concrete database operations for Schedule entities using SQLModel.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import and_, or_, select

from app.domain.scheduling.entities.schedule import Schedule, ScheduleStatus
from app.domain.scheduling.repositories.schedule_repository import (
    ScheduleRepository as DomainScheduleRepository,
)
from app.infrastructure.database.models import (
    Schedule as ScheduleModel,
    ScheduleCreate,
    ScheduleUpdate,
)

from .base import BaseRepository, DatabaseError, EntityNotFoundError


class ScheduleRepository(BaseRepository[ScheduleModel, ScheduleCreate, ScheduleUpdate]):
    """
    Repository implementation for Schedule entities.

    Provides CRUD operations plus domain-specific queries for schedules,
    including status-based filtering and version management.
    """

    @property
    def entity_class(self):
        """Return the Schedule entity class."""
        return ScheduleModel

    async def find_by_version(self, version: int) -> ScheduleModel | None:
        """
        Find schedule by version number.

        Args:
            version: Version number to search for

        Returns:
            Schedule if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(ScheduleModel).where(ScheduleModel.version == version)
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding schedule by version {version}: {str(e)}"
            ) from e

    async def find_active(self, as_of: datetime | None = None) -> ScheduleModel | None:
        """
        Find active schedule for given date.

        Args:
            as_of: Date to check against (defaults to now)

        Returns:
            Active schedule if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        if as_of is None:
            as_of = datetime.utcnow()

        try:
            statement = select(ScheduleModel).where(
                and_(
                    ScheduleModel.status == ScheduleStatus.ACTIVE,
                    ScheduleModel.start_date <= as_of,
                    or_(
                        ScheduleModel.end_date >= as_of,
                        ScheduleModel.end_date.is_(None),
                    ),
                )
            )
            return self.session.exec(statement).first()
        except Exception as e:
            raise DatabaseError(
                f"Error finding active schedule as of {as_of}: {str(e)}"
            ) from e

    async def find_by_status(self, status: ScheduleStatus) -> list[ScheduleModel]:
        """
        Find all schedules with given status.

        Args:
            status: Schedule status to filter by

        Returns:
            List of schedules with the specified status

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(ScheduleModel).where(ScheduleModel.status == status)
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding schedules by status {status}: {str(e)}"
            ) from e

    async def find_with_filters(
        self, filters: dict[str, any], limit: int = 50, offset: int = 0
    ) -> list[ScheduleModel]:
        """
        Find schedules with flexible filtering.

        Args:
            filters: Dictionary of filter criteria
            limit: Maximum number of schedules to return
            offset: Number of schedules to skip

        Returns:
            List of filtered schedules

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(ScheduleModel)

            # Apply filters
            if "status" in filters:
                statement = statement.where(ScheduleModel.status == filters["status"])

            if "name" in filters:
                statement = statement.where(
                    ScheduleModel.name.ilike(f"%{filters['name']}%")
                )

            if "created_by" in filters:
                statement = statement.where(
                    ScheduleModel.created_by == filters["created_by"]
                )

            if "start_date_from" in filters:
                statement = statement.where(
                    ScheduleModel.start_date >= filters["start_date_from"]
                )

            if "start_date_to" in filters:
                statement = statement.where(
                    ScheduleModel.start_date <= filters["start_date_to"]
                )

            # Apply pagination
            statement = statement.offset(offset).limit(limit)

            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(f"Error finding schedules with filters: {str(e)}") from e

    async def create_new_version(
        self, base_schedule: ScheduleModel
    ) -> ScheduleModel:
        """
        Create new version from existing schedule.

        Args:
            base_schedule: Schedule to create new version from

        Returns:
            New schedule version

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Get next version number
            max_version_statement = select(ScheduleModel.version).order_by(
                ScheduleModel.version.desc()
            )
            max_version = self.session.exec(max_version_statement).first()
            next_version = (max_version or 0) + 1

            # Create new schedule with incremented version
            new_schedule = ScheduleModel(
                name=f"{base_schedule.name} v{next_version}",
                description=base_schedule.description,
                version=next_version,
                status=ScheduleStatus.DRAFT,
                start_date=base_schedule.start_date,
                end_date=base_schedule.end_date,
                job_ids=base_schedule.job_ids.copy() if base_schedule.job_ids else [],
                created_by=base_schedule.created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            return self.save(new_schedule)
        except Exception as e:
            raise DatabaseError(
                f"Error creating new schedule version: {str(e)}"
            ) from e

    async def get_schedule_statistics(self) -> dict:
        """
        Get statistics about schedules in the system.

        Returns:
            Dictionary with schedule statistics

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            from sqlalchemy import func

            # Count by status
            status_counts = {}
            for status in ScheduleStatus:
                count_statement = select(func.count(ScheduleModel.id)).where(
                    ScheduleModel.status == status
                )
                count = self.session.exec(count_statement).one()
                status_counts[status.value] = count

            # Active count
            active_count = status_counts.get(ScheduleStatus.ACTIVE.value, 0)

            # Published count (ready for activation)
            published_count = status_counts.get(ScheduleStatus.PUBLISHED.value, 0)

            return {
                "by_status": status_counts,
                "active_count": active_count,
                "published_count": published_count,
                "total_schedules": sum(status_counts.values()),
            }
        except Exception as e:
            raise DatabaseError(f"Error getting schedule statistics: {str(e)}") from e

    async def find_schedules_for_jobs(self, job_ids: list[UUID]) -> list[ScheduleModel]:
        """
        Find schedules that include any of the given jobs.

        Args:
            job_ids: List of job IDs to search for

        Returns:
            List of schedules that include the jobs

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # This would require proper JSONB querying for job_ids array
            # For now, get all schedules and filter in Python
            all_schedules = await self.get_all()
            matching_schedules = []

            for schedule in all_schedules:
                if schedule.job_ids and any(
                    job_id in schedule.job_ids for job_id in job_ids
                ):
                    matching_schedules.append(schedule)

            return matching_schedules
        except Exception as e:
            raise DatabaseError(
                f"Error finding schedules for jobs: {str(e)}"
            ) from e

    async def find_conflicting_schedules(
        self, start_date: datetime, end_date: datetime
    ) -> list[ScheduleModel]:
        """
        Find schedules that conflict with the given time window.

        Args:
            start_date: Start of time window
            end_date: End of time window

        Returns:
            List of conflicting schedules

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            statement = select(ScheduleModel).where(
                and_(
                    ScheduleModel.status.in_([ScheduleStatus.ACTIVE, ScheduleStatus.PUBLISHED]),
                    or_(
                        and_(
                            ScheduleModel.start_date <= start_date,
                            ScheduleModel.end_date >= start_date,
                        ),
                        and_(
                            ScheduleModel.start_date <= end_date,
                            ScheduleModel.end_date >= end_date,
                        ),
                        and_(
                            ScheduleModel.start_date >= start_date,
                            ScheduleModel.start_date <= end_date,
                        ),
                    ),
                )
            )
            return list(self.session.exec(statement).all())
        except Exception as e:
            raise DatabaseError(
                f"Error finding conflicting schedules: {str(e)}"
            ) from e


class DomainScheduleRepositoryAdapter(DomainScheduleRepository):
    """
    Adapter that bridges the infrastructure ScheduleRepository to the domain interface.

    This adapter translates between domain Schedule entities and database models,
    implementing the domain repository interface.
    """

    def __init__(self, infra_repo: ScheduleRepository):
        self._infra_repo = infra_repo

    async def save(self, schedule: Schedule) -> None:
        """Save schedule with all assignments."""
        # Convert domain entity to infrastructure model
        # This would need proper domain-to-model mapping
        await self._infra_repo.save(schedule)  # type: ignore

    async def find_by_id(self, schedule_id: UUID) -> Schedule | None:
        """Find schedule by ID."""
        model = await self._infra_repo.get_by_id(schedule_id)
        if not model:
            return None
        # Convert model to domain entity
        return model  # type: ignore - simplified

    async def find_by_version(self, version: int) -> Schedule | None:
        """Find schedule by version number."""
        model = await self._infra_repo.find_by_version(version)
        if not model:
            return None
        return model  # type: ignore - simplified

    async def find_active(self, as_of: datetime) -> Schedule | None:
        """Find active schedule for given date."""
        model = await self._infra_repo.find_active(as_of)
        if not model:
            return None
        return model  # type: ignore - simplified

    async def create_new_version(self, base_schedule: Schedule) -> Schedule:
        """Create new version from existing schedule."""
        new_model = await self._infra_repo.create_new_version(base_schedule)  # type: ignore
        return new_model  # type: ignore - simplified

    async def find_all(self) -> list[Schedule]:
        """Find all schedules."""
        models = await self._infra_repo.get_all()
        return models  # type: ignore - simplified

    async def delete(self, schedule_id: UUID) -> None:
        """Delete a schedule."""
        await self._infra_repo.delete(schedule_id)