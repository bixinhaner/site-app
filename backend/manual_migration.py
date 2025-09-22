#!/usr/bin/env python3
"""
手动数据库迁移脚本

此脚本直接执行SQL命令来添加新字段并简化WorkOrder表结构
"""

import sys
import os
import sqlite3

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def get_db_path():
    """获取数据库文件路径"""
    return "site_manager.db"


def manual_migration():
    """执行手动数据库迁移"""
    
    db_path = get_db_path()
    print(f"连接数据库: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("开始执行数据库迁移...")
        
        # 备份提示
        print("\n⚠️  重要提示：建议在运行前备份数据库文件")
        response = input("\n继续执行？(y/N): ")
        if response.lower() != 'y':
            print("操作已取消")
            return
        
        # 1. 添加 inspection_id 字段
        try:
            print("\n1. 添加 inspection_id 字段...")
            cursor.execute("""
                ALTER TABLE work_orders 
                ADD COLUMN inspection_id VARCHAR(32)
            """)
            print("   ✓ inspection_id 字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("   ⚠️  inspection_id 字段已存在")
            else:
                raise
        
        # 2. 添加 extra_data 字段 (代替 metadata)
        try:
            print("\n2. 添加 extra_data 字段...")
            cursor.execute("""
                ALTER TABLE work_orders 
                ADD COLUMN extra_data JSON
            """)
            print("   ✓ extra_data 字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("   ⚠️  extra_data 字段已存在")
            else:
                raise
        
        # 3. 创建新状态枚举的临时字段
        try:
            print("\n3. 添加新状态字段...")
            cursor.execute("""
                ALTER TABLE work_orders 
                ADD COLUMN status_new VARCHAR(20)
            """)
            print("   ✓ status_new 字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("   ⚠️  status_new 字段已存在")
        
        # 4. 更新状态映射
        print("\n4. 更新状态映射...")
        cursor.execute("""
            UPDATE work_orders 
            SET status_new = CASE 
                WHEN status IN ('assigned', 'accepted', 'rejected') THEN 'pending'
                WHEN status IN ('in_progress', 'submitted', 'under_review') THEN 'active'
                WHEN status IN ('approved', 'completed') THEN 'completed'
                ELSE 'pending'
            END
        """)
        print(f"   ✓ 更新了 {cursor.rowcount} 条记录的状态")
        
        # 5. 获取当前表结构以确认要删除的列
        cursor.execute("PRAGMA table_info(work_orders)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"\n5. 当前表列：{column_names}")
        
        # 6. 创建新表结构（SQLite不支持删除列，需要重建表）
        print("\n6. 重建表以删除冗余字段...")
        
        # 保留的字段
        keep_columns = [
            'id', 'site_id', 'inspection_id', 'title', 'type', 'description', 
            'priority', 'assigned_by', 'assigned_to', 'assigned_at', 
            'accepted_at', 'completed_at', 'due_date', 'extra_data',
            'created_at', 'updated_at'
        ]
        
        # 构建新表的CREATE语句
        new_table_sql = """
        CREATE TABLE work_orders_new (
            id VARCHAR(32) PRIMARY KEY,
            site_id INTEGER NOT NULL,
            inspection_id VARCHAR(32),
            title VARCHAR(200) NOT NULL,
            type VARCHAR(50) NOT NULL,
            description TEXT,
            priority VARCHAR(20) DEFAULT 'normal',
            assigned_by INTEGER NOT NULL,
            assigned_to INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            assigned_at DATETIME,
            accepted_at DATETIME,
            completed_at DATETIME,
            due_date DATETIME,
            extra_data JSON,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (site_id) REFERENCES sites (id),
            FOREIGN KEY (inspection_id) REFERENCES site_inspections (id),
            FOREIGN KEY (assigned_by) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id)
        )
        """
        
        cursor.execute(new_table_sql)
        print("   ✓ 创建新表成功")
        
        # 7. 复制数据到新表
        # 只复制存在的列
        existing_keep_columns = [col for col in keep_columns if col in column_names]
        existing_keep_columns_str = ', '.join(existing_keep_columns)
        
        # 使用 status_new 作为新的 status
        if 'status_new' in column_names:
            copy_columns = [col if col != 'status' else 'status_new as status' for col in existing_keep_columns]
            copy_columns_str = ', '.join(copy_columns)
        else:
            copy_columns_str = existing_keep_columns_str
        
        copy_sql = f"""
        INSERT INTO work_orders_new ({existing_keep_columns_str})
        SELECT {copy_columns_str}
        FROM work_orders
        """
        
        cursor.execute(copy_sql)
        print(f"   ✓ 复制了 {cursor.rowcount} 条记录")
        
        # 8. 替换表
        cursor.execute("DROP TABLE work_orders")
        cursor.execute("ALTER TABLE work_orders_new RENAME TO work_orders")
        print("   ✓ 表替换成功")
        
        # 9. 提交事务
        conn.commit()
        print("\n✓ 数据库迁移完成")
        
        # 10. 验证结果
        print("\n验证迁移结果...")
        cursor.execute("PRAGMA table_info(work_orders)")
        new_columns = cursor.fetchall()
        new_column_names = [col[1] for col in new_columns]
        print(f"新表结构：{new_column_names}")
        
        cursor.execute("SELECT COUNT(*) FROM work_orders")
        count = cursor.fetchone()[0]
        print(f"工单总数：{count}")
        
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    try:
        manual_migration()
        print("\n🎉 手动数据库迁移完成！")
        print("\n下一步：运行数据迁移脚本")
        print("命令：python migrate_work_orders.py")
    except KeyboardInterrupt:
        print("\n用户中断迁移")
        sys.exit(1)
    except Exception as e:
        print(f"\n迁移失败: {str(e)}")
        sys.exit(1)