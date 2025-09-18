from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any


ALLOWED_BANDS = {"n41", "n78", "n1", "n3", "B1", "B3"}


class PlanningSector(BaseModel):
    sector_index: int = Field(..., ge=1)
    azimuth_deg: float = Field(..., ge=0, le=360)
    downtilt_deg: float = Field(..., ge=0, le=30)
    bands: List[str] = Field(default_factory=list)

    @validator("bands", each_item=True)
    def validate_band(cls, v: str) -> str:
        # Permit any string but recommend whitelist
        if not v or not isinstance(v, str):
            raise ValueError("band must be a non-empty string")
        return v


class AntennaPortPlan(BaseModel):
    port_label: str
    sector_index: int = Field(..., ge=1)
    band: Optional[str] = None
    mimo_chain: Optional[str] = None
    remarks: Optional[str] = None


class SwitchPortPlan(BaseModel):
    port_no: str
    vlan_ids: List[int] = Field(default_factory=list)
    is_uplink: bool = False
    poe: bool = False
    description: Optional[str] = None

    @validator("vlan_ids")
    def validate_vlans(cls, v: List[int]) -> List[int]:
        for vid in v:
            if vid < 1 or vid > 4094:
                raise ValueError("VLAN id must be between 1 and 4094")
        # remove duplicates while preserving order
        seen = set()
        dedup = []
        for vid in v:
            if vid not in seen:
                seen.add(vid)
                dedup.append(vid)
        return dedup


class SitePlanningBase(BaseModel):
    bands: List[str] = Field(default_factory=list)
    sector_count: int = Field(..., ge=0)
    notes: Optional[str] = None
    sectors: List[PlanningSector] = Field(default_factory=list)
    antenna_ports: List[AntennaPortPlan] = Field(default_factory=list)
    switch_ports: List[SwitchPortPlan] = Field(default_factory=list)

    @validator("sectors")
    def validate_sectors(cls, v: List[PlanningSector], values) -> List[PlanningSector]:
        if not v:
            if values.get("sector_count", 0) != 0:
                raise ValueError("sectors missing while sector_count > 0")
            return v
        idxs = [s.sector_index for s in v]
        if len(set(idxs)) != len(idxs):
            raise ValueError("sector_index must be unique")
        # Optional: enforce continuity 1..N
        if sorted(idxs) != list(range(1, len(idxs) + 1)):
            # allow gaps if needed, but warn via validation error
            pass
        return v


class SitePlanningCreate(SitePlanningBase):
    base_version: Optional[int] = Field(None, description="Optimistic lock base version")


class SitePlanningUpdate(SitePlanningCreate):
    pass


class SitePlanningVersion(BaseModel):
    id: int
    site_id: int
    version: int
    is_current: bool
    created_by: Optional[int]
    created_at: Optional[str]
    notes: Optional[str] = None


class SitePlanningResponse(SitePlanningBase):
    id: int
    site_id: int
    version: int
    is_current: bool

    class Config:
        from_attributes = True


class PlanningImportReport(BaseModel):
    dry_run: bool
    success: bool
    errors: List[str] = []
    warnings: List[str] = []
    parsed: Optional[SitePlanningBase] = None


class PlanningChangeLogItem(BaseModel):
    id: int
    operation: str
    actor_id: int
    summary: Optional[str]
    created_at: str
    diff: Optional[Dict[str, Any]]


class BatchPlanningResult(BaseModel):
    site_code: str
    site_id: Optional[int] = None
    success: bool
    errors: List[str] = []
    warnings: List[str] = []
    version_created: Optional[int] = None


class BatchImportReport(BaseModel):
    dry_run: bool
    total_sites: int
    success_count: int
    failed_count: int
    results: List[BatchPlanningResult] = []
