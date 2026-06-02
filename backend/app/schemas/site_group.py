from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, field_serializer

from app.utils.timezone import to_utc_iso


class SiteGroupOptionBase(BaseModel):
    code: Optional[str] = None
    name: str
    color: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class SiteGroupOptionCreate(SiteGroupOptionBase):
    pass


class SiteGroupOptionUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class SiteGroupOptionResponse(BaseModel):
    id: int
    category_id: int
    code: str
    name: str
    color: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class SiteGroupCategoryBase(BaseModel):
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    is_default: bool = False
    assignment_mode: str = "manual"
    source_type: Optional[str] = None
    source_field: Optional[str] = None
    source_config: Optional[Dict[str, object]] = None


class SiteGroupCategoryCreate(SiteGroupCategoryBase):
    options: List[SiteGroupOptionCreate] = []


class SiteGroupCategoryUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    assignment_mode: Optional[str] = None
    source_type: Optional[str] = None
    source_field: Optional[str] = None
    source_config: Optional[Dict[str, object]] = None


class SiteGroupCategoryResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    is_default: bool = False
    assignment_mode: str = "manual"
    source_type: Optional[str] = None
    source_field: Optional[str] = None
    source_config: Optional[Dict[str, object]] = None
    options: List[SiteGroupOptionResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class SiteGroupAssignmentResponse(BaseModel):
    category_id: int
    category_code: str
    category_name: str
    option_id: int
    option_code: str
    option_name: str
    option_color: Optional[str] = None
    source: Optional[str] = None


class SiteGroupAssignmentUpsert(BaseModel):
    category_id: int
    option_id: Optional[int] = None


class SiteGroupBatchAssignmentRequest(BaseModel):
    site_ids: List[int]
    category_id: int
    option_id: Optional[int] = None


class SiteGroupBatchAssignmentResponse(BaseModel):
    requested_count: int
    updated_count: int
    cleared_count: int
    skipped_count: int
    errors: List[str] = []


class SiteGroupSeedDeliveryScopeRequest(BaseModel):
    dry_run: bool = True
    overwrite: bool = False


class SiteGroupSeedDeliveryScopeResponse(BaseModel):
    dry_run: bool
    category_id: Optional[int] = None
    category_name: str
    requested_count: int
    suggested_count: int
    assigned_count: int
    unchanged_count: int
    conflict_count: int
    skipped_count: int
    by_option: Dict[str, int]
    warnings: List[str] = []
    samples: List[Dict[str, object]] = []


class SiteGroupSourceFieldResponse(BaseModel):
    source_type: str
    source_field: str
    label: str
    description: Optional[str] = None
    value_mode: str = "single"


class SiteGroupDerivedSyncRequest(BaseModel):
    dry_run: bool = True
    overwrite: bool = False
    create_missing_options: Optional[bool] = None
    assignment_mode: Optional[str] = None
    source_type: Optional[str] = None
    source_field: Optional[str] = None
    source_config: Optional[Dict[str, object]] = None


class SiteGroupDerivedSyncResponse(BaseModel):
    dry_run: bool
    category_id: int
    category_name: str
    source_type: Optional[str] = None
    source_field: Optional[str] = None
    requested_count: int
    suggested_count: int
    assigned_count: int
    unchanged_count: int
    conflict_count: int
    skipped_count: int
    created_option_count: int = 0
    by_option: Dict[str, int] = {}
    warnings: List[str] = []
    samples: List[Dict[str, object]] = []
