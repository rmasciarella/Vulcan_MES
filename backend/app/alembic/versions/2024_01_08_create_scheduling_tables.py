"""Create scheduling tables for labor skills import

Revision ID: 2024_01_08_create_scheduling_tables
Revises: 1a31ce608336
Create Date: 2024-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2024_01_08_create_scheduling_tables'
down_revision = '1a31ce608336'
branch_labels = None
depends_on = None


def upgrade():
    """Create the scheduling tables required for labor skills import."""
    
    # Skills table
    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('skill_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('skill_category', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('skill_code')
    )
    op.create_index('ix_skills_skill_code', 'skills', ['skill_code'], unique=True)

    # Operators table
    op.create_table(
        'operators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('status', sa.Enum('available', 'assigned', 'on_break', 'off_shift', 'absent', name='operatorstatus'), nullable=False, default='available'),
        sa.Column('default_shift_start', sa.Time(), nullable=False, default=sa.text("'07:00:00'")),
        sa.Column('default_shift_end', sa.Time(), nullable=False, default=sa.text("'16:00:00'")),
        sa.Column('lunch_start', sa.Time(), nullable=False, default=sa.text("'12:00:00'")),
        sa.Column('lunch_duration_minutes', sa.Integer(), nullable=False, default=30),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('department', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True, default='general'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_operators_employee_id', 'operators', ['employee_id'], unique=True)
    op.create_index('ix_operators_department', 'operators', ['department'])

    # Operator skills table (junction table)
    op.create_table(
        'operator_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('proficiency_level', sa.Enum('1', '2', '3', name='skilllevel'), nullable=False),
        sa.Column('certified_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['operator_id'], ['operators.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('operator_id', 'skill_id', name='uq_operator_skill')
    )

    # Additional scheduling tables for completeness (optional for basic import)
    
    # Production zones table
    op.create_table(
        'production_zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone_code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('zone_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('max_wip_limit', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone_code')
    )
    op.create_index('ix_production_zones_zone_code', 'production_zones', ['zone_code'], unique=True)

    # Machines table
    op.create_table(
        'machines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('machine_code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('machine_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('machine_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('status', sa.Enum('available', 'busy', 'maintenance', 'offline', name='machinestatus'), nullable=False, default='available'),
        sa.Column('automation_level', sa.Enum('attended', 'unattended', name='machineautomationlevel'), nullable=False, default='attended'),
        sa.Column('production_zone_id', sa.Integer(), nullable=True),
        sa.Column('setup_time_minutes', sa.Integer(), nullable=False, default=0),
        sa.Column('teardown_time_minutes', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['production_zone_id'], ['production_zones.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('machine_code')
    )
    op.create_index('ix_machines_machine_code', 'machines', ['machine_code'], unique=True)


def downgrade():
    """Drop the scheduling tables."""
    op.drop_table('operator_skills')
    op.drop_table('machines')
    op.drop_table('production_zones')
    op.drop_table('operators')
    op.drop_table('skills')
    
    # Drop custom enum types
    op.execute('DROP TYPE IF EXISTS operatorstatus')
    op.execute('DROP TYPE IF EXISTS skilllevel')
    op.execute('DROP TYPE IF EXISTS machinestatus')
    op.execute('DROP TYPE IF EXISTS machineautomationlevel')