#!/usr/bin/env python3
"""
为工单表添加审核相关字段
"""

import sqlite3
import os

def add_review_fields():
    # 找到数据库文件
    db_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                db_files.append(os.path.join(root, file))
    
    if not db_files:
        print("❌ 未找到数据库文件")
        return
    
    for db_file in db_files:
        print(f"\n=== 检查数据库 {db_file} ===")
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # 检查是否有work_orders表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='work_orders'")
            if not cursor.fetchone():
                print("  没有work_orders表，跳过")
                conn.close()
                continue
            
            print("  找到work_orders表")
            
            # 检查现有字段
            cursor.execute("PRAGMA table_info(work_orders)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            print(f"  现有字段: {', '.join(sorted(existing_columns))}")
            
            # 需要添加的字段
            new_fields = [
                ('reviewer_id', 'INTEGER'),
                ('review_comments', 'TEXT'),
                ('submitted_at', 'DATETIME'),
                ('reviewed_at', 'DATETIME')
            ]
            
            # 添加缺失的字段
            added_fields = []
            for field_name, field_type in new_fields:
                if field_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE work_orders ADD COLUMN {field_name} {field_type}")
                        added_fields.append(field_name)
                        print(f"  ✅ 添加字段: {field_name} ({field_type})")
                    except Exception as e:
                        print(f"  ❌ 添加字段{field_name}失败: {e}")
                else:
                    print(f"  ⚪ 字段{field_name}已存在")
            
            # 设置Tom的工单为SUBMITTED状态用于测试
            cursor.execute("""
                UPDATE work_orders 
                SET status = 'SUBMITTED', 
                    submitted_at = datetime('now'),
                    reviewer_id = 1
                WHERE id = '9e8b480c-f2b3-474d-9bb5-37b0a4ebc29b'
            """)
            
            conn.commit()
            
            if added_fields:
                print(f"  ✅ 成功添加 {len(added_fields)} 个字段")
                print(f"  ✅ 工单状态已更新为SUBMITTED")
            else:
                print("  ⚪ 所有字段都已存在")
            
            conn.close()
            
        except Exception as e:
            print(f"  ❌ 操作失败: {e}")

if __name__ == "__main__":
    add_review_fields()