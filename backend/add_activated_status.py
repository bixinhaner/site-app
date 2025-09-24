#!/usr/bin/env python3
"""
添加工单ACTIVATED状态和activated_at字段的数据库迁移脚本
"""

import sqlite3
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """执行数据库迁移"""
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查work_orders表是否存在activated_at列
        cursor.execute("PRAGMA table_info(work_orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'activated_at' not in columns:
            print("添加activated_at字段到work_orders表...")
            cursor.execute("ALTER TABLE work_orders ADD COLUMN activated_at DATETIME")
            print("✓ activated_at字段已添加")
        else:
            print("✓ activated_at字段已存在")
        
        # 提交更改
        conn.commit()
        print("✓ 数据库迁移完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_migration():
    """验证迁移结果"""
    db_path = "site_manager.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查表结构
        cursor.execute("PRAGMA table_info(work_orders)")
        columns = cursor.fetchall()
        
        print("\n当前work_orders表结构:")
        for column in columns:
            print(f"  {column[1]} {column[2]} {'NOT NULL' if column[3] else 'NULL'}")
        
        # 检查是否有activated_at列
        activated_at_exists = any(column[1] == 'activated_at' for column in columns)
        
        if activated_at_exists:
            print("\n✓ 验证成功：activated_at字段已正确添加")
            return True
        else:
            print("\n❌ 验证失败：activated_at字段未找到")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== 工单ACTIVATED状态数据库迁移 ===")
    
    # 执行迁移
    success = migrate_database()
    
    if success:
        # 验证迁移
        verify_migration()
        print("\n🎉 迁移完成！现在可以使用ACTIVATED状态了。")
    else:
        print("\n❌ 迁移失败，请检查错误信息。")
        sys.exit(1)