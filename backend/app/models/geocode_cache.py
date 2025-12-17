from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    # 组合主键，便于支持未来扩展不同 provider
    provider = Column(String(32), primary_key=True)
    coord_key = Column(String(64), primary_key=True)  # 归一化后的坐标 key（如 round4）

    coordtype = Column(String(20), nullable=False, default="wgs84ll")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    address = Column(Text)
    sematic_description = Column(Text)

    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime)

    payload = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
