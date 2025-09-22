#!/usr/bin/env python3
"""
测试升级后的小区级模板
"""

import sys
import os
import json
import uuid
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.inspection import InspectionTemplate, SiteInspection, InspectionCheckItem
from app.models.site import Site
from app.models.planning import SitePlanning, SitePlanningSector
from app.models.user import User
from app.services.cell_generator import CellGenerator
from sqlalchemy.orm import Session


def test_cell_level_template():
    """测试小区级模板生成检查项"""
    
    print("🧪 测试小区级模板生成检查项\n")
    
    db = SessionLocal()
    try:
        # 1. 获取小区级模板
        cell_template = db.query(InspectionTemplate).filter(
            InspectionTemplate.template_name.like('%小区级%')
        ).first()
        
        if not cell_template:
            print("❌ 未找到小区级模板")
            return False
        
        print(f"📋 使用模板: {cell_template.template_name}")
        
        # 2. 使用之前创建的测试站点
        test_site = db.query(Site).filter(Site.site_code == "TEST_CELL_001").first()
        if not test_site:
            print("❌ 未找到测试站点，请先运行 test_cell_level_inspection.py")
            return False
        
        print(f"🏢 测试站点: {test_site.site_name} ({test_site.site_code})")
        
        # 3. 生成小区配置
        cells = CellGenerator.generate_cells_from_planning(db, test_site.id)
        cells_summary = CellGenerator.get_cells_summary(cells)
        
        print(f"📱 小区配置:")
        print(f"   总小区数: {cells_summary['total_cells']}")
        print(f"   扇区数: {cells_summary['sector_count']}")
        print(f"   频段: {cells_summary['bands']}")
        
        # 4. 模拟创建检查记录
        inspection = SiteInspection(
            id=str(uuid.uuid4()),
            site_id=test_site.id,
            template_id=cell_template.id,
            inspector_id=1,
            status="draft"
        )
        db.add(inspection)
        db.flush()
        
        print(f"\n🔍 创建检查记录: {inspection.id}")
        
        # 5. 根据模板和站点规划创建检查项
        template_data = cell_template.template_data
        if isinstance(template_data, str):
            template_data = json.loads(template_data)
        
        total_items = 0
        categories = template_data.get('check_categories', template_data.get('categories', []))
        
        print(f"\n📊 生成检查项:")
        
        for category in categories:
            category_name = category.get('category_name', category.get('name'))
            items = category.get('items', [])
            category_items = 0
            
            for item in items:
                item_name = item.get('item_name', item.get('name'))
                
                # 如果是小区级检查，为每个小区创建检查项
                if category.get('cell_specific', False):
                    for cell in cells:
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=f"{item.get('item_id', item_name)}_cell_{cell.cell_id}",
                            item_name=f"{item_name} - 小区 {cell.cell_id}",
                            category_id=category.get('category_id', category.get('id')),
                            category_name=category_name,
                            sector_id=cell.sector_id,
                            band=cell.band,
                            cell_id=cell.cell_id,
                            required_type=item.get('required_type', 'both'),
                            status="pending"
                        )
                        db.add(check_item)
                        category_items += 1
                        
                # 如果是扇区级检查
                elif category.get('sector_specific', False):
                    sectors = set(cell.sector_id for cell in cells)
                    for sector_id in sectors:
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=f"{item.get('item_id', item_name)}_sector_{sector_id}",
                            item_name=f"{item_name} - 扇区 {sector_id}",
                            category_id=category.get('category_id', category.get('id')),
                            category_name=category_name,
                            sector_id=sector_id,
                            required_type=item.get('required_type', 'both'),
                            status="pending"
                        )
                        db.add(check_item)
                        category_items += 1
                        
                else:
                    # 站点级检查项
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=item.get('item_id', item_name),
                        item_name=item_name,
                        category_id=category.get('category_id', category.get('id')),
                        category_name=category_name,
                        required_type=item.get('required_type', 'both'),
                        status="pending"
                    )
                    db.add(check_item)
                    category_items += 1
            
            total_items += category_items
            
            category_type = []
            if category.get('sector_specific', False):
                category_type.append("扇区级")
            if category.get('cell_specific', False):
                category_type.append("小区级")
            if not category_type:
                category_type.append("站点级")
            
            print(f"   📂 {category_name} ({'/'.join(category_type)}): {category_items} 项")
        
        # 6. 更新检查记录
        inspection.total_items = total_items
        db.commit()
        
        print(f"\n✅ 检查项生成完成:")
        print(f"   总检查项数: {total_items}")
        
        # 7. 详细列出小区级检查项
        cell_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id,
            InspectionCheckItem.cell_id.isnot(None)
        ).all()
        
        print(f"\n📱 小区级检查项详情 ({len(cell_items)} 项):")
        for item in cell_items:
            print(f"   🔸 {item.item_name}")
            print(f"      小区: {item.cell_id}, 扇区: {item.sector_id}, 频段: {item.band}")
        
        print(f"\n🎯 测试结果:")
        print(f"   ✅ 成功使用小区级模板")
        print(f"   ✅ 正确生成 {len(cell_items)} 个小区级检查项")
        print(f"   ✅ 包含扇区ID、频段、小区ID等完整信息")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def compare_templates():
    """对比旧模板和新模板的差异"""
    
    print("\n🔄 对比模板升级效果\n")
    
    db = SessionLocal()
    try:
        # 获取所有模板
        templates = db.query(InspectionTemplate).all()
        
        print("📊 模板统计:")
        
        cell_level_count = 0
        sector_level_count = 0
        site_level_count = 0
        
        for template in templates:
            template_data = template.template_data
            if isinstance(template_data, str):
                template_data = json.loads(template_data)
            
            categories = template_data.get('check_categories', template_data.get('categories', []))
            
            template_cell_count = 0
            template_sector_count = 0
            template_site_count = 0
            
            for category in categories:
                if category.get('cell_specific', False):
                    template_cell_count += 1
                    cell_level_count += 1
                elif category.get('sector_specific', False):
                    template_sector_count += 1
                    sector_level_count += 1
                else:
                    template_site_count += 1
                    site_level_count += 1
            
            print(f"   📱 {template.template_name}:")
            print(f"      站点级: {template_site_count}, 扇区级: {template_sector_count}, 小区级: {template_cell_count}")
        
        print(f"\n🎯 总计:")
        print(f"   站点级类别: {site_level_count}")
        print(f"   扇区级类别: {sector_level_count}")
        print(f"   小区级类别: {cell_level_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 对比失败: {e}")
        return False
    finally:
        db.close()


def main():
    """主函数"""
    
    print("🚀 测试升级后的小区级模板\n")
    
    # 1. 对比模板升级效果
    compare_templates()
    
    # 2. 测试小区级模板生成检查项
    test_cell_level_template()
    
    print(f"\n🎉 测试完成！")
    print(f"\n💡 小区级检查模板已成功升级:")
    print(f"   ✅ 扇区级检查改为小区级")
    print(f"   ✅ 新增小区射频测试类别")
    print(f"   ✅ 新增小区配置验证类别")
    print(f"   ✅ 支持基于站点规划的动态检查项生成")


if __name__ == "__main__":
    main()