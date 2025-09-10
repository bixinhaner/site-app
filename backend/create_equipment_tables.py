#!/usr/bin/env python3
"""
设备管理模块数据库迁移脚本
创建设备、库存、出入库相关表
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.database import Base
from app.models.equipment import Equipment, EquipmentPackage, EquipmentInstance, Warehouse, Inventory, StockTransaction, StockTransactionItem, PickupRecord
from app.models.inspection import TaskAssignment
from app.models.user import User

def create_equipment_tables():
    """创建设备管理相关表"""
    print("正在连接数据库...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    print("正在创建设备管理表...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("数据库表创建成功！")
    
    # 创建数据库会话
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print("正在初始化基础数据...")
        
        # 1. 创建默认仓库
        existing_warehouse = db.query(Warehouse).filter(Warehouse.warehouse_code == "WH001").first()
        if not existing_warehouse:
            default_warehouse = Warehouse(
                warehouse_code="WH001",
                warehouse_name="主仓库",
                address="北京市海淀区中关村软件园",
                contact_person="仓库管理员",
                contact_phone="010-12345678",
                manager_id=1  # 假设admin用户ID为1
            )
            db.add(default_warehouse)
            print("✓ 创建默认仓库")
        
        # 2. 创建示例设备型号
        equipment_data = [
            {
                "equipment_code": "BBU-5G-001", 
                "equipment_name": "5G基带处理单元",
                "category": "main_device", 
                "model": "BBU5900", 
                "brand": "华为",
                "unit": "台",
                "barcode_prefix": "BBU",
                "standard_price": 150000.00,
                "specifications": {"频段": "2.6GHz", "功率": "200W", "接口": "CPRI"},
                "description": "5G基站核心处理单元"
            },
            {
                "equipment_code": "RRU-5G-001",
                "equipment_name": "5G射频拉远单元", 
                "category": "main_device",
                "model": "RRU5258", 
                "brand": "华为",
                "unit": "台",
                "barcode_prefix": "RRU",
                "standard_price": 80000.00,
                "specifications": {"频段": "2.6GHz", "功率": "200W"},
                "description": "5G射频处理单元"
            },
            {
                "equipment_code": "ANT-800M-001", 
                "equipment_name": "800M天线",
                "category": "auxiliary", 
                "model": "ANT-800-15dBi", 
                "brand": "凯仕林",
                "unit": "副",
                "barcode_prefix": "ANT",
                "standard_price": 2500.00,
                "specifications": {"频段": "800MHz", "增益": "15dBi", "极化": "双极化"},
                "description": "800M频段定向天线"
            },
            {
                "equipment_code": "CBL-RF-001", 
                "equipment_name": "射频同轴电缆",
                "category": "auxiliary", 
                "model": "LCF78-50J", 
                "brand": "大唐电缆",
                "unit": "米",
                "standard_price": 45.00,
                "specifications": {"阻抗": "50欧", "直径": "7/8英寸", "损耗": "0.1dB/m"},
                "description": "7/8英寸射频馈线"
            },
            {
                "equipment_code": "PWR-DC-001", 
                "equipment_name": "直流电源模块",
                "category": "auxiliary", 
                "model": "PWR48-3000", 
                "brand": "艾默生",
                "unit": "台",
                "standard_price": 12000.00,
                "specifications": {"输出电压": "-48V", "输出电流": "60A", "效率": "95%"},
                "description": "通信设备直流供电模块"
            }
        ]
        
        for eq_data in equipment_data:
            existing = db.query(Equipment).filter(Equipment.equipment_code == eq_data["equipment_code"]).first()
            if not existing:
                equipment = Equipment(**eq_data, created_by=1)
                db.add(equipment)
                print(f"✓ 创建设备型号: {eq_data['equipment_name']}")
        
        db.commit()
        
        # 3. 创建示例套装配置
        # 获取创建的设备
        bbu = db.query(Equipment).filter(Equipment.equipment_code == "BBU-5G-001").first()
        rru = db.query(Equipment).filter(Equipment.equipment_code == "RRU-5G-001").first()
        antenna = db.query(Equipment).filter(Equipment.equipment_code == "ANT-800M-001").first()
        cable = db.query(Equipment).filter(Equipment.equipment_code == "CBL-RF-001").first()
        power = db.query(Equipment).filter(Equipment.equipment_code == "PWR-DC-001").first()
        
        if bbu and rru and antenna and cable and power:
            # 创建5G基站套装
            existing_package = db.query(EquipmentPackage).filter(EquipmentPackage.package_code == "PKG-5G-BASIC").first()
            if not existing_package:
                package = EquipmentPackage(
                    package_code="PKG-5G-BASIC",
                    package_name="5G基站标准配置套装",
                    main_equipment_id=bbu.id,
                    site_type="5G基站",
                    description="5G基站标准配置，包含BBU、RRU及配套设施",
                    created_by=1
                )
                db.add(package)
                db.flush()  # 获取package.id
                
                # 添加套装明细
                from app.models.equipment import EquipmentPackageItem
                items = [
                    {"equipment_id": bbu.id, "quantity": 1, "is_required": True},  # BBU
                    {"equipment_id": rru.id, "quantity": 3, "is_required": True},  # RRU
                    {"equipment_id": antenna.id, "quantity": 6, "is_required": True},  # 天线
                    {"equipment_id": cable.id, "quantity": 200, "is_required": True},  # 电缆
                    {"equipment_id": power.id, "quantity": 2, "is_required": True}   # 电源
                ]
                
                for item_data in items:
                    package_item = EquipmentPackageItem(
                        package_id=package.id,
                        **item_data
                    )
                    db.add(package_item)
                
                print("✓ 创建5G基站标准套装")
        
        # 4. 初始化库存数据
        warehouse = db.query(Warehouse).filter(Warehouse.warehouse_code == "WH001").first()
        if warehouse:
            initial_stocks = [
                {"equipment": bbu, "stock": 10},
                {"equipment": rru, "stock": 30}, 
                {"equipment": antenna, "stock": 60},
                {"equipment": cable, "stock": 5000},
                {"equipment": power, "stock": 20}
            ]
            
            for stock_data in initial_stocks:
                if stock_data["equipment"]:
                    existing_inventory = db.query(Inventory).filter(
                        Inventory.warehouse_id == warehouse.id,
                        Inventory.equipment_id == stock_data["equipment"].id
                    ).first()
                    
                    if not existing_inventory:
                        inventory = Inventory(
                            warehouse_id=warehouse.id,
                            equipment_id=stock_data["equipment"].id,
                            current_stock=stock_data["stock"],
                            available_stock=stock_data["stock"],
                            min_stock=stock_data["stock"] // 5,  # 最低库存为初始库存的20%
                            max_stock=stock_data["stock"] * 3,   # 最大库存为初始库存的3倍
                            last_updated_by=1
                        )
                        db.add(inventory)
                        print(f"✓ 初始化库存: {stock_data['equipment'].equipment_name} - {stock_data['stock']}台")
        
        db.commit()
        print("\n✅ 设备管理模块初始化完成！")
        print("\n📊 初始化数据汇总:")
        print("- 5种设备型号 (BBU、RRU、天线、电缆、电源)")
        print("- 1个标准5G套装配置")
        print("- 1个默认仓库")
        print("- 初始库存数据")
        
    except Exception as e:
        print(f"❌ 初始化数据时出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def test_api_access():
    """测试API访问"""
    print("\n🧪 测试API访问...")
    print("请启动后端服务器：python start_backend.py")
    print("然后访问以下URL测试API:")
    print("- 设备列表: http://localhost:8000/api/equipment/")
    print("- 套装列表: http://localhost:8000/api/equipment/packages")
    print("- 库存查询: http://localhost:8000/api/stock/inventory")
    print("- API文档: http://localhost:8000/docs")

if __name__ == "__main__":
    print("🚀 开始创建设备管理模块...")
    try:
        create_equipment_tables()
        test_api_access()
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        sys.exit(1)