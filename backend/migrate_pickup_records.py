#!/usr/bin/env python3
"""
完整迁移 pickup_records 表，添加所有缺失的列
"""

import sqlite3
import os

def migrate_pickup_records():
    """迁移 pickup_records 表，添加所有缺失的列"""
    
    # 数据库文件路径
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取当前表结构
        cursor.execute("PRAGMA table_info(pickup_records)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        print(f"📋 当前表列: {existing_columns}")
        
        # 需要添加的列定义
        columns_to_add = [
            ("serial_number", "VARCHAR(100)"),
            ("mac_address_1", "VARCHAR(50)"),  
            ("mac_address_2", "VARCHAR(50)"),
            ("equipment_instance_id", "VARCHAR(32)"),
        ]
        
        added_count = 0
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"🔧 添加列: {column_name} {column_type}")
                cursor.execute(f"""
                    ALTER TABLE pickup_records 
                    ADD COLUMN {column_name} {column_type}
                """)
                added_count += 1
            else:
                print(f"✅ 列已存在: {column_name}")
        
        # 添加索引
        indexes_to_create = [
            ("idx_pickup_records_serial_number", "serial_number"),
            ("idx_pickup_records_equipment_instance", "equipment_instance_id"),
        ]
        
        for index_name, column_name in indexes_to_create:
            if column_name in [col[0] for col in columns_to_add]:
                print(f"🔧 创建索引: {index_name}")
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} 
                    ON pickup_records({column_name})
                """)
        
        conn.commit()
        
        if added_count > 0:
            print(f"✅ 成功添加 {added_count} 个列")
        else:
            print("✅ 所有列都已存在")
        
        # 验证最终表结构
        cursor.execute("PRAGMA table_info(pickup_records)")
        final_columns = [column[1] for column in cursor.fetchall()]
        print(f"📋 最终表列: {final_columns}")
        
        # 检查所有必要列是否存在
        required_columns = [
            "id", "transaction_id", "work_order_id", "package_id", "picker_id",
            "main_device_barcode", "serial_number", "mac_address_1", "mac_address_2",
            "equipment_instance_id", "scan_location", "scan_ip", "is_confirmed",
            "confirmed_at", "confirmation_notes", "is_returned", "returned_at", 
            "return_notes", "pickup_time", "created_at", "updated_at"
        ]
        
        missing_columns = [col for col in required_columns if col not in final_columns]
        if missing_columns:
            print(f"❌ 仍缺少列: {missing_columns}")
            return False
        else:
            print("✅ 所有必要列都已存在")
            return True
            
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 开始迁移 pickup_records 表...")
    success = migrate_pickup_records()
    
    if success:
        print("🎉 数据库迁移完成!")
    else:
        print("💥 数据库迁移失败!")