from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

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
    assigned_to: Optional[int] = None

class SiteResponse(SiteBase):
    id: int
    status: str
    ssv_passed: Optional[bool] = False
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
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


class SiteListResponse(BaseModel):
    sites: List[SiteResponse]
    total: int
    page: int
    size: int
    pages: int
