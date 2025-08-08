"""
Scheduling Data Models

Contains Pydantic models for representing scheduling entities including
tasks, resources, schedules, constraints, and optimization results.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from .resource import Resource, ResourceCreate, ResourcePublic, ResourceUpdate
    from .schedule import (
        Schedule,
        ScheduleCreate,
        SchedulePublic,
        ScheduleUpdate,
    )
    from .task import Task, TaskCreate, TaskPublic, TaskUpdate

__all__ = [
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "TaskPublic",
    "Resource",
    "ResourceCreate",
    "ResourceUpdate",
    "ResourcePublic",
    "Schedule",
    "ScheduleCreate",
    "ScheduleUpdate",
    "SchedulePublic",
]
