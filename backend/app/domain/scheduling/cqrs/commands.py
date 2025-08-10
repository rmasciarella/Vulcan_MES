"""
Command definitions for scheduling domain CQRS implementation.

Commands represent write operations that modify the scheduling domain state.
They are processed by command handlers and generate domain events.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class Command(BaseModel, ABC):
    """Base class for all commands."""
    
    command_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    
    class Config:
        frozen = True  # Commands are immutable


class CommandResult(BaseModel):
    """Result of command execution."""
    
    command_id: UUID
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    events_generated: int = Field(default=0, ge=0)
    processing_time_ms: float = Field(default=0.0, ge=0.0)


class ScheduleTaskCommand(Command):
    """Command to schedule a task with specific timing and resources."""
    
    task_id: UUID
    start_time: datetime
    end_time: datetime
    
    # Resource assignments
    machine_id: Optional[UUID] = None
    operator_ids: List[UUID] = Field(default_factory=list)
    
    # Scheduling context
    job_id: Optional[UUID] = None
    priority: float = Field(default=1.0, ge=0.0, le=10.0)
    force_assignment: bool = False  # Override resource conflicts
    
    # Metadata
    reason: str = "manual_scheduling"
    notes: Optional[str] = None


class RescheduleTaskCommand(Command):
    """Command to reschedule an existing task."""
    
    task_id: UUID
    new_start_time: datetime
    new_end_time: datetime
    
    # Optional resource changes
    new_machine_id: Optional[UUID] = None
    new_operator_ids: Optional[List[UUID]] = None
    
    # Rescheduling context
    reason: str = "manual_reschedule"
    cascade_dependencies: bool = True  # Reschedule dependent tasks
    notify_stakeholders: bool = False
    
    # Impact analysis
    acceptable_delay_minutes: int = Field(default=0, ge=0)
    max_cascade_depth: int = Field(default=5, ge=1, le=20)


class AssignResourceCommand(Command):
    """Command to assign or reassign resources to a task."""
    
    task_id: UUID
    
    # Resource assignments
    machine_id: Optional[UUID] = None
    operator_ids: List[UUID] = Field(default_factory=list)
    
    # Assignment preferences
    assignment_type: str = "manual"  # manual, optimized, emergency
    override_conflicts: bool = False
    validate_skills: bool = True
    
    # Context
    reason: str = "resource_assignment"
    effective_date: Optional[datetime] = None


class OptimizeScheduleCommand(Command):
    """Command to trigger schedule optimization."""
    
    # Optimization scope
    job_ids: Optional[List[UUID]] = None
    task_ids: Optional[List[UUID]] = None
    department: Optional[str] = None
    
    # Time horizon
    optimization_start: datetime
    optimization_end: datetime
    
    # Optimization parameters
    objective: str = "minimize_makespan"  # minimize_makespan, minimize_delay, maximize_utilization
    max_optimization_time_seconds: float = Field(default=300.0, ge=30.0, le=1800.0)
    solution_quality_target: float = Field(default=0.95, ge=0.5, le=1.0)
    
    # Constraints
    respect_fixed_assignments: bool = True
    allow_overtime: bool = False
    max_overtime_hours: float = Field(default=2.0, ge=0.0, le=8.0)
    
    # Execution preferences
    apply_immediately: bool = False
    create_scenario: bool = False
    scenario_name: Optional[str] = None


class CreateJobCommand(Command):
    """Command to create a new job with tasks."""
    
    job_type: str
    department: str = "general"
    
    # Job metadata
    name: str = ""
    description: Optional[str] = None
    priority: float = Field(default=1.0, ge=0.0, le=10.0)
    due_date: Optional[datetime] = None
    
    # Task definitions
    operation_sequences: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Routing preferences
    preferred_machines: Dict[str, UUID] = Field(default_factory=dict)  # operation_type -> machine_id
    preferred_operators: Dict[str, UUID] = Field(default_factory=dict)  # operation_type -> operator_id


class UpdateTaskStatusCommand(Command):
    """Command to update task status and execution details."""
    
    task_id: UUID
    new_status: str  # PENDING, READY, SCHEDULED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    
    # Status-specific data
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    completion_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    # Quality and performance data
    quality_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    rework_required: bool = False
    rework_reason: Optional[str] = None
    
    # Context
    operator_id: Optional[UUID] = None  # Who performed the status update
    notes: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)  # File paths or URLs


class HandleResourceDisruptionCommand(Command):
    """Command to handle resource disruptions (breakdowns, absences, etc.)."""
    
    disruption_type: str  # machine_breakdown, operator_absence, material_shortage
    affected_resource_ids: List[UUID]
    
    # Disruption timeline
    disruption_start: datetime
    disruption_end: Optional[datetime] = None  # None for unknown duration
    
    # Impact scope
    affected_task_ids: List[UUID] = Field(default_factory=list)
    affected_job_ids: List[UUID] = Field(default_factory=list)
    
    # Response strategy
    response_strategy: str = "reoptimize"  # reoptimize, manual_reassign, delay_acceptance
    max_delay_acceptable_hours: float = Field(default=4.0, ge=0.0)
    
    # Communication
    notify_stakeholders: bool = True
    escalation_threshold_hours: float = Field(default=2.0, ge=0.0)


class BatchScheduleCommand(Command):
    """Command to schedule multiple tasks as a batch operation."""
    
    task_assignments: List[Dict[str, Any]] = Field(default_factory=list)
    # Each assignment: {task_id, start_time, end_time, machine_id?, operator_ids?}
    
    # Batch preferences
    validation_mode: str = "strict"  # strict, permissive
    rollback_on_failure: bool = True
    max_failures_allowed: int = Field(default=0, ge=0)
    
    # Optimization
    optimize_batch: bool = False
    batch_optimization_objective: str = "minimize_total_makespan"


class CreateResourceCommand(Command):
    """Command to create new resources (machines, operators)."""
    
    resource_type: str  # machine, operator
    resource_data: Dict[str, Any]
    
    # Resource configuration
    department: str = "general"
    is_active: bool = True
    
    # Capabilities
    capabilities: List[str] = Field(default_factory=list)
    capacity_limits: Dict[str, int] = Field(default_factory=dict)
    
    # Scheduling integration
    auto_assign_tasks: bool = False
    preferred_task_types: List[str] = Field(default_factory=list)


class UpdateResourceCommand(Command):
    """Command to update resource configuration."""
    
    resource_id: UUID
    resource_type: str  # machine, operator
    
    # Updates
    updates: Dict[str, Any] = Field(default_factory=dict)
    
    # Update scope
    update_capabilities: bool = False
    update_availability: bool = False
    update_assignments: bool = False
    
    # Cascading effects
    reschedule_affected_tasks: bool = False
    notify_affected_jobs: bool = False


# Command validation helpers
def validate_time_window(start_time: datetime, end_time: datetime, field_name: str = "time_window"):
    """Validate that start time is before end time."""
    if start_time >= end_time:
        raise ValueError(f"{field_name}: start_time must be before end_time")


def validate_resource_availability(resource_ids: List[UUID], resource_type: str, time_window: tuple):
    """Validate resource availability (would need repository access)."""
    # This would be implemented in command handlers with repository access
    pass


# Command factory functions
def create_emergency_reschedule_command(
    task_id: UUID,
    delay_hours: float,
    reason: str,
    user_id: Optional[UUID] = None
) -> RescheduleTaskCommand:
    """Create a command for emergency rescheduling."""
    # This would calculate new times based on current task schedule
    # Simplified implementation
    new_start = datetime.utcnow() + timedelta(hours=delay_hours)
    new_end = new_start + timedelta(hours=1)  # Default 1 hour duration
    
    return RescheduleTaskCommand(
        task_id=task_id,
        new_start_time=new_start,
        new_end_time=new_end,
        reason=reason,
        cascade_dependencies=True,
        user_id=user_id
    )


def create_optimization_command_for_department(
    department: str,
    optimization_hours: int = 24,
    user_id: Optional[UUID] = None
) -> OptimizeScheduleCommand:
    """Create optimization command for entire department."""
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=optimization_hours)
    
    return OptimizeScheduleCommand(
        department=department,
        optimization_start=start_time,
        optimization_end=end_time,
        objective="minimize_makespan",
        max_optimization_time_seconds=300.0,
        user_id=user_id
    )