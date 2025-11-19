from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class SystemConfig(Base):
  """
  系统级配置表

  目前用于存储 OMC API 配置等全局设置，采用 key-value 形式，value 为 JSON。
  """

  __tablename__ = "system_config"

  key = Column(String(50), primary_key=True, index=True)
  value = Column(JSON, nullable=True)
  updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

