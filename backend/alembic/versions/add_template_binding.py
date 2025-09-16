"""Add template binding system

Revision ID: add_template_binding
Revises: 
Create Date: 2025-09-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'add_template_binding'
down_revision = None
depends_on = None

def upgrade():
    """Upgrade to add template binding system"""
    
    # 1. 修改 inspection_templates 表结构
    # 移除 site_id 和 status 列，因为这些将通过绑定系统管理
    op.execute(text("ALTER TABLE inspection_templates DROP COLUMN IF EXISTS site_id"))
    op.execute(text("ALTER TABLE inspection_templates DROP COLUMN IF EXISTS template_version"))
    op.execute(text("ALTER TABLE inspection_templates DROP COLUMN IF EXISTS status"))
    
    # 2. 创建 template_bindings 表
    op.create_table('template_bindings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=32), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=True),
        sa.Column('site_type', sa.String(length=50), nullable=True),
        sa.Column('task_type', sa.Enum('opening_inspection', 'maintenance', 'power_issue', 'transmission_issue', 'gps_issue', 'signal_issue', name='tasktypeenum'), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('customer', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='50'),
        sa.Column('active', sa.Boolean(), server_default='true'),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_to', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['inspection_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_template_bindings_id'), 'template_bindings', ['id'], unique=False)
    
    # 3. 迁移现有模板数据
    # 为现有的检查模板创建默认绑定（如果有历史数据的话）
    # 这个部分可以根据实际数据情况调整

def downgrade():
    """Downgrade to remove template binding system"""
    # 删除 template_bindings 表
    op.drop_index(op.f('ix_template_bindings_id'), table_name='template_bindings')
    op.drop_table('template_bindings')
    
    # 恢复 inspection_templates 表的原始结构
    op.add_column('inspection_templates', sa.Column('site_id', sa.Integer(), nullable=False))
    op.add_column('inspection_templates', sa.Column('template_version', sa.String(length=20), server_default='1.0'))
    op.add_column('inspection_templates', sa.Column('status', sa.Enum('draft', 'in_progress', 'submitted', 'under_review', 'approved', 'rejected', 'completed', name='inspectionstatusenum'), server_default='draft'))
    
    # 重新创建外键约束
    op.create_foreign_key(None, 'inspection_templates', 'sites', ['site_id'], ['id'])