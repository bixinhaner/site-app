#!/usr/bin/env python3
"""
修复检查类型枚举数据
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.models.inspection import SiteInspection

def fix_inspection_types():
    """修复检查类型枚举值"""
    db = SessionLocal()
    try:
        # 先查询所有可能的installation变体记录
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM site_inspections 
            WHERE LOWER(inspection_type) = 'installation'
        """))
        count_before = result.fetchone()[0]
        print(f"发现 {count_before} 条 'installation' 类型的记录需要更新")
        
        # 查看具体的inspection_type值
        result = db.execute(text("""
            SELECT DISTINCT inspection_type 
            FROM site_inspections 
            WHERE LOWER(inspection_type) = 'installation'
        """))
        distinct_types = result.fetchall()
        print(f"需要更新的inspection_type值: {[row[0] for row in distinct_types]}")
        
        # 使用原生SQL更新枚举值（包括大小写变体）
        result = db.execute(text("""
            UPDATE site_inspections 
            SET inspection_type = 'OPENING' 
            WHERE LOWER(inspection_type) = 'installation' OR inspection_type = 'opening'
        """))
        
        updated_count = result.rowcount
        db.commit()
        
        print(f"成功更新了 {updated_count} 条记录，将 installation/opening 改为 'OPENING'")
        
        # 验证更新结果
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM site_inspections 
            WHERE LOWER(inspection_type) = 'installation'
        """))
        count_after = result.fetchone()[0]
        print(f"更新后还有 {count_after} 条 'installation' 记录")
        
    except Exception as e:
        print(f"修复检查类型失败: {str(e)}")
        db.rollback()
    finally:
        db.close()

def main():
    """主函数"""
    print("开始修复检查类型枚举数据...")
    fix_inspection_types()
    print("修复完成！")

if __name__ == "__main__":
    main()