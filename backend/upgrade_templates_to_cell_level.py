#!/usr/bin/env python3
"""
升级检查模板：将扇区级改为小区级
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.inspection import InspectionTemplate
from sqlalchemy.orm import Session


def upgrade_template_to_cell_level(db: Session, template_id: str):
    """将单个模板升级为小区级"""
    
    template = db.query(InspectionTemplate).filter(InspectionTemplate.id == template_id).first()
    if not template:
        print(f"❌ 模板 {template_id} 不存在")
        return False
    
    print(f"🔄 升级模板: {template.template_name}")
    
    # 解析模板数据
    template_data = template.template_data
    if isinstance(template_data, str):
        template_data = json.loads(template_data)
    
    # 获取检查类别
    categories = template_data.get('check_categories', template_data.get('categories', []))
    updated = False
    
    for category in categories:
        category_name = category.get('category_name', category.get('name'))
        
        # 将扇区级改为小区级
        if category.get('sector_specific', False):
            print(f"  📱 升级类别: {category_name} (扇区级 → 小区级)")
            category['sector_specific'] = False
            category['cell_specific'] = True
            updated = True
            
            # 更新类别描述
            if '扇区' in str(category.get('description', '')):
                category['description'] = category['description'].replace('扇区', '小区')
            
            # 更新检查项
            for item in category.get('items', []):
                item_name = item.get('item_name', item.get('name'))
                if '扇区' in item_name:
                    item['item_name'] = item_name.replace('扇区', '小区')
                    item['name'] = item['item_name']  # 向后兼容
                
                if '扇区' in str(item.get('description', '')):
                    item['description'] = item['description'].replace('扇区', '小区')
    
    # 添加新的小区级检查类别
    new_categories = []
    
    # 小区射频检查
    rf_category = {
        "category_id": "cell_rf_test",
        "category_name": "小区射频测试",
        "description": "各小区射频性能和覆盖测试",
        "sector_specific": False,
        "cell_specific": True,
        "items": [
            {
                "item_id": "cell_power_measurement",
                "item_name": "小区功率测量",
                "description": "测量小区发射功率和接收功率",
                "required_type": "both",
                "mandatory": True,
                "photo_requirements": {
                    "description": "拍摄测试仪表和测试结果",
                    "gps_required": True,
                    "min_photos": 2,
                    "include": ["测试设备", "测试结果", "频谱图"]
                },
                "data_fields": [
                    {"name": "tx_power", "type": "number", "unit": "dBm", "label": "发射功率", "required": True},
                    {"name": "rx_power", "type": "number", "unit": "dBm", "label": "接收功率", "required": True},
                    {"name": "vswr", "type": "number", "label": "驻波比", "required": True}
                ]
            },
            {
                "item_id": "cell_coverage_test",
                "item_name": "小区覆盖测试",
                "description": "测试小区覆盖范围和信号质量",
                "required_type": "both",
                "mandatory": True,
                "photo_requirements": {
                    "description": "拍摄测试位置和信号强度",
                    "gps_required": True,
                    "min_photos": 3,
                    "include": ["测试位置", "信号强度", "覆盖地图"]
                },
                "data_fields": [
                    {"name": "rsrp", "type": "number", "unit": "dBm", "label": "RSRP", "required": True},
                    {"name": "rsrq", "type": "number", "unit": "dB", "label": "RSRQ", "required": True},
                    {"name": "sinr", "type": "number", "unit": "dB", "label": "SINR", "required": True},
                    {"name": "coverage_radius", "type": "number", "unit": "m", "label": "覆盖半径"}
                ]
            }
        ]
    }
    
    # 小区配置检查
    config_category = {
        "category_id": "cell_configuration",
        "category_name": "小区配置检查",
        "description": "验证小区参数配置正确性",
        "sector_specific": False,
        "cell_specific": True,
        "items": [
            {
                "item_id": "cell_params_verify",
                "item_name": "小区参数验证",
                "description": "验证小区基本参数配置",
                "required_type": "data",
                "mandatory": True,
                "data_fields": [
                    {"name": "cell_id", "type": "text", "label": "小区ID", "required": True},
                    {"name": "pci", "type": "number", "label": "PCI", "required": True},
                    {"name": "earfcn", "type": "number", "label": "频点", "required": True},
                    {"name": "bandwidth", "type": "select", "options": ["5MHz", "10MHz", "15MHz", "20MHz", "100MHz"], "label": "带宽", "required": True},
                    {"name": "tac", "type": "text", "label": "TAC", "required": True}
                ]
            },
            {
                "item_id": "neighbor_config",
                "item_name": "邻区配置",
                "description": "检查邻区关系配置",
                "required_type": "data",
                "mandatory": False,
                "data_fields": [
                    {"name": "neighbor_count", "type": "number", "label": "邻区数量"},
                    {"name": "handover_threshold", "type": "number", "unit": "dB", "label": "切换门限"},
                    {"name": "neighbor_optimization", "type": "select", "options": ["已优化", "待优化", "无需优化"], "label": "邻区优化状态"}
                ]
            }
        ]
    }
    
    # 检查是否已存在这些类别
    existing_categories = [cat.get('category_id', cat.get('id')) for cat in categories]
    
    if "cell_rf_test" not in existing_categories:
        new_categories.append(rf_category)
        print(f"  ➕ 添加类别: {rf_category['category_name']}")
        updated = True
    
    if "cell_configuration" not in existing_categories:
        new_categories.append(config_category)
        print(f"  ➕ 添加类别: {config_category['category_name']}")
        updated = True
    
    # 添加新类别到模板
    if new_categories:
        categories.extend(new_categories)
    
    if updated:
        # 更新模板数据
        if 'check_categories' in template_data:
            template_data['check_categories'] = categories
        else:
            template_data['categories'] = categories
        
        # 更新版本信息
        if 'template_version' in template_data:
            version = template_data['template_version']
            if version.count('.') == 1:
                major, minor = version.split('.')
                template_data['template_version'] = f"{major}.{int(minor)+1}"
        
        # 添加升级记录
        template_data['upgrade_history'] = template_data.get('upgrade_history', [])
        template_data['upgrade_history'].append({
            "version": template_data.get('template_version', '2.0'),
            "date": datetime.now().isoformat(),
            "description": "升级为小区级检查，支持基于站点规划的动态检查项生成"
        })
        
        # 保存到数据库
        template.template_data = template_data
        db.commit()
        
        print(f"  ✅ 模板升级完成")
        return True
    else:
        print(f"  ℹ️  模板无需升级")
        return False


def create_new_cell_level_template(db: Session):
    """创建全新的小区级检查模板"""
    
    print(f"🆕 创建全新的小区级检查模板")
    
    template_data = {
        "template_name": "5G基站小区级全面检查模板",
        "template_version": "3.0",
        "description": "支持小区级检查的5G基站全面检查模板，基于站点规划数据自动生成检查项",
        "check_categories": [
            {
                "category_id": "site_basic",
                "category_name": "站点基础检查",
                "description": "站点整体环境和基础设施检查",
                "sector_specific": False,
                "cell_specific": False,
                "items": [
                    {
                        "item_id": "site_power",
                        "item_name": "电源检查",
                        "description": "检查站点供电系统",
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄供电系统",
                            "gps_required": True,
                            "min_photos": 2
                        },
                        "data_fields": [
                            {"name": "power_voltage", "type": "number", "unit": "V", "label": "电源电压", "required": True},
                            {"name": "ups_status", "type": "select", "options": ["正常", "异常"], "label": "UPS状态", "required": True}
                        ]
                    },
                    {
                        "item_id": "site_environment",
                        "item_name": "环境检查",
                        "description": "检查站点周边环境",
                        "required_type": "photo",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄站点环境",
                            "gps_required": True,
                            "min_photos": 4
                        }
                    }
                ]
            },
            {
                "category_id": "sector_physical",
                "category_name": "扇区物理检查", 
                "description": "各扇区天线和设备物理安装检查",
                "sector_specific": True,
                "cell_specific": False,
                "items": [
                    {
                        "item_id": "antenna_installation",
                        "item_name": "天线安装检查",
                        "description": "检查天线安装位置和角度",
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄天线安装",
                            "gps_required": True,
                            "min_photos": 3
                        },
                        "data_fields": [
                            {"name": "antenna_azimuth", "type": "number", "unit": "度", "label": "天线方位角", "required": True},
                            {"name": "antenna_downtilt", "type": "number", "unit": "度", "label": "天线下倾角", "required": True},
                            {"name": "antenna_height", "type": "number", "unit": "m", "label": "天线高度", "required": True}
                        ]
                    }
                ]
            },
            {
                "category_id": "cell_rf_performance",
                "category_name": "小区射频性能",
                "description": "各小区射频性能和信号质量测试",
                "sector_specific": False,
                "cell_specific": True,
                "items": [
                    {
                        "item_id": "cell_power_test",
                        "item_name": "小区功率测试",
                        "description": "测试小区发射功率和驻波比",
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄功率测试结果",
                            "gps_required": True,
                            "min_photos": 2
                        },
                        "data_fields": [
                            {"name": "tx_power", "type": "number", "unit": "dBm", "label": "发射功率", "required": True},
                            {"name": "vswr", "type": "number", "label": "驻波比", "required": True}
                        ]
                    },
                    {
                        "item_id": "cell_signal_quality",
                        "item_name": "小区信号质量",
                        "description": "测试小区信号覆盖和质量",
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄信号测试结果",
                            "gps_required": True,
                            "min_photos": 2
                        },
                        "data_fields": [
                            {"name": "rsrp", "type": "number", "unit": "dBm", "label": "RSRP", "required": True},
                            {"name": "sinr", "type": "number", "unit": "dB", "label": "SINR", "required": True}
                        ]
                    }
                ]
            },
            {
                "category_id": "cell_configuration",
                "category_name": "小区配置验证",
                "description": "验证各小区参数配置正确性",
                "sector_specific": False,
                "cell_specific": True,
                "items": [
                    {
                        "item_id": "cell_basic_params",
                        "item_name": "小区基本参数",
                        "description": "验证小区基本配置参数",
                        "required_type": "data",
                        "mandatory": True,
                        "data_fields": [
                            {"name": "pci", "type": "number", "label": "PCI", "required": True},
                            {"name": "earfcn", "type": "number", "label": "频点", "required": True},
                            {"name": "bandwidth", "type": "select", "options": ["5MHz", "10MHz", "15MHz", "20MHz", "100MHz"], "label": "带宽", "required": True}
                        ]
                    }
                ]
            }
        ],
        "upgrade_history": [
            {
                "version": "3.0",
                "date": datetime.now().isoformat(),
                "description": "创建小区级检查模板，支持基于站点规划的动态检查项生成"
            }
        ]
    }
    
    # 检查是否已存在同名模板
    existing = db.query(InspectionTemplate).filter(
        InspectionTemplate.template_name == template_data["template_name"]
    ).first()
    
    if existing:
        print(f"  ⚠️  已存在同名模板，跳过创建")
        return False
    
    # 创建新模板
    import uuid
    new_template = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name=template_data["template_name"],
        template_data=template_data,
        created_by=1
    )
    
    db.add(new_template)
    db.commit()
    
    print(f"  ✅ 创建成功，模板ID: {new_template.id}")
    return True


def main():
    """主函数"""
    
    print("🚀 升级检查模板为小区级\n")
    
    db = SessionLocal()
    try:
        # 获取所有模板
        templates = db.query(InspectionTemplate).all()
        
        print(f"📋 找到 {len(templates)} 个模板\n")
        
        upgraded_count = 0
        
        # 升级现有模板
        for template in templates:
            if upgrade_template_to_cell_level(db, template.id):
                upgraded_count += 1
            print()
        
        # 创建新的小区级模板
        if create_new_cell_level_template(db):
            upgraded_count += 1
        
        print(f"🎉 升级完成！")
        print(f"   升级模板数: {upgraded_count}")
        print(f"   总模板数: {len(templates) + 1}")
        
        # 显示升级后的统计
        print(f"\n📊 升级后模板统计:")
        updated_templates = db.query(InspectionTemplate).all()
        
        for template in updated_templates:
            template_data = template.template_data
            if isinstance(template_data, str):
                template_data = json.loads(template_data)
            
            categories = template_data.get('check_categories', template_data.get('categories', []))
            cell_categories = sum(1 for cat in categories if cat.get('cell_specific', False))
            sector_categories = sum(1 for cat in categories if cat.get('sector_specific', False))
            site_categories = sum(1 for cat in categories if not cat.get('cell_specific', False) and not cat.get('sector_specific', False))
            
            print(f"   📱 {template.template_name}:")
            print(f"      站点级: {site_categories}, 扇区级: {sector_categories}, 小区级: {cell_categories}")
        
    except Exception as e:
        print(f"❌ 升级失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()