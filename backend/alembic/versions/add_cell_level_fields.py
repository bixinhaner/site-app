"""add cell level fields to inspection and work order items

Revision ID: add_cell_level_fields
Revises: [previous_revision]
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_cell_level_fields'
down_revision = None  # Update this with the actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Add cell-level fields to inspection_check_items table
    with op.batch_alter_table('inspection_check_items') as batch_op:
        batch_op.add_column(sa.Column('band', sa.String(20), nullable=True, comment='频段，如 n41, n78, n3'))
        batch_op.add_column(sa.Column('cell_id', sa.String(20), nullable=True, comment='小区ID，格式：sector_band'))
    
    # Add cell-level fields to work_order_items table  
    with op.batch_alter_table('work_order_items') as batch_op:
        batch_op.add_column(sa.Column('band', sa.String(20), nullable=True, comment='频段，如 n41, n78, n3'))
        batch_op.add_column(sa.Column('cell_id', sa.String(20), nullable=True, comment='小区ID，格式：sector_band'))


def downgrade():
    # Remove cell-level fields from work_order_items table
    with op.batch_alter_table('work_order_items') as batch_op:
        batch_op.drop_column('cell_id')
        batch_op.drop_column('band')
    
    # Remove cell-level fields from inspection_check_items table
    with op.batch_alter_table('inspection_check_items') as batch_op:
        batch_op.drop_column('cell_id') 
        batch_op.drop_column('band')