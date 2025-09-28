#!/usr/bin/env python3
"""
调试脚本：测试检查项创建过程，专门调试为什么小区级检查项只创建了1个
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.inspection import InspectionTemplate, SiteInspection, InspectionCheckItem
from app.services.cell_generator import CellGenerator
import json

# 创建数据库连接
engine = create_engine('sqlite:///site_manager.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def debug_inspection_creation():
    """调试检查项创建过程"""
    db = SessionLocal()
    try:
        site_id = 5
        template_id = "c9d4c05c-0d05-4795-89b7-0d4350f78092"
        inspection_id = "9ff38826-6d20-4200-8119-32b1ba696244"
        
        print(f"=== 调试检查项创建过程 ===")
        print(f"站点ID: {site_id}")
        print(f"模板ID: {template_id}")
        print(f"检查ID: {inspection_id}")
        
        # 1. 获取检查模板
        template = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == template_id
        ).first()
        
        if not template:
            print("❌ 没有找到检查模板")
            return
            
        print(f"✅ 找到检查模板: {template.template_name}")
        
        # 2. 分析模板数据
        template_data = template.template_data
        print(f"\n=== 分析模板数据 ===")
        print(f"模板数据类型: {type(template_data)}")
        
        if isinstance(template_data, str):
            template_data = json.loads(template_data)
            
        check_categories = template_data.get("check_categories", [])
        print(f"检查分类数量: {len(check_categories)}")
        
        for i, category in enumerate(check_categories):
            print(f"\n--- 分类 {i+1}: {category.get('category_name')} ---")
            print(f"   category_id: {category.get('category_id')}")
            print(f"   sector_specific: {category.get('sector_specific')}")
            print(f"   cell_specific: {category.get('cell_specific')}")
            print(f"   level_type: {category.get('level_type')}")
            
            items = category.get("items", [])
            print(f"   检查项数量: {len(items)}")
            
            for j, item in enumerate(items):
                print(f"     项目 {j+1}: {item.get('item_name')}")
                print(f"       item_id: {item.get('item_id')}")
                print(f"       required_type: {item.get('required_type')}")
                
        # 3. 生成小区数据
        print(f"\n=== 生成小区数据 ===")
        cells = CellGenerator.generate_cells_from_planning(db, site_id)
        print(f"生成的小区数量: {len(cells)}")
        for cell in cells:
            print(f"   {cell.to_dict()}")
            
        # 4. 模拟检查项创建逻辑
        print(f"\n=== 模拟检查项创建逻辑 ===")
        total_items = 0
        
        for category in check_categories:
            category_name = category.get("category_name")
            print(f"\n处理分类: {category_name}")
            
            for item in category.get("items", []):
                item_name = item.get("item_name")
                item_id = item.get("item_id")
                print(f"  处理检查项: {item_name} (ID: {item_id})")
                
                # 检查是否是小区级检查
                is_cell_specific = category.get("cell_specific", False)
                is_sector_specific = category.get("sector_specific", False)
                level_type = category.get("level_type")
                
                print(f"    cell_specific: {is_cell_specific}")
                print(f"    sector_specific: {is_sector_specific}")
                print(f"    level_type: {level_type}")
                
                if is_cell_specific:
                    print(f"    ✅ 这是小区级检查，应该为 {len(cells)} 个小区创建检查项")
                    for cell in cells:
                        print(f"      创建小区检查项: {item_id}_cell_{cell.cell_id}")
                        total_items += 1
                elif is_sector_specific:
                    sectors = set(cell.sector_id for cell in cells)
                    print(f"    ✅ 这是扇区级检查，应该为 {len(sectors)} 个扇区创建检查项")
                    for sector_id in sectors:
                        print(f"      创建扇区检查项: {item_id}_sector_{sector_id}")
                        total_items += 1
                else:
                    print(f"    ✅ 这是站点级检查，创建1个检查项")
                    print(f"      创建站点检查项: {item_id}")
                    total_items += 1
                    
        print(f"\n=== 模拟结果 ===")
        print(f"预期总检查项数: {total_items}")
        
        # 5. 查询实际创建的检查项
        print(f"\n=== 查询实际创建的检查项 ===")
        actual_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).all()
        
        print(f"实际检查项数量: {len(actual_items)}")
        for item in actual_items:
            print(f"   {item.item_name} (ID: {item.item_id}, 扇区: {item.sector_id}, 小区: {getattr(item, 'cell_id', 'N/A')})")
            
        # 6. 对比分析
        print(f"\n=== 对比分析 ===")
        print(f"预期检查项数: {total_items}")
        print(f"实际检查项数: {len(actual_items)}")
        
        if total_items != len(actual_items):
            print(f"❌ 检查项数量不匹配！")
            
            # 查找功率检查项
            power_items = [item for item in actual_items if "power" in item.item_id.lower()]
            print(f"功率相关检查项数量: {len(power_items)}")
            for item in power_items:
                print(f"   {item.item_name} - {item.item_id}")
        else:
            print(f"✅ 检查项数量匹配")
            
    except Exception as e:
        print(f"❌ 调试出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_inspection_creation()