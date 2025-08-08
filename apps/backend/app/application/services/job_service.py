"""
Job application service for coordinating job-related use cases.

This service orchestrates job operations across the domain layer,
managing transactions and coordinating with other services.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.services.scheduling_service import SchedulingService
from app.domain.scheduling.value_objects.enums import JobStatus, PriorityLevel
from app.infrastructure.database.unit_of_work import transaction
from app.infrastructure.events.event_publisher import get_event_publisher

from ..dtos.job_dtos import (
    CreateJobRequest,
    JobResponse,
    JobSummaryResponse,
    UpdateJobRequest,
)
from ..mappers.job_mappers import JobDTOMapper
from .base_service import ApplicationServiceBase


class JobApplicationService(ApplicationServiceBase):
    """
    Application service for job-related operations.

    Coordinates job creation, updates, scheduling, and status management
    while maintaining transactional integrity and publishing domain events.
    """

    def __init__(
        self, unit_of_work_factory, scheduling_service: SchedulingService | None = None
    ):
        """
        Initialize the job application service.

        Args:
            unit_of_work_factory: Factory for creating unit of work instances
            scheduling_service: Optional scheduling domain service
        """
        super().__init__(unit_of_work_factory)
        self._scheduling_service = scheduling_service or SchedulingService()
        self._event_publisher = get_event_publisher()
        self._dto_mapper = JobDTOMapper()

    def create_job(self, request: CreateJobRequest) -> JobResponse:
        """
        Create a new job.

        Args:
            request: Job creation request DTO

        Returns:
            Created job response DTO

        Raises:
            ValidationError: If request data is invalid
            BusinessRuleViolation: If business rules are violated
            DatabaseError: If database operation fails
        """
        self.validate_request(request)

        with transaction() as uow:
            # Check for duplicate job number
            existing_job = uow.jobs.get_job_by_number(request.job_number)
            if existing_job:
                raise self.validation_error(
                    f"Job with number {request.job_number} already exists"
                )

            # Create domain job
            job = Job.create(
                job_number=request.job_number,
                due_date=request.due_date,
                customer_name=request.customer_name,
                part_number=request.part_number,
                quantity=request.quantity,
                priority=PriorityLevel(request.priority),
                created_by=request.created_by,
            )

            # Validate business rules
            if not job.is_valid():
                raise self.business_rule_violation("Job validation failed")

            # Save job
            created_job = uow.jobs.create_job(job)

            # Publish domain events
            self._event_publisher.publish_events(created_job)

            return self._dto_mapper.job_to_response(created_job)

    def get_job_by_id(self, job_id: UUID) -> JobResponse | None:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job response DTO or None if not found
        """
        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                return None

            return self._dto_mapper.job_to_response(job)

    def get_job_by_number(self, job_number: str) -> JobResponse | None:
        """
        Get job by job number.

        Args:
            job_number: Job number to search for

        Returns:
            Job response DTO or None if not found
        """
        self.validate_non_empty_string(job_number, "job_number")

        with transaction() as uow:
            job = uow.jobs.get_job_by_number(job_number)
            if not job:
                return None

            return self._dto_mapper.job_to_response(job)

    def update_job(self, job_id: UUID, request: UpdateJobRequest) -> JobResponse:
        """
        Update an existing job.

        Args:
            job_id: Job identifier
            request: Job update request DTO

        Returns:
            Updated job response DTO

        Raises:
            EntityNotFoundError: If job not found
            ValidationError: If request data is invalid
            BusinessRuleViolation: If business rules are violated
        """
        self.validate_request(request)

        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Update job fields
            if request.customer_name is not None:
                job.customer_name = request.customer_name
            if request.part_number is not None:
                job.part_number = request.part_number
            if request.quantity is not None:
                job.quantity.value = request.quantity
            if request.priority is not None:
                job.adjust_priority(
                    PriorityLevel(request.priority),
                    request.change_reason or "api_update",
                )
            if request.due_date is not None:
                if request.due_date != job.due_date:
                    job.extend_due_date(
                        request.due_date, request.change_reason or "api_update"
                    )
            if request.notes is not None:
                job.notes = request.notes

            # Validate updated job
            if not job.is_valid():
                raise self.business_rule_violation("Updated job validation failed")

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)

    def change_job_status(
        self, job_id: UUID, new_status: str, reason: str = "status_change"
    ) -> JobResponse:
        """
        Change job status.

        Args:
            job_id: Job identifier
            new_status: New job status
            reason: Reason for status change

        Returns:
            Updated job response DTO
        """
        self.validate_non_empty_string(new_status, "new_status")
        self.validate_non_empty_string(reason, "reason")

        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Change status
            job.change_status(JobStatus(new_status), reason)

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)

    def release_job(self, job_id: UUID, reason: str = "manual_release") -> JobResponse:
        """
        Release a job for execution.

        Args:
            job_id: Job identifier
            reason: Reason for release

        Returns:
            Updated job response DTO
        """
        return self.change_job_status(job_id, JobStatus.RELEASED.value, reason)

    def put_job_on_hold(self, job_id: UUID, reason: str) -> JobResponse:
        """
        Put a job on hold.

        Args:
            job_id: Job identifier
            reason: Reason for hold

        Returns:
            Updated job response DTO
        """
        self.validate_non_empty_string(reason, "reason")

        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Put on hold
            job.put_on_hold(reason)

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)

    def release_job_from_hold(
        self, job_id: UUID, reason: str = "released_from_hold"
    ) -> JobResponse:
        """
        Release a job from hold.

        Args:
            job_id: Job identifier
            reason: Reason for release from hold

        Returns:
            Updated job response DTO
        """
        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Release from hold
            job.release_from_hold(reason)

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)

    def cancel_job(self, job_id: UUID, reason: str) -> JobResponse:
        """
        Cancel a job.

        Args:
            job_id: Job identifier
            reason: Reason for cancellation

        Returns:
            Updated job response DTO
        """
        self.validate_non_empty_string(reason, "reason")

        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Cancel job
            job.cancel(reason)

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)

    def delete_job(self, job_id: UUID) -> bool:
        """
        Delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        with transaction() as uow:
            return uow.jobs.delete_job(job_id)

    def get_jobs_by_status(self, statuses: list[str]) -> list[JobResponse]:
        """
        Get jobs by status.

        Args:
            statuses: List of job statuses

        Returns:
            List of job response DTOs
        """
        if not statuses:
            raise self.validation_error("At least one status must be provided")

        # Validate statuses
        job_statuses = []
        for status in statuses:
            try:
                job_statuses.append(JobStatus(status))
            except ValueError:
                raise self.validation_error(f"Invalid job status: {status}")

        with transaction() as uow:
            jobs = uow.jobs.get_jobs_by_status(job_statuses)
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_active_jobs(self) -> list[JobResponse]:
        """
        Get all active jobs.

        Returns:
            List of active job response DTOs
        """
        with transaction() as uow:
            jobs = uow.jobs.get_active_jobs()
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_overdue_jobs(self) -> list[JobResponse]:
        """
        Get all overdue jobs.

        Returns:
            List of overdue job response DTOs
        """
        with transaction() as uow:
            jobs = uow.jobs.get_overdue_jobs()
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_jobs_due_within_days(self, days: int) -> list[JobResponse]:
        """
        Get jobs due within specified number of days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of job response DTOs
        """
        if days < 0:
            raise self.validation_error("Days must be non-negative")

        with transaction() as uow:
            jobs = uow.jobs.get_jobs_due_within_days(days)
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_jobs_by_priority(
        self, priority: str, limit: int | None = None
    ) -> list[JobResponse]:
        """
        Get jobs by priority level.

        Args:
            priority: Priority level
            limit: Optional limit on results

        Returns:
            List of job response DTOs
        """
        try:
            priority_level = PriorityLevel(priority)
        except ValueError:
            raise self.validation_error(f"Invalid priority level: {priority}")

        if limit is not None and limit <= 0:
            raise self.validation_error("Limit must be positive")

        with transaction() as uow:
            jobs = uow.jobs.get_jobs_by_priority(priority_level, limit)
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_jobs_by_customer(self, customer_name: str) -> list[JobResponse]:
        """
        Get jobs for a specific customer.

        Args:
            customer_name: Customer name to search for

        Returns:
            List of job response DTOs
        """
        self.validate_non_empty_string(customer_name, "customer_name")

        with transaction() as uow:
            jobs = uow.jobs.get_jobs_by_customer(customer_name)
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def search_jobs(
        self, search_term: str, limit: int | None = None
    ) -> list[JobResponse]:
        """
        Search jobs by job number, customer, or part number.

        Args:
            search_term: Term to search for
            limit: Optional limit on results

        Returns:
            List of matching job response DTOs
        """
        self.validate_non_empty_string(search_term, "search_term")

        if limit is not None and limit <= 0:
            raise self.validation_error("Limit must be positive")

        with transaction() as uow:
            jobs = uow.jobs.search_jobs(search_term, limit)
            return [self._dto_mapper.job_to_response(job) for job in jobs]

    def get_job_statistics(self) -> dict[str, Any]:
        """
        Get job statistics for dashboard.

        Returns:
            Dictionary with job statistics
        """
        with transaction() as uow:
            return uow.jobs.get_job_statistics()

    def get_job_summary(self, job_id: UUID) -> JobSummaryResponse | None:
        """
        Get job summary information.

        Args:
            job_id: Job identifier

        Returns:
            Job summary response DTO or None if not found
        """
        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                return None

            return self._dto_mapper.job_to_summary_response(job)

    def update_job_schedule(
        self,
        job_id: UUID,
        planned_start: datetime | None,
        planned_end: datetime | None,
        reason: str = "schedule_update",
    ) -> JobResponse:
        """
        Update job schedule.

        Args:
            job_id: Job identifier
            planned_start: New planned start date
            planned_end: New planned end date
            reason: Reason for schedule change

        Returns:
            Updated job response DTO
        """
        with transaction() as uow:
            job = uow.jobs.get_job_by_id(job_id)
            if not job:
                raise self.entity_not_found_error(f"Job with ID {job_id} not found")

            # Update schedule
            job.update_schedule(planned_start, planned_end, reason)

            # Save job
            updated_job = uow.jobs.update_job(job)

            # Publish domain events
            self._event_publisher.publish_events(updated_job)

            return self._dto_mapper.job_to_response(updated_job)
