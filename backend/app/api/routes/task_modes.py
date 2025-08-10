"""
Task Modes API endpoints.

This module provides API endpoints for querying task execution modes,
including different resource combinations and durations for tasks.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.infrastructure.database.models import TaskMode, TaskModePublic

router = APIRouter()


@router.get("/", response_model=List[TaskModePublic])
def get_task_modes(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    task_id: UUID | None = Query(None, description="Filter by task ID"),
    cell_resource_id: UUID | None = Query(None, description="Filter by cell resource ID"),
    machine_resource_id: UUID | None = Query(None, description="Filter by machine resource ID"),
    min_duration_minutes: int | None = Query(None, ge=0, description="Minimum duration in minutes"),
    max_duration_minutes: int | None = Query(None, ge=0, description="Maximum duration in minutes"),
) -> List[TaskModePublic]:
    """
    Get task modes with optional filtering.
    
    Returns a list of task execution modes that define different ways
    to execute tasks with various resource combinations and durations.
    """
    query = db.query(TaskMode)
    
    # Apply filters
    if task_id:
        query = query.filter(TaskMode.task_id == task_id)
    
    if cell_resource_id:
        query = query.filter(TaskMode.cell_resource_id == cell_resource_id)
        
    if machine_resource_id:
        query = query.filter(TaskMode.machine_resource_id == machine_resource_id)
    
    if min_duration_minutes is not None:
        min_intervals = min_duration_minutes // 15  # Convert to 15-minute intervals
        query = query.filter(TaskMode.duration_15minutes >= min_intervals)
    
    if max_duration_minutes is not None:
        max_intervals = max_duration_minutes // 15  # Convert to 15-minute intervals
        query = query.filter(TaskMode.duration_15minutes <= max_intervals)
    
    # Apply pagination and execute
    task_modes = query.offset(skip).limit(limit).all()
    
    return task_modes


@router.get("/{task_mode_id}", response_model=TaskModePublic)
def get_task_mode(
    task_mode_id: UUID,
    db: Session = Depends(get_db),
) -> TaskModePublic:
    """
    Get a specific task mode by ID.
    """
    task_mode = db.query(TaskMode).filter(TaskMode.id == task_mode_id).first()
    
    if not task_mode:
        raise HTTPException(
            status_code=404,
            detail=f"Task mode with ID {task_mode_id} not found"
        )
    
    return task_mode


@router.get("/task/{task_id}", response_model=List[TaskModePublic])
def get_task_modes_for_task(
    task_id: UUID,
    db: Session = Depends(get_db),
) -> List[TaskModePublic]:
    """
    Get all execution modes available for a specific task.
    
    This endpoint returns all the different ways a task can be executed,
    showing the various resource combinations and their expected durations.
    """
    task_modes = db.query(TaskMode).filter(TaskMode.task_id == task_id).all()
    
    if not task_modes:
        raise HTTPException(
            status_code=404,
            detail=f"No task modes found for task ID {task_id}"
        )
    
    return task_modes


@router.get("/machine/{machine_resource_id}", response_model=List[TaskModePublic])
def get_task_modes_for_machine(
    machine_resource_id: UUID,
    db: Session = Depends(get_db),
) -> List[TaskModePublic]:
    """
    Get all task modes that can be executed on a specific machine.
    
    This is useful for capacity planning and understanding which
    tasks can be assigned to a particular machine resource.
    """
    task_modes = db.query(TaskMode).filter(
        TaskMode.machine_resource_id == machine_resource_id
    ).all()
    
    return task_modes


@router.get("/cell/{cell_resource_id}", response_model=List[TaskModePublic])
def get_task_modes_for_cell(
    cell_resource_id: UUID,
    db: Session = Depends(get_db),
) -> List[TaskModePublic]:
    """
    Get all task modes that can be executed in a specific cell/production area.
    
    This is useful for understanding the workload and capacity
    requirements for a particular production cell.
    """
    task_modes = db.query(TaskMode).filter(
        TaskMode.cell_resource_id == cell_resource_id
    ).all()
    
    return task_modes


@router.get("/stats/summary")
def get_task_modes_summary(
    db: Session = Depends(get_db),
) -> dict:
    """
    Get summary statistics about task modes data.
    
    Returns aggregated information useful for analytics and reporting.
    """
    from sqlalchemy import func
    
    # Basic counts
    total_modes = db.query(TaskMode).count()
    unique_tasks = db.query(TaskMode.task_id).distinct().count()
    unique_cells = db.query(TaskMode.cell_resource_id).distinct().count()
    unique_machines = db.query(TaskMode.machine_resource_id).distinct().count()
    
    # Duration statistics
    duration_stats = db.query(
        func.min(TaskMode.duration_15minutes).label('min_intervals'),
        func.max(TaskMode.duration_15minutes).label('max_intervals'),
        func.avg(TaskMode.duration_15minutes).label('avg_intervals')
    ).first()
    
    return {
        "total_task_modes": total_modes,
        "unique_tasks": unique_tasks,
        "unique_cells": unique_cells,
        "unique_machines": unique_machines,
        "duration_stats": {
            "min_minutes": duration_stats.min_intervals * 15 if duration_stats.min_intervals else 0,
            "max_minutes": duration_stats.max_intervals * 15 if duration_stats.max_intervals else 0,
            "avg_minutes": float(duration_stats.avg_intervals) * 15 if duration_stats.avg_intervals else 0,
            "min_intervals": duration_stats.min_intervals or 0,
            "max_intervals": duration_stats.max_intervals or 0,
            "avg_intervals": float(duration_stats.avg_intervals) if duration_stats.avg_intervals else 0,
        }
    }