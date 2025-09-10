#!/usr/bin/env python3
"""
简单数据库迁移脚本 - 为 site_inspections 表添加 task_id 字段
"""

import sqlite3
import os

def migrate_database():
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查是否已经有 task_id 列
        cursor.execute("PRAGMA table_info(site_inspections)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'task_id' in columns:
            print("✅ task_id 字段已存在，无需迁移")
            conn.close()
            return
        
        # 添加 task_id 列
        print("正在为 site_inspections 表添加 task_id 字段...")
        cursor.execute("ALTER TABLE site_inspections ADD COLUMN task_id TEXT")
        
        # 创建外键索引（SQLite不会自动创建外键索引）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_site_inspections_task_id ON site_inspections(task_id)")
        
        conn.commit()
        print("✅ 迁移完成：已添加 task_id 字段")
        
        # 验证迁移
        cursor.execute("PRAGMA table_info(site_inspections)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'task_id' in columns:
            print("✅ 验证成功：task_id 字段已正确添加")
        else:
            print("❌ 验证失败：task_id 字段未找到")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    migrate_database()