from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.equipment_binding_history import EquipmentBindingHistory
from app.models.inspection import SiteInspection
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.omc_state import upsert_omc_device_state
from app.services.site_progress_service import rebuild_site_progress_for_sites


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
    - 仅将 online/active 写入 OmcDeviceState，并刷新站点生命周期快照；
      不直接推进工单或站点业务状态。
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

    affected_site_ids = [
        int(site_id)
        for site_id, in (
            db.query(EquipmentBindingHistory.site_id)
            .join(SiteInspection, SiteInspection.id == EquipmentBindingHistory.inspection_id)
            .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
            .filter(
                EquipmentBindingHistory.equipment_sn == sn,
                WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
                WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            )
            .distinct()
            .all()
        )
    ]
    if affected_site_ids:
        rebuild_site_progress_for_sites(
            db,
            affected_site_ids,
            reason="omc_status_callback",
            force=True,
        )
    db.commit()
