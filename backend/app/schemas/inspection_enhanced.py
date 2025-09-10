from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

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
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    gps_info: Optional[GPSInfo] = None
    weather: Optional[str] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None
    issues_found: Optional[str] = None
    recommendations: Optional[str] = None

class CheckItemDataValue(BaseModel):
    """检查项数据值"""
    field_name: str
    value: Union[str, int, float, bool]
    unit: Optional[str] = None

class InspectionCheckItemUpdate(BaseModel):
    """更新检查项"""
    status: Optional[CheckItemStatusEnum] = None
    data_value: Optional[List[CheckItemDataValue]] = None
    sector_id: Optional[str] = None

class InspectionPhotoCreate(BaseModel):
    """创建检查照片"""
    check_item_id: Optional[str] = None
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
    original_name: str
    file_path: str
    file_size: int
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    taken_at: datetime
    has_watermark: bool
    review_status: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class InspectionCheckItemResponse(BaseModel):
    """检查项响应"""
    id: str
    inspection_id: str
    item_id: str
    item_name: str
    category_id: Optional[str]
    category_name: Optional[str]
    sector_id: Optional[str]
    required_type: str
    status: CheckItemStatusEnum
    data_value: Optional[List[Dict[str, Any]]] = None
    validation_result: Optional[Dict[str, Any]] = None
    checked_at: Optional[datetime]
    review_status: Optional[str]
    review_comments: Optional[str]
    photos: List[InspectionPhotoResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SiteInspectionResponse(BaseModel):
    """站点检查响应"""
    id: str
    site_id: int
    template_id: str
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
    notes: Optional[str]
    issues_found: Optional[str]
    recommendations: Optional[str]
    check_items: List[InspectionCheckItemResponse] = []
    photos: List[InspectionPhotoResponse] = []
    created_at: datetime
    updated_at: datetime
    
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
    
    class Config:
        from_attributes = True

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