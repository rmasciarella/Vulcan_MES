"""add work_cells table

Revision ID: d2be6d3079d4
Revises: 1100bef7c15b
Create Date: 2025-08-08 09:06:00.242027

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd2be6d3079d4'
down_revision = '1100bef7c15b'
branch_labels = None
depends_on = None


def upgrade():
    """Add work_cells table for production work cells/zones."""
    op.create_table(
        'work_cells',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cell_id', sqlmodel.sql.sqltypes.AutoString(length=36), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cell_id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_work_cells_cell_id', 'work_cells', ['cell_id'], unique=True)
    op.create_index('ix_work_cells_name', 'work_cells', ['name'], unique=True)


def downgrade():
    """Remove work_cells table."""
    op.drop_index('ix_work_cells_name', table_name='work_cells')
    op.drop_index('ix_work_cells_cell_id', table_name='work_cells') 
    op.drop_table('work_cells')
