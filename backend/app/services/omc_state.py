from datetime import datetime
from typing import Optional, Dict, List

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.omc_state import OmcDeviceState
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum


def upsert_omc_device_state(
    db: Session,
    sn: str,
    online_raw: Optional[bool],
    activated_raw: Optional[bool],
    source: str,
    status_payload: Optional[Dict] = None,
) -> OmcDeviceState:
    """
    将一次 OMC 观测写入 OmcDeviceState（SN 级聚合）:

    - 更新最近一次观测的原始状态（允许回退）
    - 推进里程碑状态 ever_online / ever_activated（只升不降）
    """
    sn = (sn or "").strip()
    if not sn:
        raise ValueError("sn is required")

    now = datetime.utcnow()

    state: Optional[OmcDeviceState] = (
        db.query(OmcDeviceState).filter(OmcDeviceState.sn == sn).first()
    )
    if not state:
        state = OmcDeviceState(sn=sn)
        db.add(state)

    # 原始视图（允许回退）
    state.last_source = source
    state.last_seen_at = now
    if status_payload is not None:
        state.last_status_payload = status_payload

    if online_raw is not None:
        state.omc_online_raw = bool(online_raw)
        # 里程碑：曾经在线
        if online_raw and not state.ever_online:
            state.ever_online = True
            if not state.first_online_at:
                state.first_online_at = now

    if activated_raw is not None:
        state.omc_active_raw = bool(activated_raw)
        # 里程碑：曾经激活
        if activated_raw and not state.ever_activated:
            state.ever_activated = True
            if not state.first_activated_at:
                state.first_activated_at = now

    return state


def get_device_state_by_sn(db: Session, sn: str) -> Optional[OmcDeviceState]:
    """
    按 SN 查询聚合后的设备状态（若不存在则返回 None）。
    """
    sn = (sn or "").strip()
    if not sn:
        return None
    return db.query(OmcDeviceState).filter(OmcDeviceState.sn == sn).first()


def get_bound_sns_for_site(db: Session, site_id: int) -> List[str]:
    """
    基于设备绑定历史推导当前站点绑定的设备 SN 列表。

    规则与 OMC 相关逻辑保持一致：
    - 同一 SN 取最新一条记录
    - 若 action != UNBIND 则视为仍然绑定
    """
    subq = (
        db.query(
            EquipmentBindingHistory.equipment_sn.label("sn"),
            func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
        )
        .filter(EquipmentBindingHistory.site_id == site_id)
        .group_by(EquipmentBindingHistory.equipment_sn)
        .subquery()
    )

    latest_rows: List[EquipmentBindingHistory] = (
        db.query(EquipmentBindingHistory)
        .join(
            subq,
            and_(
                EquipmentBindingHistory.equipment_sn == subq.c.sn,
                EquipmentBindingHistory.operated_at == subq.c.latest_at,
            ),
        )
        .all()
    )

    sns: List[str] = []
    for row in latest_rows:
        if row.action != BindingActionEnum.UNBIND and row.equipment_sn:
            sns.append(row.equipment_sn)
    return sns


def summarize_site_omc_state(db: Session, site_id: int) -> Dict:
    """
    基于 SN 聚合表对站点设备状态做“ever”汇总。

    返回示例:
    {
      "site_id": 1,
      "sns": [...],
      "all_ever_online": bool,
      "all_ever_activated": bool,
      "devices": [
        {
          "sn": "...",
          "ever_online": bool,
          "ever_activated": bool,
          "omc_online_raw": bool | None,
          "omc_active_raw": bool | None,
          "last_seen_at": iso-str | None,
        },
        ...
      ],
    }
    """
    sns = get_bound_sns_for_site(db, site_id)
    devices: List[Dict] = []

    if not sns:
        return {
            "site_id": site_id,
            "sns": [],
            "all_ever_online": False,
            "all_ever_activated": False,
            "devices": [],
        }

    all_ever_online = True
    all_ever_activated = True

    for sn in sns:
        state = get_device_state_by_sn(db, sn)

        ever_online = bool(state.ever_online) if state else False
        ever_activated = bool(state.ever_activated) if state else False
        omc_online_raw = state.omc_online_raw if state else None
        omc_active_raw = state.omc_active_raw if state else None
        last_seen_at_str = (
            state.last_seen_at.isoformat() if state and state.last_seen_at else None
        )

        devices.append(
            {
                "sn": sn,
                "ever_online": ever_online,
                "ever_activated": ever_activated,
                "omc_online_raw": omc_online_raw,
                "omc_active_raw": omc_active_raw,
                "last_seen_at": last_seen_at_str,
            }
        )

        if not ever_online:
            all_ever_online = False
        if not ever_activated:
            all_ever_activated = False

    return {
        "site_id": site_id,
        "sns": sns,
        "all_ever_online": all_ever_online,
        "all_ever_activated": all_ever_activated,
        "devices": devices,
    }

