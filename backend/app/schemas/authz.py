from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.utils.timezone import to_utc_iso


class PermissionResponse(BaseModel):
    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: List[str] = Field(default_factory=list)
    data_scopes: Dict[str, str] = Field(default_factory=dict)

    @field_serializer("created_at", "updated_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class RoleCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    data_scopes: Dict[str, str] = Field(default_factory=dict)


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None
    data_scopes: Optional[Dict[str, str]] = None


class SetRolePermissionsRequest(BaseModel):
    permissions: List[str] = Field(default_factory=list)


class SetRoleDataScopesRequest(BaseModel):
    data_scopes: Dict[str, str] = Field(default_factory=dict)


class SetUserRolesRequest(BaseModel):
    roles: List[str] = Field(default_factory=list)


class DataScopeOptionResponse(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class DataScopeDefinitionResponse(BaseModel):
    resource: str
    name: str
    description: Optional[str] = None
    options: List[DataScopeOptionResponse] = Field(default_factory=list)


class WorkOrderExecutionPreviewResponse(BaseModel):
    can_open_entry: bool = False
    is_user_active: bool = True
    has_web_login_permission: bool = False
    has_execute_permission: bool = False
    global_enabled: bool = False
    allow_photo_upload: bool = True
    allow_device_binding: bool = True
    allow_submit: bool = True
    allow_recall: bool = True
    allow_local_upload_without_geo: bool = False
    visible_work_order_types: List[str] = Field(default_factory=list)
    editable_work_order_types: List[str] = Field(default_factory=list)
    has_any_visible_type: bool = False
    has_any_editable_type: bool = False
    reasons: List[str] = Field(default_factory=list)


class EffectivePermissionsResponse(BaseModel):
    user_id: int
    username: str
    roles: List[str]
    permissions: List[str]
    permission_modules: Dict[str, List[str]]
    data_scopes: Dict[str, str] = Field(default_factory=dict)
    inventory_scope: str = 'self'
    managed_warehouse_ids: List[int] = Field(default_factory=list)
    managed_warehouse_count: int = 0
    has_managed_warehouses: bool = False
    work_order_execution: WorkOrderExecutionPreviewResponse = Field(
        default_factory=WorkOrderExecutionPreviewResponse,
    )
