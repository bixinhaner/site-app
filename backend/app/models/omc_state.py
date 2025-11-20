from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class OmcDeviceState(Base):
    """
    OMC 设备状态快照表（按 SN 聚合）

    - 记录最近一次从 OMC 观测到的在线/激活状态（raw）
    - 记录历史里程碑状态：是否曾经在线 / 曾经激活（只升不降）
    """

    __tablename__ = 'omc_device_states'

    # 主键：设备 SN（与 OMC 上报保持一致）
    sn = Column(String(100), primary_key=True, index=True)

    # 最近一次从 OMC 观测到的原始状态（允许回退）
    omc_online_raw = Column(Boolean, nullable=True)
    omc_active_raw = Column(Boolean, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_source = Column(String(32), nullable=True)  # api_poll / omc_push / inventory_ftp 等
    last_status_payload = Column(JSON, nullable=True)

    # 业务里程碑状态（只升不降）
    ever_online = Column(Boolean, default=False)
    ever_activated = Column(Boolean, default=False)
    first_online_at = Column(DateTime, nullable=True)
    first_activated_at = Column(DateTime, nullable=True)

    # 审计字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

