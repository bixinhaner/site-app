from pydantic import BaseModel, EmailStr, Field, validator, field_serializer
from typing import Dict, Optional, List
from datetime import datetime

from app.utils.timezone import to_utc_iso


def _normalize_role_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    code = str(value).strip()
    if not code:
        return None
    if len(code) > 64:
        raise ValueError("Role code too long")
    return code


def _normalize_roles(values: Optional[List[str]]) -> List[str]:
    codes: List[str] = []
    for item in values or []:
        code = _normalize_role_code(item)
        if code:
            codes.append(code)
    return sorted(set(codes))


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = None
    roles: List[str] = Field(default_factory=list)

    @validator('role')
    def validate_role(cls, v):
        return _normalize_role_code(v)

    @validator('roles')
    def validate_roles(cls, v):
        return _normalize_roles(v)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @validator('role')
    def validate_role(cls, v):
        return _normalize_role_code(v)

    @validator('roles')
    def validate_roles(cls, v):
        if v is None:
            return None
        return _normalize_roles(v)

class UserPasswordReset(BaseModel):
    user_id: int
    new_password: str


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserBatchOperation(BaseModel):
    user_ids: List[int]
    operation: str  # 'activate', 'deactivate', 'delete'
    value: Optional[str] = None  # for role change operations

class UserSearchParams(BaseModel):
    keyword: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
    skip: int = 0
    limit: int = 50

class UserResponse(UserBase):
    id: int
    role: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    data_scopes: Dict[str, str] = Field(default_factory=dict)
    is_active: bool
    avatar: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_serializer('created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    user: Optional[UserResponse] = None
