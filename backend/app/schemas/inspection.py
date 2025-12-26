from pydantic import BaseModel, field_serializer
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.utils.timezone import to_utc_iso

class InspectionBase(BaseModel):
    site_id: int
    inspection_type: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None

class InspectionCreate(InspectionBase):
    pass

class InspectionUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    weather: Optional[str] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None
    photos: Optional[List[str]] = None
    equipment_status: Optional[Dict[str, Any]] = None
    safety_check: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    issues_found: Optional[str] = None
    recommendations: Optional[str] = None

class InspectionResponse(InspectionBase):
    id: int
    inspector_id: int
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    photos: Optional[List[str]] = None
    equipment_status: Optional[Dict[str, Any]] = None
    safety_check: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    issues_found: Optional[str] = None
    recommendations: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('start_time', 'end_time', 'created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
    
    class Config:
        from_attributes = True
