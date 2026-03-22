from pydantic import BaseModel, field_serializer
from typing import Optional, List
from datetime import datetime

from app.utils.timezone import to_utc_iso

class SiteBase(BaseModel):
    site_code: str
    site_name: str
    site_type: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    priority: Optional[str] = "normal"
    description: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contract_amount: Optional[float] = None

class SiteCreate(SiteBase):
    pass

class SiteUpdate(BaseModel):
    site_name: Optional[str] = None
    site_type: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contract_amount: Optional[float] = None
    assigned_to: Optional[int] = None


class SiteBatchUpdateItem(BaseModel):
    site_id: int
    site_name: Optional[str] = None
    site_type: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contract_amount: Optional[float] = None

    class Config:
        extra = "forbid"


class SiteBatchUpdateRequest(BaseModel):
    updates: List[SiteBatchUpdateItem]

    class Config:
        extra = "forbid"


class SiteBatchUpdateRowResult(BaseModel):
    row_index: int
    site_id: Optional[int] = None
    site_code: Optional[str] = None
    site_name: Optional[str] = None
    success: bool
    errors: Optional[List[str]] = []


class SiteBatchUpdateReport(BaseModel):
    total_rows: int
    success_count: int
    failed_count: int
    results: List[SiteBatchUpdateRowResult]


class SiteResponse(SiteBase):
    id: int
    status: str
    ssv_passed: Optional[bool] = False
    survey_required: Optional[bool] = True
    survey_skip_reason: Optional[str] = None
    survey_skipped_at: Optional[datetime] = None
    survey_skipped_by: Optional[int] = None
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('survey_skipped_at', 'created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True


# ===== 批量导入（基础信息） =====
class BasicImportRowResult(BaseModel):
    row_index: int
    site_code: Optional[str] = None
    success: bool
    action: Optional[str] = None  # created|skipped
    site_id: Optional[int] = None
    warnings: Optional[List[str]] = []
    errors: Optional[List[str]] = []


class BasicBatchImportReport(BaseModel):
    batch_id: str
    dry_run: bool
    total_rows: int
    success_count: int
    failed_count: int
    results: List[BasicImportRowResult]


class BasicImportHistoryItem(BaseModel):
    batch_id: str
    action: str  # dry_run|import
    operator_id: int
    operator_name: Optional[str] = None
    file_name: Optional[str] = None
    created_at: datetime
    total_rows: Optional[int] = None
    success_count: Optional[int] = None
    failed_count: Optional[int] = None

    @field_serializer('created_at')
    def _serialize_created_at(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)


class SiteListResponse(BaseModel):
    sites: List[SiteResponse]
    total: int
    page: int
    size: int
    pages: int
