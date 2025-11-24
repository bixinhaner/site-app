from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SiteSSVArchive(Base):
    __tablename__ = "site_ssv_archives"

    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), index=True, nullable=False)
    work_order_id = Column(String(32), ForeignKey("work_orders.id"), index=True, nullable=False)
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), index=True, nullable=False)
    template_id = Column(String(32), ForeignKey("inspection_templates.id"), index=True, nullable=False)
    template_version = Column(String(20))

    current_version = Column(Integer, default=1)
    content = Column(JSON, nullable=False)

    status = Column(String(20), default="active")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    site = relationship("Site")
    work_order = relationship("WorkOrder")
    inspection = relationship("SiteInspection")
    template = relationship("InspectionTemplate")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    versions = relationship("SiteSSVArchiveVersion", back_populates="archive", cascade="all, delete-orphan")


class SiteSSVArchiveVersion(Base):
    __tablename__ = "site_ssv_archive_versions"

    id = Column(String(32), primary_key=True)
    archive_id = Column(String(32), ForeignKey("site_ssv_archives.id"), index=True, nullable=False)
    version = Column(Integer, index=True, nullable=False)
    content = Column(JSON, nullable=False)
    diff = Column(JSON)
    change_summary = Column(Text)
    changed_by = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())

    archive = relationship("SiteSSVArchive", back_populates="versions")
    changer = relationship("User", foreign_keys=[changed_by])


class SiteSSVArchiveKVIndex(Base):
    __tablename__ = "site_ssv_archive_kv_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(32), ForeignKey("site_ssv_archives.id"), index=True, nullable=False)
    version = Column(Integer, index=True, nullable=False)
    path = Column(String(200), index=True, nullable=False)
    field_label = Column(String(200))
    type = Column(String(20))

    value_number = Column(Float)
    value_bool = Column(Boolean)
    value_string = Column(Text)
    value_datetime = Column(DateTime)
    raw_json = Column(JSON)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
