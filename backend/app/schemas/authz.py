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


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None


class SetRolePermissionsRequest(BaseModel):
    permissions: List[str] = Field(default_factory=list)


class SetUserRolesRequest(BaseModel):
    roles: List[str] = Field(default_factory=list)


class EffectivePermissionsResponse(BaseModel):
    user_id: int
    username: str
    roles: List[str]
    permissions: List[str]
    permission_modules: Dict[str, List[str]]
