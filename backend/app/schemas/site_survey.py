from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.utils.timezone import to_utc_iso


class SiteSurveyFeasibilityEnum(str):
    feasible = "feasible"
    conditional = "conditionally_feasible"
    infeasible = "infeasible"


class SiteSurveyCreate(BaseModel):
    site_id: int
    survey_date: datetime
    surveyor_name: str
    surveyor_phone: Optional[str] = None

    # Geo
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    gps_accuracy: Optional[float] = None

    # Site/Structure
    site_type: Optional[str] = None
    tower_type: Optional[str] = None
    available_height_m: Optional[float] = None
    load_capacity_kg: Optional[float] = None

    # Power/Earthing
    power_available: Optional[bool] = None
    power_distance_m: Optional[float] = None
    power_capacity_kw: Optional[float] = None
    earthing_feasible: Optional[bool] = None

    # Transmission
    fiber_available: Optional[bool] = None
    fiber_distance_m: Optional[float] = None
    duct_notes: Optional[str] = None
    microwave_los: Optional[bool] = None
    los_azimuth_deg: Optional[float] = None
    los_distance_km: Optional[float] = None

    # Environment/Compliance
    sensitive_points: Optional[str] = None
    safety_notes: Optional[str] = None
    permits_constraints: Optional[str] = None

    # Owner/Access
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    access_time_window: Optional[str] = None
    entry_constraints: Optional[str] = None

    # Conclusion
    feasibility: str = Field(..., pattern="^(feasible|conditionally_feasible|infeasible)$")
    risks: Optional[str] = None
    recommendations: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class SiteSurveyUpdate(BaseModel):
    survey_date: Optional[datetime] = None
    surveyor_name: Optional[str] = None
    surveyor_phone: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    gps_accuracy: Optional[float] = None

    site_type: Optional[str] = None
    tower_type: Optional[str] = None
    available_height_m: Optional[float] = None
    load_capacity_kg: Optional[float] = None

    power_available: Optional[bool] = None
    power_distance_m: Optional[float] = None
    power_capacity_kw: Optional[float] = None
    earthing_feasible: Optional[bool] = None

    fiber_available: Optional[bool] = None
    fiber_distance_m: Optional[float] = None
    duct_notes: Optional[str] = None
    microwave_los: Optional[bool] = None
    los_azimuth_deg: Optional[float] = None
    los_distance_km: Optional[float] = None

    sensitive_points: Optional[str] = None
    safety_notes: Optional[str] = None
    permits_constraints: Optional[str] = None

    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    access_time_window: Optional[str] = None
    entry_constraints: Optional[str] = None

    feasibility: Optional[str] = Field(None, pattern="^(feasible|conditionally_feasible|infeasible)$")
    risks: Optional[str] = None
    recommendations: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class SiteSurveyPhotoResponse(BaseModel):
    id: str
    survey_id: str
    original_name: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    address: Optional[str] = None
    taken_at: Optional[datetime] = None
    has_watermark: Optional[bool] = None
    created_at: datetime

    @field_serializer('taken_at', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class SiteSurveyResponse(BaseModel):
    id: str
    site_id: int
    site_name: Optional[str] = None
    site_code: Optional[str] = None
    survey_date: datetime
    surveyor_name: str
    surveyor_phone: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    gps_accuracy: Optional[float] = None

    site_type: Optional[str] = None
    tower_type: Optional[str] = None
    available_height_m: Optional[float] = None
    load_capacity_kg: Optional[float] = None

    power_available: Optional[bool] = None
    power_distance_m: Optional[float] = None
    power_capacity_kw: Optional[float] = None
    earthing_feasible: Optional[bool] = None

    fiber_available: Optional[bool] = None
    fiber_distance_m: Optional[float] = None
    duct_notes: Optional[str] = None
    microwave_los: Optional[bool] = None
    los_azimuth_deg: Optional[float] = None
    los_distance_km: Optional[float] = None

    sensitive_points: Optional[str] = None
    safety_notes: Optional[str] = None
    permits_constraints: Optional[str] = None

    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    access_time_window: Optional[str] = None
    entry_constraints: Optional[str] = None

    feasibility: str
    risks: Optional[str] = None
    recommendations: Optional[str] = None

    extra_data: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    photos: List[SiteSurveyPhotoResponse] = []

    @field_serializer('survey_date', 'created_at', 'updated_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class SiteSurveySummary(BaseModel):
    id: str
    site_id: int
    site_name: Optional[str] = None
    site_code: Optional[str] = None
    survey_date: datetime
    surveyor_name: str
    feasibility: str
    created_at: datetime

    @field_serializer('survey_date', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
