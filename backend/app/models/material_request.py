from __future__ import annotations

import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MaterialRequestStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    ABANDONED = "abandoned"
    REJECTED = "rejected"
    CANCELED = "canceled"
    CLOSED = "closed"


class MaterialRequest(Base):
    __tablename__ = "material_requests"

    id = Column(String(32), primary_key=True)
    request_no = Column(String(50), unique=True, index=True, nullable=False)

    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(
        Enum(
            MaterialRequestStatusEnum,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="materialrequeststatusenum",
        ),
        default=MaterialRequestStatusEnum.DRAFT,
        nullable=False,
        index=True,
    )

    notes = Column(Text)
    submitted_at = Column(DateTime)

    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approval_comments = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approved_by])
    items = relationship("MaterialRequestItem", back_populates="request", cascade="all, delete-orphan")
    issue_drafts = relationship("IssueDraft", back_populates="request")


class MaterialRequestItem(Base):
    __tablename__ = "material_request_items"
    __table_args__ = (
        UniqueConstraint("request_id", "equipment_id", name="uq_material_request_item_request_equipment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(32), ForeignKey("material_requests.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)

    requested_qty = Column(Integer, nullable=False)
    approved_qty = Column(Integer, default=0)
    issued_qty = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    request = relationship("MaterialRequest", back_populates="items")
    equipment = relationship("Equipment")
