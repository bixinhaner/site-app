from pydantic import BaseModel, Field, validator, field_serializer
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import json

from app.utils.timezone import to_utc_iso

# Import for photos
if True:  # Avoid circular import
    from .inspection_enhanced import InspectionPhotoResponse


class WorkOrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class WorkOrderTypeEnum(str, Enum):
    OPENING_INSPECTION = "opening_inspection"
    MAINTENANCE = "maintenance"
    EQUIPMENT_REPLACEMENT = "equipment_replacement"
    POWER_ISSUE = "power_issue"
    TRANSMISSION_ISSUE = "transmission_issue"
    GPS_ISSUE = "gps_issue"
    SIGNAL_ISSUE = "signal_issue"
    SITE_SURVEY = "site_survey"
    SSV = "ssv"


class WorkOrderPriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkOrderReplacementTarget(BaseModel):
    """设备更换工单目标设备位（设备级：sector_id + band）。"""

    sector_id: str = Field(..., description="扇区ID（设备位）")
    band: str = Field(..., description="频段（设备位）")


class WorkOrderCreate(BaseModel):
    site_id: int
    type: WorkOrderTypeEnum
    title: str
    description: Optional[str] = None
    assigned_to: int
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.NORMAL
    due_date: Optional[datetime] = None
    template_id: Optional[str] = None
    # 设备更换工单：必须选择要更换的设备位（支持多选）
    replacement_targets: Optional[List[WorkOrderReplacementTarget]] = None
    # 仅当同站点存在“历史”安装工单（已完成/已驳回）时，前端可提示并在确认后置为 True 以允许继续创建；
    # 若存在“进行中”的安装工单，则后端会直接拒绝创建（不允许通过 confirm_duplicate 绕过）。
    confirm_duplicate: Optional[bool] = False


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[WorkOrderPriorityEnum] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = None
    auto_approve_if_all_pass: Optional[bool] = None


class WorkOrderItemAnswer(BaseModel):
    field_id: Optional[str] = None
    type: str
    value: Any
    unit: Optional[str] = None


class WorkOrderItemUpdate(BaseModel):
    data_value: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None


class WorkOrderStatusChangeRequest(BaseModel):
    status: WorkOrderStatusEnum
    comments: Optional[str] = None
    actual_duration: Optional[int] = None


class WorkOrderReviewStart(BaseModel):
    pass


class WorkOrderReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    comments: Optional[str] = None
    comments_i18n: Optional[Dict[str, str]] = None
    score: Optional[float] = None
    require_recheck: Optional[bool] = False


class WorkOrderOmcManualConfirmRequest(BaseModel):
    sn: str
    confirm_online: Optional[bool] = False
    confirm_activated: Optional[bool] = False


class ItemReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(pass|fail|warning)$")
    comments: Optional[str] = None
    comments_i18n: Optional[Dict[str, str]] = None


class ReviewCommentsI18nUpdateItem(BaseModel):
    item_id: str
    comments_i18n: Optional[Dict[str, str]] = None


class WorkOrderReviewCommentsI18nUpdateRequest(BaseModel):
    comments_i18n: Optional[Dict[str, str]] = None
    items: Optional[List[ReviewCommentsI18nUpdateItem]] = None


class WorkOrderItemResponse(BaseModel):
    id: str
    work_order_id: str
    item_id: str
    item_name: str
    category_id: Optional[str]
    category_name: Optional[str]
    sector_id: Optional[str]
    required_type: str
    status: str
    data_value: Optional[List[Dict[str, Any]]]
    validation_result: Optional[Dict[str, Any]]
    notes: Optional[str] = None
    review_status: Optional[str]
    review_comments: Optional[str]
    review_comments_i18n: Optional[Dict[str, str]] = None
    reviewed_at: Optional[datetime]
    ai_status: Optional[str] = None
    ai_mode: Optional[str] = None
    ai_model: Optional[str] = None
    ai_input_hash: Optional[str] = None
    ai_result: Optional[Dict[str, Any]] = None
    ai_error: Optional[str] = None
    ai_checked_by: Optional[int] = None
    ai_checked_at: Optional[datetime] = None
    ai_applied_by: Optional[int] = None
    ai_applied_at: Optional[datetime] = None
    photos: List['InspectionPhotoResponse'] = []
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        'reviewed_at',
        'ai_checked_at',
        'ai_applied_at',
        'created_at',
        'updated_at',
    )
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class WorkOrderResponse(BaseModel):
    id: str
    site_id: int
    site_name: Optional[str] = None
    site_code: Optional[str] = None
    inspection_id: Optional[str] = None
    title: str
    type: WorkOrderTypeEnum
    description: Optional[str]
    priority: WorkOrderPriorityEnum
    status: WorkOrderStatusEnum
    assigned_by: int
    assigner_name: Optional[str] = None
    assigned_to: int
    assignee_name: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    assigned_at: datetime
    accepted_at: Optional[datetime]
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    completed_at: Optional[datetime]
    due_date: Optional[datetime]
    review_comments: Optional[str] = None
    review_comments_i18n: Optional[Dict[str, str]] = None
    has_duplicate_photos: bool = False
    duplicate_photo_count: int = 0
    extra_data: Optional[Dict[str, Any]] = {}
    
    @validator('extra_data', pre=True)
    def parse_extra_data(cls, v):
        """处理extra_data字段，如果是字符串则解析为字典"""
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return json.loads(v) if v else {}
            except json.JSONDecodeError:
                return {}
        return v
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        'assigned_at',
        'accepted_at',
        'submitted_at',
        'reviewed_at',
        'completed_at',
        'due_date',
        'created_at',
        'updated_at',
    )
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    total_items: int
    pass_count: int
    fail_count: int
    warning_count: int
    pending_count: int


class WorkOrderBatchOperation(BaseModel):
    work_order_ids: List[str]
    operation: str  # 'delete', 'change_status', 'change_assignee', 'change_priority'
    value: Optional[str] = None  # For operations that need a value


class WorkOrderSearchParams(BaseModel):
    keyword: Optional[str] = None
    status: Optional[WorkOrderStatusEnum] = None
    type: Optional[WorkOrderTypeEnum] = None
    assigned_to: Optional[int] = None
    priority: Optional[WorkOrderPriorityEnum] = None
    skip: int = 0
    limit: int = 50


class WorkOrderListResponse(BaseModel):
    work_orders: List[WorkOrderResponse]
    total: int
    page: int
    size: int
    pages: int
