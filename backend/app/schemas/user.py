from pydantic import BaseModel, EmailStr, validator, field_serializer
from typing import Optional, List
from datetime import datetime

from app.utils.timezone import to_utc_iso

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"
    
    @validator('role')
    def validate_role(cls, v):
        # Align with roles referenced across the codebase
        allowed_roles = [
            'admin', 'manager',
            'inspector', 'surveyor',
            'planner', 'warehouse_manager', 'reviewer',
            'user'
        ]
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {allowed_roles}')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = [
                'admin', 'manager',
                'inspector', 'surveyor',
                'planner', 'warehouse_manager', 'reviewer',
                'user'
            ]
            if v not in allowed_roles:
                raise ValueError(f'Role must be one of: {allowed_roles}')
        return v

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
    role: str
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
    token_type: str
    user: UserResponse
