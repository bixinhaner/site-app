#!/usr/bin/env python3
"""
数据库迁移脚本 - 修复 site_surveys 表 work_order_id 字段

此脚本会：
1. 检查 site_surveys 表是否存在 work_order_id 字段
2. 如果不存在，则添加该字段
3. 验证迁移结果

使用方法：
    cd /path/to/backend
    python run_site_survey_migration.py
"""

import sqlite3
import sys
import os

def check_and_add_work_order_id(db_path):
    """检查并添加 work_order_id 字段"""
    conn = None
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取表结构信息
        cursor.execute("PRAGMA table_info(site_surveys)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]  # col[1] 是列名

        print("=== site_surveys 表当前列结构 ===")
        for col in columns:
            print(f"  {col[1]}: {col[2]} (nullable: {not col[3]}, default: {col[4]}, pk: {col[5]})")

        # 检查 work_order_id 字段是否存在
        if 'work_order_id' in column_names:
            print("\n✅ work_order_id 字段已存在，无需添加")
            return True

        print("\n⚠️  work_order_id 字段不存在，正在添加...")

        # 添加 work_order_id 字段
        cursor.execute("""
            ALTER TABLE site_surveys
            ADD COLUMN work_order_id VARCHAR(32)
        """)
        conn.commit()

        # 验证字段是否添加成功
        cursor.execute("PRAGMA table_info(site_surveys)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'work_order_id' in column_names:
            print("✅ work_order_id 字段添加成功！")
        else:
            print("❌ work_order_id 字段添加失败！")
            return False

        # 尝试添加外键约束（如果 work_orders 表存在）
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='work_orders'")
            if cursor.fetchone():
                print("✓ work_orders 表存在，外键约束会在需要时自动生效")
            else:
                print("⚠️  work_orders 表不存在，请确保在创建该表后重新建立外键关系")
        except Exception as e:
            print(f"⚠️  检查 work_orders 表时出错: {e}")

        return True

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
            print("✅ work_order_id 字段已存在")
            return True
        else:
            print(f"❌ 数据库操作错误: {e}")
            return False
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def main():
    """主函数"""
    # 查找数据库文件
    db_path = "site_manager.db"

    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        print("请确保在 backend 目录下执行此脚本")
        sys.exit(1)

    print("=" * 50)
    print("site_surveys 表 work_order_id 字段迁移工具")
    print("=" * 50)
    print(f"数据库路径: {os.path.abspath(db_path)}")
    print()

    # 执行迁移
    success = check_and_add_work_order_id(db_path)

    print()
    print("=" * 50)
    if success:
        print("✅ 迁移完成！")
        print("\n建议：重启后端服务以使更改生效")
    else:
        print("❌ 迁移失败！")
        print("\n请检查错误信息并手动处理")
        sys.exit(1)
    print("=" * 50)

if __name__ == "__main__":
    main()
