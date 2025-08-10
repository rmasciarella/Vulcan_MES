"""
Mapper for converting between Job domain entities and SQL entities.

This module provides mapping functionality to convert between Job domain entities
and their corresponding SQLModel database representations.
"""

from datetime import datetime
from uuid import UUID

from app.domain.scheduling.entities.job import Job as DomainJob
from app.domain.scheduling.value_objects.common import Quantity
from app.domain.scheduling.value_objects.enums import JobStatus, PriorityLevel
from app.infrastructure.database.sqlmodel_entities import Job as SQLJob
from app.infrastructure.database.sqlmodel_entities import (
    JobStatusEnum,
    PriorityLevelEnum,
)


class JobMapper:
    """
    Mapper class for converting between Job domain entities and SQL entities.

    Handles the translation of value objects, enums, and complex types between
    the domain layer and the database persistence layer.
    """

    @staticmethod
    def domain_to_sql(domain_job: DomainJob) -> SQLJob:
        """
        Convert domain Job entity to SQL Job entity.

        Args:
            domain_job: Domain job entity to convert

        Returns:
            SQL job entity
        """
        return SQLJob(
            id=JobMapper._map_uuid_to_int(domain_job.id) if domain_job.id else None,
            job_number=domain_job.job_number,
            customer_name=domain_job.customer_name,
            part_number=domain_job.part_number,
            quantity=domain_job.quantity.value,
            priority=PriorityLevelEnum(domain_job.priority.value),
            status=JobStatusEnum(domain_job.status.value),
            release_date=domain_job.release_date,
            due_date=domain_job.due_date,
            planned_start_date=domain_job.planned_start_date,
            planned_end_date=domain_job.planned_end_date,
            actual_start_date=domain_job.actual_start_date,
            actual_end_date=domain_job.actual_end_date,
            current_operation_sequence=domain_job.current_operation_sequence,
            notes=domain_job.notes,
            created_by=domain_job.created_by,
            created_at=domain_job.created_at,
            updated_at=domain_job.updated_at or datetime.utcnow(),
        )

    @staticmethod
    def sql_to_domain(sql_job: SQLJob) -> DomainJob:
        """
        Convert SQL Job entity to domain Job entity.

        Args:
            sql_job: SQL job entity to convert

        Returns:
            Domain job entity
        """
        domain_job = DomainJob(
            job_number=sql_job.job_number,
            customer_name=sql_job.customer_name,
            part_number=sql_job.part_number,
            quantity=Quantity(value=sql_job.quantity),
            priority=PriorityLevel(sql_job.priority.value),
            status=JobStatus(sql_job.status.value),
            release_date=sql_job.release_date,
            due_date=sql_job.due_date,
            planned_start_date=sql_job.planned_start_date,
            planned_end_date=sql_job.planned_end_date,
            actual_start_date=sql_job.actual_start_date,
            actual_end_date=sql_job.actual_end_date,
            current_operation_sequence=sql_job.current_operation_sequence or 0,
            notes=sql_job.notes,
            created_by=sql_job.created_by,
        )

        # Set timestamps and ID
        if sql_job.id:
            domain_job.id = JobMapper._map_int_to_uuid(sql_job.id)
        domain_job.created_at = sql_job.created_at
        domain_job.updated_at = sql_job.updated_at

        return domain_job

    @staticmethod
    def update_sql_from_domain(sql_job: SQLJob, domain_job: DomainJob) -> SQLJob:
        """
        Update SQL Job entity with data from domain Job entity.

        Args:
            sql_job: SQL job entity to update
            domain_job: Domain job entity with new data

        Returns:
            Updated SQL job entity
        """
        sql_job.job_number = domain_job.job_number
        sql_job.customer_name = domain_job.customer_name
        sql_job.part_number = domain_job.part_number
        sql_job.quantity = domain_job.quantity.value
        sql_job.priority = PriorityLevelEnum(domain_job.priority.value)
        sql_job.status = JobStatusEnum(domain_job.status.value)
        sql_job.release_date = domain_job.release_date
        sql_job.due_date = domain_job.due_date
        sql_job.planned_start_date = domain_job.planned_start_date
        sql_job.planned_end_date = domain_job.planned_end_date
        sql_job.actual_start_date = domain_job.actual_start_date
        sql_job.actual_end_date = domain_job.actual_end_date
        sql_job.current_operation_sequence = domain_job.current_operation_sequence
        sql_job.notes = domain_job.notes
        sql_job.created_by = domain_job.created_by
        sql_job.updated_at = datetime.utcnow()

        return sql_job

    @staticmethod
    def _map_uuid_to_int(uuid_id: UUID) -> int:
        """
        Map UUID to integer ID for database storage.

        This is a simplified mapping - in production you would want
        a proper UUID-to-integer mapping table or use UUIDs throughout.

        Args:
            uuid_id: UUID to convert

        Returns:
            Integer representation
        """
        return hash(str(uuid_id)) % (10**9)

    @staticmethod
    def _map_int_to_uuid(int_id: int) -> UUID:
        """
        Map integer ID back to UUID.

        This is a simplified mapping - in production you would want
        a proper integer-to-UUID mapping table.

        Args:
            int_id: Integer ID to convert

        Returns:
            UUID representation
        """
        # For now, generate a deterministic UUID based on the integer
        # In production, you'd maintain a proper mapping
        import hashlib

        namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # Standard namespace
        name = str(int_id)
        return UUID(bytes=hashlib.md5(f"{namespace}{name}".encode()).digest()[:16])
