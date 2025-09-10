#!/usr/bin/env python3
"""
初始化测试数据到数据库
运行此脚本来添加测试用户、站点和检查模板数据
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal, engine
from app.models.user import User
from app.models.site import Site
from app.models.inspection import (
    Inspection, InspectionTemplate, SiteInspection, 
    InspectionCheckItem, InspectionStatusEnum, InspectionTypeEnum
)
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

async def init_test_data():
    """初始化测试数据"""
    
    # 获取数据库连接
    db = SessionLocal()
    
    try:
        print("🚀 开始初始化测试数据...")
        
        # 1. 创建测试用户
        print("👤 创建测试用户...")
        test_users = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "hashed_password": hash_password("admin123"),
                "full_name": "系统管理员",
                "role": "admin",
                "is_active": True,
            },
            {
                "username": "inspector1",
                "email": "inspector1@example.com", 
                "hashed_password": hash_password("password123"),
                "full_name": "张工程师",
                "role": "inspector",
                "is_active": True,
            },
            {
                "username": "inspector2",
                "email": "inspector2@example.com",
                "hashed_password": hash_password("password123"),
                "full_name": "李工程师", 
                "role": "inspector",
                "is_active": True,
            },
            {
                "username": "reviewer1",
                "email": "reviewer1@example.com",
                "hashed_password": hash_password("password123"),
                "full_name": "王审核员",
                "role": "reviewer",
                "is_active": True,
            }
        ]
        
        created_users = {}
        for user_data in test_users:
            # 检查用户是否已存在
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing_user:
                user = User(**user_data)
                db.add(user)
                db.flush()  # 获取 ID
                created_users[user_data["username"]] = user
                print(f"  ✓ 创建用户: {user_data['username']} ({user_data['full_name']})")
            else:
                created_users[user_data["username"]] = existing_user
                print(f"  - 用户已存在: {user_data['username']}")
        
        # 2. 创建测试站点
        print("\n🏗️ 创建测试站点...")
        test_sites = [
            {
                "site_name": "北京朝阳站点001",
                "site_code": "BJ-CY-001", 
                "status": "construction",
                "site_type": "base_station",
                "address": "北京市朝阳区建国门外大街1号",
                "latitude": 39.9042,
                "longitude": 116.4074,
                "province": "北京市",
                "city": "北京市",
                "district": "朝阳区",
                "assigned_to": created_users["inspector1"].id,
                "created_by": created_users["admin"].id,
                "description": "中国移动基站点",
                "priority": "high"
            },
            {
                "site_name": "北京海淀站点002",
                "site_code": "BJ-HD-002",
                "status": "construction", 
                "site_type": "base_station",
                "address": "北京市海淀区中关村大街59号",
                "latitude": 39.9889,
                "longitude": 116.3068,
                "province": "北京市",
                "city": "北京市", 
                "district": "海淀区",
                "assigned_to": created_users["inspector1"].id,
                "created_by": created_users["admin"].id,
                "description": "中国联通基站点",
                "priority": "normal"
            },
            {
                "site_name": "北京丰台站点003",
                "site_code": "BJ-FT-003",
                "status": "construction",
                "site_type": "base_station", 
                "address": "北京市丰台区丰台街道1号",
                "latitude": 39.8583,
                "longitude": 116.2860,
                "province": "北京市",
                "city": "北京市",
                "district": "丰台区",
                "assigned_to": created_users["inspector2"].id,
                "created_by": created_users["admin"].id,
                "description": "中国电信基站点",
                "priority": "normal"
            },
            {
                "site_name": "北京西城站点004",
                "site_code": "BJ-XC-004",
                "status": "operational",
                "site_type": "base_station",
                "address": "北京市西城区西长安街1号",
                "latitude": 39.9133,
                "longitude": 116.3833,
                "province": "北京市",
                "city": "北京市",
                "district": "西城区",
                "assigned_to": created_users["inspector2"].id,
                "created_by": created_users["admin"].id,
                "description": "中国移动基站点",
                "priority": "high"
            }
        ]
        
        created_sites = {}
        for site_data in test_sites:
            # 检查站点是否已存在
            existing_site = db.query(Site).filter(Site.site_code == site_data["site_code"]).first()
            if not existing_site:
                site = Site(**site_data)
                db.add(site)
                db.flush()
                created_sites[site_data["site_code"]] = site
                print(f"  ✓ 创建站点: {site_data['site_name']} ({site_data['site_code']})")
            else:
                created_sites[site_data["site_code"]] = existing_site
                print(f"  - 站点已存在: {site_data['site_code']}")
        
        # 3. 创建检查模板
        print("\n📋 创建检查模板...")
        
        # 创建一个完整的检查模板JSON结构
        template_json = {
            "template_name": "标准安装检查模板",
            "version": "1.0",
            "check_categories": [
                {
                    "category_id": "site_level",
                    "category_name": "站点级安装检查",
                    "sector_specific": False,
                    "items": [
                        {
                            "item_id": "tower_id_photo",
                            "item_name": "Picture of Tower ID with Coordinate",
                            "description": "拍摄站点大门照片",
                            "required_type": "photo",
                            "assigned_role": "施工队",
                            "validation_rules": {}
                        },
                        {
                            "item_id": "tower_height_check",
                            "item_name": "Full Picture of Tower&Antenna Height Check",
                            "description": "全塔照片和挂高检查",
                            "required_type": "both",
                            "assigned_role": "施工队",
                            "validation_rules": {"height": "必须在0-100米范围内"}
                        },
                        {
                            "item_id": "cabinet_environment",
                            "item_name": "Picture of Cabinet installation Environment",
                            "description": "机柜安装环境检查",
                            "required_type": "photo",
                            "assigned_role": "施工队",
                            "validation_rules": {}
                        }
                    ]
                },
                {
                    "category_id": "sector_level",
                    "category_name": "小区级安装检查",
                    "sector_specific": True,
                    "items": [
                        {
                            "item_id": "antenna_downtilt",
                            "item_name": "Antenna downtilt check",
                            "description": "天线下倾角检查",
                            "required_type": "both",
                            "assigned_role": "施工队",
                            "validation_rules": {"downtilt_angle": "下倾角必须在0-20度范围内"}
                        },
                        {
                            "item_id": "azimuth_check",
                            "item_name": "Azimuth check",
                            "description": "天线方位角检查",
                            "required_type": "both",
                            "assigned_role": "施工队",
                            "validation_rules": {"azimuth_angle": "方位角必须在0-360度范围内"}
                        },
                        {
                            "item_id": "vswr_check",
                            "item_name": "VSWR check",
                            "description": "驻波比检查",
                            "required_type": "both",
                            "assigned_role": "NOC",
                            "validation_rules": {"vswr_value": "驻波比必须在1.0-2.0范围内"}
                        }
                    ]
                }
            ]
        }
        
        # 为每个站点创建检查模板
        template_id_counter = 1
        for site_code, site in created_sites.items():
            template_id = f"template_{template_id_counter:03d}"
            existing_template = db.query(InspectionTemplate).filter(
                InspectionTemplate.id == template_id
            ).first()
            
            if not existing_template:
                template = InspectionTemplate(
                    id=template_id,
                    site_id=site.id,
                    template_name=f"{site.site_name} - 标准安装检查模板",
                    template_data=template_json,
                    status=InspectionStatusEnum.DRAFT,
                    created_by=created_users["admin"].id
                )
                db.add(template)
                print(f"  ✓ 创建检查模板: {template.template_name}")
            else:
                print(f"  - 检查模板已存在: {template_id}")
            
            template_id_counter += 1
        
        # 4. 创建示例检查记录
        print("\n📝 创建示例检查记录...")
        
        # 获取创建的模板
        db.flush()  # 确保模板已保存
        template_001 = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == "template_001"
        ).first()
        template_004 = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == "template_004"
        ).first()
        
        sample_inspections = [
            {
                "id": "inspection_001",
                "site_id": created_sites["BJ-CY-001"].id,
                "template_id": template_001.id if template_001 else "template_001",
                "inspection_type": InspectionTypeEnum.INSTALLATION,
                "status": InspectionStatusEnum.IN_PROGRESS,
                "inspector_id": created_users["inspector1"].id,
                "start_time": datetime.now() - timedelta(hours=2),
                "location": "北京市朝阳区建国门外大街1号",
                "weather": "晴天",
                "temperature": "25°C",
                "latitude": 39.9042,
                "longitude": 116.4074,
                "gps_accuracy": 5.0,
                "notes": "正在进行安装检查",
                "completion_rate": 35.0,
                "total_items": 9,  # 3站点级 + 3扇区级*3扇区 = 12项
                "completed_items": 3,
                "failed_items": 0
            },
            {
                "id": "inspection_002", 
                "site_id": created_sites["BJ-XC-004"].id,
                "template_id": template_004.id if template_004 else "template_004",
                "inspection_type": InspectionTypeEnum.MAINTENANCE,
                "status": InspectionStatusEnum.COMPLETED,
                "inspector_id": created_users["inspector2"].id,
                "start_time": datetime.now() - timedelta(days=7),
                "end_time": datetime.now() - timedelta(days=7, hours=-4),
                "location": "北京市西城区西长安街1号",
                "weather": "多云",
                "temperature": "22°C",
                "latitude": 39.9133,
                "longitude": 116.3833,
                "gps_accuracy": 3.0,
                "notes": "维护检查已完成，所有项目通过",
                "completion_rate": 100.0,
                "total_items": 9,
                "completed_items": 9,
                "failed_items": 0,
                "score": 95.0,
                "result": "pass"
            }
        ]
        
        for inspection_data in sample_inspections:
            existing_inspection = db.query(SiteInspection).filter(
                SiteInspection.id == inspection_data["id"]
            ).first()
            
            if not existing_inspection:
                inspection = SiteInspection(**inspection_data)
                db.add(inspection)
                db.flush()
                print(f"  ✓ 创建检查记录: 站点 {inspection.site_id} - {inspection.inspection_type.value}")
            else:
                print(f"  - 检查记录已存在: {inspection_data['id']}")
                
        # 提交所有更改
        db.commit()
        print("\n✅ 测试数据初始化完成！")
        
        # 显示登录信息
        print("\n🔐 测试用户登录信息:")
        print("  管理员: admin / admin123")
        print("  检查员1: inspector1 / password123")
        print("  检查员2: inspector2 / password123")
        print("  审核员: reviewer1 / password123")
        
        print(f"\n📍 创建了 {len(created_sites)} 个测试站点")
        print(f"📋 创建了 {len(created_sites)} 个检查模板")
        print(f"📝 创建了 {len(sample_inspections)} 个示例检查记录")
        
    except Exception as e:
        print(f"❌ 初始化失败: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    # 运行初始化
    asyncio.run(init_test_data())