#!/usr/bin/env python3
"""
调试脚本：测试CellGenerator为站点5生成小区的逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.planning import SitePlanning, SitePlanningSector
from app.services.cell_generator import CellGenerator
import json

# 创建数据库连接
engine = create_engine('sqlite:///site_manager.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_cell_generator():
    """测试站点5的小区生成"""
    db = SessionLocal()
    try:
        site_id = 5
        print(f"=== 调试站点 {site_id} 的小区生成 ===")
        
        # 1. 直接查询规划数据
        planning = db.query(SitePlanning).filter(
            SitePlanning.site_id == site_id,
            SitePlanning.is_current == True
        ).first()
        
        if not planning:
            print("❌ 没有找到当前规划数据")
            return
            
        print(f"✅ 找到规划数据:")
        print(f"   规划ID: {planning.id}")
        print(f"   站点ID: {planning.site_id}")
        print(f"   版本: {planning.version}")
        print(f"   扇区数量: {planning.sector_count}")
        print(f"   站点频段: {planning.bands}")
        print(f"   是否当前: {planning.is_current}")
        
        # 2. 查询扇区数据
        sectors = db.query(SitePlanningSector).filter(
            SitePlanningSector.planning_id == planning.id
        ).order_by(SitePlanningSector.sector_index).all()
        
        print(f"\n✅ 找到 {len(sectors)} 个扇区:")
        for sector in sectors:
            print(f"   扇区 {sector.sector_index}: 方位角={sector.azimuth_deg}°, 下倾角={sector.downtilt_deg}°, 频段={sector.bands}")
            
        # 3. 测试CellGenerator.get_site_planning
        print(f"\n=== 测试 CellGenerator.get_site_planning ===")
        planning_from_generator = CellGenerator.get_site_planning(db, site_id)
        if planning_from_generator:
            print(f"✅ CellGenerator找到规划数据: ID={planning_from_generator.id}")
            print(f"   扇区关系数量: {len(planning_from_generator.sectors) if planning_from_generator.sectors else 0}")
        else:
            print("❌ CellGenerator没有找到规划数据")
            
        # 4. 测试完整的小区生成
        print(f"\n=== 测试 CellGenerator.generate_cells_from_planning ===")
        cells = CellGenerator.generate_cells_from_planning(db, site_id)
        
        print(f"✅ 生成了 {len(cells)} 个小区:")
        for i, cell in enumerate(cells):
            print(f"   小区 {i+1}: {cell.to_dict()}")
            
        # 5. 获取小区摘要
        summary = CellGenerator.get_cells_summary(cells)
        print(f"\n✅ 小区摘要:")
        print(f"   总小区数: {summary['total_cells']}")
        print(f"   扇区数: {summary['sector_count']}")
        print(f"   频段: {summary['bands']}")
        print(f"   平均每扇区小区数: {summary['cells_per_sector']}")
        
        # 6. 分析期望vs实际
        expected_cells = []
        for sector in sectors:
            sector_bands = sector.bands or []
            if not sector_bands:
                sector_bands = planning.bands or ["default"]
            for band in sector_bands:
                expected_cells.append({
                    "sector_id": str(sector.sector_index),
                    "band": band,
                    "cell_id": f"{sector.sector_index}_{band}"
                })
                
        print(f"\n=== 期望vs实际对比 ===")
        print(f"期望小区数: {len(expected_cells)}")
        print(f"实际小区数: {len(cells)}")
        print(f"期望小区详情:")
        for cell in expected_cells:
            print(f"   {cell}")
            
        if len(expected_cells) != len(cells):
            print(f"❌ 小区数量不匹配！期望{len(expected_cells)}个，实际{len(cells)}个")
        else:
            print(f"✅ 小区数量匹配")
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_cell_generator()