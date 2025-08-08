"""
Domain Integration Example API Routes.

This module demonstrates complete integration patterns between API endpoints,
domain services, repositories, and event handling. It serves as a reference
implementation showing best practices for clean architecture with FastAPI.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import CurrentUser
from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.schedule import Schedule
from app.domain.scheduling.events.domain_events import (
    JobCreated,
    JobStatusChanged,
    SchedulePublished,
    TaskScheduled,
)
from app.domain.scheduling.factories.job_factory import JobFactory
from app.domain.scheduling.services.constraint_validation_service import (
    ConstraintValidationService,
)
from app.domain.scheduling.services.optimization_service import OptimizationService
from app.domain.scheduling.services.resource_allocation_service import (
    ResourceAllocationService,
)
from app.domain.scheduling.services.schedule_validator import ScheduleValidator
from app.domain.scheduling.services.skill_matcher import SkillMatcher
from app.domain.scheduling.value_objects.business_calendar import BusinessCalendar
from app.domain.scheduling.value_objects.enums import JobStatus, PriorityLevel
from app.domain.shared.exceptions import BusinessRuleViolation, ValidationError
from app.infrastructure.adapters.repository_adapters import create_domain_repositories
from app.infrastructure.database.domain_unit_of_work import domain_transaction
from app.infrastructure.database.repositories import DatabaseError
from app.infrastructure.events.domain_event_publisher import (
    get_domain_event_publisher,
    publish_domain_events_async,
)

router = APIRouter(prefix="/domain-integration", tags=["domain-integration-examples"])


@router.post("/complete-workflow-example")
async def complete_scheduling_workflow(
    job_number: str,
    customer_name: str,
    due_date: datetime,
    operation_count: int = 50,
    current_user: CurrentUser = Depends(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    """
    Complete scheduling workflow example demonstrating full domain integration.
    
    This endpoint shows how to:
    1. Create jobs using domain factories
    2. Manage transactions with domain events
    3. Use domain services for complex business logic
    4. Handle errors and validation properly
    5. Publish events asynchronously
    """
    
    collected_events = []
    
    try:
        # Phase 1: Create Job with Domain Factory and Events
        async with domain_transaction() as uow:
            # Check if job number already exists
            existing_job = await uow.jobs.find_by_job_number(job_number)
            if existing_job:
                raise BusinessRuleViolation(f"Job number {job_number} already exists")

            # Create job using domain factory
            job = JobFactory.create_standard_job(
                job_number=job_number,
                operation_count=operation_count,
                priority=1,  # Normal priority
                due_date=due_date
            )
            
            # Additional job details
            job.customer_name = customer_name
            job.created_by = current_user.email
            
            # Save job
            await uow.jobs.save(job)
            
            # Create domain event for job creation
            job_created_event = JobCreated(
                job_id=job.id,
                job_number=job.job_number,
                priority=job.priority.value if hasattr(job.priority, 'value') else 1,
                due_date=job.due_date,
                release_date=datetime.utcnow(),
                task_count=len(job.get_tasks_in_sequence())
            )
            
            uow.add_domain_event(job_created_event)
            collected_events.append(job_created_event)

        # Phase 2: Create and Optimize Schedule
        async with domain_transaction() as uow:
            # Reload job to get fresh instance
            job = await uow.jobs.find_by_job_number_required(job_number)
            
            # Create schedule
            schedule = Schedule.create(
                name=f"Schedule for {job_number}",
                description=f"Production schedule for job {job_number}",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7),
                job_ids={job.id},
                created_by=current_user.id
            )
            
            await uow.schedules.save(schedule)

            # Create domain repository adapters for optimization service
            domain_repos = create_domain_repositories(
                uow.jobs, uow.tasks, uow.machines, uow.operators
            )
            job_repo, task_repo, machine_repo, operator_repo = domain_repos

            # Phase 3: Use Domain Services for Validation and Optimization
            
            # 3a. Skill Analysis
            skill_matcher = SkillMatcher()
            available_operators = await operator_repo.get_available_operators()
            available_machines = await machine_repo.get_available_machines()
            
            # Analyze skill coverage (simplified)
            skill_coverage = {}
            for operator in available_operators:
                for skill in getattr(operator, 'skills', []):
                    skill_type = str(skill.skill_type)
                    if skill_type not in skill_coverage:
                        skill_coverage[skill_type] = 0
                    skill_coverage[skill_type] += 1

            # 3b. Schedule Validation
            calendar = BusinessCalendar.standard_calendar()
            validator = ScheduleValidator(calendar)
            
            # Validate schedule constraints (simplified)
            validation_violations = []
            if not available_machines:
                validation_violations.append("No machines available")
            if not available_operators:
                validation_violations.append("No operators available")

            # 3c. Resource Allocation
            resource_allocator = ResourceAllocationService()
            
            # Create mock allocation for demonstration
            allocations = []
            tasks = job.get_tasks_in_sequence()
            
            for i, task in enumerate(tasks[:min(len(available_machines), len(tasks))]):
                if i < len(available_machines):
                    machine = available_machines[i % len(available_machines)]
                    operators = available_operators[:1] if available_operators else []
                    
                    # Create task assignment
                    start_time = schedule.start_date + timedelta(hours=i * 2)
                    end_time = start_time + timedelta(hours=1.5)
                    
                    allocations.append({
                        "task_id": task.id,
                        "job_id": job.id,
                        "machine_id": machine.id,
                        "operator_ids": [op.id for op in operators],
                        "start_time": start_time,
                        "end_time": end_time,
                    })

            # Phase 4: Create Task Scheduling Events
            task_events = []
            for allocation in allocations:
                task_event = TaskScheduled(
                    task_id=allocation["task_id"],
                    job_id=allocation["job_id"], 
                    machine_id=allocation["machine_id"],
                    operator_ids=allocation["operator_ids"],
                    planned_start=allocation["start_time"],
                    planned_end=allocation["end_time"]
                )
                task_events.append(task_event)

            # Add events to unit of work for atomic publishing
            uow.add_domain_events(task_events)
            collected_events.extend(task_events)

            # Phase 5: Update Job Status with Event
            old_status = job.status
            job.status = JobStatus.RELEASED
            await uow.jobs.save(job)

            job_status_event = JobStatusChanged(
                job_id=job.id,
                job_number=job.job_number,
                old_status=old_status.value if hasattr(old_status, 'value') else str(old_status),
                new_status=job.status.value,
                reason="Job released due to successful scheduling"
            )
            
            uow.add_domain_event(job_status_event)
            collected_events.append(job_status_event)

            # Phase 6: Schedule Publication Event
            schedule_event = SchedulePublished(
                schedule_id=schedule.id,
                version=1,
                effective_date=schedule.start_date,
                task_count=len(allocations),
                makespan_hours=len(allocations) * 1.5  # Simplified calculation
            )
            
            uow.add_domain_event(schedule_event)
            collected_events.append(schedule_event)

        # Phase 7: Background Processing for Additional Analytics
        background_tasks.add_task(
            _perform_post_scheduling_analytics,
            job.id,
            schedule.id,
            skill_coverage
        )

        # Return comprehensive response
        return {
            "success": True,
            "message": "Complete scheduling workflow executed successfully",
            "job": {
                "id": str(job.id),
                "job_number": job.job_number,
                "status": job.status.value,
                "customer_name": job.customer_name,
                "due_date": job.due_date.isoformat(),
                "task_count": len(tasks),
            },
            "schedule": {
                "id": str(schedule.id),
                "name": schedule.name,
                "status": schedule.status.value if hasattr(schedule.status, 'value') else str(schedule.status),
                "start_date": schedule.start_date.isoformat(),
                "end_date": schedule.end_date.isoformat(),
                "task_assignments_count": len(allocations),
            },
            "resource_analysis": {
                "available_machines": len(available_machines),
                "available_operators": len(available_operators),
                "skill_coverage": skill_coverage,
            },
            "validation": {
                "violations": validation_violations,
                "is_valid": len(validation_violations) == 0,
            },
            "events_published": len(collected_events),
            "domain_services_used": [
                "JobFactory",
                "SkillMatcher", 
                "ScheduleValidator",
                "ResourceAllocationService",
                "DomainEventPublisher"
            ],
            "infrastructure_patterns": [
                "Domain Unit of Work",
                "Repository Pattern with Adapters",
                "Domain Event Publishing",
                "Transaction Boundaries",
                "Background Tasks"
            ]
        }

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}"
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business rule violation: {e.message}"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}"
        )


@router.get("/domain-event-history")
async def get_domain_event_history(
    event_type: str | None = None,
    limit: int = 50,
    current_user: CurrentUser = Depends(),
) -> dict[str, Any]:
    """
    Get domain event history from the event bus.
    
    Demonstrates how to access published domain events for monitoring
    and debugging purposes.
    """
    try:
        publisher = get_domain_event_publisher()
        
        if event_type:
            # Convert string to event class (simplified)
            event_class_map = {
                "JobCreated": JobCreated,
                "JobStatusChanged": JobStatusChanged,
                "TaskScheduled": TaskScheduled,
                "SchedulePublished": SchedulePublished,
            }
            
            if event_type in event_class_map:
                events = publisher.get_event_history(event_class_map[event_type])
            else:
                events = []
        else:
            events = publisher.get_event_history()

        # Limit results
        events = events[-limit:] if len(events) > limit else events

        return {
            "total_events": len(events),
            "events": [
                {
                    "event_id": str(event.event_id),
                    "event_type": type(event).__name__,
                    "occurred_at": event.occurred_at.isoformat(),
                    "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
                    "event_data": _serialize_event_data(event),
                }
                for event in events
            ],
            "available_event_types": [
                "JobCreated", "JobStatusChanged", 
                "TaskScheduled", "SchedulePublished"
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving event history: {str(e)}"
        )


@router.post("/demonstrate-error-handling")
async def demonstrate_error_handling(
    should_fail: bool = True,
    failure_type: str = "validation",
    current_user: CurrentUser = Depends(),
) -> dict[str, Any]:
    """
    Demonstrate comprehensive error handling in domain-driven architecture.
    
    Shows how different types of errors are handled:
    - Validation errors
    - Business rule violations  
    - Database errors
    - Domain service errors
    """
    try:
        async with domain_transaction() as uow:
            if should_fail:
                if failure_type == "validation":
                    # Trigger validation error
                    raise ValidationError("Demonstration validation error")
                elif failure_type == "business_rule":
                    # Trigger business rule violation
                    raise BusinessRuleViolation("Demonstration business rule violation")
                elif failure_type == "database":
                    # Trigger database error
                    raise DatabaseError("Demonstration database error")
                else:
                    # Generic error
                    raise RuntimeError("Demonstration generic error")

            # If not failing, show successful transaction with events
            job = JobFactory.create_rush_job(
                job_number=f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                operation_count=10,
                due_hours=24
            )
            
            await uow.jobs.save(job)
            
            # Add demonstration event
            uow.add_domain_event(
                JobCreated(
                    job_id=job.id,
                    job_number=job.job_number,
                    priority=job.priority.value if hasattr(job.priority, 'value') else 2,
                    due_date=job.due_date,
                    release_date=datetime.utcnow(),
                    task_count=10
                )
            )

            return {
                "success": True,
                "message": "Error handling demonstration - no error occurred",
                "job_created": str(job.id),
                "transaction_committed": True,
                "events_will_be_published": True
            }

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_type": "ValidationError",
                "message": str(e),
                "handling": "Returned 400 Bad Request with validation details"
            }
        )
    except BusinessRuleViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_type": "BusinessRuleViolation", 
                "message": str(e),
                "handling": "Returned 409 Conflict with business rule details"
            }
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "DatabaseError",
                "message": str(e),
                "handling": "Returned 500 Internal Server Error with database error details"
            }
        )


# Background task functions

async def _perform_post_scheduling_analytics(
    job_id: UUID,
    schedule_id: UUID, 
    skill_coverage: dict[str, int]
) -> None:
    """
    Background task for post-scheduling analytics.
    
    Demonstrates how to perform complex analytics using domain services
    outside of the main request-response cycle.
    """
    try:
        async with domain_transaction() as uow:
            job = await uow.jobs.get_by_id_required(job_id)
            schedule = await uow.schedules.get_by_id_required(schedule_id)

            # Perform analytics using domain services
            analytics_results = {
                "job_complexity_score": _calculate_job_complexity(job),
                "resource_utilization_forecast": _forecast_resource_utilization(skill_coverage),
                "scheduling_efficiency_score": _calculate_scheduling_efficiency(job, schedule),
            }

            # Store results or publish additional events
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Post-scheduling analytics completed: {analytics_results}")

            # Could publish analytics completion event
            # analytics_event = AnalyticsCompleted(...)
            # await publish_domain_events_async([analytics_event])

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Post-scheduling analytics failed: {str(e)}")


# Helper functions

def _serialize_event_data(event) -> dict[str, Any]:
    """Serialize domain event data for API response."""
    event_dict = {}
    for attr_name in dir(event):
        if not attr_name.startswith('_') and not callable(getattr(event, attr_name)):
            attr_value = getattr(event, attr_name)
            if isinstance(attr_value, (str, int, float, bool, type(None))):
                event_dict[attr_name] = attr_value
            elif isinstance(attr_value, UUID):
                event_dict[attr_name] = str(attr_value)
            elif isinstance(attr_value, datetime):
                event_dict[attr_name] = attr_value.isoformat()
            elif isinstance(attr_value, list):
                event_dict[attr_name] = [str(item) if isinstance(item, UUID) else item for item in attr_value]
    return event_dict


def _calculate_job_complexity(job) -> float:
    """Calculate job complexity score based on various factors."""
    tasks = job.get_tasks_in_sequence()
    return len(tasks) * 0.1  # Simplified complexity calculation


def _forecast_resource_utilization(skill_coverage: dict[str, int]) -> dict[str, float]:
    """Forecast resource utilization based on skill coverage."""
    return {
        skill_type: min(count / 10.0 * 100, 100.0)  # Simplified forecast
        for skill_type, count in skill_coverage.items()
    }


def _calculate_scheduling_efficiency(job, schedule) -> float:
    """Calculate scheduling efficiency score."""
    # Simplified efficiency calculation
    task_count = len(job.get_tasks_in_sequence())
    time_span = (schedule.end_date - schedule.start_date).total_seconds() / 3600  # hours
    
    if time_span > 0:
        return min((task_count / time_span) * 10, 100.0)
    return 0.0