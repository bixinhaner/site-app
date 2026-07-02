from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserSubcontractorAssignment(Base):
    __tablename__ = "user_subcontractor_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_subcontractor_assignments_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey("site_group_options.id"), nullable=False, index=True)
    is_primary = Column(Boolean, default=True, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="subcontractor_assignment")
    option = relationship("SiteGroupOption", foreign_keys=[option_id])
    operator = relationship("User", foreign_keys=[updated_by])
