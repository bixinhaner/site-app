"""add equipment sn indexes

Revision ID: add_equipment_sn_indexes
Revises: add_cell_level_fields
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_equipment_sn_indexes'
down_revision = 'add_cell_level_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加设备SN相关索引以优化查询性能"""
    
    # 为 equipment_sn 添加单列索引（支持模糊查询）
    op.create_index(
        'ix_inspection_check_items_equipment_sn',
        'inspection_check_items',
        ['equipment_sn'],
        unique=False
    )
    
    # 为小区级检查项添加复合索引（sector_id + band + equipment_sn）
    # 用于快速查询特定小区的设备绑定情况
    op.create_index(
        'ix_inspection_check_items_cell',
        'inspection_check_items',
        ['sector_id', 'band', 'equipment_sn'],
        unique=False
    )
    
    # 为检查ID和设备SN的组合索引
    # 用于快速查询某个检查的所有设备绑定情况
    op.create_index(
        'ix_inspection_check_items_inspection_equipment',
        'inspection_check_items',
        ['inspection_id', 'equipment_sn'],
        unique=False
    )


def downgrade():
    """移除添加的索引"""
    
    op.drop_index('ix_inspection_check_items_inspection_equipment', table_name='inspection_check_items')
    op.drop_index('ix_inspection_check_items_cell', table_name='inspection_check_items')
    op.drop_index('ix_inspection_check_items_equipment_sn', table_name='inspection_check_items')
