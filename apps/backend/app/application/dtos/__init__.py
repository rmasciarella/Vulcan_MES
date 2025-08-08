"""
Data Transfer Objects for application layer.

This module contains DTOs used for communication between the application layer
and external interfaces (API, UI, etc). DTOs provide a stable interface that
is independent of domain model changes.
"""

from .job_dtos import (
    CreateJobRequest,
    JobResponse,
    JobSummaryResponse,
    UpdateJobRequest,
)
from .scheduling_dtos import (
    CreateScheduleRequest,
    OptimizationRequest,
    OptimizationResponse,
    ScheduleResponse,
)
from .task_dtos import (
    CreateTaskRequest,
    TaskResponse,
    TaskSummaryResponse,
    UpdateTaskRequest,
)

__all__ = [
    # Job DTOs
    "CreateJobRequest",
    "UpdateJobRequest",
    "JobResponse",
    "JobSummaryResponse",
    # Task DTOs
    "CreateTaskRequest",
    "UpdateTaskRequest",
    "TaskResponse",
    "TaskSummaryResponse",
    # Scheduling DTOs
    "CreateScheduleRequest",
    "ScheduleResponse",
    "OptimizationRequest",
    "OptimizationResponse",
]
