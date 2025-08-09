"""merge multiple heads

Revision ID: 1100bef7c15b
Revises: 2024_01_08_create_scheduling_tables, add_skills_table, 5b8f9e1d2c3a, b7e8c4d1f2a3, f1a2b3c4d5e6
Create Date: 2025-08-08 09:05:56.857783

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '1100bef7c15b'
down_revision = ('2024_01_08_create_scheduling_tables', 'add_skills_table', '5b8f9e1d2c3a', 'b7e8c4d1f2a3', 'f1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
