import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SiteProgressSnapshot(Base):
    __tablename__ = "site_progress_snapshots"

    site_id = Column(Integer, ForeignKey("sites.id"), primary_key=True)
    install_started_at = Column(DateTime)
    install_completed_at = Column(DateTime)
    online_at = Column(DateTime)
    activated_at = Column(DateTime)
    online_at_device_fact = Column(DateTime)
    activated_at_device_fact = Column(DateTime)
    ssv_at = Column(DateTime)
    current_opening_stage = Column(String(50), default="survey_pending", nullable=False)
    snapshot_version = Column(Integer, default=1, server_default="1", nullable=False)
    last_rebuilt_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_rebuild_reason = Column(String(100))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    site = relationship("Site", foreign_keys=[site_id])


class SiteProgressEvent(Base):
    __tablename__ = "site_progress_events"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    milestone_code = Column(String(50), nullable=False, index=True)
    event_type = Column(String(20), nullable=False, index=True)
    effective_at = Column(DateTime)
    previous_effective_at = Column(DateTime)
    source_type = Column(String(50))
    source_id = Column(String(64))
    reason = Column(Text)
    operator_id = Column(Integer, ForeignKey("users.id"))
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    site = relationship("Site", foreign_keys=[site_id])
    operator = relationship("User", foreign_keys=[operator_id])
