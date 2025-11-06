from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SiteSurvey(Base):
    __tablename__ = "site_surveys"

    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)

    # Basic
    survey_date = Column(DateTime, nullable=False)
    surveyor_name = Column(String(100), nullable=False)
    surveyor_phone = Column(String(30))

    # Geo
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(Text)
    gps_accuracy = Column(Float)

    # Site/Structure
    site_type = Column(String(50))
    tower_type = Column(String(50))
    available_height_m = Column(Float)
    load_capacity_kg = Column(Float)

    # Power/Earthing
    power_available = Column(Boolean)
    power_distance_m = Column(Float)
    power_capacity_kw = Column(Float)
    earthing_feasible = Column(Boolean)

    # Transmission
    fiber_available = Column(Boolean)
    fiber_distance_m = Column(Float)
    duct_notes = Column(Text)
    microwave_los = Column(Boolean)
    los_azimuth_deg = Column(Float)
    los_distance_km = Column(Float)

    # Environment/Compliance
    sensitive_points = Column(Text)
    safety_notes = Column(Text)
    permits_constraints = Column(Text)

    # Owner/Access
    owner_name = Column(String(100))
    owner_phone = Column(String(30))
    access_time_window = Column(String(100))
    entry_constraints = Column(Text)

    # Conclusion
    feasibility = Column(String(30))  # feasible | conditional | infeasible
    risks = Column(Text)
    recommendations = Column(Text)

    # Meta
    extra_data = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    work_order_id = Column(String(32), ForeignKey("work_orders.id"))

    # Relationships
    site = relationship("Site")
    creator = relationship("User", foreign_keys=[created_by])
    photos = relationship(
        "SiteSurveyPhoto",
        back_populates="survey",
        cascade="all, delete-orphan",
    )


class SiteSurveyPhoto(Base):
    __tablename__ = "site_survey_photos"

    id = Column(String(32), primary_key=True)
    survey_id = Column(String(32), ForeignKey("site_surveys.id"), nullable=False, index=True)

    # File
    original_name = Column(String(255))
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    category = Column(String(50))  # overview|power|room|duct|roof|hazard|custom

    # Ordering and raw EXIF metadata for advanced operations
    sort_order = Column(Integer)
    exif = Column(JSON)

    # EXIF/GPS
    latitude = Column(Float)
    longitude = Column(Float)
    gps_accuracy = Column(Float)
    address = Column(Text)
    taken_at = Column(DateTime)

    # Integrity/Watermark
    has_watermark = Column(Boolean, default=False)
    watermark_data = Column(JSON)
    hash_value = Column(String(64))

    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    survey = relationship("SiteSurvey", back_populates="photos")
    uploader = relationship("User", foreign_keys=[uploaded_by])
