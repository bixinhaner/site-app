from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.inspection import InspectionCheckItem, SiteInspection
from app.models.omc_state import OmcDeviceState
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.planning import SitePlanning, SitePlanningCell, SitePlanningSector
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
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


def _normalize_site_ids(site_ids: Iterable[int]) -> List[int]:
    normalized: List[int] = []
    seen: set[int] = set()
    for raw_site_id in site_ids or []:
        try:
            site_id = int(raw_site_id)
        except (TypeError, ValueError):
            continue
        if site_id in seen:
            continue
        seen.add(site_id)
        normalized.append(site_id)
    return normalized


def upsert_omc_device_state(
    db: Session,
    sn: str,
    online_raw: Optional[bool],
    activated_raw: Optional[bool],
    source: str,
    status_payload: Optional[Dict] = None,
    observed_at: Optional[datetime] = None,
    online_evidence_at: Optional[datetime] = None,
    activated_evidence_at: Optional[datetime] = None,
) -> tuple[OmcDeviceState, bool, bool]:
    """
    将一次 OMC 观测写入 OmcDeviceState（SN 级聚合）:

    - 更新最近一次观测的原始状态（允许回退；None 表示本次没有可靠原始状态）
    - 推进里程碑状态 ever_online / ever_activated（只升不降）
    - 支持来自库存快照的“曾上线证据”时间，例如 device/query.offlineDays
    """
    sn = (sn or "").strip()
    if not sn:
        raise ValueError("sn is required")

    now = observed_at or datetime.utcnow()
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

    online_milestone_at = online_evidence_at
    if online_raw:
        online_milestone_at = online_milestone_at or now
    if online_milestone_at is not None:
        if not state.ever_online:
            state.ever_online = True
            newly_online = True
        if not state.first_online_at or online_milestone_at < state.first_online_at:
            state.first_online_at = online_milestone_at

    if activated_raw is not None:
        state.omc_active_raw = bool(activated_raw)

    activated_milestone_at = activated_evidence_at
    if activated_raw:
        activated_milestone_at = activated_milestone_at or now
    if activated_milestone_at is not None:
        if not state.ever_activated:
            state.ever_activated = True
            newly_activated = True
        if not state.first_activated_at or activated_milestone_at < state.first_activated_at:
            state.first_activated_at = activated_milestone_at

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
    return get_expected_device_slots_for_sites(db, [site_id]).get(int(site_id), [])


def get_expected_device_slots_for_sites(
    db: Session,
    site_ids: Iterable[int],
) -> Dict[int, List[DeviceSlot]]:
    """批量读取站点当前规划中的设备位，查询数量不随站点数增长。"""
    normalized_site_ids = _normalize_site_ids(site_ids)
    result: Dict[int, List[DeviceSlot]] = {
        site_id: [] for site_id in normalized_site_ids
    }
    if not normalized_site_ids:
        return result

    planning_by_site: Dict[int, SitePlanning] = {}
    planning_rows = (
        db.query(SitePlanning)
        .filter(
            SitePlanning.site_id.in_(normalized_site_ids),
            SitePlanning.is_current.is_(True),
        )
        .order_by(SitePlanning.site_id.asc(), SitePlanning.id.asc())
        .all()
    )
    for planning in planning_rows:
        planning_by_site.setdefault(int(planning.site_id), planning)

    planning_ids = [int(planning.id) for planning in planning_by_site.values()]
    if not planning_ids:
        return result

    cells_by_planning: Dict[int, List[SitePlanningCell]] = {
        planning_id: [] for planning_id in planning_ids
    }
    planning_site_by_id = {
        int(planning.id): site_id for site_id, planning in planning_by_site.items()
    }
    for cell in (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.planning_id.in_(planning_ids),
            SitePlanningCell.site_id.in_(normalized_site_ids),
        )
        .order_by(
            SitePlanningCell.planning_id.asc(),
            SitePlanningCell.local_cell_id.asc(),
            SitePlanningCell.band_code.asc(),
            SitePlanningCell.frequency.asc(),
            SitePlanningCell.id.asc(),
        )
        .all()
    ):
        if int(cell.site_id) != planning_site_by_id.get(int(cell.planning_id)):
            continue
        cells_by_planning.setdefault(int(cell.planning_id), []).append(cell)

    fallback_planning_ids = [
        planning_id
        for planning_id, cells in cells_by_planning.items()
        if not cells
    ]
    sectors_by_planning: Dict[int, List[SitePlanningSector]] = {
        planning_id: [] for planning_id in fallback_planning_ids
    }
    if fallback_planning_ids:
        for sector in (
            db.query(SitePlanningSector)
            .filter(SitePlanningSector.planning_id.in_(fallback_planning_ids))
            .order_by(
                SitePlanningSector.planning_id.asc(),
                SitePlanningSector.sector_index.asc(),
                SitePlanningSector.id.asc(),
            )
            .all()
        ):
            sectors_by_planning.setdefault(int(sector.planning_id), []).append(sector)

    for site_id, planning in planning_by_site.items():
        slots: set[DeviceSlot] = set()
        planning_id = int(planning.id)
        cells = cells_by_planning.get(planning_id, [])
        for cell in cells:
            if cell.local_cell_id is None or not cell.band_code:
                continue
            slot = _normalize_device_slot(str(int(cell.local_cell_id)), cell.band_code)
            if slot:
                slots.add(slot)

        if not cells:
            for sector in sectors_by_planning.get(planning_id, []):
                sector_bands = sector.bands or planning.bands or ["default"]
                for band in sector_bands:
                    slot = _normalize_device_slot(str(sector.sector_index), band)
                    if slot:
                        slots.add(slot)

        result[site_id] = sorted(slots, key=_slot_sort_key)

    return result


def get_opening_expected_device_slots_for_site(db: Session, site_id: int) -> List[DeviceSlot]:
    """
    获取开站工单生成时的设备位基线。

    站点完成小区扩容后，当前 LLD 可能从 3 小区变成 6 小区；开站交付概况仍应按原开站
    基线计算，不能用扩容后的当前规划拉大分母。
    """
    return get_opening_expected_device_slots_for_sites(db, [site_id]).get(int(site_id), [])


def get_opening_expected_device_slots_for_sites(
    db: Session,
    site_ids: Iterable[int],
) -> Dict[int, List[DeviceSlot]]:
    """批量读取开站工单设备位基线。"""
    normalized_site_ids = _normalize_site_ids(site_ids)
    result: Dict[int, List[DeviceSlot]] = {
        site_id: [] for site_id in normalized_site_ids
    }
    if not normalized_site_ids:
        return result

    rows = (
        db.query(InspectionCheckItem.sector_id, InspectionCheckItem.band)
        .join(SiteInspection, SiteInspection.id == InspectionCheckItem.inspection_id)
        .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
        .filter(
            SiteInspection.site_id.in_(normalized_site_ids),
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            InspectionCheckItem.is_active.is_(True),
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.band.isnot(None),
        )
        .with_entities(
            SiteInspection.site_id,
            InspectionCheckItem.sector_id,
            InspectionCheckItem.band,
        )
        .all()
    )
    opening_slots: Dict[int, set[DeviceSlot]] = {
        site_id: set() for site_id in normalized_site_ids
    }
    for site_id, sector_id, band in rows:
        slot = _normalize_device_slot(sector_id, band)
        if slot:
            opening_slots[int(site_id)].add(slot)

    for site_id in normalized_site_ids:
        result[site_id] = sorted(opening_slots[site_id], key=_slot_sort_key)
    return result


def get_bound_slot_rows_for_site(
    db: Session,
    site_id: int,
    *,
    opening_only: bool = False,
) -> List[EquipmentBindingHistory]:
    return get_bound_slot_rows_for_sites(
        db,
        [site_id],
        opening_only=opening_only,
    ).get(int(site_id), [])


def get_bound_slot_rows_for_sites(
    db: Session,
    site_ids: Iterable[int],
    *,
    opening_only: bool = False,
) -> Dict[int, List[EquipmentBindingHistory]]:
    """批量读取每个站点、每个设备位最后一次绑定操作。"""
    normalized_site_ids = _normalize_site_ids(site_ids)
    result: Dict[int, List[EquipmentBindingHistory]] = {
        site_id: [] for site_id in normalized_site_ids
    }
    if not normalized_site_ids:
        return result

    latest_at_query = (
        db.query(
            EquipmentBindingHistory.site_id.label("site_id"),
            EquipmentBindingHistory.sector_id.label("sector_id"),
            EquipmentBindingHistory.band.label("band"),
            func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
        )
        .filter(EquipmentBindingHistory.site_id.in_(normalized_site_ids))
    )
    latest_id_query = (
        db.query(
            EquipmentBindingHistory.site_id.label("site_id"),
            EquipmentBindingHistory.sector_id.label("sector_id"),
            EquipmentBindingHistory.band.label("band"),
            func.max(EquipmentBindingHistory.id).label("latest_id"),
        )
        .filter(EquipmentBindingHistory.site_id.in_(normalized_site_ids))
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
            EquipmentBindingHistory.site_id,
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
                EquipmentBindingHistory.site_id == latest_at_subq.c.site_id,
                EquipmentBindingHistory.sector_id == latest_at_subq.c.sector_id,
                EquipmentBindingHistory.band == latest_at_subq.c.band,
                EquipmentBindingHistory.operated_at == latest_at_subq.c.latest_at,
            ),
        )
        .group_by(
            EquipmentBindingHistory.site_id,
            EquipmentBindingHistory.sector_id,
            EquipmentBindingHistory.band,
        )
        .subquery()
    )

    rows = (
        db.query(EquipmentBindingHistory)
        .join(
            latest_id_subq,
            and_(
                EquipmentBindingHistory.id == latest_id_subq.c.latest_id,
                EquipmentBindingHistory.site_id == latest_id_subq.c.site_id,
            ),
        )
        .order_by(
            EquipmentBindingHistory.site_id.asc(),
            EquipmentBindingHistory.sector_id.asc(),
            EquipmentBindingHistory.band.asc(),
            EquipmentBindingHistory.cell_id.asc(),
            EquipmentBindingHistory.id.asc(),
        )
        .all()
    )
    for row in rows:
        result.setdefault(int(row.site_id), []).append(row)
    return result


def _summarize_binding_slots(
    site_id: int,
    expected_slots: List[DeviceSlot],
    bound_rows: List[EquipmentBindingHistory],
) -> Dict[str, Any]:
    all_bound_rows = [
        row for row in bound_rows
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


def summarize_site_binding_slots(
    db: Session,
    site_id: int,
    *,
    opening_only: bool = False,
) -> Dict[str, Any]:
    return summarize_site_binding_slots_for_sites(
        db,
        [site_id],
        opening_only=opening_only,
    )[int(site_id)]


def summarize_site_binding_slots_for_sites(
    db: Session,
    site_ids: Iterable[int],
    *,
    opening_only: bool = False,
) -> Dict[int, Dict[str, Any]]:
    """批量汇总站点设备位，业务口径与单站点接口完全一致。"""
    normalized_site_ids = _normalize_site_ids(site_ids)
    if not normalized_site_ids:
        return {}

    if opening_only:
        expected_slots_by_site = get_opening_expected_device_slots_for_sites(
            db,
            normalized_site_ids,
        )
        fallback_site_ids = [
            site_id
            for site_id in normalized_site_ids
            if not expected_slots_by_site.get(site_id)
        ]
        fallback_slots = get_expected_device_slots_for_sites(db, fallback_site_ids)
        for site_id in fallback_site_ids:
            expected_slots_by_site[site_id] = fallback_slots.get(site_id, [])
    else:
        expected_slots_by_site = get_expected_device_slots_for_sites(
            db,
            normalized_site_ids,
        )
    bound_rows_by_site = get_bound_slot_rows_for_sites(
        db,
        normalized_site_ids,
        opening_only=opening_only,
    )

    return {
        site_id: _summarize_binding_slots(
            site_id,
            expected_slots_by_site.get(site_id, []),
            bound_rows_by_site.get(site_id, []),
        )
        for site_id in normalized_site_ids
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
