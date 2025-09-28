#!/usr/bin/env python3
"""
修复 pickup_records 表中的 task_id NOT NULL 约束问题
由于 task 概念已废弃，需要删除该约束或设置默认值
"""

import sqlite3
import os

def fix_task_id_constraint():
    """修复 task_id 的 NOT NULL 约束"""
    
    # 数据库文件路径
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔧 开始修复 task_id 约束问题...")
        
        # 检查当前表结构
        cursor.execute("PRAGMA table_info(pickup_records)")
        columns_info = cursor.fetchall()
        print("📋 当前表结构:")
        for col in columns_info:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'}")
        
        # 由于 SQLite 不支持直接修改列约束，我们需要重建表
        print("🔧 重建表以移除 task_id NOT NULL 约束...")
        
        # 1. 创建新表结构（没有 task_id NOT NULL 约束）
        cursor.execute("""
            CREATE TABLE pickup_records_new (
                id VARCHAR(32) PRIMARY KEY,
                transaction_id VARCHAR(32) NOT NULL,
                task_id VARCHAR(32),  -- 移除 NOT NULL 约束
                work_order_id VARCHAR(32),
                package_id INTEGER NOT NULL,
                picker_id INTEGER NOT NULL,
                pickup_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                main_device_barcode VARCHAR(100) NOT NULL,
                serial_number VARCHAR(100),
                mac_address_1 VARCHAR(50),
                mac_address_2 VARCHAR(50),
                equipment_instance_id VARCHAR(32),
                scan_location JSON,
                scan_ip VARCHAR(45),
                is_confirmed BOOLEAN DEFAULT 0,
                confirmed_at DATETIME,
                confirmation_notes TEXT,
                is_returned BOOLEAN DEFAULT 0,
                returned_at DATETIME,
                return_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 复制现有数据（为 task_id 设置默认值）
        cursor.execute("""
            INSERT INTO pickup_records_new 
            SELECT 
                id, transaction_id, 
                COALESCE(task_id, 'DEPRECATED') as task_id,  -- 给 NULL 值设置默认值
                work_order_id, package_id, picker_id, pickup_time,
                main_device_barcode, serial_number, mac_address_1, mac_address_2,
                equipment_instance_id, scan_location, scan_ip, is_confirmed,
                confirmed_at, confirmation_notes, is_returned, returned_at,
                return_notes, created_at, updated_at
            FROM pickup_records
        """)
        
        # 3. 删除旧表
        cursor.execute("DROP TABLE pickup_records")
        
        # 4. 重命名新表
        cursor.execute("ALTER TABLE pickup_records_new RENAME TO pickup_records")
        
        # 5. 重新创建索引
        indexes_to_create = [
            "CREATE INDEX IF NOT EXISTS idx_pickup_records_work_order_id ON pickup_records(work_order_id)",
            "CREATE INDEX IF NOT EXISTS idx_pickup_records_serial_number ON pickup_records(serial_number)",
            "CREATE INDEX IF NOT EXISTS idx_pickup_records_equipment_instance ON pickup_records(equipment_instance_id)",
            "CREATE INDEX IF NOT EXISTS idx_pickup_records_picker_id ON pickup_records(picker_id)",
            "CREATE INDEX IF NOT EXISTS idx_pickup_records_package_id ON pickup_records(package_id)",
        ]
        
        for index_sql in indexes_to_create:
            cursor.execute(index_sql)
            print(f"✅ 创建索引成功")
        
        conn.commit()
        
        # 验证新表结构
        cursor.execute("PRAGMA table_info(pickup_records)")
        new_columns_info = cursor.fetchall()
        print("📋 修复后表结构:")
        for col in new_columns_info:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'}")
        
        # 检查数据是否正确迁移
        cursor.execute("SELECT COUNT(*) FROM pickup_records")
        count = cursor.fetchone()[0]
        print(f"📊 迁移后记录数: {count}")
        
        print("✅ task_id 约束问题修复完成!")
        return True
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 开始修复 pickup_records 表的 task_id 约束问题...")
    success = fix_task_id_constraint()
    
    if success:
        print("🎉 约束修复完成!")
    else:
        print("💥 约束修复失败!")