#!/usr/bin/env python3
"""
数据库表创建脚本 - 增强版检查系统
创建新的增强版检查相关表结构
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.database import Base
from app.models.inspection import (
    InspectionTemplate, 
    SiteInspection, 
    InspectionCheckItem, 
    InspectionPhoto,
    Inspection  # 保持原有表
)

def create_enhanced_tables():
    """创建增强版检查相关表"""
    
    # 连接数据库
    engine = create_engine(settings.DATABASE_URL)
    
    print("开始创建增强版检查数据库表...")
    
    try:
        # 创建所有新表
        Base.metadata.create_all(bind=engine)
        print("✓ 数据库表创建成功")
        
        # 插入示例检查模板数据
        create_sample_templates(engine)
        
        print("数据库部署完成!")
        return True
        
    except Exception as e:
        print(f"✗ 创建数据库表失败: {str(e)}")
        return False

def create_sample_templates(engine):
    """创建示例检查模板"""
    
    sample_template = {
        "template_name": "基站安装检查模板",
        "categories": [
            {
                "id": "site_level",
                "name": "站点级检查", 
                "description": "整体站点环境检查",
                "items": [
                    {
                        "id": "site_access",
                        "name": "站点接入道路",
                        "description": "检查站点接入道路通畅性",
                        "required_type": "photo",
                        "photo_requirements": {
                            "description": "拍摄站点入口道路全景",
                            "gps_required": True,
                            "include": ["道路标识", "路面状况", "通行能力"]
                        }
                    },
                    {
                        "id": "site_environment", 
                        "name": "站点周边环境",
                        "description": "检查站点周边环境情况",
                        "required_type": "both",
                        "photo_requirements": {
                            "description": "拍摄站点360度环境",
                            "gps_required": True,
                            "include": ["建筑物分布", "地形地貌", "潜在干扰源"]
                        },
                        "data_fields": [
                            {"name": "noise_level", "type": "number", "unit": "dB", "label": "噪音等级"},
                            {"name": "dust_level", "type": "select", "options": ["低", "中", "高"], "label": "粉尘等级"}
                        ]
                    }
                ]
            },
            {
                "id": "sector_level",
                "name": "扇区级检查",
                "description": "各扇区设备检查", 
                "items": [
                    {
                        "id": "antenna_installation",
                        "name": "天线安装",
                        "description": "检查天线安装状况",
                        "required_type": "photo",
                        "photo_requirements": {
                            "description": "拍摄天线安装细节",
                            "gps_required": True,
                            "include": ["天线位置", "安装角度", "固定方式", "标识标签"]
                        }
                    },
                    {
                        "id": "rru_installation", 
                        "name": "RRU设备安装",
                        "description": "检查RRU设备安装",
                        "required_type": "both",
                        "photo_requirements": {
                            "description": "拍摄RRU设备安装状况",
                            "gps_required": True,
                            "include": ["设备位置", "散热情况", "线缆连接", "设备标签"]
                        },
                        "data_fields": [
                            {"name": "device_sn", "type": "text", "label": "设备序列号"},
                            {"name": "power_level", "type": "number", "unit": "dBm", "label": "功率等级"}
                        ]
                    }
                ]
            }
        ]
    }
    
    try:
        with engine.connect() as conn:
            # 检查是否已有模板数据
            result = conn.execute(text("SELECT COUNT(*) FROM inspection_templates"))
            count = result.scalar()
            
            if count == 0:
                # 插入示例模板
                template_sql = """
                INSERT INTO inspection_templates 
                (id, site_id, template_name, template_version, template_data, status, created_by)
                VALUES 
                ('default_install_template', 1, :template_name, '1.0', :template_data, 'approved', 1)
                """
                
                import json
                conn.execute(text(template_sql), {
                    'template_name': sample_template['template_name'],
                    'template_data': json.dumps(sample_template, ensure_ascii=False)
                })
                conn.commit()
                print("✓ 示例检查模板创建成功")
            else:
                print("✓ 检查模板已存在，跳过创建")
                
    except Exception as e:
        print(f"✗ 创建示例模板失败: {str(e)}")

def show_table_info():
    """显示表结构信息"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    table_info = {
        'inspection_templates': '检查模板表 - 存储检查模板配置',
        'site_inspections': '站点检查记录表 - 存储检查实例',
        'inspection_check_items': '检查项记录表 - 存储具体检查项结果',
        'inspection_photos': '检查照片表 - 存储检查照片信息',
        'inspections': '原检查表 - 向后兼容'
    }
    
    print("\n=== 数据库表结构信息 ===")
    for table, desc in table_info.items():
        print(f"- {table}: {desc}")
    
    try:
        with engine.connect() as conn:
            print("\n=== 表创建状态 ===")
            for table in table_info.keys():
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"✓ {table}: {count} 条记录")
                except Exception as e:
                    print(f"✗ {table}: 表不存在或查询失败")
                    
    except Exception as e:
        print(f"查询表状态失败: {str(e)}")

if __name__ == "__main__":
    print("=== 增强版检查系统数据库部署 ===")
    print(f"数据库URL: {settings.DATABASE_URL}")
    
    success = create_enhanced_tables()
    
    if success:
        show_table_info()
        print("\n部署完成! 可以启动应用服务器了.")
    else:
        print("\n部署失败! 请检查错误信息.")
        sys.exit(1)