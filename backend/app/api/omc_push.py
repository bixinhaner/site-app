from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.omc_state import upsert_omc_device_state


router = APIRouter()


class OmcPushStatusPayload(BaseModel):
    """
    OMC 主动上报告的设备状态结构（占位定义）。

    - sn: ENB 序列号
    - online: "1" 表示打开，"0" 表示关闭
    - active: "1" 表示激活，"0" 表示去激活
    - reported_at: 可选的 OMC 报告时间
    """

    sn: str
    online: str
    active: str
    reported_at: Optional[datetime] = None


@router.post("/devices/status-callback", status_code=204)
async def omc_status_callback(
    payload: OmcPushStatusPayload,
    db: Session = Depends(get_db),
):
    """
    OMC 主动上报告的设备状态回调接口（占位实现）。

    说明:
    - 当前不做鉴权和签名校验，后续接入真实 OMC 时再补充。
    - 仅将 online/active 写入 OmcDeviceState，不影响现有业务流程。
    """
    sn = (payload.sn or "").strip()
    if not sn:
        # 无效 SN，直接忽略
        return

    online_raw = payload.online.strip() == "1"
    activated_raw = payload.active.strip() == "1"

    upsert_omc_device_state(
        db=db,
        sn=sn,
        online_raw=online_raw,
        activated_raw=activated_raw,
        source="omc_push",
        status_payload=payload.dict(),
    )
    db.commit()

