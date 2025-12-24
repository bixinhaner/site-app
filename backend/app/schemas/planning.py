from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


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
    actor_name: Optional[str] = None
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
    # LLD 导入扩展字段（可选）
    lte_cell_count: Optional[int] = None
    nr_cell_count: Optional[int] = None
    bands: Optional[List[str]] = None
    # 仅在 dry_run 场景下使用：用于在前端预览本次导入将带来的 Cell 级变更
    preview_diff: Optional[Dict[str, Any]] = None


class BatchImportReport(BaseModel):
    dry_run: bool
    total_sites: int
    success_count: int
    failed_count: int
    results: List[BatchPlanningResult] = []


class PlanningCell(BaseModel):
    """LLD Cell 明细返回模型（字段与 SitePlanningCell 模型对应的子集）"""

    id: int
    planning_id: int
    site_id: int

    rat: str
    band_code: str
    sheet_name: Optional[str] = None

    tower_id: str
    site_information: Optional[str] = None
    site_name: Optional[str] = None

    local_cell_id: Optional[int] = None
    cell_name: Optional[str] = None

    enb_id: Optional[int] = None
    eci: Optional[int] = None
    plmn: Optional[str] = None
    tac: Optional[str] = None
    pci: Optional[int] = None
    zc_root_index: Optional[int] = None

    longitude: Optional[float] = None
    latitude: Optional[float] = None

    power_dbm: Optional[float] = None
    pa: Optional[str] = None
    pb: Optional[str] = None

    cover_type: Optional[str] = None
    band_in_file: Optional[str] = None
    frequency: Optional[int] = None
    bandwidth: Optional[str] = None

    mechanical_downtilt_deg: Optional[float] = None
    electrical_downtilt_deg: Optional[float] = None
    azimuth_deg: Optional[float] = None

    tower_height: Optional[float] = None
    antenna_height: Optional[float] = None
    tower_merchants: Optional[str] = None

    band_combination: Optional[str] = None
    antenna_ports: Optional[int] = None
    cell_allocation: Optional[str] = None

    tower_name: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    coverage_area: Optional[str] = None
    coverage_weight: Optional[str] = None
    scenario: Optional[str] = None
    scenario_weight: Optional[str] = None
    weight: Optional[str] = None
    remark: Optional[str] = None

    # 5G 专有字段
    gnb_id: Optional[int] = None
    gnb_length: Optional[int] = None
    nci: Optional[int] = None

    gnb_wan_ip: Optional[str] = None
    master_5gc_ip1: Optional[str] = None
    master_5gc_ip2: Optional[str] = None
    master_5gc_ip3: Optional[str] = None
    backup_5gc_ip1: Optional[str] = None
    backup_5gc_ip2: Optional[str] = None
    backup_5gc_ip3: Optional[str] = None

    master_omc_ip: Optional[str] = None
    backup_omc_ip: Optional[str] = None

    ntp_ip1: Optional[str] = None
    ntp_ip2: Optional[str] = None

    kssb: Optional[float] = None
    offset_to_point_a: Optional[str] = None
    slot_config: Optional[str] = None
    slot_config_dl_ul: Optional[str] = None
    symbol_config_dl_ul: Optional[str] = None

    # 新版 LLD 模板扩展字段（统一字符串）
    excel_index: Optional[str] = None
    province_region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    address: Optional[str] = None
    cluster: Optional[str] = None
    sn: Optional[str] = None

    work_mode: Optional[str] = None
    duplex_mode: Optional[str] = None
    mimo: Optional[str] = None
    cell_id_in_file: Optional[str] = None
    sa: Optional[str] = None
    ssp: Optional[str] = None

    total_tilt: Optional[str] = None
    antenna_model: Optional[str] = None
    antenna_gain: Optional[str] = None
    ret: Optional[str] = None
    transmission_port: Optional[str] = None
    lld_type: Optional[str] = None

    dl_bandwidth: Optional[str] = None
    ul_bandwidth: Optional[str] = None
    ssb_absolute_freq: Optional[str] = None
    dl_subcarrier_spacing: Optional[str] = None

    oam_ip_type: Optional[str] = None
    oam_ip_address: Optional[str] = None
    oam_ip_submask: Optional[str] = None
    oam_ip_gateway: Optional[str] = None
    oam_ip_vlan: Optional[str] = None
    oam_ip_dns: Optional[str] = None
    oam_binding_port: Optional[str] = None

    control_plane_ip_type: Optional[str] = None
    control_plane_address: Optional[str] = None
    control_plane_submask: Optional[str] = None
    control_plane_gateway: Optional[str] = None
    control_plane_vlan: Optional[str] = None
    control_plane_dns: Optional[str] = None
    control_plane_binding_port: Optional[str] = None

    user_plane_ip_type: Optional[str] = None
    user_plane_address: Optional[str] = None
    user_plane_submask: Optional[str] = None
    user_plane_gateway: Optional[str] = None
    user_plane_vlan: Optional[str] = None
    user_plane_dns: Optional[str] = None
    user_plane_binding_port: Optional[str] = None

    x2_ip_type: Optional[str] = None
    x2_address: Optional[str] = None
    x2_submask: Optional[str] = None
    x2_gateway: Optional[str] = None
    x2_vlan: Optional[str] = None
    x2_dns: Optional[str] = None
    x2_binding_port: Optional[str] = None

    xn_ip_type: Optional[str] = None
    xn_address: Optional[str] = None
    xn_submask: Optional[str] = None
    xn_gateway: Optional[str] = None
    xn_vlan: Optional[str] = None
    xn_dns: Optional[str] = None
    xn_binding_port: Optional[str] = None

    mme_ip_1: Optional[str] = None
    mme_ip_2: Optional[str] = None
    mme_ip_3: Optional[str] = None
    mme_ip_4: Optional[str] = None
    mme_ip_5: Optional[str] = None
    mme_ip_6: Optional[str] = None
    mme_ip_7: Optional[str] = None
    mme_ip_8: Optional[str] = None

    class Config:
        from_attributes = True


class SitePlanningLldSummary(BaseModel):
    bands: List[str] = []
    sector_count: int = 0
    lte_cell_count: int = 0
    nr_cell_count: int = 0
    mechanical_downtilt_min: Optional[float] = None
    mechanical_downtilt_max: Optional[float] = None
    electrical_downtilt_min: Optional[float] = None
    electrical_downtilt_max: Optional[float] = None


class LldEditPolicy(BaseModel):
    mode: Literal["readonly", "limited", "full"]
    can_edit: bool = False
    can_import: bool = False
    can_add_cell: bool = False
    can_delete_cell: bool = False
    locked_fields: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class SitePlanningLldResponse(BaseModel):
    planning: Optional[SitePlanningResponse] = None
    cells: List[PlanningCell] = []
    summary: SitePlanningLldSummary
    edit_policy: Optional[LldEditPolicy] = None


class LldPlanningSummaryItem(BaseModel):
    site_id: int
    site_code: str
    site_name: str
    site_type: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: Optional[str] = None

    planning_id: int
    planning_version: int
    planning_created_at: Optional[datetime] = None
    planning_updated_at: Optional[datetime] = None
    planning_notes: Optional[str] = None

    bands: List[str] = []
    sector_count: int = 0
    lte_cell_count: int = 0
    nr_cell_count: int = 0
    mechanical_downtilt_min: Optional[float] = None
    mechanical_downtilt_max: Optional[float] = None
    electrical_downtilt_min: Optional[float] = None
    electrical_downtilt_max: Optional[float] = None
    edit_policy: Optional[LldEditPolicy] = None


class LldPlanningSummaryListResponse(BaseModel):
    items: List[LldPlanningSummaryItem] = []
    total: int
    page: int
    size: int
    pages: int


class LldPlanningCellItem(PlanningCell):
    site_code: str
    site_name: Optional[str] = None
    site_status: Optional[str] = None
    site_city: Optional[str] = None
    planning_version: int
    planning_created_at: Optional[datetime] = None
    planning_updated_at: Optional[datetime] = None


class LldPlanningCellListResponse(BaseModel):
    items: List[LldPlanningCellItem] = []
    total: int
    page: int
    size: int
    pages: int


class LldTemplateCellListResponse(BaseModel):
    sheet: str
    headers: List[str] = []
    items: List[Dict[str, Any]] = []
    total: int
    page: int
    size: int
    pages: int


class PlanningCellCreate(BaseModel):
    """用于创建新 LLD Cell 的请求模型"""
    rat: str = Field(..., description="Radio Access Technology: LTE or NR")
    band_code: str = Field(..., description="Band code like n41, n78, B1, B3")
    sheet_name: Optional[str] = None
    tower_id: Optional[str] = None
    local_cell_id: int = Field(..., ge=1, le=65535, description="Local Cell ID (1-65535)")
    cell_name: Optional[str] = None
    enb_id: Optional[int] = Field(None, ge=0, description="eNodeB ID for LTE")
    eci: Optional[int] = Field(None, ge=0, description="E-UTRAN Cell Identity")
    plmn: Optional[str] = None
    tac: Optional[str] = None
    pci: Optional[int] = Field(None, ge=0, le=503, description="Physical Cell ID (0-503)")
    zc_root_index: Optional[int] = None
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    power_dbm: Optional[float] = Field(None, ge=-50, le=80, description="Power in dBm")
    pa: Optional[str] = None
    pb: Optional[str] = None
    cover_type: Optional[str] = None
    band_in_file: Optional[str] = None
    frequency: Optional[int] = None
    bandwidth: Optional[str] = None
    mechanical_downtilt_deg: Optional[float] = Field(None, ge=0, le=90, description="Mechanical downtilt in degrees")
    electrical_downtilt_deg: Optional[float] = Field(None, ge=0, le=90, description="Electrical downtilt in degrees")
    azimuth_deg: Optional[float] = Field(None, ge=0, le=360, description="Azimuth in degrees")
    tower_height: Optional[float] = None
    antenna_height: Optional[float] = None
    tower_merchants: Optional[str] = None
    band_combination: Optional[str] = None
    antenna_ports: Optional[int] = None
    cell_allocation: Optional[str] = None
    tower_name: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    coverage_area: Optional[str] = None
    coverage_weight: Optional[str] = None
    scenario: Optional[str] = None
    scenario_weight: Optional[str] = None
    weight: Optional[str] = None
    remark: Optional[str] = None
    # 5G 专有字段
    gnb_id: Optional[int] = Field(None, ge=0, description="gNodeB ID for 5G")
    gnb_length: Optional[int] = None
    nci: Optional[int] = Field(None, ge=0, description="NR Cell Identity")
    gnb_wan_ip: Optional[str] = None
    master_5gc_ip1: Optional[str] = None
    master_5gc_ip2: Optional[str] = None
    master_5gc_ip3: Optional[str] = None
    backup_5gc_ip1: Optional[str] = None
    backup_5gc_ip2: Optional[str] = None
    backup_5gc_ip3: Optional[str] = None
    master_omc_ip: Optional[str] = None
    backup_omc_ip: Optional[str] = None
    ntp_ip1: Optional[str] = None
    ntp_ip2: Optional[str] = None
    kssb: Optional[float] = None
    offset_to_point_a: Optional[str] = None
    slot_config: Optional[str] = None
    slot_config_dl_ul: Optional[str] = None
    symbol_config_dl_ul: Optional[str] = None
    # 新版 LLD 模板扩展字段（统一字符串）
    excel_index: Optional[str] = None
    province_region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    address: Optional[str] = None
    cluster: Optional[str] = None
    sn: Optional[str] = None

    work_mode: Optional[str] = None
    duplex_mode: Optional[str] = None
    mimo: Optional[str] = None
    cell_id_in_file: Optional[str] = None
    sa: Optional[str] = None
    ssp: Optional[str] = None

    total_tilt: Optional[str] = None
    antenna_model: Optional[str] = None
    antenna_gain: Optional[str] = None
    ret: Optional[str] = None
    transmission_port: Optional[str] = None
    lld_type: Optional[str] = None

    dl_bandwidth: Optional[str] = None
    ul_bandwidth: Optional[str] = None
    ssb_absolute_freq: Optional[str] = None
    dl_subcarrier_spacing: Optional[str] = None

    oam_ip_type: Optional[str] = None
    oam_ip_address: Optional[str] = None
    oam_ip_submask: Optional[str] = None
    oam_ip_gateway: Optional[str] = None
    oam_ip_vlan: Optional[str] = None
    oam_ip_dns: Optional[str] = None
    oam_binding_port: Optional[str] = None

    control_plane_ip_type: Optional[str] = None
    control_plane_address: Optional[str] = None
    control_plane_submask: Optional[str] = None
    control_plane_gateway: Optional[str] = None
    control_plane_vlan: Optional[str] = None
    control_plane_dns: Optional[str] = None
    control_plane_binding_port: Optional[str] = None

    user_plane_ip_type: Optional[str] = None
    user_plane_address: Optional[str] = None
    user_plane_submask: Optional[str] = None
    user_plane_gateway: Optional[str] = None
    user_plane_vlan: Optional[str] = None
    user_plane_dns: Optional[str] = None
    user_plane_binding_port: Optional[str] = None

    x2_ip_type: Optional[str] = None
    x2_address: Optional[str] = None
    x2_submask: Optional[str] = None
    x2_gateway: Optional[str] = None
    x2_vlan: Optional[str] = None
    x2_dns: Optional[str] = None
    x2_binding_port: Optional[str] = None

    xn_ip_type: Optional[str] = None
    xn_address: Optional[str] = None
    xn_submask: Optional[str] = None
    xn_gateway: Optional[str] = None
    xn_vlan: Optional[str] = None
    xn_dns: Optional[str] = None
    xn_binding_port: Optional[str] = None

    mme_ip_1: Optional[str] = None
    mme_ip_2: Optional[str] = None
    mme_ip_3: Optional[str] = None
    mme_ip_4: Optional[str] = None
    mme_ip_5: Optional[str] = None
    mme_ip_6: Optional[str] = None
    mme_ip_7: Optional[str] = None
    mme_ip_8: Optional[str] = None

    @validator('rat')
    def validate_rat(cls, v):
        if v not in ['LTE', 'NR']:
            raise ValueError('rat must be either LTE or NR')
        return v

    @validator('pci')
    def validate_pci(cls, v):
        if v is not None and (v < 0 or v > 503):
            raise ValueError('PCI must be between 0 and 503')
        return v


class PlanningCellUpdate(BaseModel):
    """用于更新 LLD Cell 的请求模型"""
    rat: Optional[str] = Field(None, description="Radio Access Technology: LTE or NR")
    band_code: Optional[str] = Field(None, description="Band code like n41, n78, B1, B3")
    sheet_name: Optional[str] = None
    tower_id: Optional[str] = None
    local_cell_id: Optional[int] = Field(None, ge=1, le=65535, description="Local Cell ID (1-65535)")
    cell_name: Optional[str] = None
    enb_id: Optional[int] = Field(None, ge=0, description="eNodeB ID for LTE")
    eci: Optional[int] = Field(None, ge=0, description="E-UTRAN Cell Identity")
    plmn: Optional[str] = None
    tac: Optional[str] = None
    pci: Optional[int] = Field(None, ge=0, le=503, description="Physical Cell ID (0-503)")
    zc_root_index: Optional[int] = None
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    power_dbm: Optional[float] = Field(None, ge=-50, le=80, description="Power in dBm")
    pa: Optional[str] = None
    pb: Optional[str] = None
    cover_type: Optional[str] = None
    band_in_file: Optional[str] = None
    frequency: Optional[int] = None
    bandwidth: Optional[str] = None
    mechanical_downtilt_deg: Optional[float] = Field(None, ge=0, le=90, description="Mechanical downtilt in degrees")
    electrical_downtilt_deg: Optional[float] = Field(None, ge=0, le=90, description="Electrical downtilt in degrees")
    azimuth_deg: Optional[float] = Field(None, ge=0, le=360, description="Azimuth in degrees")
    tower_height: Optional[float] = None
    antenna_height: Optional[float] = None
    tower_merchants: Optional[str] = None
    band_combination: Optional[str] = None
    antenna_ports: Optional[int] = None
    cell_allocation: Optional[str] = None
    tower_name: Optional[str] = None
    town: Optional[str] = None
    region: Optional[str] = None
    coverage_area: Optional[str] = None
    coverage_weight: Optional[str] = None
    scenario: Optional[str] = None
    scenario_weight: Optional[str] = None
    weight: Optional[str] = None
    remark: Optional[str] = None
    # 5G 专有字段
    gnb_id: Optional[int] = Field(None, ge=0, description="gNodeB ID for 5G")
    gnb_length: Optional[int] = None
    nci: Optional[int] = Field(None, ge=0, description="NR Cell Identity")
    gnb_wan_ip: Optional[str] = None
    master_5gc_ip1: Optional[str] = None
    master_5gc_ip2: Optional[str] = None
    master_5gc_ip3: Optional[str] = None
    backup_5gc_ip1: Optional[str] = None
    backup_5gc_ip2: Optional[str] = None
    backup_5gc_ip3: Optional[str] = None
    master_omc_ip: Optional[str] = None
    backup_omc_ip: Optional[str] = None
    ntp_ip1: Optional[str] = None
    ntp_ip2: Optional[str] = None
    kssb: Optional[float] = None
    offset_to_point_a: Optional[str] = None
    slot_config: Optional[str] = None
    slot_config_dl_ul: Optional[str] = None
    symbol_config_dl_ul: Optional[str] = None
    # 新版 LLD 模板扩展字段（统一字符串）
    excel_index: Optional[str] = None
    province_region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    address: Optional[str] = None
    cluster: Optional[str] = None
    sn: Optional[str] = None

    work_mode: Optional[str] = None
    duplex_mode: Optional[str] = None
    mimo: Optional[str] = None
    cell_id_in_file: Optional[str] = None
    sa: Optional[str] = None
    ssp: Optional[str] = None

    total_tilt: Optional[str] = None
    antenna_model: Optional[str] = None
    antenna_gain: Optional[str] = None
    ret: Optional[str] = None
    transmission_port: Optional[str] = None
    lld_type: Optional[str] = None

    dl_bandwidth: Optional[str] = None
    ul_bandwidth: Optional[str] = None
    ssb_absolute_freq: Optional[str] = None
    dl_subcarrier_spacing: Optional[str] = None

    oam_ip_type: Optional[str] = None
    oam_ip_address: Optional[str] = None
    oam_ip_submask: Optional[str] = None
    oam_ip_gateway: Optional[str] = None
    oam_ip_vlan: Optional[str] = None
    oam_ip_dns: Optional[str] = None
    oam_binding_port: Optional[str] = None

    control_plane_ip_type: Optional[str] = None
    control_plane_address: Optional[str] = None
    control_plane_submask: Optional[str] = None
    control_plane_gateway: Optional[str] = None
    control_plane_vlan: Optional[str] = None
    control_plane_dns: Optional[str] = None
    control_plane_binding_port: Optional[str] = None

    user_plane_ip_type: Optional[str] = None
    user_plane_address: Optional[str] = None
    user_plane_submask: Optional[str] = None
    user_plane_gateway: Optional[str] = None
    user_plane_vlan: Optional[str] = None
    user_plane_dns: Optional[str] = None
    user_plane_binding_port: Optional[str] = None

    x2_ip_type: Optional[str] = None
    x2_address: Optional[str] = None
    x2_submask: Optional[str] = None
    x2_gateway: Optional[str] = None
    x2_vlan: Optional[str] = None
    x2_dns: Optional[str] = None
    x2_binding_port: Optional[str] = None

    xn_ip_type: Optional[str] = None
    xn_address: Optional[str] = None
    xn_submask: Optional[str] = None
    xn_gateway: Optional[str] = None
    xn_vlan: Optional[str] = None
    xn_dns: Optional[str] = None
    xn_binding_port: Optional[str] = None

    mme_ip_1: Optional[str] = None
    mme_ip_2: Optional[str] = None
    mme_ip_3: Optional[str] = None
    mme_ip_4: Optional[str] = None
    mme_ip_5: Optional[str] = None
    mme_ip_6: Optional[str] = None
    mme_ip_7: Optional[str] = None
    mme_ip_8: Optional[str] = None

    @validator('rat')
    def validate_rat(cls, v):
        if v is not None and v not in ['LTE', 'NR']:
            raise ValueError('rat must be either LTE or NR')
        return v

    @validator('pci')
    def validate_pci(cls, v):
        if v is not None and (v < 0 or v > 503):
            raise ValueError('PCI must be between 0 and 503')
        return v
