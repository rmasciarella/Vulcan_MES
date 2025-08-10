"""
API routes for Task Templates.
Provides access to task template configuration data imported from CSV.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.infrastructure.database.repositories.task_template_repository import TaskTemplateRepository
from app.infrastructure.database.sqlmodel_entities import TaskTemplate

router = APIRouter()


@router.get("/", response_model=List[TaskTemplate])
async def get_task_templates(
    department_id: Optional[str] = Query(None, description="Filter by department ID"),
    is_setup: Optional[bool] = Query(None, description="Filter by setup tasks"),
    is_unattended: Optional[bool] = Query(None, description="Filter by unattended tasks"),
    sequence_id: Optional[str] = Query(None, description="Filter by sequence ID"),
    search: Optional[str] = Query(None, description="Search in task names"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
):
    """Get task templates with optional filters."""
    repo = TaskTemplateRepository(db)
    
    if department_id:
        templates = await repo.find_by_department(department_id)
    elif is_setup is True:
        templates = await repo.find_setup_tasks()
    elif is_unattended is True:
        templates = await repo.find_unattended_tasks()
    elif sequence_id:
        templates = await repo.find_by_sequence(sequence_id)
    elif search:
        templates = await repo.search_by_name(search)
    else:
        templates = await repo.get_all()
    
    # Apply pagination
    return templates[skip:skip + limit]


@router.get("/departments", response_model=List[dict])
async def get_department_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Get task template statistics by department."""
    repo = TaskTemplateRepository(db)
    return await repo.get_department_statistics()


@router.get("/setup-mappings", response_model=List[dict])
async def get_setup_task_mappings(
    db: AsyncSession = Depends(get_db),
):
    """Get setup task to production task mappings."""
    repo = TaskTemplateRepository(db)
    return await repo.get_setup_task_mappings()


@router.get("/{task_id}", response_model=TaskTemplate)
async def get_task_template(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific task template by task_id."""
    repo = TaskTemplateRepository(db)
    template = await repo.find_by_task_id(task_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    
    return template


@router.get("/departments/{department_id}", response_model=List[TaskTemplate])
async def get_department_tasks(
    department_id: str,
    include_setup: bool = Query(True, description="Include setup tasks"),
    include_production: bool = Query(True, description="Include production tasks"),
    db: AsyncSession = Depends(get_db),
):
    """Get all task templates for a specific department."""
    repo = TaskTemplateRepository(db)
    templates = await repo.find_by_department(department_id)
    
    if not include_setup:
        templates = [t for t in templates if not t.is_setup]
    
    if not include_production:
        templates = [t for t in templates if t.is_setup]
    
    return templates


@router.get("/sequences/{sequence_id}", response_model=List[TaskTemplate])
async def get_sequence_tasks(
    sequence_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all task templates in a specific sequence."""
    repo = TaskTemplateRepository(db)
    templates = await repo.find_by_sequence(sequence_id)
    
    if not templates:
        raise HTTPException(status_code=404, detail="No tasks found for this sequence")
    
    return templates