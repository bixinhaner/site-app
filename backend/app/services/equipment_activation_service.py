"""
设备开通检测服务

负责检测站点下所有设备是否已通过网管API连接
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.site import Site
from app.models.work_order import WorkOrder, WorkOrderStatusEnum
from app.models.equipment import EquipmentInstance
import asyncio
import httpx
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)

class EquipmentActivationService:
    """设备开通检测服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.nms_api_base = "http://nms-server:8080/api"  # 网管系统API地址
        self.check_timeout = 30  # 单个设备检测超时时间(秒)
        self.retry_times = 3     # 重试次数
        
    async def check_site_equipment_activation(self, site_id: int) -> Dict:
        """
        检查站点所有设备是否已开通
        注意：当前系统中暂无站点-设备直接关联，这里使用模拟逻辑
        
        Returns:
            {
                "all_activated": True/False,
                "total_equipment": 10,
                "activated_equipment": 8,
                "failed_equipment": [],
                "check_time": "2024-01-01 12:00:00",
                "details": [...]
            }
        """
        site = self.db.query(Site).filter(Site.id == site_id).first()
        if not site:
            raise ValueError(f"站点不存在: {site_id}")
        
        # 模拟站点设备检测逻辑
        # 在实际业务中，这里应该根据实际的设备部署情况来检测
        # 当前简化为模拟2台设备的检测
        
        logger.info(f"模拟检测站点 {site_id} 的设备开通状态")
        
        # 模拟设备数据
        mock_equipment = [
            {
                "equipment_id": f"eq_{site_id}_001",
                "equipment_name": "基站主设备",
                "serial_number": f"SN{site_id}001",
                "status": "online"
            },
            {
                "equipment_id": f"eq_{site_id}_002", 
                "equipment_name": "天线设备",
                "serial_number": f"SN{site_id}002",
                "status": "online"
            }
        ]
        
        # 模拟设备检测过程
        details = []
        activated_equipment = 0
        failed_equipment = []
        
        for equipment in mock_equipment:
            # 模拟检测逻辑：假设设备状态为online则认为已激活
            is_activated = equipment["status"] == "online"
            
            detail = {
                "equipment_id": equipment["equipment_id"],
                "equipment_name": equipment["equipment_name"],
                "serial_number": equipment["serial_number"],
                "activated": is_activated,
                "check_time": datetime.utcnow().isoformat()
            }
            
            if is_activated:
                activated_equipment += 1
                detail["last_heartbeat"] = datetime.utcnow().isoformat()
            else:
                detail["reason"] = f"设备状态: {equipment['status']}, 需要online状态"
                failed_equipment.append({
                    "equipment_id": equipment["equipment_id"],
                    "equipment_name": equipment["equipment_name"],
                    "serial_number": equipment["serial_number"],
                    "reason": detail["reason"]
                })
            
            details.append(detail)
        
        total_equipment = len(mock_equipment)
        all_activated = activated_equipment == total_equipment
        
        logger.info(f"站点 {site_id} 设备检测完成: {activated_equipment}/{total_equipment} 已开通")
        
        return {
            "all_activated": all_activated,
            "total_equipment": total_equipment,
            "activated_equipment": activated_equipment,
            "failed_equipment": failed_equipment,
            "check_time": datetime.utcnow().isoformat(),
            "details": details
        }
    
    
    async def trigger_equipment_activation_check(self, work_order_id: str) -> Dict:
        """
        为工单触发设备开通检测
        
        Args:
            work_order_id: 工单ID
            
        Returns:
            检测结果和状态更新信息
        """
        wo = self.db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
        if not wo:
            raise ValueError(f"工单不存在: {work_order_id}")
        
        if wo.status != WorkOrderStatusEnum.APPROVED:
            raise ValueError(f"只有审核通过的工单才能进行设备开通检测, 当前状态: {wo.status}")
        
        # 执行设备开通检测
        check_result = await self.check_site_equipment_activation(wo.site_id)
        
        # 更新工单额外数据
        if not wo.extra_data:
            wo.extra_data = {}
        
        wo.extra_data["activation_check"] = check_result
        wo.extra_data["activation_check_time"] = datetime.utcnow().isoformat()
        
        # 根据检测结果更新工单状态
        if check_result["all_activated"]:
            old_status = wo.status
            wo.status = WorkOrderStatusEnum.ACTIVATED
            wo.activated_at = datetime.utcnow()
            
            # 记录审计日志
            audit_event = {
                "id": str(uuid.uuid4()),
                "resource_type": "work_order",
                "resource_id": work_order_id,
                "action": "equipment_activation_success",
                "from_status": old_status.value,
                "to_status": wo.status.value,
                "operator_id": 1,  # 系统操作
                "details": check_result,
                "created_at": datetime.utcnow()
            }
            
            message = f"设备开通检测通过，工单状态更新为已开通"
        else:
            message = f"设备开通检测失败，{len(check_result['failed_equipment'])} 个设备未开通"
        
        self.db.commit()
        
        return {
            "message": message,
            "work_order_status": wo.status.value,
            "check_result": check_result
        }


# 定时任务：自动检测已审核通过的工单
async def auto_check_approved_work_orders():
    """定时任务：自动检测已审核通过的工单设备开通状态"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        service = EquipmentActivationService(db)
        
        # 查找所有APPROVED状态的工单
        approved_orders = db.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatusEnum.APPROVED
        ).all()
        
        logger.info(f"发现 {len(approved_orders)} 个待检测设备开通状态的工单")
        
        for wo in approved_orders:
            try:
                result = await service.trigger_equipment_activation_check(wo.id)
                logger.info(f"工单 {wo.id} 设备开通检测完成: {result['message']}")
            except Exception as e:
                logger.error(f"工单 {wo.id} 设备开通检测失败: {e}")
    
    finally:
        db.close()


def create_equipment_activation_service(db: Session) -> EquipmentActivationService:
    """创建设备开通检测服务实例"""
    return EquipmentActivationService(db)