#!/usr/bin/env python3
"""
数据库迁移脚本：为 inspection_check_items 表添加 description 字段

运行方式：
    python migrate_add_description.py

说明：
    此脚本会在 inspection_check_items 表中添加 description 列（如果不存在）
    description 列用于存储检查项的详细描述和填写要求说明
"""

import sqlite3
import sys
import os
from pathlib import Path

# 数据库路径配置
DB_PATH = os.environ.get('DB_PATH', 'site_manager.db')

def check_column_exists(cursor, table_name, column_name):
    """检查表中是否存在指定列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_database(db_path):
    """执行数据库迁移"""
    print(f"开始数据库迁移...")
    print(f"数据库路径: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        print("请确认数据库路径是否正确，或者运行 start_backend.py 初始化数据库")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查 description 列是否已存在
        if check_column_exists(cursor, 'inspection_check_items', 'description'):
            print("✓ description 字段已存在，无需迁移")
            conn.close()
            return True
        
        print("正在添加 description 字段...")
        
        # 添加 description 列
        cursor.execute("""
            ALTER TABLE inspection_check_items 
            ADD COLUMN description TEXT
        """)
        
        conn.commit()
        print("✓ 成功添加 description 字段")
        
        # 验证迁移结果
        if check_column_exists(cursor, 'inspection_check_items', 'description'):
            print("✓ 迁移验证成功")
            
            # 显示表结构
            cursor.execute("PRAGMA table_info(inspection_check_items)")
            columns = cursor.fetchall()
            print("\n当前 inspection_check_items 表结构:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            conn.close()
            return True
        else:
            print("✗ 迁移验证失败")
            conn.close()
            return False
            
    except sqlite3.Error as e:
        print(f"✗ 数据库操作失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 发生错误: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("数据库迁移工具 - 添加 inspection_check_items.description 字段")
    print("=" * 60)
    print()
    
    # 检查是否提供了自定义数据库路径
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = DB_PATH
    
    # 执行迁移
    success = migrate_database(db_path)
    
    print()
    if success:
        print("=" * 60)
        print("迁移完成！")
        print("=" * 60)
        print()
        print("下一步操作：")
        print("1. 请重启后端服务")
        print("2. 在服务器上运行: pkill -f 'uvicorn.*8000' && python start_backend.py")
        print("3. 验证工单检查项功能是否正常")
        sys.exit(0)
    else:
        print("=" * 60)
        print("迁移失败！请检查错误信息")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
