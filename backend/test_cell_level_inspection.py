#!/usr/bin/env python3
"""
测试小区级检查功能
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import get_db, SessionLocal
from app.models.site import Site
from app.models.planning import SitePlanning, SitePlanningSector
from app.models.user import User
from app.services.cell_generator import CellGenerator
from sqlalchemy.orm import Session


def create_test_site_planning(db: Session):
    """创建测试站点规划数据"""
    
    # 创建测试站点
    test_site = Site(
        site_code="TEST_CELL_001",
        site_name="小区级检查测试站点", 
        site_type="macro",
        address="测试地址",
        province="北京",
        city="北京",
        district="朝阳区",
        priority="normal",
        created_by=1
    )
    db.add(test_site)
    db.flush()
    
    # 创建站点规划：3个扇区，每个扇区2个频段
    planning = SitePlanning(
        site_id=test_site.id,
        version=1,
        bands=["n41", "n78", "n3"],
        sector_count=3,
        notes="测试规划：3扇区×多频段配置",
        is_current=True,
        created_by=1
    )
    db.add(planning)
    db.flush()
    
    # 创建扇区配置
    sectors_config = [
        {"index": 1, "azimuth": 0, "downtilt": 5, "bands": ["n41", "n78"]},
        {"index": 2, "azimuth": 120, "downtilt": 6, "bands": ["n41", "n3"]},
        {"index": 3, "azimuth": 240, "downtilt": 4, "bands": ["n78", "n3"]}
    ]
    
    for config in sectors_config:
        sector = SitePlanningSector(
            planning_id=planning.id,
            sector_index=config["index"],
            azimuth_deg=config["azimuth"],
            downtilt_deg=config["downtilt"],
            bands=config["bands"]
        )
        db.add(sector)
    
    db.commit()
    print(f"✅ 创建测试站点: {test_site.site_code} (ID: {test_site.id})")
    return test_site.id


def test_cell_generation(db: Session, site_id: int):
    """测试小区生成功能"""
    
    print(f"\n🧪 测试小区生成 - 站点ID: {site_id}")
    
    # 测试基于规划数据的小区生成
    cells = CellGenerator.generate_cells_from_planning(db, site_id)
    cells_summary = CellGenerator.get_cells_summary(cells)
    
    print(f"📊 小区生成结果:")
    print(f"   总小区数: {cells_summary['total_cells']}")
    print(f"   扇区数: {cells_summary['sector_count']}")
    print(f"   频段: {cells_summary['bands']}")
    print(f"   平均每扇区小区数: {cells_summary['cells_per_sector']:.1f}")
    
    print(f"\n📱 小区详情:")
    for i, cell in enumerate(cells, 1):
        print(f"   {i}. 小区ID: {cell.cell_id}, 扇区: {cell.sector_id}, 频段: {cell.band}")
        if cell.azimuth is not None:
            print(f"      方位角: {cell.azimuth}°, 下倾角: {cell.downtilt}°")
    
    return cells


def test_template_structure():
    """测试模板结构"""
    
    print(f"\n📋 检查模板结构:")
    
    # 读取示例模板
    with open("cell_level_template_example.json", "r", encoding="utf-8") as f:
        template = json.load(f)
    
    categories = template["template_data"]["check_categories"]
    
    for category in categories:
        category_type = []
        if category.get("sector_specific"):
            category_type.append("扇区级")
        if category.get("cell_specific"):
            category_type.append("小区级")
        if not category_type:
            category_type.append("站点级")
            
        print(f"   📂 {category['category_name']} ({'/'.join(category_type)})")
        for item in category["items"]:
            print(f"      ▪ {item['item_name']} - {item['required_type']}")


def simulate_inspection_creation(db: Session, site_id: int, cells):
    """模拟检查项创建过程"""
    
    print(f"\n🔧 模拟检查项创建:")
    
    # 读取模板
    with open("cell_level_template_example.json", "r", encoding="utf-8") as f:
        template = json.load(f)
    
    total_items = 0
    categories = template["template_data"]["check_categories"]
    
    for category in categories:
        category_name = category["category_name"]
        items = category["items"]
        
        if category.get("cell_specific"):
            # 小区级检查项
            item_count = len(items) * len(cells)
            print(f"   🔸 {category_name}: {item_count} 项 ({len(items)} 项 × {len(cells)} 小区)")
            
            for item in items:
                for cell in cells:
                    item_name = f"{item['item_name']} - 小区 {cell.cell_id}"
                    print(f"      - {item_name}")
                    
        elif category.get("sector_specific"):
            # 扇区级检查项
            sectors = set(cell.sector_id for cell in cells)
            item_count = len(items) * len(sectors)
            print(f"   🔸 {category_name}: {item_count} 项 ({len(items)} 项 × {len(sectors)} 扇区)")
            
        else:
            # 站点级检查项
            item_count = len(items)
            print(f"   🔸 {category_name}: {item_count} 项")
        
        total_items += item_count
    
    print(f"\n📈 检查项统计:")
    print(f"   总检查项数: {total_items}")
    
    # 对比传统方式（固定3扇区）
    traditional_items = 0
    for category in categories:
        if category.get("sector_specific") or category.get("cell_specific"):
            traditional_items += len(category["items"]) * 3  # 假设3个扇区
        else:
            traditional_items += len(category["items"])
    
    print(f"   传统方式(3扇区): {traditional_items}")
    print(f"   改进效果: {total_items - traditional_items:+d} 项 ({((total_items/traditional_items-1)*100):+.1f}%)")


def main():
    """主测试函数"""
    
    print("🚀 开始测试小区级检查功能\n")
    
    db = SessionLocal()
    try:
        # 1. 创建测试数据
        site_id = create_test_site_planning(db)
        
        # 2. 测试小区生成
        cells = test_cell_generation(db, site_id)
        
        # 3. 测试模板结构
        test_template_structure()
        
        # 4. 模拟检查项创建
        simulate_inspection_creation(db, site_id, cells)
        
        print(f"\n✅ 测试完成!")
        
        # 展示使用示例
        print(f"\n📚 使用示例:")
        print(f"   1. 创建支持小区级检查的模板，设置 'cell_specific': true")
        print(f"   2. 站点规划配置扇区和频段信息")
        print(f"   3. 创建工单时自动生成对应数量的小区检查项")
        print(f"   4. 检查项包含扇区ID、频段、小区ID等完整信息")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()