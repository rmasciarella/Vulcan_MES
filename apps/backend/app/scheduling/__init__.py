"""
Vulcan Engine Scheduling Module

This module provides comprehensive scheduling optimization capabilities using
OR-Tools CP-SAT solver for complex manufacturing and resource allocation problems.

Key Components:
- solvers: Core scheduling algorithms and optimization engines
- models: Data models for tasks, resources, schedules, and constraints
- algorithms: Optimization algorithms and heuristics
"""

from typing import TYPE_CHECKING

# Avoid importing heavy submodules at package import time to keep imports light and prevent
# cascading type-checking errors. When type checking, import symbols for editor support.
if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .models.resource import (
        Resource,
        ResourceCreate,
        ResourcePublic,
        ResourceUpdate,
    )
    from .models.schedule import (
        Schedule,
        ScheduleCreate,
        SchedulePublic,
        ScheduleUpdate,
    )
    from .models.task import Task, TaskCreate, TaskPublic, TaskUpdate

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
