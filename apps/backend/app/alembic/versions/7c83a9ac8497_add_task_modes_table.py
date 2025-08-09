"""Add task_modes table

Revision ID: 7c83a9ac8497
Revises: 1a31ce608336
Create Date: 2025-01-08 16:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7c83a9ac8497'
down_revision = '1a31ce608336'
branch_labels = None
depends_on = None


def upgrade():
    # Create task_modes table
    op.create_table(
        'task_modes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cell_resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('machine_resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('duration_15minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Add constraints
        sa.CheckConstraint('duration_15minutes >= 0', name='check_duration_15minutes_non_negative'),
        
        # Add indexes
        sa.Index('ix_task_modes_task_id', 'task_id'),
        sa.Index('ix_task_modes_cell_resource_id', 'cell_resource_id'),
        sa.Index('ix_task_modes_machine_resource_id', 'machine_resource_id'),
        
        # Add foreign key constraint if tasks table exists
        # Note: We're not adding FK constraint as the referenced tables might not exist yet
        # sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_task_modes_task_id'),
    )


def downgrade():
    # Drop task_modes table
    op.drop_table('task_modes')