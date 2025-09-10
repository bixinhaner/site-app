from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.inspection import TaskStatusEnum, TaskTypeEnum, BaseStationStatusEnum

class BaseStationDeviceBase(BaseModel):
    device_name: str
    device_type: str
    device_model: Optional[str] = None
    device_sn: Optional[str] = None
    status: BaseStationStatusEnum = BaseStationStatusEnum.OFFLINE
    omc_device_id: Optional[str] = None
    frequency_bands: Optional[Dict[str, Any]] = None
    power_config: Optional[Dict[str, Any]] = None
    network_config: Optional[Dict[str, Any]] = None
    maintenance_notes: Optional[str] = None
    issues_history: Optional[List[Dict[str, Any]]] = None

class BaseStationDeviceCreate(BaseStationDeviceBase):
    site_id: int

class BaseStationDeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    device_model: Optional[str] = None
    device_sn: Optional[str] = None
    status: Optional[BaseStationStatusEnum] = None
    omc_device_id: Optional[str] = None
    frequency_bands: Optional[Dict[str, Any]] = None
    power_config: Optional[Dict[str, Any]] = None
    network_config: Optional[Dict[str, Any]] = None
    maintenance_notes: Optional[str] = None
    issues_history: Optional[List[Dict[str, Any]]] = None
    last_online_time: Optional[datetime] = None
    last_activated_time: Optional[datetime] = None

class BaseStationDeviceResponse(BaseStationDeviceBase):
    id: str
    site_id: int
    last_online_time: Optional[datetime] = None
    last_activated_time: Optional[datetime] = None
    last_sync_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskAssignmentBase(BaseModel):
    task_title: str
    task_type: TaskTypeEnum
    task_description: Optional[str] = None
    priority: str = "normal"  # urgent, high, normal, low
    site_id: int
    assigned_to: int
    due_date: Optional[datetime] = None
    requirements: Optional[Dict[str, Any]] = None
    estimated_duration: Optional[int] = None  # 预计工期（小时）

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['urgent', 'high', 'normal', 'low']:
            raise ValueError('优先级必须是: urgent, high, normal, low')
        return v

class TaskAssignmentCreate(TaskAssignmentBase):
    pass

class TaskAssignmentUpdate(BaseModel):
    task_title: Optional[str] = None
    task_description: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    requirements: Optional[Dict[str, Any]] = None
    estimated_duration: Optional[int] = None
    accept_comments: Optional[str] = None
    progress_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    actual_duration: Optional[int] = None

class TaskAssignmentResponse(TaskAssignmentBase):
    id: str
    inspection_id: Optional[str] = None
    assigned_by: int
    status: TaskStatusEnum
    assigned_at: datetime
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_duration: Optional[int] = None
    accept_comments: Optional[str] = None
    progress_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # 站点信息
    site_name: Optional[str] = None
    site_code: Optional[str] = None
    
    # 分配人员信息
    assigner_name: Optional[str] = None
    assignee_name: Optional[str] = None

    class Config:
        from_attributes = True

class TaskStatusChangeRequest(BaseModel):
    status: TaskStatusEnum
    comments: Optional[str] = None
    actual_duration: Optional[int] = None  # 用于完成任务时填写实际工期

class TaskFilterParams(BaseModel):
    task_type: Optional[TaskTypeEnum] = None
    status: Optional[TaskStatusEnum] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    assigned_by: Optional[int] = None
    site_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class OMCDeviceStatusRequest(BaseModel):
    """OMC系统设备状态查询请求"""
    device_ids: List[str]  # OMC设备ID列表
    operation_type: str = "query_status"  # query_status, sync_all

class OMCDeviceStatusResponse(BaseModel):
    """OMC系统设备状态响应"""
    device_id: str
    status: str  # online, offline, activated
    last_online_time: Optional[datetime] = None
    last_activated_time: Optional[datetime] = None
    additional_info: Optional[Dict[str, Any]] = None

class OMCSyncResult(BaseModel):
    """OMC同步结果"""
    success: bool
    synced_count: int
    failed_count: int
    total_count: int
    failed_devices: List[str] = []
    error_messages: List[str] = []

class SiteDeviceStatusSummary(BaseModel):
    """站点设备状态汇总"""
    site_id: int
    site_name: str
    total_devices: int
    offline_devices: int
    online_devices: int
    activated_devices: int
    devices: List[BaseStationDeviceResponse]

class OpeningInspectionRequest(BaseModel):
    """新站点设备安装请求"""
    site_id: int
    inspector_id: Optional[int] = None  # 如果为空则使用当前用户
    start_time: Optional[datetime] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class MaintenanceTaskRequest(BaseModel):
    """维护任务请求"""
    site_id: int
    task_type: TaskTypeEnum
    task_title: str
    task_description: str
    priority: str = "normal"
    assigned_to: int
    due_date: Optional[datetime] = None
    requirements: Optional[Dict[str, Any]] = None

class TaskStatistics(BaseModel):
    """任务统计"""
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    overdue_tasks: int
    completion_rate: float
    average_completion_time: Optional[float] = None  # 平均完成时间（小时）

class TaskDashboard(BaseModel):
    """任务仪表板"""
    statistics: TaskStatistics
    recent_tasks: List[TaskAssignmentResponse]
    urgent_tasks: List[TaskAssignmentResponse]
    overdue_tasks: List[TaskAssignmentResponse]