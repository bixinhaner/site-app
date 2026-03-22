from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SiteMilestoneRecord(Base):
    __tablename__ = "site_milestone_records"

    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    milestone_code = Column(String(50), nullable=False, index=True)
    approved_at = Column(DateTime, nullable=False)
    remark = Column(Text)
    proof_files = Column(JSON, nullable=False, default=list)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    site = relationship("Site", foreign_keys=[site_id])
    operator = relationship("User", foreign_keys=[operator_id])
