from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from app.models.inspection import (
    TaskAssignment, 
    TaskStatusHistory, 
    BaseStationDevice,
    SiteInspection,
    TaskStatusEnum,
    TaskTypeEnum,
    BaseStationStatusEnum
)
from app.models.user import User
from app.models.site import Site
from app.schemas.task import (
    TaskAssignmentCreate, 
    TaskAssignmentUpdate, 
    TaskFilterParams,
    BaseStationDeviceCreate,
    BaseStationDeviceUpdate,
    TaskStatistics
)

def create_task_assignment(db: Session, task: TaskAssignmentCreate, assigned_by: int) -> TaskAssignment:
    """创建任务分配"""
    db_task = TaskAssignment(
        id=str(uuid.uuid4()),
        task_title=task.task_title,
        task_type=task.task_type,
        task_description=task.task_description,
        priority=task.priority,
        site_id=task.site_id,
        assigned_by=assigned_by,
        assigned_to=task.assigned_to,
        due_date=task.due_date,
        requirements=task.requirements,
        estimated_duration=task.estimated_duration,
        status=TaskStatusEnum.ASSIGNED
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # 记录状态变更历史
    _create_status_history(
        db=db,
        task_id=db_task.id,
        from_status=None,
        to_status=TaskStatusEnum.ASSIGNED,
        changed_by=assigned_by,
        change_reason="任务创建并分配"
    )
    
    return db_task

def get_task_assignment(db: Session, task_id: str) -> Optional[TaskAssignment]:
    """获取任务详情"""
    return db.query(TaskAssignment).filter(TaskAssignment.id == task_id).first()

def get_task_assignments(
    db: Session, 
    filters: Optional[TaskFilterParams] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[TaskAssignment]:
    """获取任务列表"""
    query = db.query(TaskAssignment)
    
    if filters:
        if filters.task_type:
            query = query.filter(TaskAssignment.task_type == filters.task_type)
        if filters.status:
            query = query.filter(TaskAssignment.status == filters.status)
        if filters.priority:
            query = query.filter(TaskAssignment.priority == filters.priority)
        if filters.assigned_to:
            query = query.filter(TaskAssignment.assigned_to == filters.assigned_to)
        if filters.assigned_by:
            query = query.filter(TaskAssignment.assigned_by == filters.assigned_by)
        if filters.site_id:
            query = query.filter(TaskAssignment.site_id == filters.site_id)
        if filters.date_from:
            query = query.filter(TaskAssignment.assigned_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(TaskAssignment.assigned_at <= filters.date_to)
    
    return query.order_by(desc(TaskAssignment.assigned_at)).offset(skip).limit(limit).all()

def update_task_assignment(
    db: Session, 
    task_id: str, 
    task_update: TaskAssignmentUpdate
) -> Optional[TaskAssignment]:
    """更新任务信息"""
    db_task = db.query(TaskAssignment).filter(TaskAssignment.id == task_id).first()
    if not db_task:
        return None
    
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

def change_task_status(
    db: Session, 
    task_id: str, 
    new_status: TaskStatusEnum, 
    changed_by: int,
    comments: Optional[str] = None,
    actual_duration: Optional[int] = None
) -> Optional[TaskAssignment]:
    """变更任务状态"""
    db_task = db.query(TaskAssignment).filter(TaskAssignment.id == task_id).first()
    if not db_task:
        return None
    
    old_status = db_task.status
    db_task.status = new_status
    
    # 根据状态更新时间字段
    now = datetime.now()
    if new_status == TaskStatusEnum.ACCEPTED:
        db_task.accepted_at = now
        if comments:
            db_task.accept_comments = comments
    elif new_status == TaskStatusEnum.IN_PROGRESS:
        db_task.started_at = now
    elif new_status == TaskStatusEnum.COMPLETED:
        db_task.completed_at = now
        if actual_duration:
            db_task.actual_duration = actual_duration
        if comments:
            db_task.completion_notes = comments
    elif new_status == TaskStatusEnum.REJECTED:
        if comments:
            db_task.rejection_reason = comments
    
    db.commit()
    db.refresh(db_task)
    
    # 记录状态变更历史
    _create_status_history(
        db=db,
        task_id=task_id,
        from_status=old_status,
        to_status=new_status,
        changed_by=changed_by,
        change_reason=comments or f"状态变更: {old_status} -> {new_status}"
    )
    
    return db_task

def get_task_statistics(
    db: Session, 
    assigned_to: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> TaskStatistics:
    """获取任务统计信息"""
    query = db.query(TaskAssignment)
    
    if assigned_to:
        query = query.filter(TaskAssignment.assigned_to == assigned_to)
    if date_from:
        query = query.filter(TaskAssignment.assigned_at >= date_from)
    if date_to:
        query = query.filter(TaskAssignment.assigned_at <= date_to)
    
    total_tasks = query.count()
    
    # 各状态任务数量
    pending_tasks = query.filter(TaskAssignment.status == TaskStatusEnum.PENDING).count()
    in_progress_tasks = query.filter(
        TaskAssignment.status.in_([TaskStatusEnum.ASSIGNED, TaskStatusEnum.ACCEPTED, TaskStatusEnum.IN_PROGRESS])
    ).count()
    completed_tasks = query.filter(TaskAssignment.status == TaskStatusEnum.COMPLETED).count()
    
    # 逾期任务
    overdue_tasks = query.filter(
        and_(
            TaskAssignment.due_date < datetime.now(),
            TaskAssignment.status.in_([
                TaskStatusEnum.PENDING, 
                TaskStatusEnum.ASSIGNED, 
                TaskStatusEnum.ACCEPTED, 
                TaskStatusEnum.IN_PROGRESS
            ])
        )
    ).count()
    
    # 完成率
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # 平均完成时间
    completed_query = query.filter(
        and_(
            TaskAssignment.status == TaskStatusEnum.COMPLETED,
            TaskAssignment.actual_duration.isnot(None)
        )
    )
    avg_completion_time = db.query(func.avg(TaskAssignment.actual_duration)).filter(
        TaskAssignment.id.in_([t.id for t in completed_query.all()])
    ).scalar()
    
    return TaskStatistics(
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        average_completion_time=avg_completion_time
    )

def get_user_tasks(
    db: Session, 
    user_id: int, 
    status_filter: Optional[List[TaskStatusEnum]] = None,
    skip: int = 0, 
    limit: int = 50
) -> List[TaskAssignment]:
    """获取用户的任务"""
    query = db.query(TaskAssignment).filter(TaskAssignment.assigned_to == user_id)
    
    if status_filter:
        query = query.filter(TaskAssignment.status.in_(status_filter))
    
    return query.order_by(desc(TaskAssignment.assigned_at)).offset(skip).limit(limit).all()

def get_urgent_tasks(db: Session, assigned_to: Optional[int] = None) -> List[TaskAssignment]:
    """获取紧急任务"""
    query = db.query(TaskAssignment).filter(
        and_(
            TaskAssignment.priority == "urgent",
            TaskAssignment.status.in_([
                TaskStatusEnum.PENDING,
                TaskStatusEnum.ASSIGNED,
                TaskStatusEnum.ACCEPTED,
                TaskStatusEnum.IN_PROGRESS
            ])
        )
    )
    
    if assigned_to:
        query = query.filter(TaskAssignment.assigned_to == assigned_to)
    
    return query.order_by(TaskAssignment.assigned_at).all()

def get_overdue_tasks(db: Session, assigned_to: Optional[int] = None) -> List[TaskAssignment]:
    """获取逾期任务"""
    query = db.query(TaskAssignment).filter(
        and_(
            TaskAssignment.due_date < datetime.now(),
            TaskAssignment.status.in_([
                TaskStatusEnum.PENDING,
                TaskStatusEnum.ASSIGNED,
                TaskStatusEnum.ACCEPTED,
                TaskStatusEnum.IN_PROGRESS
            ])
        )
    )
    
    if assigned_to:
        query = query.filter(TaskAssignment.assigned_to == assigned_to)
    
    return query.order_by(TaskAssignment.due_date).all()

# 基站设备管理
def create_base_station_device(
    db: Session, 
    device: BaseStationDeviceCreate
) -> BaseStationDevice:
    """创建基站设备"""
    db_device = BaseStationDevice(
        id=str(uuid.uuid4()),
        **device.dict()
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

def get_base_station_device(db: Session, device_id: str) -> Optional[BaseStationDevice]:
    """获取基站设备"""
    return db.query(BaseStationDevice).filter(BaseStationDevice.id == device_id).first()

def get_site_devices(db: Session, site_id: int) -> List[BaseStationDevice]:
    """获取站点下的所有设备"""
    return db.query(BaseStationDevice).filter(BaseStationDevice.site_id == site_id).all()

def update_base_station_device(
    db: Session, 
    device_id: str, 
    device_update: BaseStationDeviceUpdate
) -> Optional[BaseStationDevice]:
    """更新基站设备"""
    db_device = db.query(BaseStationDevice).filter(BaseStationDevice.id == device_id).first()
    if not db_device:
        return None
    
    update_data = device_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    db.commit()
    db.refresh(db_device)
    return db_device

def get_devices_by_omc_ids(db: Session, omc_device_ids: List[str]) -> List[BaseStationDevice]:
    """根据OMC设备ID获取设备列表"""
    return db.query(BaseStationDevice).filter(
        BaseStationDevice.omc_device_id.in_(omc_device_ids)
    ).all()

def update_device_status_batch(
    db: Session, 
    status_updates: Dict[str, Dict[str, Any]]
) -> int:
    """批量更新设备状态"""
    updated_count = 0
    
    for omc_device_id, update_data in status_updates.items():
        device = db.query(BaseStationDevice).filter(
            BaseStationDevice.omc_device_id == omc_device_id
        ).first()
        
        if device:
            for field, value in update_data.items():
                setattr(device, field, value)
            updated_count += 1
    
    db.commit()
    return updated_count

def get_site_device_summary(db: Session, site_id: int) -> Dict[str, Any]:
    """获取站点设备状态汇总"""
    devices = get_site_devices(db, site_id)
    
    total_devices = len(devices)
    offline_devices = sum(1 for d in devices if d.status == BaseStationStatusEnum.OFFLINE)
    online_devices = sum(1 for d in devices if d.status == BaseStationStatusEnum.ONLINE)
    activated_devices = sum(1 for d in devices if d.status == BaseStationStatusEnum.ACTIVATED)
    
    return {
        "total_devices": total_devices,
        "offline_devices": offline_devices,
        "online_devices": online_devices,
        "activated_devices": activated_devices,
        "devices": devices
    }

def _create_status_history(
    db: Session,
    task_id: str,
    from_status: Optional[TaskStatusEnum],
    to_status: TaskStatusEnum,
    changed_by: int,
    change_reason: Optional[str] = None
):
    """创建状态变更历史记录"""
    history = TaskStatusHistory(
        id=str(uuid.uuid4()),
        task_id=task_id,
        from_status=from_status.value if from_status else None,
        to_status=to_status.value,
        change_reason=change_reason,
        changed_by=changed_by
    )
    db.add(history)
    db.commit()

def get_task_status_history(db: Session, task_id: str) -> List[TaskStatusHistory]:
    """获取任务状态变更历史"""
    return db.query(TaskStatusHistory).filter(
        TaskStatusHistory.task_id == task_id
    ).order_by(TaskStatusHistory.changed_at).all()

def create_opening_inspection_task(
    db: Session,
    site_id: int,
    assigned_to: int,
    assigned_by: int,
    due_date: Optional[datetime] = None
) -> TaskAssignment:
    """创建新站点设备安装任务"""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("站点不存在")
    
    task_data = TaskAssignmentCreate(
        task_title=f"站点新站点设备安装 - {site.site_name}",
        task_type=TaskTypeEnum.OPENING_INSPECTION,
        task_description=f"对站点 {site.site_name} 进行新站点设备安装，包括所有检查项目的验证和设备状态确认",
        priority="high",
        site_id=site_id,
        assigned_to=assigned_to,
        due_date=due_date or (datetime.now() + timedelta(days=3)),
        requirements={
            "inspection_type": "opening",
            "check_all_items": True,
            "verify_device_status": True,
            "submit_all_photos": True
        },
        estimated_duration=8  # 预计8小时
    )
    
    return create_task_assignment(db, task_data, assigned_by)