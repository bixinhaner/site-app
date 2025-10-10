#!/usr/bin/env python3
"""
修复数据库：添加 equipment_sn 字段到 inspection_check_items 表
"""

import sqlite3
import os
from pathlib import Path

def find_database_with_table(table_name):
    """查找包含指定表的数据库文件"""
    current_dir = Path.cwd()
    
    # 查找所有 .db 文件
    db_files = list(current_dir.glob("*.db"))
    
    for db_file in db_files:
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            result = cursor.fetchone()
            
            if result:
                print(f"找到表 {table_name} 在数据库: {db_file}")
                conn.close()
                return str(db_file)
            
            conn.close()
        except Exception as e:
            print(f"检查数据库 {db_file} 时出错: {e}")
            continue
    
    return None

def check_column_exists(db_path, table_name, column_name):
    """检查表中是否存在指定字段"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    for column in columns:
        if column[1] == column_name:
            conn.close()
            return True
    
    conn.close()
    return False

def add_equipment_sn_column(db_path, table_name):
    """添加 equipment_sn 字段"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 添加字段
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN equipment_sn VARCHAR(100)")
        conn.commit()
        print(f"成功添加 equipment_sn 字段到 {table_name} 表")
    except Exception as e:
        print(f"添加字段失败: {e}")
    finally:
        conn.close()

def main():
    """主函数"""
    table_name = "inspection_check_items"
    column_name = "equipment_sn"
    
    print("开始修复数据库...")
    print(f"查找包含表 {table_name} 的数据库...")
    
    # 查找数据库
    db_path = find_database_with_table(table_name)
    
    if not db_path:
        print(f"未找到包含表 {table_name} 的数据库文件")
        return
    
    # 检查字段是否已存在
    if check_column_exists(db_path, table_name, column_name):
        print(f"字段 {column_name} 已存在于表 {table_name} 中")
        return
    
    # 添加字段
    print(f"添加字段 {column_name} 到表 {table_name}...")
    add_equipment_sn_column(db_path, table_name)
    
    # 验证字段是否添加成功
    if check_column_exists(db_path, table_name, column_name):
        print("✅ 数据库修复成功！")
    else:
        print("❌ 数据库修复失败！")

if __name__ == "__main__":
    main()