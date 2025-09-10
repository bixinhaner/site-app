#!/usr/bin/env python3
"""
检查模板数据创建脚本
基于设计文档创建完整的检查模板数据
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from sqlalchemy import create_engine, text
from app.core.config import settings

def create_comprehensive_templates():
    """创建完整的检查模板数据"""
    
    # 安装检查模板
    installation_template = {
        "template_name": "基站安装检查模板",
        "template_version": "2.0",
        "description": "基站设备安装验收检查模板，包含站点级、扇区级和系统级检查",
        "categories": [
            {
                "id": "site_level",
                "name": "站点级检查",
                "description": "站点整体环境和基础设施检查",
                "sort_order": 1,
                "items": [
                    {
                        "id": "site_access_road",
                        "name": "站点接入道路",
                        "description": "检查站点接入道路的通畅性和标识",
                        "sort_order": 1,
                        "required_type": "photo",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄站点入口道路全景，确保道路标识清晰可见",
                            "gps_required": True,
                            "min_photos": 2,
                            "include": ["道路入口", "路面状况", "通行能力", "道路标识"]
                        }
                    },
                    {
                        "id": "site_environment",
                        "name": "站点周边环境",
                        "description": "评估站点周边环境对设备运行的影响",
                        "sort_order": 2,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄站点360度环境，重点关注潜在干扰源",
                            "gps_required": True,
                            "min_photos": 4,
                            "include": ["建筑物分布", "地形地貌", "潜在干扰源", "周边基站"]
                        },
                        "data_fields": [
                            {"name": "noise_level", "type": "number", "unit": "dB", "label": "环境噪音等级", "required": True},
                            {"name": "dust_level", "type": "select", "options": ["低", "中", "高"], "label": "粉尘等级", "required": True},
                            {"name": "interference_sources", "type": "multiselect", "options": ["高压线", "电视台", "雷达站", "工业设备", "无"], "label": "干扰源"}
                        ]
                    },
                    {
                        "id": "power_system",
                        "name": "供电系统",
                        "description": "检查站点供电系统的安装和配置",
                        "sort_order": 3,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄供电系统安装情况",
                            "gps_required": True,
                            "min_photos": 3,
                            "include": ["配电柜", "UPS设备", "电池组", "接地系统"]
                        },
                        "data_fields": [
                            {"name": "power_voltage", "type": "number", "unit": "V", "label": "供电电压", "required": True},
                            {"name": "ups_capacity", "type": "number", "unit": "kVA", "label": "UPS容量", "required": True},
                            {"name": "battery_backup_time", "type": "number", "unit": "小时", "label": "电池备电时间", "required": True}
                        ]
                    },
                    {
                        "id": "transmission_room",
                        "name": "传输机房",
                        "description": "检查传输机房环境和设备安装",
                        "sort_order": 4,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄机房内部环境和设备安装",
                            "gps_required": True,
                            "min_photos": 5,
                            "include": ["机房全景", "机柜安装", "线缆管理", "空调系统", "消防设备"]
                        },
                        "data_fields": [
                            {"name": "room_temperature", "type": "number", "unit": "°C", "label": "机房温度", "required": True},
                            {"name": "humidity", "type": "number", "unit": "%", "label": "相对湿度", "required": True},
                            {"name": "air_conditioning", "type": "select", "options": ["正常", "异常", "无"], "label": "空调状态", "required": True}
                        ]
                    }
                ]
            },
            {
                "id": "sector_level", 
                "name": "扇区级检查",
                "description": "各扇区天线和RRU设备检查",
                "sort_order": 2,
                "sectors": ["A", "B", "C"],
                "items": [
                    {
                        "id": "antenna_installation",
                        "name": "天线安装",
                        "description": "检查天线安装位置、角度和固定情况",
                        "sort_order": 1,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄天线安装的详细情况",
                            "gps_required": True,
                            "min_photos": 3,
                            "include": ["天线位置", "安装角度", "固定方式", "标识标签", "线缆连接"]
                        },
                        "data_fields": [
                            {"name": "antenna_height", "type": "number", "unit": "m", "label": "天线高度", "required": True},
                            {"name": "azimuth", "type": "number", "unit": "°", "label": "方位角", "required": True},
                            {"name": "downtilt", "type": "number", "unit": "°", "label": "下倾角", "required": True},
                            {"name": "antenna_gain", "type": "number", "unit": "dBi", "label": "天线增益"}
                        ]
                    },
                    {
                        "id": "rru_installation",
                        "name": "RRU设备安装",
                        "description": "检查RRU设备安装和配置",
                        "sort_order": 2,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄RRU设备安装状况和标签信息",
                            "gps_required": True,
                            "min_photos": 4,
                            "include": ["设备位置", "散热情况", "线缆连接", "设备标签", "接地线"]
                        },
                        "data_fields": [
                            {"name": "device_sn", "type": "text", "label": "设备序列号", "required": True},
                            {"name": "software_version", "type": "text", "label": "软件版本", "required": True},
                            {"name": "output_power", "type": "number", "unit": "dBm", "label": "输出功率", "required": True},
                            {"name": "working_frequency", "type": "number", "unit": "MHz", "label": "工作频率", "required": True}
                        ]
                    },
                    {
                        "id": "feeder_system",
                        "name": "馈线系统",
                        "description": "检查馈线连接和驻波比测试",
                        "sort_order": 3,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄馈线连接情况和测试结果",
                            "gps_required": True,
                            "min_photos": 3,
                            "include": ["馈线连接", "防水处理", "走线槽", "测试仪表"]
                        },
                        "data_fields": [
                            {"name": "vswr", "type": "number", "label": "驻波比", "required": True},
                            {"name": "return_loss", "type": "number", "unit": "dB", "label": "回波损耗"},
                            {"name": "feeder_loss", "type": "number", "unit": "dB", "label": "馈线损耗"}
                        ]
                    }
                ]
            },
            {
                "id": "system_level",
                "name": "系统级检查", 
                "description": "系统集成和性能测试",
                "sort_order": 3,
                "items": [
                    {
                        "id": "bbu_configuration",
                        "name": "BBU配置",
                        "description": "检查BBU设备配置和参数",
                        "sort_order": 1,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄BBU设备和配置界面",
                            "gps_required": True,
                            "min_photos": 3,
                            "include": ["BBU设备", "LCD显示", "指示灯状态", "配置界面"]
                        },
                        "data_fields": [
                            {"name": "bbu_sn", "type": "text", "label": "BBU序列号", "required": True},
                            {"name": "cell_id", "type": "text", "label": "小区ID", "required": True},
                            {"name": "pci", "type": "number", "label": "PCI", "required": True},
                            {"name": "earfcn", "type": "number", "label": "EARFCN", "required": True}
                        ]
                    },
                    {
                        "id": "network_test",
                        "name": "网络测试",
                        "description": "进行网络连通性和性能测试",
                        "sort_order": 2,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄测试设备和测试结果",
                            "gps_required": True,
                            "min_photos": 4,
                            "include": ["测试终端", "信号强度", "测试结果", "网络分析仪"]
                        },
                        "data_fields": [
                            {"name": "rsrp", "type": "number", "unit": "dBm", "label": "RSRP", "required": True},
                            {"name": "rsrq", "type": "number", "unit": "dB", "label": "RSRQ", "required": True},
                            {"name": "sinr", "type": "number", "unit": "dB", "label": "SINR", "required": True},
                            {"name": "throughput_dl", "type": "number", "unit": "Mbps", "label": "下行吞吐量"},
                            {"name": "throughput_ul", "type": "number", "unit": "Mbps", "label": "上行吞吐量"}
                        ]
                    },
                    {
                        "id": "alarm_monitoring",
                        "name": "告警监控",
                        "description": "检查告警和监控系统功能",
                        "sort_order": 3,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄监控系统界面和告警状态",
                            "gps_required": True,
                            "min_photos": 2,
                            "include": ["监控界面", "告警信息", "日志记录"]
                        },
                        "data_fields": [
                            {"name": "active_alarms", "type": "number", "label": "当前告警数", "required": True},
                            {"name": "monitoring_status", "type": "select", "options": ["正常", "异常"], "label": "监控状态", "required": True},
                            {"name": "snmp_connectivity", "type": "select", "options": ["连通", "不连通"], "label": "SNMP连通性"}
                        ]
                    }
                ]
            }
        ]
    }
    
    # 维护检查模板
    maintenance_template = {
        "template_name": "基站维护检查模板",
        "template_version": "1.0", 
        "description": "基站设备日常维护检查模板",
        "categories": [
            {
                "id": "equipment_status",
                "name": "设备状态检查",
                "description": "检查各设备运行状态",
                "sort_order": 1,
                "items": [
                    {
                        "id": "equipment_appearance", 
                        "name": "设备外观",
                        "description": "检查设备外观是否完好",
                        "sort_order": 1,
                        "required_type": "both",
                        "mandatory": True,
                        "photo_requirements": {
                            "description": "拍摄各主要设备外观",
                            "gps_required": True,
                            "min_photos": 3,
                            "include": ["BBU外观", "RRU外观", "天线外观"]
                        },
                        "data_fields": [
                            {"name": "appearance_status", "type": "select", "options": ["良好", "一般", "差"], "label": "外观状态", "required": True},
                            {"name": "damage_description", "type": "text", "label": "损坏描述"}
                        ]
                    },
                    {
                        "id": "performance_test",
                        "name": "性能测试",
                        "description": "测试设备关键性能指标",
                        "sort_order": 2,
                        "required_type": "data",
                        "mandatory": True,
                        "data_fields": [
                            {"name": "cpu_usage", "type": "number", "unit": "%", "label": "CPU使用率", "required": True},
                            {"name": "memory_usage", "type": "number", "unit": "%", "label": "内存使用率", "required": True},
                            {"name": "temperature", "type": "number", "unit": "°C", "label": "设备温度", "required": True}
                        ]
                    }
                ]
            }
        ]
    }
    
    templates = [
        ("installation_template", installation_template),
        ("maintenance_template", maintenance_template)
    ]
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            for template_id, template_data in templates:
                # 检查模板是否已存在
                result = conn.execute(
                    text("SELECT COUNT(*) FROM inspection_templates WHERE id = :id"),
                    {"id": template_id}
                )
                
                if result.scalar() == 0:
                    # 插入新模板
                    insert_sql = """
                    INSERT INTO inspection_templates 
                    (id, site_id, template_name, template_version, template_data, status, created_by, created_at)
                    VALUES 
                    (:id, 1, :name, :version, :data, 'approved', 1, datetime('now'))
                    """
                    
                    conn.execute(text(insert_sql), {
                        'id': template_id,
                        'name': template_data['template_name'],
                        'version': template_data['template_version'],
                        'data': json.dumps(template_data, ensure_ascii=False, indent=2)
                    })
                    conn.commit()
                    print(f"✓ 创建模板: {template_data['template_name']}")
                else:
                    print(f"✓ 模板已存在: {template_data['template_name']}")
                    
        print("\n检查模板创建完成!")
        return True
        
    except Exception as e:
        print(f"✗ 创建检查模板失败: {str(e)}")
        return False

def show_template_info():
    """显示模板信息"""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, template_name, template_version, status, created_at
                FROM inspection_templates
                ORDER BY created_at DESC
            """))
            
            templates = result.fetchall()
            
            print("\n=== 检查模板列表 ===")
            for template in templates:
                print(f"- ID: {template[0]}")
                print(f"  名称: {template[1]}")
                print(f"  版本: {template[2]}")  
                print(f"  状态: {template[3]}")
                print(f"  创建时间: {template[4]}")
                print()
                
    except Exception as e:
        print(f"查询模板信息失败: {str(e)}")

if __name__ == "__main__":
    print("=== 检查模板数据创建 ===")
    
    success = create_comprehensive_templates()
    
    if success:
        show_template_info()
        print("检查模板数据创建完成!")
    else:
        print("检查模板数据创建失败!")
        sys.exit(1)