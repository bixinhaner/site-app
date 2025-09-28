#!/usr/bin/env python3
"""
添加 work_order_id 列到 stock_transactions 表
"""

import sqlite3
import os

def add_work_order_id_column():
    """添加 work_order_id 列到 stock_transactions 和 pickup_records 表"""
    
    # 数据库文件路径
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 处理 stock_transactions 表
        print("🔧 处理 stock_transactions 表...")
        cursor.execute("PRAGMA table_info(stock_transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'work_order_id' not in columns:
            print("🔧 添加 stock_transactions.work_order_id 列...")
            cursor.execute("""
                ALTER TABLE stock_transactions 
                ADD COLUMN work_order_id VARCHAR(32)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_transactions_work_order_id 
                ON stock_transactions(work_order_id)
            """)
            print("✅ stock_transactions.work_order_id 列添加成功")
        else:
            print("✅ stock_transactions.work_order_id 列已存在")
        
        # 处理 pickup_records 表
        print("🔧 处理 pickup_records 表...")
        cursor.execute("PRAGMA table_info(pickup_records)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'work_order_id' not in columns:
            print("🔧 添加 pickup_records.work_order_id 列...")
            cursor.execute("""
                ALTER TABLE pickup_records 
                ADD COLUMN work_order_id VARCHAR(32)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pickup_records_work_order_id 
                ON pickup_records(work_order_id)
            """)
            print("✅ pickup_records.work_order_id 列添加成功")
        else:
            print("✅ pickup_records.work_order_id 列已存在")
        
        conn.commit()
        
        # 验证所有列是否添加成功
        success = True
        for table_name in ['stock_transactions', 'pickup_records']:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'work_order_id' in columns:
                print(f"✅ 验证成功：{table_name}.work_order_id 列已存在")
            else:
                print(f"❌ 验证失败：{table_name}.work_order_id 列未找到")
                success = False
        
        return success
            
    except Exception as e:
        print(f"❌ 添加列失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 开始添加 work_order_id 列到 stock_transactions 表...")
    success = add_work_order_id_column()
    
    if success:
        print("🎉 数据库迁移完成!")
    else:
        print("💥 数据库迁移失败!")