"""
工单进度计算器

包含ACTIVATED状态的完整进度计算逻辑
"""

from sqlalchemy.orm import Session
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.models.inspection import InspectionCheckItem, CheckItemStatusEnum

class WorkOrderProgressCalculator:
    """工单进度计算器"""
    
    # 基础状态进度映射 (包含新的ACTIVATED状态)
    STATUS_PROGRESS_MAP = {
        WorkOrderStatusEnum.PENDING: 0,        # 待处理
        WorkOrderStatusEnum.ACTIVE: 20,       # 执行中 (20%-65%)
        WorkOrderStatusEnum.SUBMITTED: 65,    # 已提交待审核
        WorkOrderStatusEnum.UNDER_REVIEW: 75, # 审核中
        WorkOrderStatusEnum.APPROVED: 85,     # 审核通过
        WorkOrderStatusEnum.ACTIVATED: 95,    # 已开通 (新增)
        WorkOrderStatusEnum.COMPLETED: 100,   # 已完成
        WorkOrderStatusEnum.REJECTED: 50      # 审核驳回
    }
    
    @classmethod
    def calculate_progress(cls, db: Session, work_order: WorkOrder) -> dict:
        """
        计算工单完成进度
        
        Returns:
            {
                "progress": 85,           # 总体进度百分比
                "stage": "ACTIVE",        # 当前阶段
                "stage_progress": 65,     # 当前阶段内的进度
                "details": {              # 详细信息
                    "total_items": 10,
                    "completed_items": 7,
                    "pending_items": 3
                }
            }
        """
        base_progress = cls.STATUS_PROGRESS_MAP.get(work_order.status, 0)
        
        # 针对开站工单，使用自定义阶段进度：APPROVED=80, ACTIVATED=90, COMPLETED=100
        if work_order.type == WorkOrderTypeEnum.OPENING_INSPECTION:
            if work_order.status == WorkOrderStatusEnum.APPROVED:
                base_progress = 80
            elif work_order.status == WorkOrderStatusEnum.ACTIVATED:
                base_progress = 90
            elif work_order.status == WorkOrderStatusEnum.COMPLETED:
                base_progress = 100

        result = {
            "progress": base_progress,
            "stage": work_order.status.value,
            "stage_progress": 100,  # 非ACTIVE阶段默认该阶段100%完成
            "details": {}
        }
        
        # ACTIVE阶段需要计算检查项完成度
        if work_order.status == WorkOrderStatusEnum.ACTIVE and work_order.inspection_id:
            progress_info = cls._calculate_active_progress(db, work_order)
            result.update(progress_info)
        
        # REJECTED阶段也可以显示检查项完成度
        elif work_order.status == WorkOrderStatusEnum.REJECTED and work_order.inspection_id:
            progress_info = cls._calculate_active_progress(db, work_order)
            # 保持基础进度50%，但显示检查项详情
            result["details"] = progress_info["details"]
            result["stage_progress"] = progress_info["stage_progress"]
        
        # ACTIVATED阶段显示设备开通信息
        elif work_order.status == WorkOrderStatusEnum.ACTIVATED:
            activation_info = cls._calculate_activation_progress(work_order)
            result["details"] = activation_info
        
        return result
    
    @classmethod
    def _calculate_active_progress(cls, db: Session, work_order: WorkOrder) -> dict:
        """计算ACTIVE阶段的详细进度"""
        items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == work_order.inspection_id
        ).all()
        
        total_items = len(items)
        if total_items == 0:
            return {
                "progress": 20,
                "stage_progress": 0,
                "details": {
                    "total_items": 0,
                    "completed_items": 0,
                    "pending_items": 0,
                    "in_progress_items": 0
                }
            }
        
        # 统计各状态检查项数量
        completed_items = sum(1 for item in items 
                             if item.status == CheckItemStatusEnum.COMPLETED)
        in_progress_items = sum(1 for item in items 
                               if item.status == CheckItemStatusEnum.IN_PROGRESS)
        pending_items = total_items - completed_items - in_progress_items
        
        # 计算完成率（进行中的算50%完成）
        completion_rate = (completed_items + in_progress_items * 0.5) / total_items
        
        # ACTIVE阶段进度：20% + 完成率 × 45% (20%到65%)
        progress = 20 + (completion_rate * 45)
        stage_progress = completion_rate * 100
        
        return {
            "progress": min(progress, 65),  # 不超过SUBMITTED状态
            "stage_progress": stage_progress,
            "details": {
                "total_items": total_items,
                "completed_items": completed_items,
                "in_progress_items": in_progress_items,
                "pending_items": pending_items,
                "completion_rate": round(completion_rate * 100, 1)
            }
        }
    
    @classmethod
    def _calculate_activation_progress(cls, work_order: WorkOrder) -> dict:
        """计算ACTIVATED阶段的设备开通信息"""
        activation_check = work_order.extra_data.get("activation_check") if work_order.extra_data else None
        
        if activation_check:
            return {
                "activation_status": "activated",
                "total_equipment": activation_check.get("total_equipment", 0),
                "activated_equipment": activation_check.get("activated_equipment", 0),
                "failed_equipment_count": len(activation_check.get("failed_equipment", [])),
                "check_time": activation_check.get("check_time"),
                "activated_at": work_order.activated_at.isoformat() if work_order.activated_at else None
            }
        else:
            return {
                "activation_status": "activated",
                "message": "设备已成功开通",
                "activated_at": work_order.activated_at.isoformat() if work_order.activated_at else None
            }
    
    @classmethod
    def get_progress_color(cls, progress: float) -> str:
        """根据进度返回颜色类"""
        if progress >= 100:
            return "success"      # 绿色
        elif progress >= 95:
            return "info"         # 蓝色 (ACTIVATED状态)
        elif progress >= 75:
            return "primary"      # 主色调 (审核阶段)
        elif progress >= 50:
            return "warning"      # 橙色
        else:
            return "danger"       # 红色
    
    @classmethod
    def get_stage_name(cls, status: WorkOrderStatusEnum) -> str:
        """获取阶段中文名称"""
        stage_names = {
            WorkOrderStatusEnum.PENDING: "待处理",
            WorkOrderStatusEnum.ACTIVE: "执行中",
            WorkOrderStatusEnum.SUBMITTED: "已提交",
            WorkOrderStatusEnum.UNDER_REVIEW: "审核中",
            WorkOrderStatusEnum.APPROVED: "审核通过",
            WorkOrderStatusEnum.ACTIVATED: "已开通",
            WorkOrderStatusEnum.COMPLETED: "已完成",
            WorkOrderStatusEnum.REJECTED: "审核驳回"
        }
        return stage_names.get(status, status.value)
    
    @classmethod
    def get_next_action(cls, status: WorkOrderStatusEnum) -> str:
        """获取下一步操作提示"""
        next_actions = {
            WorkOrderStatusEnum.PENDING: "等待检查员接受",
            WorkOrderStatusEnum.ACTIVE: "正在进行现场检查",
            WorkOrderStatusEnum.SUBMITTED: "等待审核员审核",
            WorkOrderStatusEnum.UNDER_REVIEW: "审核员正在审核",
            WorkOrderStatusEnum.APPROVED: "等待设备开通检测",
            WorkOrderStatusEnum.ACTIVATED: "等待管理员确认完成",
            WorkOrderStatusEnum.COMPLETED: "工单已完成",
            WorkOrderStatusEnum.REJECTED: "需要重新修改"
        }
        return next_actions.get(status, "")


def calculate_work_order_progress(db: Session, work_order_id: str) -> dict:
    """便捷函数：计算指定工单的进度"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise ValueError(f"工单不存在: {work_order_id}")
    
    return WorkOrderProgressCalculator.calculate_progress(db, wo)
