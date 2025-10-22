"""设备绑定历史记录模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class BindingActionEnum(str, enum.Enum):
    """绑定操作类型"""
    BIND = "bind"        # 绑定
    UNBIND = "unbind"    # 解绑
    REBIND = "rebind"    # 重新绑定


class EquipmentBindingHistory(Base):
    """设备绑定历史表"""
    __tablename__ = "equipment_binding_history"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), nullable=False)
    check_item_id = Column(String(32), ForeignKey("inspection_check_items.id"), nullable=False)
    
    # 站点和小区信息
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    sector_id = Column(String(10), nullable=False)  # 扇区编号
    band = Column(String(20), nullable=False)       # 频段
    cell_id = Column(String(20), nullable=False)    # 小区ID
    
    # 设备信息
    equipment_sn = Column(String(100), nullable=False, index=True)  # 设备序列号
    equipment_type = Column(String(50))  # 设备类型（如：RRU, BBU等）
    equipment_model = Column(String(100))  # 设备型号
    
    # 操作信息
    action = Column(Enum(BindingActionEnum), nullable=False, default=BindingActionEnum.BIND)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operated_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # 额外信息
    previous_equipment_sn = Column(String(100))  # 如果是重新绑定，记录之前的设备SN
    notes = Column(Text)  # 备注说明
    
    # GPS信息（操作时的位置）
    latitude = Column(String(50))
    longitude = Column(String(50))
    gps_accuracy = Column(String(50))
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    inspection = relationship("SiteInspection", foreign_keys=[inspection_id])
    check_item = relationship("InspectionCheckItem", foreign_keys=[check_item_id])
    site = relationship("Site", foreign_keys=[site_id])
    operator = relationship("User", foreign_keys=[operator_id])
