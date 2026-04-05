from pydantic import BaseModel, Field, validator, field_serializer
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date, time
from enum import Enum

from app.utils.timezone import to_utc_iso

# 字段类型枚举
class FieldTypeEnum(str, Enum):
    """字段类型枚举"""
    TEXT = "text"                    # 文本
    NUMBER = "number"                # 数字
    BOOLEAN = "boolean"              # 布尔
    SELECT_SINGLE = "select_single"  # 单选
    SELECT_MULTI = "select_multi"    # 多选
    DATE = "date"                    # 日期
    TIME = "time"                    # 时间
    DATETIME = "datetime"            # 日期时间
    RICH_TEXT = "rich_text"          # 富文本

# 枚举类型
class InspectionStatusEnum(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

class InspectionTypeEnum(str, Enum):
    OPENING = "OPENING"
    MAINTENANCE = "MAINTENANCE"

class CheckItemStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

# 检查模板相关Schema
class CheckItemRequirements(BaseModel):
    """检查项要求"""
    photo_requirements: Optional[Dict[str, Any]] = None
    data_requirements: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None

class CheckItemTemplate(BaseModel):
    """检查项模板"""
    item_id: str
    item_name: str
    description: str
    required_type: str = Field(..., pattern="^(photo|data|both)$")
    photo_requirements: Optional[Dict[str, Any]] = None
    data_requirements: Optional[Dict[str, Any]] = None
    assigned_role: str
    validation_rules: Optional[Dict[str, Any]] = None
    status: str = "pending"
    fields: Optional[List["FieldDefinition"]] = None  # 字段配置（使用前向声明）

class CheckCategoryTemplate(BaseModel):
    """检查分类模板"""
    category_id: str
    category_name: str
    description: str
    sector_specific: Optional[bool] = False
    items: List[CheckItemTemplate]

class InspectionTemplateData(BaseModel):
    """检查模板数据"""
    site_id: str
    site_name: str
    template_version: str = "1.0"
    check_categories: List[CheckCategoryTemplate]

class InspectionTemplateCreate(BaseModel):
    """创建检查模板"""
    site_id: int
    template_name: str
    template_data: InspectionTemplateData

class InspectionTemplateResponse(BaseModel):
    """检查模板响应"""
    id: str
    site_id: int
    template_name: str
    template_version: str
    template_data: InspectionTemplateData
    status: InspectionStatusEnum
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True

# 检查记录相关Schema
class GPSInfo(BaseModel):
    """GPS信息"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None
    address: Optional[str] = None

class SiteInspectionCreate(BaseModel):
    """创建站点检查"""
    site_id: int
    task_id: Optional[str] = None  # 关联的任务ID
    template_id: Optional[str] = None  # 如果不提供，将自动创建默认模板
    inspection_type: InspectionTypeEnum = InspectionTypeEnum.OPENING
    location: Optional[str] = None
    gps_info: Optional[GPSInfo] = None
    weather: Optional[str] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None

class SiteInspectionUpdate(BaseModel):
    """更新站点检查"""
    status: Optional[InspectionStatusEnum] = None
    work_order_id: Optional[str] = None  # 添加工单关联字段
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    gps_info: Optional[GPSInfo] = None
    weather: Optional[str] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None
    issues_found: Optional[str] = None
    recommendations: Optional[str] = None

class FieldOption(BaseModel):
    """字段选项"""
    label: str
    value: Union[str, int]

class FieldConstraints(BaseModel):
    """字段约束"""
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # 正则表达式

class FieldDefinition(BaseModel):
    """字段定义"""
    field_id: str
    label: str
    type: FieldTypeEnum
    required: bool = False
    # 字段级照片控制：默认不允许拍照；当 allow_photo=True 时才允许为该字段上传照片
    allow_photo: bool = False
    # 字段级照片必拍：仅在 allow_photo=True 时生效；表示该字段至少需要 1 张照片
    photo_required: bool = False
    options: Optional[List[FieldOption]] = None  # 用于select_single和select_multi
    constraints: Optional[FieldConstraints] = None
    default_value: Optional[Any] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None

class CheckItemDataValue(BaseModel):
    """检查项数据值"""
    field_name: str
    value: Union[str, int, float, bool, List[Union[str, int]], date, time, datetime, None]
    unit: Optional[str] = None
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
            datetime: lambda v: to_utc_iso(v)
        }

class InspectionCheckItemUpdate(BaseModel):
    """更新检查项"""
    status: Optional[CheckItemStatusEnum] = None
    data_value: Optional[List[CheckItemDataValue]] = None
    sector_id: Optional[str] = None
    notes: Optional[str] = None

class InspectionPhotoCreate(BaseModel):
    """创建检查照片"""
    check_item_id: Optional[str] = None
    field_id: Optional[str] = None
    original_name: str
    file_path: str
    file_size: int
    mime_type: str
    gps_info: GPSInfo
    taken_at: datetime
    camera_info: Optional[Dict[str, Any]] = None
    watermark_data: Optional[Dict[str, Any]] = None

class InspectionPhotoResponse(BaseModel):
    """检查照片响应"""
    id: str
    inspection_id: str
    check_item_id: Optional[str]
    field_id: Optional[str] = None
    original_name: str
    file_path: str
    file_size: int
    latitude: Optional[float]
    longitude: Optional[float]
    gps_accuracy: Optional[float] = None
    address: Optional[str]
    taken_at: datetime
    has_watermark: bool
    watermark_data: Optional[Dict[str, Any]] = None
    content_hash: Optional[str] = None
    original_content_hash: Optional[str] = None
    content_phash: Optional[str] = None
    content_vector_backend: Optional[str] = None
    hash_value: Optional[str] = None
    is_duplicate_global: Optional[bool] = False
    duplicate_info: Optional[Dict[str, Any]] = None
    is_similar_risk: Optional[bool] = False
    similar_info: Optional[Dict[str, Any]] = None
    # 上传接口在“命中重复但未阻断”时返回该字段，便于APP弹窗汇总提醒
    duplicate_warning: Optional[Dict[str, Any]] = None
    # 上传接口在“命中极度相似但未阻断”时返回该字段，便于APP弹窗汇总提醒
    similar_warning: Optional[Dict[str, Any]] = None
    review_status: Optional[str]
    created_at: datetime

    @field_serializer('taken_at', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True


class InspectionPhotoDetailContext(BaseModel):
    """检查照片详情上下文（用于独立详情页展示归属信息）"""
    photo_id: str
    inspection_id: str
    site_id: Optional[int] = None
    site_name: Optional[str] = None
    work_order_id: Optional[str] = None
    work_order_title: Optional[str] = None
    work_order_type: Optional[str] = None
    work_order_status: Optional[str] = None
    check_item_id: Optional[str] = None
    check_item_name: Optional[str] = None
    category_name: Optional[str] = None
    field_id: Optional[str] = None
    field_label: Optional[str] = None
    field_label_i18n: Optional[Dict[str, str]] = None


class InspectionPhotoDetailResponse(BaseModel):
    """检查照片详情响应"""
    photo: InspectionPhotoResponse
    context: InspectionPhotoDetailContext

class FieldIssueComment(BaseModel):
    """字段问题备注"""
    field_key: Optional[str] = None
    field_id: Optional[str] = None
    field_label: str
    field_label_i18n: Optional[Dict[str, str]] = None
    comment: str

class InspectionCheckItemResponse(BaseModel):
    """检查项响应"""
    id: str
    inspection_id: str
    item_id: str
    item_name: str
    item_name_i18n: Optional[Dict[str, str]] = None
    description: Optional[str] = None  # 检查项描述
    description_i18n: Optional[Dict[str, str]] = None
    category_id: Optional[str]
    category_name: Optional[str]
    category_name_i18n: Optional[Dict[str, str]] = None
    sector_id: Optional[str]
    band: Optional[str]
    cell_id: Optional[str]
    equipment_sn: Optional[str]
    required_type: str
    status: CheckItemStatusEnum
    data_value: Optional[List[Dict[str, Any]]] = None
    validation_result: Optional[Dict[str, Any]] = None
    fields: Optional[List[Dict[str, Any]]] = None  # 字段配置
    notes: Optional[str] = None
    checked_at: Optional[datetime]
    review_status: Optional[str]
    review_comments: Optional[str]
    review_comments_manual: Optional[str] = None
    review_comments_i18n: Optional[Dict[str, str]] = None
    field_issue_comments: Optional[List[FieldIssueComment]] = None
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
    photos: List[InspectionPhotoResponse] = []
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        'checked_at',
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

class SiteInspectionResponse(BaseModel):
    """站点检查响应"""
    id: str
    site_id: int
    work_order_id: Optional[str] = None  # 添加工单关联字段
    template_id: str
    applied_template_revision: Optional[int] = 1
    template_revision: Optional[int] = None
    template_sync: Optional[Dict[str, Any]] = None
    inspector_id: int
    inspection_type: InspectionTypeEnum
    status: InspectionStatusEnum
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    submitted_at: Optional[datetime]
    location: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    weather: Optional[str]
    temperature: Optional[str]
    completion_rate: float
    total_items: int
    completed_items: int
    failed_items: int
    score: Optional[float]
    result: Optional[str]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    review_comments: Optional[str]
    review_comments_i18n: Optional[Dict[str, str]] = None
    notes: Optional[str]
    issues_found: Optional[str]
    recommendations: Optional[str]
    check_items: List[InspectionCheckItemResponse] = []
    photos: List[InspectionPhotoResponse] = []
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        'start_time',
        'end_time',
        'submitted_at',
        'reviewed_at',
        'created_at',
        'updated_at',
    )
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True

class InspectionSummary(BaseModel):
    """检查摘要"""
    id: str
    site_id: int
    site_name: Optional[str]
    inspector_id: int
    inspector_name: Optional[str]
    inspection_type: InspectionTypeEnum
    status: InspectionStatusEnum
    start_time: Optional[datetime]
    completion_rate: float
    score: Optional[float]
    created_at: datetime

    @field_serializer('start_time', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

# 审核相关Schema
class InspectionReviewRequest(BaseModel):
    """检查审核请求"""
    action: str = Field(..., pattern="^(approve|reject)$")
    comments: Optional[str] = None
    score: Optional[float] = Field(None, ge=0, le=100)

class InspectionAuditLogResponse(BaseModel):
    """审核日志响应"""
    id: str
    inspection_id: str
    action: str
    from_status: Optional[str]
    to_status: Optional[str]
    operator_id: int
    operator_name: Optional[str]
    comments: Optional[str]
    created_at: datetime

    @field_serializer('created_at')
    def _serialize_created_at(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True

# 离线数据同步Schema
class OfflineInspectionDataCreate(BaseModel):
    """创建离线检查数据"""
    device_id: str
    local_id: str
    data_type: str = Field(..., pattern="^(inspection|check_item|photo)$")
    data_content: Dict[str, Any]

class OfflineInspectionDataResponse(BaseModel):
    """离线检查数据响应"""
    id: str
    device_id: str
    local_id: str
    data_type: str
    sync_status: str
    sync_attempts: int
    last_sync_attempt: Optional[datetime]
    sync_error: Optional[str]
    created_at: datetime

    @field_serializer('last_sync_attempt', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True

# 逐项/照片审核请求
class CheckItemReviewRequest(BaseModel):
    """检查项审核请求"""
    action: str = Field(..., pattern="^(pass|fail|warning)$")
    comments: Optional[str] = None
    comments_i18n: Optional[Dict[str, str]] = None
    field_issue_comments: Optional[List[FieldIssueComment]] = None

class PhotoReviewRequest(BaseModel):
    """照片审核请求"""
    action: str = Field(..., pattern="^(approved|rejected)$")
    comments: Optional[str] = None

class InspectionReviewSummary(BaseModel):
    """检查审核汇总"""
    total_items: int
    pass_count: int
    fail_count: int
    warning_count: int
    pending_count: int

# 数据验证函数
class DataValidator:
    """数据验证器"""
    
    @staticmethod
    def validate_gps_coordinates(latitude: float, longitude: float) -> bool:
        """验证GPS坐标"""
        return -90 <= latitude <= 90 and -180 <= longitude <= 180
    
    @staticmethod
    def validate_antenna_angle(angle: float, angle_type: str) -> bool:
        """验证天线角度"""
        if angle_type == "azimuth":
            return 0 <= angle <= 360
        elif angle_type == "downtilt":
            return 0 <= angle <= 20
        return False
    
    @staticmethod
    def validate_vswr(value: float) -> bool:
        """验证驻波比"""
        return 1.0 <= value <= 2.0
    
    @staticmethod
    def validate_height(height: float) -> bool:
        """验证挂高"""
        return 0 <= height <= 100

# 统计相关Schema
class InspectionStatistics(BaseModel):
    """检查统计"""
    total_inspections: int
    completed_inspections: int
    pending_inspections: int
    approved_inspections: int
    rejected_inspections: int
    average_score: Optional[float]
    completion_rate: float
    
class SiteInspectionProgress(BaseModel):
    """站点检查进度"""
    site_id: int
    site_name: str
    total_items: int
    completed_items: int
    completion_rate: float
    status: InspectionStatusEnum
    inspector_name: Optional[str]
    last_updated: datetime
