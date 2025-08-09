"""
Repository for TaskTemplate entity.
Handles data access for task template configuration data imported from CSV.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.sqlmodel_entities import TaskTemplate
from .base import BaseRepository


class TaskTemplateRepository(BaseRepository[TaskTemplate]):
    """Repository for managing task templates."""

    def __init__(self, session: AsyncSession):
        super().__init__(TaskTemplate, session)

    async def find_by_task_id(self, task_id: str) -> Optional[TaskTemplate]:
        """Find a task template by its task_id."""
        result = await self.session.execute(
            select(TaskTemplate).where(TaskTemplate.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_department(self, department_id: str) -> List[TaskTemplate]:
        """Find all task templates for a specific department."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.department_id == department_id)
            .order_by(TaskTemplate.name)
        )
        return list(result.scalars().all())

    async def find_setup_tasks(self) -> List[TaskTemplate]:
        """Find all setup tasks."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.is_setup == True)
            .order_by(TaskTemplate.department_id, TaskTemplate.name)
        )
        return list(result.scalars().all())

    async def find_unattended_tasks(self) -> List[TaskTemplate]:
        """Find all unattended tasks."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.is_unattended == True)
            .order_by(TaskTemplate.department_id, TaskTemplate.name)
        )
        return list(result.scalars().all())

    async def find_by_sequence(self, sequence_id: str) -> List[TaskTemplate]:
        """Find all task templates in a specific sequence."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.sequence_id == sequence_id)
            .order_by(TaskTemplate.name)
        )
        return list(result.scalars().all())

    async def find_with_setup_relationships(self) -> List[TaskTemplate]:
        """Find task templates that have setup relationships."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.setup_for_task_id.isnot(None))
            .order_by(TaskTemplate.department_id, TaskTemplate.name)
        )
        return list(result.scalars().all())

    async def get_department_statistics(self) -> List[dict]:
        """Get statistics by department."""
        result = await self.session.execute(
            select(
                TaskTemplate.department_id,
                func.count(TaskTemplate.id).label('total_tasks'),
                func.sum(func.cast(TaskTemplate.is_setup, 'integer')).label('setup_tasks'),
                func.sum(func.cast(TaskTemplate.is_unattended, 'integer')).label('unattended_tasks'),
                func.avg(TaskTemplate.wip_limit).label('avg_wip_limit'),
                func.avg(TaskTemplate.max_batch_size).label('avg_batch_size')
            )
            .group_by(TaskTemplate.department_id)
            .order_by(TaskTemplate.department_id)
        )
        return [
            {
                'department_id': row.department_id,
                'total_tasks': row.total_tasks,
                'setup_tasks': row.setup_tasks or 0,
                'unattended_tasks': row.unattended_tasks or 0,
                'avg_wip_limit': float(row.avg_wip_limit) if row.avg_wip_limit else 0.0,
                'avg_batch_size': float(row.avg_batch_size) if row.avg_batch_size else 0.0
            }
            for row in result.all()
        ]

    async def get_setup_task_mappings(self) -> List[dict]:
        """Get setup task to production task mappings."""
        # Self-join to get setup task and its corresponding production task
        setup_task = TaskTemplate.__table__.alias('setup_task')
        prod_task = TaskTemplate.__table__.alias('prod_task')
        
        result = await self.session.execute(
            select(
                setup_task.c.task_id.label('setup_task_id'),
                setup_task.c.name.label('setup_task_name'),
                prod_task.c.task_id.label('production_task_id'),
                prod_task.c.name.label('production_task_name'),
                setup_task.c.department_id.label('department_id')
            )
            .select_from(
                setup_task.join(
                    prod_task,
                    setup_task.c.task_id == prod_task.c.setup_for_task_id
                )
            )
            .order_by(setup_task.c.department_id, setup_task.c.name)
        )
        
        return [
            {
                'setup_task_id': row.setup_task_id,
                'setup_task_name': row.setup_task_name,
                'production_task_id': row.production_task_id,
                'production_task_name': row.production_task_name,
                'department_id': row.department_id
            }
            for row in result.all()
        ]

    async def search_by_name(self, name_pattern: str) -> List[TaskTemplate]:
        """Search task templates by name pattern (case insensitive)."""
        result = await self.session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.name.ilike(f"%{name_pattern}%"))
            .order_by(TaskTemplate.department_id, TaskTemplate.name)
        )
        return list(result.scalars().all())