from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SitePlanning(Base):
    __tablename__ = "site_planning"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    # Overall planning info
    bands = Column(JSON)  # list of strings, e.g., ["n41", "n78"]
    sector_count = Column(Integer, default=0)
    notes = Column(String(500))
    is_current = Column(Boolean, default=True, index=True)

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    site = relationship("Site")
    creator = relationship("User")
    sectors = relationship("SitePlanningSector", back_populates="planning", cascade="all, delete-orphan")
    antenna_ports = relationship("SiteAntennaPort", back_populates="planning", cascade="all, delete-orphan")
    switch_ports = relationship("SiteSwitchPort", back_populates="planning", cascade="all, delete-orphan")


class SitePlanningSector(Base):
    __tablename__ = "site_planning_sectors"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("site_planning.id"), nullable=False, index=True)
    sector_index = Column(Integer, nullable=False)  # 1..N
    azimuth_deg = Column(Float)  # 0-360
    downtilt_deg = Column(Float)  # 0-30
    bands = Column(JSON)  # list of strings

    created_at = Column(DateTime, server_default=func.now())

    planning = relationship("SitePlanning", back_populates="sectors")


class SiteAntennaPort(Base):
    __tablename__ = "site_antenna_ports"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("site_planning.id"), nullable=False, index=True)
    port_label = Column(String(50), nullable=False)  # e.g., ANT1
    sector_index = Column(Integer, nullable=False)
    band = Column(String(20))
    mimo_chain = Column(String(20))  # e.g., 4x4
    remarks = Column(String(200))

    created_at = Column(DateTime, server_default=func.now())

    planning = relationship("SitePlanning", back_populates="antenna_ports")


class SiteSwitchPort(Base):
    __tablename__ = "site_switch_ports"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("site_planning.id"), nullable=False, index=True)
    port_no = Column(String(50), nullable=False)
    vlan_ids = Column(JSON)  # list of ints
    is_uplink = Column(Boolean, default=False)
    poe = Column(Boolean, default=False)
    description = Column(String(200))

    created_at = Column(DateTime, server_default=func.now())

    planning = relationship("SitePlanning", back_populates="switch_ports")


class SitePlanningCell(Base):
    """
    LLD 规划导入产生的 Cell 级明细表
    按规划版本 + 站点 + RAT/Band 存储 4G/5G 的每一条小区配置
    """

    __tablename__ = "site_planning_cells"

    id = Column(Integer, primary_key=True, index=True)
    planning_id = Column(Integer, ForeignKey("site_planning.id"), nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)

    # 识别信息
    rat = Column(String(8))  # LTE / NR
    band_code = Column(String(20))  # 归一化 Band，如 B28/B40/B3/N41
    sheet_name = Column(String(50))

    tower_id = Column(String(50), index=True)  # Excel 中的 TOWER ID，用作 SITE ID
    site_information = Column(String(100))
    site_name = Column(String(200))

    local_cell_id = Column(Integer)  # LOCAL CELL ID
    cell_name = Column(String(200))

    # 通用/4G 字段
    enb_id = Column(Integer)
    eci = Column(Integer)
    plmn = Column(String(20))
    tac = Column(String(20))
    pci = Column(Integer)
    zc_root_index = Column(Integer)

    longitude = Column(Float)
    latitude = Column(Float)

    power_dbm = Column(Float)  # 功率 / 功率（dbm）
    pa = Column(String(10))
    pb = Column(String(10))

    cover_type = Column(String(50))
    band_in_file = Column(String(20))  # Excel BAND 列原始值
    frequency = Column(Integer)
    bandwidth = Column(String(20))  # 带宽 / Bandwidth

    mechanical_downtilt_deg = Column(Float)
    electrical_downtilt_deg = Column(Float)
    azimuth_deg = Column(Float)

    tower_height = Column(Float)
    antenna_height = Column(Float)
    tower_merchants = Column(String(50))

    band_combination = Column(String(100))
    antenna_ports = Column(Integer)
    cell_allocation = Column(String(50))

    tower_name = Column(String(100))
    town = Column(String(50))
    region = Column(String(50))
    coverage_area = Column(String(100))
    coverage_weight = Column(String(20))
    scenario = Column(String(100))
    scenario_weight = Column(String(20))
    weight = Column(String(20))
    remark = Column(Text)

    # 5G 专有字段（主要来自 N41）
    gnb_id = Column(Integer)
    gnb_length = Column(Integer)
    nci = Column(Integer)

    gnb_wan_ip = Column(String(50))
    master_5gc_ip1 = Column(String(50))
    master_5gc_ip2 = Column(String(50))
    master_5gc_ip3 = Column(String(50))
    backup_5gc_ip1 = Column(String(50))
    backup_5gc_ip2 = Column(String(50))
    backup_5gc_ip3 = Column(String(50))

    master_omc_ip = Column(String(50))
    backup_omc_ip = Column(String(50))

    ntp_ip1 = Column(String(50))
    ntp_ip2 = Column(String(50))

    kssb = Column(Float)
    offset_to_point_a = Column(String(20))
    slot_config = Column(String(20))
    slot_config_dl_ul = Column(String(20))
    symbol_config_dl_ul = Column(String(20))

    extra_params = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())


class PlanningChangeLog(Base):
    __tablename__ = "planning_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    planning_id = Column(Integer, ForeignKey("site_planning.id"), nullable=True)
    operation = Column(String(20), nullable=False)  # create|import|update|restore|delete
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    summary = Column(String(500))
    before_snapshot = Column(JSON)
    after_snapshot = Column(JSON)
    diff = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    site = relationship("Site")
    planning = relationship("SitePlanning")
    actor = relationship("User")
