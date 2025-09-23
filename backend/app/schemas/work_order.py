from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Import for photos
if True:  # Avoid circular import
    from .inspection_enhanced import InspectionPhotoResponse


class WorkOrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class WorkOrderTypeEnum(str, Enum):
    OPENING_INSPECTION = "opening_inspection"
    MAINTENANCE = "maintenance"
    POWER_ISSUE = "power_issue"
    TRANSMISSION_ISSUE = "transmission_issue"
    GPS_ISSUE = "gps_issue"
    SIGNAL_ISSUE = "signal_issue"


class WorkOrderPriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkOrderCreate(BaseModel):
    site_id: int
    type: WorkOrderTypeEnum
    title: str
    description: Optional[str] = None
    assigned_to: int
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.NORMAL
    due_date: Optional[datetime] = None
    template_id: Optional[str] = None


class WorkOrderUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    priority: Optional[WorkOrderPriorityEnum]
    due_date: Optional[datetime]
    auto_approve_if_all_pass: Optional[bool]


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
    score: Optional[float] = None
    require_recheck: Optional[bool] = False


class ItemReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(pass|fail|warning)$")
    comments: Optional[str] = None


class PhotoReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected)$")
    comments: Optional[str] = None


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
    review_status: Optional[str]
    review_comments: Optional[str]
    reviewed_at: Optional[datetime]
    photos: List['InspectionPhotoResponse'] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkOrderPhotoResponse(BaseModel):
    id: str
    work_order_id: str
    item_id: Optional[str]
    original_name: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    taken_at: datetime
    has_watermark: bool
    review_status: Optional[str]
    created_at: datetime

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
    extra_data: Optional[Dict[str, Any]] = {}
    created_at: datetime
    updated_at: datetime

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
