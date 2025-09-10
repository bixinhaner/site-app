#!/usr/bin/env python3
"""
初始化任务管理相关的测试数据
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.inspection import (
    BaseStationDevice, 
    TaskAssignment, 
    BaseStationStatusEnum,
    TaskStatusEnum,
    TaskTypeEnum
)
from app.models.site import Site
from app.models.user import User
import uuid
from datetime import datetime, timedelta

def init_base_station_devices():
    """初始化基站设备数据"""
    db = SessionLocal()
    try:
        # 检查是否已有设备数据
        existing_device = db.query(BaseStationDevice).first()
        if existing_device:
            print("基站设备数据已存在，跳过初始化")
            return
        
        # 获取站点数据
        sites = db.query(Site).all()
        if not sites:
            print("没有站点数据，请先初始化站点数据")
            return
        
        devices_data = []
        
        # 为每个站点创建2-3个基站设备
        for site in sites[:3]:  # 只为前3个站点创建设备
            for i in range(2):  # 每个站点2个设备
                device_data = {
                    "id": str(uuid.uuid4()),
                    "site_id": site.id,
                    "device_name": f"BaseStation_{site.id}_{i+1}",
                    "device_type": "LTE_eNodeB",
                    "device_model": "Baicells Nova 243",
                    "device_sn": f"BS{site.id:03d}{i+1:02d}2024",
                    "status": BaseStationStatusEnum.OFFLINE if i == 0 else BaseStationStatusEnum.ACTIVATED,
                    "omc_device_id": f"OMC_{site.id}_{i+1}",
                    "frequency_bands": {
                        "bands": ["B3", "B8", "B20"],
                        "bandwidth": "20MHz",
                        "duplex": "FDD"
                    },
                    "power_config": {
                        "tx_power": "40dBm",
                        "power_control": "enabled"
                    },
                    "network_config": {
                        "earfcn": 1575 + i,
                        "pci": 100 + i,
                        "tac": 1001
                    },
                    "maintenance_notes": f"设备安装于{site.site_name}，状态正常" if i == 1 else "设备离线，需要检查",
                    "issues_history": []
                }
                devices_data.append(device_data)
        
        # 批量插入设备数据
        for device_data in devices_data:
            device = BaseStationDevice(**device_data)
            db.add(device)
        
        db.commit()
        print(f"成功创建 {len(devices_data)} 个基站设备")
        
        # 显示创建的设备信息
        for device_data in devices_data:
            print(f"  - {device_data['device_name']} ({device_data['status']}) - OMC ID: {device_data['omc_device_id']}")
            
    except Exception as e:
        print(f"创建基站设备失败: {str(e)}")
        db.rollback()
    finally:
        db.close()

def init_task_assignments():
    """初始化任务分配数据"""
    db = SessionLocal()
    try:
        # 检查是否已有任务数据
        existing_task = db.query(TaskAssignment).first()
        if existing_task:
            print("任务数据已存在，跳过初始化")
            return
        
        # 获取用户和站点数据
        admin_user = db.query(User).filter(User.role == "admin").first()
        inspector_user = db.query(User).filter(User.role == "inspector").first()
        sites = db.query(Site).all()
        
        if not admin_user or not inspector_user or not sites:
            print("缺少必要的用户或站点数据，请先初始化这些数据")
            return
        
        tasks_data = []
        
        # 创建新站点设备安装任务
        for i, site in enumerate(sites[:2]):  # 为前2个站点创建开站任务
            task_data = {
                "id": str(uuid.uuid4()),
                "task_title": f"站点新站点设备安装 - {site.site_name}",
                "task_type": TaskTypeEnum.OPENING_INSPECTION,
                "task_description": f"对站点 {site.site_name} 进行全面的新站点设备安装，包括设备状态验证、信号测试和所有检查项目的确认。",
                "priority": "high",
                "site_id": site.id,
                "assigned_by": admin_user.id,
                "assigned_to": inspector_user.id,
                "status": TaskStatusEnum.ASSIGNED if i == 0 else TaskStatusEnum.IN_PROGRESS,
                "assigned_at": datetime.now() - timedelta(days=i+1),
                "due_date": datetime.now() + timedelta(days=3-i),
                "requirements": {
                    "inspection_type": "opening",
                    "check_all_items": True,
                    "verify_device_status": True,
                    "submit_all_photos": True,
                    "required_checks": [
                        "tower_id_photo",
                        "tower_antenna_height",
                        "cabinet_environment",
                        "antenna_downtilt",
                        "azimuth_check",
                        "vswr_check"
                    ]
                },
                "estimated_duration": 8
            }
            
            if i == 1:  # 第二个任务设置为进行中
                task_data["accepted_at"] = datetime.now() - timedelta(hours=4)
                task_data["started_at"] = datetime.now() - timedelta(hours=2)
                task_data["accept_comments"] = "任务已接受，正在现场进行检查"
                task_data["progress_notes"] = "已完成50%的检查项目，设备状态正常"
            
            tasks_data.append(task_data)
        
        # 创建维护任务
        if len(sites) > 2:
            maintenance_tasks = [
                {
                    "title": "信号质量问题排查",
                    "type": TaskTypeEnum.SIGNAL_ISSUE,
                    "description": "用户反映该站点覆盖区域信号质量较差，需要进行现场测试和调优",
                    "priority": "urgent"
                },
                {
                    "title": "设备断电故障修复",
                    "type": TaskTypeEnum.POWER_ISSUE,
                    "description": "基站设备出现间歇性断电，需要检查电源系统和备电设备",
                    "priority": "high"
                },
                {
                    "title": "GPS同步异常处理",
                    "type": TaskTypeEnum.GPS_ISSUE,
                    "description": "基站GPS时钟同步异常，影响网络同步，需要现场检查GPS天线和设备",
                    "priority": "normal"
                }
            ]
            
            for i, task_info in enumerate(maintenance_tasks):
                if i + 3 < len(sites):
                    site = sites[i + 3]
                    task_data = {
                        "id": str(uuid.uuid4()),
                        "task_title": task_info["title"],
                        "task_type": task_info["type"],
                        "task_description": task_info["description"],
                        "priority": task_info["priority"],
                        "site_id": site.id,
                        "assigned_by": admin_user.id,
                        "assigned_to": inspector_user.id,
                        "status": TaskStatusEnum.PENDING if i == 0 else TaskStatusEnum.ASSIGNED,
                        "assigned_at": datetime.now() - timedelta(hours=i*2),
                        "due_date": datetime.now() + timedelta(days=1+i),
                        "requirements": {
                            "inspection_type": "maintenance",
                            "issue_type": task_info["type"],
                            "tools_required": ["信号分析仪", "万用表", "网络测试仪"],
                            "safety_requirements": ["安全帽", "防滑鞋", "绝缘手套"]
                        },
                        "estimated_duration": 4
                    }
                    tasks_data.append(task_data)
        
        # 批量插入任务数据
        for task_data in tasks_data:
            task = TaskAssignment(**task_data)
            db.add(task)
        
        db.commit()
        print(f"成功创建 {len(tasks_data)} 个任务分配")
        
        # 显示创建的任务信息
        for task_data in tasks_data:
            print(f"  - {task_data['task_title']} ({task_data['status']}) - 优先级: {task_data['priority']}")
            
    except Exception as e:
        print(f"创建任务分配失败: {str(e)}")
        db.rollback()
    finally:
        db.close()

def main():
    """主函数"""
    print("开始初始化任务管理测试数据...")
    
    # 初始化基站设备
    print("\n1. 初始化基站设备数据")
    init_base_station_devices()
    
    # 初始化任务分配
    print("\n2. 初始化任务分配数据")
    init_task_assignments()
    
    print("\n任务管理测试数据初始化完成！")
    print("\n可以使用以下API端点测试功能：")
    print("- GET  /api/tasks/ - 获取任务列表")
    print("- GET  /api/tasks/my/tasks - 获取我的任务")
    print("- GET  /api/tasks/dashboard/overview - 获取任务仪表板")
    print("- GET  /api/tasks/sites/{site_id}/devices - 获取站点设备状态")
    print("- POST /api/tasks/omc/sync-all - 同步所有设备状态")

if __name__ == "__main__":
    main()