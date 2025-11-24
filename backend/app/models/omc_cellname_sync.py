from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.sql import func
from app.core.database import Base


class OmcCellNameSync(Base):
    __tablename__ = "omc_cellname_sync"

    sn = Column(String(100), primary_key=True, index=True)
    cell_name = Column(String(200))
    synced_at = Column(DateTime, server_default=func.now())
    status = Column(String(20))  # success | failed
    message = Column(Text)
    site_id = Column(Integer, nullable=True)
    work_order_id = Column(String(32), nullable=True)
