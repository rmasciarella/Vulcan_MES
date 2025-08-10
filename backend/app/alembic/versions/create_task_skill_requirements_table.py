"""Create task_skill_requirements table

Revision ID: b7e8c4d1f2a3
Revises: 1a31ce608336
Create Date: 2025-08-08 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from uuid import uuid4

# revision identifiers, used by Alembic.
revision = "b7e8c4d1f2a3"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade():
    # Create the task_skill_requirements table
    op.create_table(
        'task_skill_requirements',
        sa.Column('id', sa.UUID(), default=uuid4, primary_key=True, nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('skill_type_id', sa.UUID(), nullable=False),
        sa.Column('minimum_level', sa.Integer(), nullable=False, default=1),
        sa.Column('is_required', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Foreign key constraints
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_type_id'], ['skill_types.id'], ondelete='CASCADE'),
        
        # Ensure unique combination of task and skill
        sa.UniqueConstraint('task_id', 'skill_type_id', name='uq_task_skill_requirements_task_skill'),
        
        # Indexes for performance
        sa.Index('ix_task_skill_requirements_task_id', 'task_id'),
        sa.Index('ix_task_skill_requirements_skill_type_id', 'skill_type_id'),
    )


def downgrade():
    op.drop_table('task_skill_requirements')