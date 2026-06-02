from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SiteGroupCategory(Base):
    __tablename__ = "site_group_categories"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)
    assignment_mode = Column(String(20), default="manual", nullable=False, index=True)
    source_type = Column(String(50))
    source_field = Column(String(80))
    source_config = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    options = relationship(
        "SiteGroupOption",
        back_populates="category",
        order_by="SiteGroupOption.sort_order.asc(), SiteGroupOption.id.asc()",
    )
    assignments = relationship("SiteGroupAssignment", back_populates="category")
    creator = relationship("User", foreign_keys=[created_by])


class SiteGroupOption(Base):
    __tablename__ = "site_group_options"
    __table_args__ = (
        UniqueConstraint("category_id", "code", name="uq_site_group_options_category_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("site_group_categories.id"), nullable=False, index=True)
    code = Column(String(80), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20))
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    category = relationship("SiteGroupCategory", back_populates="options")
    assignments = relationship("SiteGroupAssignment", back_populates="option")


class SiteGroupAssignment(Base):
    __tablename__ = "site_group_assignments"
    __table_args__ = (
        UniqueConstraint("site_id", "category_id", name="uq_site_group_assignments_site_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("site_group_categories.id"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey("site_group_options.id"), nullable=False, index=True)
    source = Column(String(50), default="manual", nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    site = relationship("Site", back_populates="group_assignments", foreign_keys=[site_id])
    category = relationship("SiteGroupCategory", back_populates="assignments")
    option = relationship("SiteGroupOption", back_populates="assignments")
    operator = relationship("User", foreign_keys=[updated_by])
