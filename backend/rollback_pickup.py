#!/usr/bin/env python3
"""
回退刚才的领料记录，恢复库存状态
"""

import sqlite3
import os

def rollback_pickup():
    """回退领料记录"""
    
    # 目标事务ID
    transaction_id = "4c816430-1ac5-4760-aed4-e26f17d7d05d"
    
    # 数据库文件路径
    db_path = "site_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"🔄 开始回退事务: {transaction_id}")
        
        # 1. 查看出库事务详情
        cursor.execute("""
            SELECT package_id, total_quantity 
            FROM stock_transactions 
            WHERE id = ?
        """, (transaction_id,))
        
        transaction_info = cursor.fetchone()
        if not transaction_info:
            print("❌ 未找到出库事务记录")
            return False
        
        package_id, total_quantity = transaction_info
        print(f"📦 套装ID: {package_id}, 出库总量: {total_quantity}")
        
        # 2. 查找套装包含的设备
        cursor.execute("""
            SELECT equipment_id, quantity 
            FROM equipment_package_items 
            WHERE package_id = ?
        """, (package_id,))
        
        package_items = cursor.fetchall()
        print(f"📋 套装包含 {len(package_items)} 种设备")
        
        # 3. 恢复库存 - 将allocated_stock减回去，available_stock加回去
        for equipment_id, quantity in package_items:
            cursor.execute("""
                UPDATE inventory 
                SET available_stock = available_stock + ?,
                    allocated_stock = allocated_stock - ?
                WHERE equipment_id = ?
            """, (quantity, quantity, equipment_id))
            
            print(f"✅ 恢复设备 {equipment_id} 库存: +{quantity}")
        
        # 4. 删除领料记录
        cursor.execute("""
            DELETE FROM pickup_records 
            WHERE transaction_id = ?
        """, (transaction_id,))
        
        deleted_pickup = cursor.rowcount
        print(f"🗑️ 删除领料记录: {deleted_pickup} 条")
        
        # 5. 删除出库事务记录  
        cursor.execute("""
            DELETE FROM stock_transactions 
            WHERE id = ?
        """, (transaction_id,))
        
        deleted_transaction = cursor.rowcount
        print(f"🗑️ 删除出库事务: {deleted_transaction} 条")
        
        # 6. 验证库存恢复
        print("\n📊 库存恢复情况:")
        for equipment_id, quantity in package_items:
            cursor.execute("""
                SELECT e.equipment_name, i.available_stock, i.allocated_stock
                FROM inventory i 
                JOIN equipments e ON i.equipment_id = e.id
                WHERE i.equipment_id = ?
            """, (equipment_id,))
            
            result = cursor.fetchone()
            if result:
                equipment_name, available, allocated = result
                print(f"  {equipment_name}: 可用 {available}, 已分配 {allocated}")
        
        conn.commit()
        
        print("✅ 领料记录回退完成!")
        print("💡 现在可以在APP端重新进行扫码领料测试")
        return True
            
    except Exception as e:
        print(f"❌ 回退失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 开始回退领料记录...")
    success = rollback_pickup()
    
    if success:
        print("🎉 回退完成!")
    else:
        print("💥 回退失败!")