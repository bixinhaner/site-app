#!/usr/bin/env python3
"""
数据库迁移脚本：向inspection_check_items表添加description字段
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def add_description_column():
    """添加description字段到inspection_check_items表"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 检查字段是否已存在
            check_sql = text("""
                SELECT COUNT(*) as count 
                FROM pragma_table_info('inspection_check_items') 
                WHERE name = 'description'
            """)
            
            result = conn.execute(check_sql)
            row = result.fetchone()
            
            if row[0] > 0:
                print("✅ description字段已存在，无需添加")
                return True
            
            # 添加description字段
            alter_sql = text("""
                ALTER TABLE inspection_check_items 
                ADD COLUMN description TEXT
            """)
            
            conn.execute(alter_sql)
            conn.commit()
            
            print("✅ 成功添加description字段到inspection_check_items表")
            
            # 验证字段是否添加成功
            verify_sql = text("""
                SELECT COUNT(*) as count 
                FROM pragma_table_info('inspection_check_items') 
                WHERE name = 'description'
            """)
            
            result = conn.execute(verify_sql)
            row = result.fetchone()
            
            if row[0] > 0:
                print("✅ 字段添加验证成功")
                return True
            else:
                print("❌ 字段添加验证失败")
                return False
                
    except Exception as e:
        print(f"❌ 添加字段失败: {e}")
        return False

if __name__ == "__main__":
    print("开始数据库迁移...")
    success = add_description_column()
    
    if success:
        print("\n✅ 数据库迁移完成！")
        print("说明：新创建的检查项将包含描述信息，旧的检查项description字段为空")
    else:
        print("\n❌ 数据库迁移失败！")
        sys.exit(1)
