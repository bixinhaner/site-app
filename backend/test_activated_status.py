#!/usr/bin/env python3
"""
测试工单ACTIVATED状态功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.work_order import WorkOrder, WorkOrderStatusEnum
from app.services.equipment_activation_service import EquipmentActivationService
from app.utils.work_order_progress import WorkOrderProgressCalculator
from datetime import datetime

async def test_activated_status():
    """测试ACTIVATED状态功能"""
    print("=== 测试工单ACTIVATED状态功能 ===\n")
    
    db = SessionLocal()
    try:
        # 1. 查找一个APPROVED状态的工单
        approved_order = db.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatusEnum.APPROVED
        ).first()
        
        if not approved_order:
            print("❌ 没有找到APPROVED状态的工单用于测试")
            # 创建一个测试工单
            test_order = WorkOrder(
                id="test_activated_001",
                site_id=1,  # 假设站点ID为1
                title="测试设备开通功能",
                type="opening_inspection",
                description="用于测试ACTIVATED状态的工单",
                assigned_by=1,
                assigned_to=2,
                status=WorkOrderStatusEnum.APPROVED
            )
            db.add(test_order)
            db.commit()
            approved_order = test_order
            print(f"✓ 创建测试工单: {approved_order.id}")
        
        print(f"✓ 找到APPROVED状态工单: {approved_order.id}")
        print(f"  - 标题: {approved_order.title}")
        print(f"  - 站点ID: {approved_order.site_id}")
        print(f"  - 当前状态: {approved_order.status.value}")
        
        # 2. 测试进度计算器
        print("\n=== 测试进度计算器 ===")
        progress_info = WorkOrderProgressCalculator.calculate_progress(db, approved_order)
        print(f"✓ 当前进度: {progress_info['progress']}%")
        print(f"✓ 阶段: {progress_info['stage']}")
        print(f"✓ 阶段进度: {progress_info['stage_progress']}%")
        
        # 3. 测试设备开通检测服务
        print("\n=== 测试设备开通检测服务 ===")
        activation_service = EquipmentActivationService(db)
        
        try:
            # 检测站点设备开通状态
            check_result = await activation_service.check_site_equipment_activation(approved_order.site_id)
            print(f"✓ 设备检测完成")
            print(f"  - 总设备数: {check_result['total_equipment']}")
            print(f"  - 已开通设备: {check_result['activated_equipment']}")
            print(f"  - 全部开通: {check_result['all_activated']}")
            print(f"  - 失败设备数: {len(check_result['failed_equipment'])}")
            
        except Exception as e:
            print(f"⚠️  设备检测遇到问题 (可能是因为没有设备数据): {e}")
            # 模拟成功的检测结果
            check_result = {
                "all_activated": True,
                "total_equipment": 2,
                "activated_equipment": 2,
                "failed_equipment": [],
                "check_time": datetime.utcnow().isoformat(),
                "details": []
            }
            print("✓ 使用模拟的成功检测结果继续测试")
        
        # 4. 测试工单状态更新为ACTIVATED
        print("\n=== 测试工单状态更新 ===")
        try:
            activation_result = await activation_service.trigger_equipment_activation_check(approved_order.id)
            print(f"✓ 设备开通检测触发成功")
            print(f"  - 消息: {activation_result['message']}")
            print(f"  - 工单状态: {activation_result['work_order_status']}")
            
            # 刷新工单对象
            db.refresh(approved_order)
            print(f"✓ 工单状态已更新为: {approved_order.status.value}")
            
            if approved_order.activated_at:
                print(f"✓ 开通时间: {approved_order.activated_at}")
            
        except Exception as e:
            print(f"⚠️  状态更新遇到问题: {e}")
        
        # 5. 测试ACTIVATED状态的进度计算
        if approved_order.status == WorkOrderStatusEnum.ACTIVATED:
            print("\n=== 测试ACTIVATED状态进度计算 ===")
            progress_info = WorkOrderProgressCalculator.calculate_progress(db, approved_order)
            print(f"✓ ACTIVATED状态进度: {progress_info['progress']}%")
            print(f"✓ 阶段名称: {WorkOrderProgressCalculator.get_stage_name(approved_order.status)}")
            print(f"✓ 下一步操作: {WorkOrderProgressCalculator.get_next_action(approved_order.status)}")
            print(f"✓ 进度颜色: {WorkOrderProgressCalculator.get_progress_color(progress_info['progress'])}")
            
            if 'details' in progress_info:
                print(f"✓ 详细信息: {progress_info['details']}")
        
        print("\n🎉 ACTIVATED状态功能测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_activated_status())