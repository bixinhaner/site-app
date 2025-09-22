#!/usr/bin/env python3
"""
直接应用数据库Schema更改

由于项目没有配置完整的Alembic，这个脚本直接使用SQLAlchemy来应用模式更改
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from app.models.work_order import WorkOrder
from app.models.inspection import SiteInspection
from app.models.user import User
from app.models.site import Site


def apply_schema_changes():
    """应用数据库模式更改"""
    
    try:
        print("开始应用数据库模式更改...")
        
        # 备份提示
        print("\n⚠️  重要提示：建议在运行前备份数据库文件")
        print("SQLite数据库位置：./site_management.db")
        
        # 确认继续
        response = input("\n继续执行？(y/N): ")
        if response.lower() != 'y':
            print("操作已取消")
            return
        
        # 创建所有表（如果不存在）和更新现有表结构
        print("\n正在更新数据库模式...")
        Base.metadata.create_all(bind=engine)
        
        print("✓ 数据库模式更新完成")
        
        # 验证表结构
        print("\n验证表结构...")
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        
        # 检查work_orders表的列
        work_order_columns = [col['name'] for col in inspector.get_columns('work_orders')]
        print(f"WorkOrder表列：{work_order_columns}")
        
        # 检查是否有inspection_id列
        if 'inspection_id' in work_order_columns:
            print("✓ inspection_id 字段已添加")
        else:
            print("⚠️  inspection_id 字段未找到")
        
        # 检查是否有metadata列
        if 'metadata' in work_order_columns:
            print("✓ metadata 字段已添加")
        else:
            print("⚠️  metadata 字段未找到")
        
        print("\n🎉 模式更改应用完成！")
        print("\n下一步：运行数据迁移脚本")
        print("命令：python migrate_work_orders.py")
        
    except Exception as e:
        print(f"模式更改失败: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        apply_schema_changes()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n操作失败: {str(e)}")
        sys.exit(1)