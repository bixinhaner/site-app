from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class IssueDraftStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    PENDING_CONFIRM = "pending_confirm"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELED = "canceled"


class IssueDraftSerialStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class IssueDraft(Base):
    __tablename__ = "issue_drafts"

    id = Column(String(32), primary_key=True)
    draft_no = Column(String(50), unique=True, index=True, nullable=False)

    request_id = Column(String(32), ForeignKey("material_requests.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(
        Enum(
            IssueDraftStatusEnum,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="issuedraftstatusenum",
        ),
        default=IssueDraftStatusEnum.DRAFT,
        nullable=False,
        index=True,
    )

    submitted_at = Column(DateTime)
    confirmed_by = Column(Integer, ForeignKey("users.id"))
    confirmed_at = Column(DateTime)
    reject_reason = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    request = relationship("MaterialRequest", back_populates="issue_drafts")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    requester = relationship("User", foreign_keys=[requester_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])
    items = relationship("IssueDraftItem", back_populates="draft", cascade="all, delete-orphan")
    serials = relationship("IssueDraftSerial", back_populates="draft", cascade="all, delete-orphan")


class IssueDraftItem(Base):
    __tablename__ = "issue_draft_items"
    __table_args__ = (UniqueConstraint("draft_id", "equipment_id", name="uq_issue_draft_item_draft_equipment"),)

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(String(32), ForeignKey("issue_drafts.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)

    planned_qty = Column(Integer, default=0)
    confirmed_qty = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    draft = relationship("IssueDraft", back_populates="items")
    equipment = relationship("Equipment")


class IssueDraftSerial(Base):
    __tablename__ = "issue_draft_serials"
    __table_args__ = (UniqueConstraint("draft_id", "serial_number", name="uq_issue_draft_serial_draft_sn"),)

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(String(32), ForeignKey("issue_drafts.id"), nullable=False, index=True)
    equipment_instance_id = Column(String(32), ForeignKey("equipment_instances.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    serial_number = Column(String(100), nullable=False, index=True)

    status = Column(
        Enum(
            IssueDraftSerialStatusEnum,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            name="issuedraftserialstatusenum",
        ),
        default=IssueDraftSerialStatusEnum.PENDING,
        nullable=False,
        index=True,
    )

    scanned_by = Column(Integer, ForeignKey("users.id"))
    scanned_at = Column(DateTime)

    confirmed_transaction_id = Column(String(36), index=True)
    confirmed_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())

    draft = relationship("IssueDraft", back_populates="serials")
    equipment_instance = relationship("EquipmentInstance")
    equipment = relationship("Equipment")
    scanner = relationship("User", foreign_keys=[scanned_by])

