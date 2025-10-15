#!/usr/bin/env python3
"""
测试站点状态自动更新功能
场景1：创建安装工单时，站点状态从planning变为construction
场景2：完成安装工单时，站点状态从construction变为operational
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.site import Site
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum, WorkOrderPriorityEnum
from app.models.user import User
from datetime import datetime
import uuid


def test_site_status_auto_update():
    """测试站点状态自动更新"""
    db = SessionLocal()
    
    try:
        # 1. 创建测试站点（状态为planning）
        print("\n=== 测试场景1：创建安装工单时自动更新站点状态 ===")
        test_site = Site(
            site_code=f"TEST-SITE-{uuid.uuid4().hex[:8]}",
            site_name="测试站点-状态自动更新",
            status="planning",
            site_type="base_station",
            address="测试地址",
            latitude=39.9042,
            longitude=116.4074,
            province="北京市",
            city="北京市",
            district="朝阳区",
            created_by=1
        )
        db.add(test_site)
        db.commit()
        db.refresh(test_site)
        
        print(f"✓ 创建测试站点: {test_site.site_name} (ID: {test_site.id})")
        print(f"  初始状态: {test_site.status}")
        
        # 获取测试用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        inspector_user = db.query(User).filter(User.role == "inspector").first()
        
        if not admin_user or not inspector_user:
            print("❌ 未找到测试用户，请先运行 init_test_data.py")
            return
        
        # 2. 创建安装工单
        work_order = WorkOrder(
            id=str(uuid.uuid4()),
            site_id=test_site.id,
            title="测试安装工单-状态自动更新",
            type=WorkOrderTypeEnum.OPENING_INSPECTION,
            description="测试站点状态自动更新功能",
            priority=WorkOrderPriorityEnum.NORMAL,
            assigned_by=admin_user.id,
            assigned_to=inspector_user.id,
            status=WorkOrderStatusEnum.PENDING
        )
        db.add(work_order)
        
        # 模拟自动更新站点状态的逻辑
        from app.api.work_orders import _update_site_status_on_work_order_create
        _update_site_status_on_work_order_create(db, test_site.id, work_order.type)
        
        db.commit()
        db.refresh(test_site)
        
        print(f"\n✓ 创建安装工单: {work_order.title} (ID: {work_order.id})")
        print(f"  工单类型: {work_order.type}")
        print(f"  站点状态更新后: {test_site.status}")
        
        if test_site.status == "construction":
            print("✅ 测试通过：站点状态已自动从 planning 更新为 construction")
        else:
            print(f"❌ 测试失败：站点状态应为 construction，实际为 {test_site.status}")
        
        # 3. 完成安装工单
        print("\n=== 测试场景2：完成安装工单时自动更新站点状态 ===")
        work_order.status = WorkOrderStatusEnum.COMPLETED
        work_order.completed_at = datetime.utcnow()
        
        # 模拟自动更新站点状态的逻辑
        from app.api.work_orders import _update_site_status_on_work_order_complete
        _update_site_status_on_work_order_complete(db, test_site.id, work_order.type)
        
        db.commit()
        db.refresh(test_site)
        
        print(f"✓ 完成安装工单: {work_order.title}")
        print(f"  工单状态: {work_order.status}")
        print(f"  站点状态更新后: {test_site.status}")
        
        if test_site.status == "operational":
            print("✅ 测试通过：站点状态已自动从 construction 更新为 operational")
        else:
            print(f"❌ 测试失败：站点状态应为 operational，实际为 {test_site.status}")
        
        # 4. 测试多个安装工单的情况
        print("\n=== 测试场景3：多个安装工单时的状态更新 ===")
        
        # 创建第二个测试站点
        test_site2 = Site(
            site_code=f"TEST-SITE-{uuid.uuid4().hex[:8]}",
            site_name="测试站点2-多工单",
            status="planning",
            site_type="base_station",
            address="测试地址2",
            latitude=39.9042,
            longitude=116.4074,
            province="北京市",
            city="北京市",
            district="朝阳区",
            created_by=1
        )
        db.add(test_site2)
        db.commit()
        db.refresh(test_site2)
        
        print(f"✓ 创建测试站点2: {test_site2.site_name} (ID: {test_site2.id})")
        
        # 创建两个安装工单
        work_order2 = WorkOrder(
            id=str(uuid.uuid4()),
            site_id=test_site2.id,
            title="测试安装工单2-1",
            type=WorkOrderTypeEnum.OPENING_INSPECTION,
            description="第一个安装工单",
            priority=WorkOrderPriorityEnum.NORMAL,
            assigned_by=admin_user.id,
            assigned_to=inspector_user.id,
            status=WorkOrderStatusEnum.PENDING
        )
        db.add(work_order2)
        
        work_order3 = WorkOrder(
            id=str(uuid.uuid4()),
            site_id=test_site2.id,
            title="测试安装工单2-2",
            type=WorkOrderTypeEnum.OPENING_INSPECTION,
            description="第二个安装工单",
            priority=WorkOrderPriorityEnum.NORMAL,
            assigned_by=admin_user.id,
            assigned_to=inspector_user.id,
            status=WorkOrderStatusEnum.PENDING
        )
        db.add(work_order3)
        
        _update_site_status_on_work_order_create(db, test_site2.id, work_order2.type)
        db.commit()
        db.refresh(test_site2)
        
        print(f"✓ 创建两个安装工单")
        print(f"  站点状态: {test_site2.status}")
        
        # 完成第一个工单
        work_order2.status = WorkOrderStatusEnum.COMPLETED
        work_order2.completed_at = datetime.utcnow()
        _update_site_status_on_work_order_complete(db, test_site2.id, work_order2.type)
        db.commit()
        db.refresh(test_site2)
        
        print(f"\n✓ 完成第一个安装工单")
        print(f"  站点状态: {test_site2.status}")
        
        if test_site2.status == "construction":
            print("✅ 测试通过：还有未完成的工单，站点保持 construction 状态")
        else:
            print(f"❌ 测试失败：站点状态应保持 construction，实际为 {test_site2.status}")
        
        # 完成第二个工单
        work_order3.status = WorkOrderStatusEnum.COMPLETED
        work_order3.completed_at = datetime.utcnow()
        _update_site_status_on_work_order_complete(db, test_site2.id, work_order3.type)
        db.commit()
        db.refresh(test_site2)
        
        print(f"\n✓ 完成第二个安装工单")
        print(f"  站点状态: {test_site2.status}")
        
        if test_site2.status == "operational":
            print("✅ 测试通过：所有安装工单完成，站点状态更新为 operational")
        else:
            print(f"❌ 测试失败：站点状态应为 operational，实际为 {test_site2.status}")
        
        # 清理测试数据
        print("\n=== 清理测试数据 ===")
        db.delete(work_order)
        db.delete(work_order2)
        db.delete(work_order3)
        db.delete(test_site)
        db.delete(test_site2)
        db.commit()
        print("✓ 测试数据已清理")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("站点状态自动更新功能测试")
    print("=" * 60)
    test_site_status_auto_update()
    print("\n测试完成！")
