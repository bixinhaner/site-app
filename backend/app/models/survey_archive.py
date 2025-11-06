from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SiteSurveyArchive(Base):
    """勘察档案（当前版本快照）"""
    __tablename__ = "site_survey_archives"

    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), index=True, nullable=False)
    work_order_id = Column(String(32), ForeignKey("work_orders.id"), index=True, nullable=False)
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), index=True, nullable=False)
    template_id = Column(String(32), ForeignKey("inspection_templates.id"), index=True, nullable=False)
    template_version = Column(String(20))

    # 当前版本号与内容（完整JSON）
    current_version = Column(Integer, default=1)
    content = Column(JSON, nullable=False)

    # 状态与系统字段
    status = Column(String(20), default="active")  # active|archived
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    site = relationship("Site")
    work_order = relationship("WorkOrder")
    inspection = relationship("SiteInspection")
    template = relationship("InspectionTemplate")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    versions = relationship("SiteSurveyArchiveVersion", back_populates="archive", cascade="all, delete-orphan")


class SiteSurveyArchiveVersion(Base):
    """档案版本历史（追加写）"""
    __tablename__ = "site_survey_archive_versions"

    id = Column(String(32), primary_key=True)
    archive_id = Column(String(32), ForeignKey("site_survey_archives.id"), index=True, nullable=False)
    version = Column(Integer, index=True, nullable=False)

    content = Column(JSON, nullable=False)  # 完整快照
    diff = Column(JSON)                     # JSON Patch（相对于上一个版本）
    change_summary = Column(Text)

    changed_by = Column(Integer, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())

    archive = relationship("SiteSurveyArchive", back_populates="versions")
    changer = relationship("User", foreign_keys=[changed_by])


class SiteSurveyArchiveKVIndex(Base):
    """档案KV索引（便于任意字段检索/统计）"""
    __tablename__ = "site_survey_archive_kv_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String(32), ForeignKey("site_survey_archives.id"), index=True, nullable=False)
    version = Column(Integer, index=True, nullable=False)
    path = Column(String(200), index=True, nullable=False)  # 例如 "catA.itemX.fieldY"
    field_label = Column(String(200))
    type = Column(String(20))  # number|bool|string|datetime|json

    value_number = Column(Float)
    value_bool = Column(Boolean)
    value_string = Column(Text)
    value_datetime = Column(DateTime)
    raw_json = Column(JSON)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

