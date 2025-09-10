from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    site_code = Column(String(50), unique=True, index=True, nullable=False)
    site_name = Column(String(100), nullable=False)
    site_type = Column(String(50))  # base_station, tower, indoor, etc.
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    province = Column(String(50))
    city = Column(String(50))
    district = Column(String(50))
    status = Column(String(20), default="planning")  # planning, construction, operational, maintenance
    priority = Column(String(20), default="normal")  # high, normal, low
    description = Column(Text)
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])