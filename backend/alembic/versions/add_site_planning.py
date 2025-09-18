"""Add site planning tables

Revision ID: add_site_planning
Revises: add_template_binding
Create Date: 2025-09-18 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_site_planning'
down_revision = 'add_template_binding'
branch_labels = None
depends_on = None


def upgrade():
    # site_planning
    op.create_table(
        'site_planning',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('bands', sa.JSON(), nullable=True),
        sa.Column('sector_count', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=True, server_default=sa.text('1')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_site_planning_id', 'site_planning', ['id'], unique=False)
    op.create_index('ix_site_planning_site_id', 'site_planning', ['site_id'], unique=False)
    op.create_index('ix_site_planning_is_current', 'site_planning', ['is_current'], unique=False)
    op.create_unique_constraint('uq_site_planning_site_version', 'site_planning', ['site_id', 'version'])

    # site_planning_sectors
    op.create_table(
        'site_planning_sectors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('planning_id', sa.Integer(), nullable=False),
        sa.Column('sector_index', sa.Integer(), nullable=False),
        sa.Column('azimuth_deg', sa.Float(), nullable=True),
        sa.Column('downtilt_deg', sa.Float(), nullable=True),
        sa.Column('bands', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['planning_id'], ['site_planning.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_site_planning_sectors_id', 'site_planning_sectors', ['id'], unique=False)
    op.create_index('ix_site_planning_sectors_planning_id', 'site_planning_sectors', ['planning_id'], unique=False)

    # site_antenna_ports
    op.create_table(
        'site_antenna_ports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('planning_id', sa.Integer(), nullable=False),
        sa.Column('port_label', sa.String(length=50), nullable=False),
        sa.Column('sector_index', sa.Integer(), nullable=False),
        sa.Column('band', sa.String(length=20), nullable=True),
        sa.Column('mimo_chain', sa.String(length=20), nullable=True),
        sa.Column('remarks', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['planning_id'], ['site_planning.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_site_antenna_ports_id', 'site_antenna_ports', ['id'], unique=False)
    op.create_index('ix_site_antenna_ports_planning_id', 'site_antenna_ports', ['planning_id'], unique=False)

    # site_switch_ports
    op.create_table(
        'site_switch_ports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('planning_id', sa.Integer(), nullable=False),
        sa.Column('port_no', sa.String(length=50), nullable=False),
        sa.Column('vlan_ids', sa.JSON(), nullable=True),
        sa.Column('is_uplink', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('poe', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['planning_id'], ['site_planning.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_site_switch_ports_id', 'site_switch_ports', ['id'], unique=False)
    op.create_index('ix_site_switch_ports_planning_id', 'site_switch_ports', ['planning_id'], unique=False)

    # planning_change_logs
    op.create_table(
        'planning_change_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('planning_id', sa.Integer(), nullable=True),
        sa.Column('operation', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('before_snapshot', sa.JSON(), nullable=True),
        sa.Column('after_snapshot', sa.JSON(), nullable=True),
        sa.Column('diff', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.ForeignKeyConstraint(['planning_id'], ['site_planning.id'], ),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_planning_change_logs_id', 'planning_change_logs', ['id'], unique=False)
    op.create_index('ix_planning_change_logs_site_id', 'planning_change_logs', ['site_id'], unique=False)


def downgrade():
    op.drop_index('ix_planning_change_logs_site_id', table_name='planning_change_logs')
    op.drop_index('ix_planning_change_logs_id', table_name='planning_change_logs')
    op.drop_table('planning_change_logs')

    op.drop_index('ix_site_switch_ports_planning_id', table_name='site_switch_ports')
    op.drop_index('ix_site_switch_ports_id', table_name='site_switch_ports')
    op.drop_table('site_switch_ports')

    op.drop_index('ix_site_antenna_ports_planning_id', table_name='site_antenna_ports')
    op.drop_index('ix_site_antenna_ports_id', table_name='site_antenna_ports')
    op.drop_table('site_antenna_ports')

    op.drop_index('ix_site_planning_sectors_planning_id', table_name='site_planning_sectors')
    op.drop_index('ix_site_planning_sectors_id', table_name='site_planning_sectors')
    op.drop_table('site_planning_sectors')

    op.drop_constraint('uq_site_planning_site_version', 'site_planning', type_='unique')
    op.drop_index('ix_site_planning_is_current', table_name='site_planning')
    op.drop_index('ix_site_planning_site_id', table_name='site_planning')
    op.drop_index('ix_site_planning_id', table_name='site_planning')
    op.drop_table('site_planning')

