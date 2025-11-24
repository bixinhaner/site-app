"""
Mock OMC 测试桩
- 提供与现网 OMC 相同的关键接口：获取 Token、查询设备状态
- 额外提供 /admin 管理接口用于前端手工配置 SN 在线/激活状态
- 独立运行，不与业务代码耦合。
运行示例：
  uvicorn main:app --reload --port 9000
"""
import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

DB_PATH = os.path.join(os.path.dirname(__file__), "mock_omc.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Device(Base):
    __tablename__ = "devices"
    sn = Column(String(64), primary_key=True)
    online = Column(Boolean, default=False)
    activated = Column(Boolean, default=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mock OMC Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============== 数据模型 ==============
class DeviceCreate(BaseModel):
    sn: str
    online: bool = False
    activated: bool = False
    description: Optional[str] = None


class DeviceUpdate(BaseModel):
    online: Optional[bool] = None
    activated: Optional[bool] = None
    description: Optional[str] = None


class DeviceOut(BaseModel):
    sn: str
    online: bool
    activated: bool
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ============== 管理接口（系统配置页面使用） ==============
@app.get("/admin/devices", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.sn.asc()).all()


@app.post("/admin/devices", response_model=DeviceOut)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    if db.query(Device).filter(Device.sn == payload.sn).first():
        raise HTTPException(status_code=400, detail="SN 已存在")
    dev = Device(
        sn=payload.sn,
        online=payload.online,
        activated=payload.activated,
        description=payload.description,
        updated_at=datetime.utcnow(),
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


@app.put("/admin/devices/{sn}", response_model=DeviceOut)
def update_device(sn: str, payload: DeviceUpdate, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.sn == sn).first()
    if not dev:
        raise HTTPException(status_code=404, detail="SN 不存在")
    if payload.online is not None:
        dev.online = payload.online
    if payload.activated is not None:
        dev.activated = payload.activated
    if payload.description is not None:
        dev.description = payload.description
    dev.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dev)
    return dev


@app.delete("/admin/devices/{sn}")
def delete_device(sn: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.sn == sn).first()
    if not dev:
        raise HTTPException(status_code=404, detail="SN 不存在")
    db.delete(dev)
    db.commit()
    return {"message": "deleted"}


@app.post("/admin/devices/{sn}/state", response_model=DeviceOut)
def set_state(sn: str, payload: DeviceUpdate = Body(...), db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.sn == sn).first()
    if not dev:
        raise HTTPException(status_code=404, detail="SN 不存在")
    if payload.online is not None:
        dev.online = payload.online
    if payload.activated is not None:
        dev.activated = payload.activated
    if payload.description is not None:
        dev.description = payload.description
    dev.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dev)
    return dev


@app.post("/admin/reset")
def reset_all(db: Session = Depends(get_db)):
    db.query(Device).delete()
    db.commit()
    return {"message": "reset"}


# ============== OMC 公开接口（被业务代码调用） ==============
@app.post("/northboundApi/v1/access/token")
def get_token():
    return {"code": 0, "data": {"token": "mock-token"}}


@app.get("/northboundApi/v1/enodeb/infos/status/{sn}")
def get_status(sn: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.sn == sn).first()
    if not dev:
        raise HTTPException(status_code=404, detail="SN 未找到")
    data = {
        "connectionStatus": "on" if dev.online else "off",
        # cellStatus 约定首位 1 表示已激活
        "cellStatus": "1,0" if dev.activated else "0,0",
        "sn": dev.sn,
        "updated_at": (dev.updated_at or datetime.utcnow()).isoformat(),
    }
    return {"code": 0, "data": data}


@app.get("/")
def root():
    return {"message": "Mock OMC is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
