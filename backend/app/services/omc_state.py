from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.inspection import SiteInspection
from app.models.omc_state import OmcDeviceState
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.cell_generator import CellGenerator
from app.utils.timezone import to_utc_iso


DeviceSlot = Tuple[str, str]


def _normalize_slot_value(value: Optional[str]) -> str:
    return str(value or "").strip()


def _normalize_device_slot(sector_id: Optional[str], band: Optional[str]) -> Optional[DeviceSlot]:
    normalized_sector_id = _normalize_slot_value(sector_id)
    normalized_band = _normalize_slot_value(band)
    if not normalized_sector_id or not normalized_band:
        return None
    return normalized_sector_id, normalized_band


def _slot_sort_key(slot: DeviceSlot) -> Tuple[int, int | str, str]:
    sector_id, band = slot
    if str(sector_id).isdigit():
        return (0, int(sector_id), band)
    return (1, str(sector_id), band)


def _serialize_slot(slot: DeviceSlot) -> Dict[str, str]:
    sector_id, band = slot
    return {
        "sector_id": sector_id,
        "band": band,
        "cell_id": f"{sector_id}_{band}",
    }


def upsert_omc_device_state(
    db: Session,
    sn: str,
    online_raw: Optional[bool],
    activated_raw: Optional[bool],
    source: str,
    status_payload: Optional[Dict] = None,
) -> tuple[OmcDeviceState, bool, bool]:
    """
    将一次 OMC 观测写入 OmcDeviceState（SN 级聚合）:

    - 更新最近一次观测的原始状态（允许回退）
    - 推进里程碑状态 ever_online / ever_activated（只升不降）
    """
    sn = (sn or "").strip()
    if not sn:
        raise ValueError("sn is required")

    now = datetime.utcnow()
    newly_online = False
    newly_activated = False

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
        # 里程碑：曾经在线（只升不降）
        if online_raw:
            if not state.ever_online:
                state.ever_online = True
            if not state.first_online_at:
                state.first_online_at = now
                newly_online = True

    if activated_raw is not None:
        state.omc_active_raw = bool(activated_raw)
        # 里程碑：曾经激活（只升不降）
        if activated_raw:
            if not state.ever_activated:
                state.ever_activated = True
            if not state.first_activated_at:
                state.first_activated_at = now
                newly_activated = True

    return state, newly_online, newly_activated


def get_device_state_by_sn(db: Session, sn: str) -> Optional[OmcDeviceState]:
    """
    按 SN 查询聚合后的设备状态（若不存在则返回 None）。
    """
    sn = (sn or "").strip()
    if not sn:
        return None
    return db.query(OmcDeviceState).filter(OmcDeviceState.sn == sn).first()


def get_expected_device_slots_for_site(db: Session, site_id: int) -> List[DeviceSlot]:
    planning = CellGenerator.get_site_planning(db, site_id)
    if not planning:
        return []

    slots = {
        slot
        for slot in (
            _normalize_device_slot(getattr(device, "sector_id", None), getattr(device, "band", None))
            for device in CellGenerator.generate_devices_from_planning(db, site_id)
        )
        if slot
    }
    return sorted(slots, key=_slot_sort_key)


def get_bound_slot_rows_for_site(
    db: Session,
    site_id: int,
    *,
    opening_only: bool = False,
) -> List[EquipmentBindingHistory]:
    latest_at_query = (
        db.query(
            EquipmentBindingHistory.sector_id.label("sector_id"),
            EquipmentBindingHistory.band.label("band"),
            func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
        )
        .filter(EquipmentBindingHistory.site_id == site_id)
    )
    latest_id_query = (
        db.query(
            EquipmentBindingHistory.sector_id.label("sector_id"),
            EquipmentBindingHistory.band.label("band"),
            func.max(EquipmentBindingHistory.id).label("latest_id"),
        )
        .filter(EquipmentBindingHistory.site_id == site_id)
    )

    if opening_only:
        latest_at_query = (
            latest_at_query
            .join(SiteInspection, SiteInspection.id == EquipmentBindingHistory.inspection_id)
            .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
            .filter(
                WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
                WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            )
        )
        latest_id_query = (
            latest_id_query
            .join(SiteInspection, SiteInspection.id == EquipmentBindingHistory.inspection_id)
            .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
            .filter(
                WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
                WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            )
        )

    latest_at_subq = (
        latest_at_query
        .group_by(
            EquipmentBindingHistory.sector_id,
            EquipmentBindingHistory.band,
        )
        .subquery()
    )

    latest_id_subq = (
        latest_id_query
        .join(
            latest_at_subq,
            and_(
                EquipmentBindingHistory.sector_id == latest_at_subq.c.sector_id,
                EquipmentBindingHistory.band == latest_at_subq.c.band,
                EquipmentBindingHistory.operated_at == latest_at_subq.c.latest_at,
            ),
        )
        .group_by(
            EquipmentBindingHistory.sector_id,
            EquipmentBindingHistory.band,
        )
        .subquery()
    )

    return (
        db.query(EquipmentBindingHistory)
        .join(latest_id_subq, EquipmentBindingHistory.id == latest_id_subq.c.latest_id)
        .order_by(
            EquipmentBindingHistory.sector_id.asc(),
            EquipmentBindingHistory.band.asc(),
            EquipmentBindingHistory.cell_id.asc(),
            EquipmentBindingHistory.id.asc(),
        )
        .all()
    )


def summarize_site_binding_slots(
    db: Session,
    site_id: int,
    *,
    opening_only: bool = False,
) -> Dict[str, Any]:
    expected_slots = get_expected_device_slots_for_site(db, site_id)

    all_bound_rows = [
        row for row in get_bound_slot_rows_for_site(db, site_id, opening_only=opening_only)
        if row.action != BindingActionEnum.UNBIND and str(row.equipment_sn or "").strip()
    ]

    all_slot_map = {
        slot: row
        for row in all_bound_rows
        for slot in [_normalize_device_slot(row.sector_id, row.band)]
        if slot
    }

    slot_check_required = bool(expected_slots)
    if slot_check_required:
        relevant_rows = [all_slot_map[slot] for slot in expected_slots if slot in all_slot_map]
        covered_slots = [slot for slot in expected_slots if slot in all_slot_map]
        missing_slots = [slot for slot in expected_slots if slot not in all_slot_map]
        all_slots_bound = len(missing_slots) == 0
    else:
        covered_slots = sorted(all_slot_map.keys(), key=_slot_sort_key)
        missing_slots = []
        relevant_rows = [all_slot_map[slot] for slot in covered_slots]
        all_slots_bound = True

    return {
        "site_id": site_id,
        "slot_check_required": slot_check_required,
        "expected_slots": [_serialize_slot(slot) for slot in expected_slots],
        "expected_slot_count": len(expected_slots),
        "covered_slots": [_serialize_slot(slot) for slot in covered_slots],
        "bound_slot_count": len(covered_slots),
        "missing_slots": [_serialize_slot(slot) for slot in missing_slots],
        "all_slots_bound": all_slots_bound,
        "rows": relevant_rows,
        "all_rows": all_bound_rows,
        "ready_for_status": bool(relevant_rows) and (all_slots_bound or not slot_check_required),
    }


def get_bound_sns_for_site(db: Session, site_id: int) -> List[str]:
    """
    基于设备位当前绑定关系推导站点绑定的设备 SN 列表。

    规则：
    - 同一设备位（sector_id + band）取最新一条记录
    - 若 action != UNBIND 则视为该设备位当前仍有绑定
    - 同一 SN 若异常地出现在多个设备位，最终按去重后的 SN 列表返回
    """
    sns = {
        str(row.equipment_sn).strip()
        for row in get_bound_slot_rows_for_site(db, site_id, opening_only=False)
        if row.action != BindingActionEnum.UNBIND and str(row.equipment_sn or "").strip()
    }
    return sorted(sns)


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
    binding_summary = summarize_site_binding_slots(db, site_id, opening_only=False)
    binding_rows: List[EquipmentBindingHistory] = list(binding_summary.get("rows") or [])
    sns = sorted({
        str(row.equipment_sn).strip()
        for row in binding_rows
        if str(row.equipment_sn or "").strip()
    })
    devices: List[Dict] = []

    if not sns:
        return {
            "site_id": site_id,
            "sns": [],
            "all_ever_online": False,
            "all_ever_activated": False,
            "devices": [],
            "slot_check_required": bool(binding_summary.get("slot_check_required")),
            "expected_slot_count": int(binding_summary.get("expected_slot_count") or 0),
            "bound_slot_count": int(binding_summary.get("bound_slot_count") or 0),
            "all_slots_bound": bool(binding_summary.get("all_slots_bound")),
            "missing_slots": list(binding_summary.get("missing_slots") or []),
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
            to_utc_iso(state.last_seen_at) if state and state.last_seen_at else None
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

    if not bool(binding_summary.get("ready_for_status")):
        all_ever_online = False
        all_ever_activated = False

    return {
        "site_id": site_id,
        "sns": sns,
        "all_ever_online": all_ever_online,
        "all_ever_activated": all_ever_activated,
        "devices": devices,
        "slot_check_required": bool(binding_summary.get("slot_check_required")),
        "expected_slot_count": int(binding_summary.get("expected_slot_count") or 0),
        "bound_slot_count": int(binding_summary.get("bound_slot_count") or 0),
        "all_slots_bound": bool(binding_summary.get("all_slots_bound")),
        "missing_slots": list(binding_summary.get("missing_slots") or []),
    }
