from pydantic import BaseModel
from typing import Optional
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
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True