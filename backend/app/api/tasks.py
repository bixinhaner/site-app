from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.inspection import TaskStatusEnum, TaskTypeEnum
from app.schemas.task import (
    TaskAssignmentCreate, 
    TaskAssignmentUpdate, 
    TaskAssignmentResponse,
    TaskFilterParams,
    TaskStatusChangeRequest,
    TaskStatistics,
    TaskDashboard,
    OpeningInspectionRequest,
    MaintenanceTaskRequest,
    BaseStationDeviceCreate,
    BaseStationDeviceUpdate,
    BaseStationDeviceResponse,
    SiteDeviceStatusSummary,
    OMCSyncResult
)
from app.crud import task as crud_task
from app.services.omc_service import omc_service
from app.models.site import Site

router = APIRouter()

def enrich_task_response(db: Session, task) -> dict:
    """丰富任务响应数据，添加站点和用户信息"""
    # 使用模型的字段直接构建字典
    from sqlalchemy import inspect
    
    task_dict = {}
    mapper = inspect(task.__class__)
    
    # 获取所有模型字段
    for column in mapper.columns:
        column_name = column.name
        value = getattr(task, column_name)
        task_dict[column_name] = value
    
    # 添加丰富字段
    task_dict.update({
        "site_name": None,
        "site_code": None,
        "assigner_name": None,
        "assignee_name": None
    })
    
    # 获取站点信息
    if task.site_id:
        site = db.query(Site).filter(Site.id == task.site_id).first()
        if site:
            task_dict["site_name"] = site.site_name
            task_dict["site_code"] = site.site_code
    
    # 获取分配人信息
    if task.assigned_by:
        assigner = db.query(User).filter(User.id == task.assigned_by).first()
        if assigner:
            task_dict["assigner_name"] = assigner.full_name or assigner.username
    
    # 获取被分配人信息
    if task.assigned_to:
        assignee = db.query(User).filter(User.id == task.assigned_to).first()
        if assignee:
            task_dict["assignee_name"] = assignee.full_name or assignee.username
    
    return task_dict

# 任务管理API
@router.post("/", response_model=TaskAssignmentResponse)
async def create_task(
    task: TaskAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建任务分配"""
    # 检查权限：只有管理员和规划员可以分配任务
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限分配任务")
    
    try:
        db_task = crud_task.create_task_assignment(
            db=db, 
            task=task, 
            assigned_by=current_user.id
        )
        # 丰富响应数据
        enriched_task = enrich_task_response(db, db_task)
        return TaskAssignmentResponse(**enriched_task)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[TaskAssignmentResponse])
async def get_tasks(
    task_type: Optional[TaskTypeEnum] = None,
    status: Optional[TaskStatusEnum] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[int] = None,
    site_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务列表"""
    filters = TaskFilterParams(
        task_type=task_type,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to
    )
    
    # 如果是普通用户，只能看到分配给自己的任务
    if current_user.role == "user":
        filters.assigned_to = current_user.id
    
    tasks = crud_task.get_task_assignments(
        db=db, 
        filters=filters, 
        skip=skip, 
        limit=limit
    )
    
    # 丰富每个任务的响应数据
    enriched_tasks = []
    for task in tasks:
        enriched_task = enrich_task_response(db, task)
        enriched_tasks.append(TaskAssignmentResponse(**enriched_task))
    
    return enriched_tasks

@router.get("/{task_id}", response_model=TaskAssignmentResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务详情"""
    task = crud_task.get_task_assignment(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 权限检查：只能查看自己相关的任务
    if current_user.role == "user" and task.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限查看此任务")
    
    # 丰富响应数据
    enriched_task = enrich_task_response(db, task)
    return TaskAssignmentResponse(**enriched_task)

@router.put("/{task_id}", response_model=TaskAssignmentResponse)
async def update_task(
    task_id: str,
    task_update: TaskAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新任务信息"""
    task = crud_task.get_task_assignment(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 权限检查
    if current_user.role == "user" and task.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限修改此任务")
    
    updated_task = crud_task.update_task_assignment(
        db=db, 
        task_id=task_id, 
        task_update=task_update
    )
    # 丰富响应数据
    enriched_task = enrich_task_response(db, updated_task)
    return TaskAssignmentResponse(**enriched_task)

@router.post("/{task_id}/status", response_model=TaskAssignmentResponse)
async def change_task_status(
    task_id: str,
    status_change: TaskStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """变更任务状态"""
    task = crud_task.get_task_assignment(db=db, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 权限检查
    if current_user.role == "user" and task.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限修改此任务状态")
    
    # 状态变更逻辑验证
    current_status = task.status
    new_status = status_change.status
    
    # 定义允许的状态转换
    allowed_transitions = {
        TaskStatusEnum.PENDING: [TaskStatusEnum.ASSIGNED],
        TaskStatusEnum.ASSIGNED: [TaskStatusEnum.ACCEPTED, TaskStatusEnum.REJECTED],
        TaskStatusEnum.ACCEPTED: [TaskStatusEnum.IN_PROGRESS],
        TaskStatusEnum.IN_PROGRESS: [TaskStatusEnum.SUBMITTED],
        TaskStatusEnum.SUBMITTED: [TaskStatusEnum.UNDER_REVIEW, TaskStatusEnum.REJECTED],
        TaskStatusEnum.UNDER_REVIEW: [TaskStatusEnum.APPROVED, TaskStatusEnum.REJECTED],
        TaskStatusEnum.APPROVED: [TaskStatusEnum.COMPLETED],
        TaskStatusEnum.REJECTED: [TaskStatusEnum.ASSIGNED, TaskStatusEnum.IN_PROGRESS],
        TaskStatusEnum.COMPLETED: []  # 完成状态不能再变更
    }
    
    if new_status not in allowed_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400, 
            detail=f"不能从状态 {current_status} 转换到 {new_status}"
        )
    
    updated_task = crud_task.change_task_status(
        db=db,
        task_id=task_id,
        new_status=new_status,
        changed_by=current_user.id,
        comments=status_change.comments,
        actual_duration=status_change.actual_duration
    )
    
    # 丰富响应数据
    enriched_task = enrich_task_response(db, updated_task)
    return TaskAssignmentResponse(**enriched_task)

@router.get("/my/tasks", response_model=List[TaskAssignmentResponse])
async def get_my_tasks(
    status: Optional[List[TaskStatusEnum]] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取我的任务"""
    tasks = crud_task.get_user_tasks(
        db=db, 
        user_id=current_user.id, 
        status_filter=status,
        skip=skip, 
        limit=limit
    )
    
    # 丰富每个任务的响应数据
    enriched_tasks = []
    for task in tasks:
        enriched_task = enrich_task_response(db, task)
        enriched_tasks.append(TaskAssignmentResponse(**enriched_task))
    
    return enriched_tasks

@router.get("/statistics/overview", response_model=TaskStatistics)
async def get_task_statistics(
    assigned_to: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务统计信息"""
    # 如果是普通用户，只统计自己的任务
    if current_user.role == "user":
        assigned_to = current_user.id
    
    stats = crud_task.get_task_statistics(
        db=db,
        assigned_to=assigned_to,
        date_from=date_from,
        date_to=date_to
    )
    return stats

@router.get("/dashboard/overview", response_model=TaskDashboard)
async def get_task_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务仪表板数据"""
    assigned_to = current_user.id if current_user.role == "user" else None
    
    # 获取统计信息
    statistics = crud_task.get_task_statistics(db=db, assigned_to=assigned_to)
    
    # 获取最近任务
    recent_tasks_raw = crud_task.get_task_assignments(
        db=db,
        filters=TaskFilterParams(assigned_to=assigned_to),
        skip=0,
        limit=10
    )
    
    # 获取紧急任务
    urgent_tasks_raw = crud_task.get_urgent_tasks(db=db, assigned_to=assigned_to)
    
    # 获取逾期任务
    overdue_tasks_raw = crud_task.get_overdue_tasks(db=db, assigned_to=assigned_to)
    
    # 丰富所有任务的响应数据
    recent_tasks = []
    for task in recent_tasks_raw:
        enriched_task = enrich_task_response(db, task)
        recent_tasks.append(TaskAssignmentResponse(**enriched_task))
    
    urgent_tasks = []
    for task in urgent_tasks_raw:
        enriched_task = enrich_task_response(db, task)
        urgent_tasks.append(TaskAssignmentResponse(**enriched_task))
    
    overdue_tasks = []
    for task in overdue_tasks_raw:
        enriched_task = enrich_task_response(db, task)
        overdue_tasks.append(TaskAssignmentResponse(**enriched_task))
    
    return TaskDashboard(
        statistics=statistics,
        recent_tasks=recent_tasks,
        urgent_tasks=urgent_tasks,
        overdue_tasks=overdue_tasks
    )

# 快捷任务创建API
@router.post("/opening-inspection", response_model=TaskAssignmentResponse)
async def create_opening_inspection_task(
    request: OpeningInspectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新站点设备安装任务"""
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限创建新站点设备安装任务")
    
    inspector_id = request.inspector_id or current_user.id
    
    try:
        task = crud_task.create_opening_inspection_task(
            db=db,
            site_id=request.site_id,
            assigned_to=inspector_id,
            assigned_by=current_user.id
        )
        # 丰富响应数据
        enriched_task = enrich_task_response(db, task)
        return TaskAssignmentResponse(**enriched_task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/maintenance", response_model=TaskAssignmentResponse)
async def create_maintenance_task(
    request: MaintenanceTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建维护任务"""
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限创建维护任务")
    
    task_data = TaskAssignmentCreate(
        task_title=request.task_title,
        task_type=request.task_type,
        task_description=request.task_description,
        priority=request.priority,
        site_id=request.site_id,
        assigned_to=request.assigned_to,
        due_date=request.due_date,
        requirements=request.requirements
    )
    
    try:
        task = crud_task.create_task_assignment(
            db=db,
            task=task_data,
            assigned_by=current_user.id
        )
        # 丰富响应数据
        enriched_task = enrich_task_response(db, task)
        return TaskAssignmentResponse(**enriched_task)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 基站设备管理API
@router.post("/devices/", response_model=BaseStationDeviceResponse)
async def create_device(
    device: BaseStationDeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建基站设备"""
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限创建设备")
    
    try:
        db_device = crud_task.create_base_station_device(db=db, device=device)
        return db_device
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/devices/{device_id}", response_model=BaseStationDeviceResponse)
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取基站设备详情"""
    device = crud_task.get_base_station_device(db=db, device_id=device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device

@router.get("/sites/{site_id}/devices", response_model=SiteDeviceStatusSummary)
async def get_site_devices(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取站点设备状态汇总"""
    summary = crud_task.get_site_device_summary(db=db, site_id=site_id)
    
    # 获取站点信息
    from app.models.site import Site
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="站点不存在")
    
    return SiteDeviceStatusSummary(
        site_id=site_id,
        site_name=site.site_name,
        **summary
    )

@router.put("/devices/{device_id}", response_model=BaseStationDeviceResponse)
async def update_device(
    device_id: str,
    device_update: BaseStationDeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新基站设备"""
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限修改设备")
    
    device = crud_task.update_base_station_device(
        db=db, 
        device_id=device_id, 
        device_update=device_update
    )
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device

# OMC系统同步API
@router.post("/omc/sync-site/{site_id}", response_model=OMCSyncResult)
async def sync_site_devices(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """同步站点设备状态"""
    if current_user.role not in ["admin", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限同步设备状态")
    
    try:
        result = await omc_service.sync_site_devices(
            site_id=site_id, 
            db=db, 
            operator_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")

@router.post("/omc/sync-all", response_model=OMCSyncResult)
async def sync_all_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """同步所有设备状态"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="无权限执行全局同步")
    
    try:
        result = await omc_service.sync_all_devices(
            db=db, 
            operator_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除任务"""
    # 检查权限：只有管理员可以删除任务
    if current_user.role not in ["admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以删除任务"
        )
    
    # 获取任务
    task = crud_task.get_task_assignment(db=db, task_id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查任务状态，只能删除特定状态的任务
    deletable_statuses = [TaskStatusEnum.PENDING, TaskStatusEnum.ASSIGNED, TaskStatusEnum.REJECTED]
    if task.status not in deletable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只能删除待分配、已分配或已驳回的任务，当前状态：{task.status}"
        )
    
    try:
        # 删除相关的状态历史记录
        from app.models.inspection import TaskStatusHistory
        db.query(TaskStatusHistory).filter(TaskStatusHistory.task_id == task_id).delete()
        
        # 删除任务
        db.delete(task)
        db.commit()
        
        return {"message": f"任务 '{task.task_title}' 已成功删除"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}"
        )

@router.post("/{task_id}/review")
async def review_task(
    task_id: str,
    review_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """审核任务"""
    # 检查权限：只有管理员可以审核任务
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员或经理可以审核任务"
        )
    
    # 获取任务
    task = crud_task.get_task_assignment(db=db, task_id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查任务状态，只能审核已提交的任务
    if task.status != TaskStatusEnum.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只能审核已提交的任务，当前状态：{task.status}"
        )
    
    try:
        result = review_data.get("result")  # approved 或 rejected
        comments = review_data.get("comments", "")
        require_recheck = review_data.get("require_recheck", False)
        
        if result not in ["approved", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="审核结果必须为 approved 或 rejected"
            )
        
        # 更新任务状态
        if result == "approved":
            new_status = TaskStatusEnum.APPROVED
        else:
            new_status = TaskStatusEnum.REJECTED
        
        # 使用现有的状态变更方法
        updated_task = crud_task.change_task_status(
            db=db,
            task_id=task_id,
            new_status=new_status,
            changed_by=current_user.id,
            comments=f"审核{result}: {comments}"
        )
        
        if not updated_task:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新任务状态失败"
            )
        
        # 如果是驳回且需要重新检查，将状态设置为assigned以便重新分配
        if result == "rejected" and require_recheck:
            updated_task = crud_task.change_task_status(
                db=db,
                task_id=task_id,
                new_status=TaskStatusEnum.ASSIGNED,
                changed_by=current_user.id,
                comments="审核驳回，需要重新检查"
            )
        
        # 丰富响应数据
        enriched_task = enrich_task_response(db, updated_task)
        return {
            "message": f"任务审核{result}成功",
            "task": TaskAssignmentResponse(**enriched_task)
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"审核任务失败: {str(e)}"
        )