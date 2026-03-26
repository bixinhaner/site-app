"""add field issue comments to inspection check items

Revision ID: add_check_item_field_issue_comments
Revises: add_equipment_binding_history
Create Date: 2026-03-23 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_check_item_field_issue_comments'
down_revision = 'add_equipment_binding_history'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('inspection_check_items') as batch_op:
        batch_op.add_column(sa.Column('review_comments_manual', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('field_issue_comments', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('inspection_check_items') as batch_op:
        batch_op.drop_column('field_issue_comments')
        batch_op.drop_column('review_comments_manual')
