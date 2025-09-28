#!/usr/bin/env python3
"""
实时调试脚本：模拟检查创建过程，找出为什么小区级检查项没有正确创建
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.inspection import InspectionTemplate, SiteInspection, InspectionCheckItem, CheckItemStatusEnum
from app.services.cell_generator import CellGenerator
import json
import uuid

# 创建数据库连接
engine = create_engine('sqlite:///site_manager.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def simulate_inspection_creation():
    """模拟检查创建过程并调试问题"""
    db = SessionLocal()
    try:
        site_id = 5
        template_id = "c9d4c05c-0d05-4795-89b7-0d4350f78092"
        
        print(f"=== 模拟检查创建过程 ===")
        print(f"站点ID: {site_id}")
        print(f"模板ID: {template_id}")
        
        # 1. 获取检查模板
        template = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == template_id
        ).first()
        
        if not template:
            print("❌ 没有找到检查模板")
            return
            
        print(f"✅ 找到检查模板: {template.template_name}")
        
        # 2. 获取模板数据
        template_data = template.template_data
        if isinstance(template_data, str):
            template_data = json.loads(template_data)
            
        # 3. 生成小区数据 (模拟 inspections.py:244 的逻辑)
        print(f"\n=== 生成小区数据 ===")
        cells = CellGenerator.generate_cells_from_planning(db, site_id)
        cells_summary = CellGenerator.get_cells_summary(cells)
        
        print(f"✅ 生成了 {len(cells)} 个小区:")
        for cell in cells:
            print(f"   {cell.to_dict()}")
        print(f"✅ 小区摘要: {cells_summary}")
        
        # 4. 模拟检查项创建逻辑 (inspections.py:247-297)
        print(f"\n=== 模拟检查项创建逻辑 ===")
        check_categories = template_data.get("check_categories", [])
        total_items = 0
        created_items = []
        
        for category in check_categories:
            category_name = category.get("category_name")
            category_id = category.get("category_id")
            print(f"\n--- 处理分类: {category_name} ---")
            
            for item in category.get("items", []):
                item_name = item.get("item_name")
                item_id = item.get("item_id")
                required_type = item.get("required_type")
                
                print(f"  检查项: {item_name} (ID: {item_id})")
                
                # 关键逻辑：判断是否是小区级检查
                is_cell_specific = category.get("cell_specific", False)
                is_sector_specific = category.get("sector_specific", False)
                
                print(f"    cell_specific: {is_cell_specific}")
                print(f"    sector_specific: {is_sector_specific}")
                print(f"    required_type: {required_type}")
                
                # 复制 inspections.py:249-297 的逻辑
                if is_cell_specific:
                    print(f"    ✅ 这是小区级检查，为 {len(cells)} 个小区创建检查项")
                    for cell in cells:
                        check_item_data = {
                            "id": str(uuid.uuid4()),
                            "item_id": f"{item_id}_cell_{cell.cell_id}",
                            "item_name": f"{item_name} - 小区 {cell.cell_id}",
                            "category_id": category_id,
                            "category_name": category_name,
                            "sector_id": cell.sector_id,
                            "band": cell.band,
                            "cell_id": cell.cell_id,
                            "required_type": required_type,
                            "status": "PENDING"
                        }
                        created_items.append(check_item_data)
                        print(f"      创建: {check_item_data['item_name']}")
                        total_items += 1
                        
                elif is_sector_specific:
                    print(f"    ✅ 这是扇区级检查")
                    sectors = set(cell.sector_id for cell in cells)
                    for sector_id in sectors:
                        check_item_data = {
                            "id": str(uuid.uuid4()),
                            "item_id": f"{item_id}_sector_{sector_id}",
                            "item_name": f"{item_name} - 扇区 {sector_id}",
                            "category_id": category_id,
                            "category_name": category_name,
                            "sector_id": sector_id,
                            "required_type": required_type,
                            "status": "PENDING"
                        }
                        created_items.append(check_item_data)
                        print(f"      创建: {check_item_data['item_name']}")
                        total_items += 1
                else:
                    print(f"    ✅ 这是站点级检查")
                    check_item_data = {
                        "id": str(uuid.uuid4()),
                        "item_id": item_id,
                        "item_name": item_name,
                        "category_id": category_id,
                        "category_name": category_name,
                        "required_type": required_type,
                        "status": "PENDING"
                    }
                    created_items.append(check_item_data)
                    print(f"      创建: {check_item_data['item_name']}")
                    total_items += 1
                    
        print(f"\n=== 模拟结果汇总 ===")
        print(f"应创建的检查项总数: {total_items}")
        print(f"详细检查项列表:")
        for i, item in enumerate(created_items, 1):
            print(f"  {i}. {item['item_name']} (ID: {item['item_id']})")
            
        # 5. 与实际情况对比
        print(f"\n=== 与实际情况对比 ===")
        
        # 查询新创建的检查
        new_inspection = db.query(SiteInspection).filter(
            SiteInspection.id == "aaf886d1-7734-49d7-ab7f-1f994afa14aa"
        ).first()
        
        if new_inspection:
            actual_items = db.query(InspectionCheckItem).filter(
                InspectionCheckItem.inspection_id == new_inspection.id
            ).all()
            
            print(f"实际创建的检查项数: {len(actual_items)}")
            print(f"实际检查项列表:")
            for i, item in enumerate(actual_items, 1):
                print(f"  {i}. {item.item_name} (ID: {item.item_id}, 扇区: {item.sector_id})")
                
            print(f"\n差异分析:")
            print(f"  预期: {total_items} 个检查项")
            print(f"  实际: {len(actual_items)} 个检查项")
            print(f"  差异: {total_items - len(actual_items)} 个检查项")
            
            if total_items != len(actual_items):
                print(f"❌ 检查项数量不匹配！")
                print(f"  这证明了检查项创建逻辑有问题")
                
                # 分析具体缺失的检查项
                actual_item_ids = {item.item_id for item in actual_items}
                expected_item_ids = {item['item_id'] for item in created_items}
                missing_item_ids = expected_item_ids - actual_item_ids
                
                print(f"  缺失的检查项ID:")
                for item_id in missing_item_ids:
                    missing_item = next(item for item in created_items if item['item_id'] == item_id)
                    print(f"    - {item_id}: {missing_item['item_name']}")
            else:
                print(f"✅ 检查项数量匹配")
        else:
            print(f"❌ 没有找到新创建的检查记录")
            
    except Exception as e:
        print(f"❌ 模拟过程出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    simulate_inspection_creation()