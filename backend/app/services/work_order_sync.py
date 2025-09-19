"""
工单与检查状态同步服务
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.models.work_order import WorkOrder, WorkOrderStatusEnum
from app.models.inspection import SiteInspection, InspectionStatusEnum


class WorkOrderSyncService:
    """工单与检查状态同步服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def sync_work_order_to_inspection_status(self, work_order: WorkOrder) -> None:
        """工单状态变更时同步检查状态"""
        
        # 获取关联的检查实例
        inspections = self.db.query(SiteInspection).filter(
            SiteInspection.work_order_id == work_order.id
        ).all()
        
        if not inspections:
            return
        
        # 状态映射关系
        status_mapping = {
            WorkOrderStatusEnum.PENDING: InspectionStatusEnum.DRAFT,
            WorkOrderStatusEnum.ACTIVE: InspectionStatusEnum.IN_PROGRESS,
            WorkOrderStatusEnum.SUBMITTED: InspectionStatusEnum.SUBMITTED,
            WorkOrderStatusEnum.UNDER_REVIEW: InspectionStatusEnum.UNDER_REVIEW,
            WorkOrderStatusEnum.COMPLETED: InspectionStatusEnum.COMPLETED,
        }
        
        new_inspection_status = status_mapping.get(work_order.status)
        if not new_inspection_status:
            return
        
        # 更新所有关联检查的状态
        for inspection in inspections:
            old_status = inspection.status
            inspection.status = new_inspection_status
            
            # 同步时间字段
            if work_order.status == WorkOrderStatusEnum.SUBMITTED and work_order.submitted_at:
                inspection.submitted_at = work_order.submitted_at
            
            print(f"同步检查状态: {inspection.id} {old_status} -> {new_inspection_status}")
    
    def sync_inspection_to_work_order_status(self, inspection: SiteInspection) -> None:
        """检查状态变更时同步工单状态"""
        
        if not inspection.work_order_id:
            return
        
        work_order = self.db.query(WorkOrder).filter(
            WorkOrder.id == inspection.work_order_id
        ).first()
        
        if not work_order:
            return
        
        # 获取检查状态的字符串值，处理可能的大小写不一致
        if hasattr(inspection.status, 'value'):
            inspection_status_str = inspection.status.value.upper()
        else:
            # 处理直接存储的字符串值
            inspection_status_str = str(inspection.status).upper()
            # 如果包含枚举类名，提取实际值
            if 'ENUM.' in inspection_status_str:
                inspection_status_str = inspection_status_str.split('.')[-1]
        
        # 状态映射关系 - 使用字符串映射以避免枚举值不一致问题
        status_mapping = {
            "DRAFT": WorkOrderStatusEnum.ACTIVE,
            "IN_PROGRESS": WorkOrderStatusEnum.ACTIVE,
            "SUBMITTED": WorkOrderStatusEnum.SUBMITTED,
            "UNDER_REVIEW": WorkOrderStatusEnum.UNDER_REVIEW,
            "APPROVED": WorkOrderStatusEnum.COMPLETED,
            "REJECTED": WorkOrderStatusEnum.ACTIVE,  # 驳回后回到活跃状态
            "COMPLETED": WorkOrderStatusEnum.COMPLETED,
        }
        
        new_work_order_status = status_mapping.get(inspection_status_str)
        if not new_work_order_status:
            print(f"DEBUG: 未找到状态映射 - 检查状态: {inspection_status_str}")
            return
        
        old_status = work_order.status
        work_order.status = new_work_order_status
        
        # 同步时间字段 - 使用字符串比较避免枚举值不一致
        if inspection_status_str == "SUBMITTED":
            # 如果检查还没有设置提交时间，先设置它
            if not inspection.submitted_at:
                inspection.submitted_at = datetime.utcnow()
            # 然后同步到工单
            work_order.submitted_at = inspection.submitted_at
        
        if inspection_status_str in ["APPROVED", "COMPLETED"]:
            work_order.completed_at = datetime.utcnow()
        
        print(f"同步工单状态: {work_order.id} {old_status} -> {new_work_order_status}")
        
        # 注意：不在这里提交事务，由调用方统一提交
    
    def sync_work_order_review_info(self, work_order: WorkOrder) -> None:
        """同步工单审核信息到检查"""
        
        inspections = self.db.query(SiteInspection).filter(
            SiteInspection.work_order_id == work_order.id
        ).all()
        
        for inspection in inspections:
            if work_order.reviewer_id and not inspection.reviewed_by:
                inspection.reviewed_by = work_order.reviewer_id
            
            if work_order.reviewed_at and not inspection.reviewed_at:
                inspection.reviewed_at = work_order.reviewed_at
            
            if work_order.review_comments and not inspection.review_comments:
                inspection.review_comments = work_order.review_comments


def get_work_order_sync_service(db: Session) -> WorkOrderSyncService:
    """获取工单同步服务实例"""
    return WorkOrderSyncService(db)