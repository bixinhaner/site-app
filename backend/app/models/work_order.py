from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class WorkOrderStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUBMITTED = "SUBMITTED"     # 已提交待审核
    UNDER_REVIEW = "UNDER_REVIEW"  # 审核中
    APPROVED = "APPROVED"       # 审核通过
    ACTIVATED = "ACTIVATED"     # 已开通
    REJECTED = "REJECTED"       # 审核驳回
    COMPLETED = "COMPLETED"


class WorkOrderPriorityEnum(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkOrderTypeEnum(str, enum.Enum):
    OPENING_INSPECTION = "opening_inspection"
    SSV = "ssv"
    MAINTENANCE = "maintenance"
    POWER_ISSUE = "power_issue"
    TRANSMISSION_ISSUE = "transmission_issue"
    GPS_ISSUE = "gps_issue"
    SIGNAL_ISSUE = "signal_issue"
    SITE_SURVEY = "site_survey"


class ItemStatusEnum(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # 关联检查实例
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), nullable=True)

    # 基本信息
    title = Column(String(200), nullable=False)
    type = Column(Enum(WorkOrderTypeEnum), nullable=False)
    description = Column(Text)
    priority = Column(Enum(WorkOrderPriorityEnum), default=WorkOrderPriorityEnum.NORMAL)

    # 分配信息
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 审核信息
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comments = Column(Text)
    review_comments_i18n = Column(JSON)

    # 状态
    status = Column(Enum(WorkOrderStatusEnum), default=WorkOrderStatusEnum.PENDING)

    # 时间
    assigned_at = Column(DateTime, server_default=func.now())
    accepted_at = Column(DateTime)
    submitted_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    activated_at = Column(DateTime)
    completed_at = Column(DateTime)
    due_date = Column(DateTime)

    # 扩展信息 (JSON格式存储其他配置)
    extra_data = Column(JSON, default={})

    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    site = relationship("Site")
    assigner = relationship("User", foreign_keys=[assigned_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    inspection = relationship("SiteInspection", foreign_keys=[inspection_id])
    inspections = relationship("SiteInspection", foreign_keys="SiteInspection.work_order_id", back_populates="work_order")
    items = relationship("WorkOrderItem", back_populates="work_order")


class WorkOrderItem(Base):
    __tablename__ = "work_order_items"

    id = Column(String(32), primary_key=True)
    work_order_id = Column(String(32), ForeignKey("work_orders.id"), nullable=False)

    item_id = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    category_id = Column(String(50))
    category_name = Column(String(100))
    sector_id = Column(String(10))

    required_type = Column(String(20))  # photo, data, both
    status = Column(Enum(ItemStatusEnum), default=ItemStatusEnum.PENDING)

    data_value = Column(JSON)
    validation_result = Column(JSON)

    review_status = Column(String(20))  # pass, fail, warning
    review_comments = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    work_order = relationship("WorkOrder", back_populates="items")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(32), primary_key=True)
    resource_type = Column(String(50), nullable=False)  # work_order, item, photo
    resource_id = Column(String(32), nullable=False)

    action = Column(String(50), nullable=False)
    from_status = Column(String(20))
    to_status = Column(String(20))

    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operator_ip = Column(String(45))

    comments = Column(Text)
    details = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())

    operator = relationship("User")
