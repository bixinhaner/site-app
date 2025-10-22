"""add equipment binding history table

Revision ID: add_equipment_binding_history
Revises: add_equipment_sn_indexes
Create Date: 2024-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_equipment_binding_history'
down_revision = 'add_equipment_sn_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """创建设备绑定历史表"""
    
    op.create_table(
        'equipment_binding_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inspection_id', sa.String(32), nullable=False),
        sa.Column('check_item_id', sa.String(32), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('sector_id', sa.String(10), nullable=False),
        sa.Column('band', sa.String(20), nullable=False),
        sa.Column('cell_id', sa.String(20), nullable=False),
        sa.Column('equipment_sn', sa.String(100), nullable=False),
        sa.Column('equipment_type', sa.String(50), nullable=True),
        sa.Column('equipment_model', sa.String(100), nullable=True),
        sa.Column('action', sa.Enum('bind', 'unbind', 'rebind', name='bindingactionenum'), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('operated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('previous_equipment_sn', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('latitude', sa.String(50), nullable=True),
        sa.Column('longitude', sa.String(50), nullable=True),
        sa.Column('gps_accuracy', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['check_item_id'], ['inspection_check_items.id'], ),
        sa.ForeignKeyConstraint(['inspection_id'], ['site_inspections.id'], ),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引以优化查询
    op.create_index('ix_equipment_binding_history_equipment_sn', 'equipment_binding_history', ['equipment_sn'])
    op.create_index('ix_equipment_binding_history_operated_at', 'equipment_binding_history', ['operated_at'])
    op.create_index('ix_equipment_binding_history_cell', 'equipment_binding_history', ['site_id', 'sector_id', 'band'])


def downgrade():
    """删除设备绑定历史表"""
    
    op.drop_index('ix_equipment_binding_history_cell', table_name='equipment_binding_history')
    op.drop_index('ix_equipment_binding_history_operated_at', table_name='equipment_binding_history')
    op.drop_index('ix_equipment_binding_history_equipment_sn', table_name='equipment_binding_history')
    op.drop_table('equipment_binding_history')
