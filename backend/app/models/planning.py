from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON, Float
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

