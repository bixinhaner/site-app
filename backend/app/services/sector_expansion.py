from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.planning import (
    PlanningChangeLog,
    SitePlanning,
    SitePlanningCell,
    SitePlanningSector,
)
from app.models.site import Site
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.site_progress_service import rebuild_site_progress


EXPANSION_ALLOWED_SITE_STATUSES = {
    "construction",
    "pending_online",
    "online_pending_activation",
    "operational",
    "maintenance",
}

EXPANSION_IN_PROGRESS_STATUSES = {
    WorkOrderStatusEnum.PENDING,
    WorkOrderStatusEnum.ACTIVE,
    WorkOrderStatusEnum.SUBMITTED,
    WorkOrderStatusEnum.UNDER_REVIEW,
    WorkOrderStatusEnum.APPROVED,
    WorkOrderStatusEnum.ACTIVATED,
}

EXPANSION_LOCKED_FIELDS = {
    "rat",
    "band_code",
    "local_cell_id",
    "enb_id",
    "gnb_id",
    "eci",
    "nci",
    "pci",
    "frequency",
    "bandwidth",
}


def get_current_planning(db: Session, site_id: int) -> Optional[SitePlanning]:
    return (
        db.query(SitePlanning)
        .filter(SitePlanning.site_id == site_id, SitePlanning.is_current.is_(True))
        .first()
    )


def cell_kwargs_from_model(cell: SitePlanningCell) -> Dict[str, Any]:
    exclude = {"id", "planning_id", "created_at"}
    return {
        c.name: getattr(cell, c.name)
        for c in SitePlanningCell.__table__.columns
        if c.name not in exclude
    }


def normalize_cell_payload(site: Site, raw: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        c.name: raw.get(c.name)
        for c in SitePlanningCell.__table__.columns
        if c.name not in {"id", "planning_id", "created_at"}
    }
    payload["site_id"] = site.id
    if not payload.get("site_information"):
        payload["site_information"] = site.site_code
    if not payload.get("site_name"):
        payload["site_name"] = site.site_name
    if payload.get("tower_id") is not None:
        payload["tower_id"] = str(payload.get("tower_id")).strip() or None
    if payload.get("band_code") is not None:
        payload["band_code"] = str(payload.get("band_code")).strip().upper()
    if payload.get("rat") is not None:
        payload["rat"] = str(payload.get("rat")).strip().upper()
    return payload


def cell_identity_key(cell: Any) -> Tuple[str, str, int]:
    rat = getattr(cell, "rat", None) if isinstance(cell, SitePlanningCell) else cell.get("rat")
    band = getattr(cell, "band_code", None) if isinstance(cell, SitePlanningCell) else cell.get("band_code")
    lcid = getattr(cell, "local_cell_id", None) if isinstance(cell, SitePlanningCell) else cell.get("local_cell_id")
    if rat is None or band is None or lcid is None:
        raise ValueError("Cell 缺少 rat/band_code/local_cell_id")
    return str(rat).strip().upper(), str(band).strip().upper(), int(lcid)


def device_slot_key(cell: Any) -> Tuple[str, str]:
    band = getattr(cell, "band_code", None) if isinstance(cell, SitePlanningCell) else cell.get("band_code")
    lcid = getattr(cell, "local_cell_id", None) if isinstance(cell, SitePlanningCell) else cell.get("local_cell_id")
    if band is None or lcid is None:
        raise ValueError("Cell 缺少 band_code/local_cell_id")
    return str(int(lcid)), str(band).strip().upper()


def serialize_slot(slot: Tuple[str, str]) -> Dict[str, str]:
    sector_id, band = slot
    return {
        "sector_id": str(sector_id),
        "band": str(band),
        "cell_id": f"{sector_id}_{band}",
    }


def normalize_slot_payload(payload: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    if not isinstance(payload, dict):
        return None
    sector_id = str(payload.get("sector_id") or "").strip()
    band = str(payload.get("band") or "").strip().upper()
    if not sector_id or not band:
        return None
    return sector_id, band


def get_expansion_target_slots_from_work_order(work_order: WorkOrder) -> List[Tuple[str, str]]:
    extra_data = work_order.extra_data or {}
    slots = []
    seen = set()
    for raw in extra_data.get("expansion_targets") or []:
        slot = normalize_slot_payload(raw)
        if not slot or slot in seen:
            continue
        seen.add(slot)
        slots.append(slot)
    return sorted(slots, key=_slot_sort_key)


def _slot_sort_key(slot: Tuple[str, str]) -> Tuple[int, int | str, str]:
    sector_id, band = slot
    if str(sector_id).isdigit():
        return 0, int(sector_id), band
    return 1, sector_id, band


def _snapshot(planning: Optional[SitePlanning]) -> Optional[Dict[str, Any]]:
    if planning is None:
        return None
    return {
        "planning": {
            "bands": planning.bands or [],
            "sector_count": planning.sector_count or 0,
            "notes": planning.notes or "",
        },
        "sectors": [
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (planning.sectors or [])
        ],
    }


def _max_version(db: Session, site_id: int) -> int:
    version = db.query(func.max(SitePlanning.version)).filter(SitePlanning.site_id == site_id).scalar()
    return int(version or 0)


def _build_planning_summary_from_cells(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    bands = sorted({str(c.get("band_code")).strip().upper() for c in cells if c.get("band_code")})
    sector_ids = sorted(
        {int(c.get("local_cell_id")) for c in cells if c.get("local_cell_id") is not None}
    )
    sectors = []
    for sector_id in sector_ids:
        sec_cells = [c for c in cells if int(c.get("local_cell_id") or 0) == sector_id]
        azimuth = None
        mech = None
        elec = None
        sector_bands = []
        for cell in sec_cells:
            if azimuth is None and cell.get("azimuth_deg") is not None:
                azimuth = float(cell.get("azimuth_deg"))
            if mech is None and cell.get("mechanical_downtilt_deg") is not None:
                mech = float(cell.get("mechanical_downtilt_deg"))
            if elec is None and cell.get("electrical_downtilt_deg") is not None:
                elec = float(cell.get("electrical_downtilt_deg"))
            if cell.get("band_code"):
                sector_bands.append(str(cell.get("band_code")).strip().upper())
        sectors.append(
            {
                "sector_index": sector_id,
                "azimuth_deg": float(azimuth or 0.0),
                "downtilt_deg": float(mech or 0.0) + float(elec or 0.0),
                "bands": sorted(set(sector_bands)),
            }
        )
    return {
        "bands": bands,
        "sector_count": len(sector_ids),
        "sectors": sectors,
    }


def _normalize_locked_compare_value(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"rat", "band_code", "bandwidth"}:
        text = str(value).strip()
        return text.upper() if field in {"rat", "band_code"} else text
    if field in {"local_cell_id", "enb_id", "gnb_id", "eci", "nci", "pci", "frequency"}:
        try:
            return int(value)
        except Exception:
            return value
    return value


def _validate_site_can_expand(site: Site) -> None:
    status = str(getattr(site, "status", "") or "").strip()
    if status not in EXPANSION_ALLOWED_SITE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"站点当前状态为 {status or '-'}，不适合创建扇区扩容工单；未安装站点请直接更新 LLD 后创建开站工单。",
        )


def _validate_no_active_expansion_work_order(db: Session, site_id: int, exclude_id: Optional[str] = None) -> None:
    query = db.query(WorkOrder).filter(
        WorkOrder.site_id == site_id,
        WorkOrder.type == WorkOrderTypeEnum.SECTOR_EXPANSION,
        WorkOrder.status.in_(list(EXPANSION_IN_PROGRESS_STATUSES)),
    )
    if exclude_id:
        query = query.filter(WorkOrder.id != exclude_id)
    existing = query.order_by(WorkOrder.created_at.desc()).first()
    if existing:
        raise HTTPException(status_code=409, detail="该站点已有进行中的扇区扩容工单")


def validate_expansion_target_cells(
    db: Session,
    site: Site,
    target_cells_raw: List[Dict[str, Any]],
    *,
    check_active_work_order: bool = True,
    exclude_work_order_id: Optional[str] = None,
) -> Dict[str, Any]:
    _validate_site_can_expand(site)
    if check_active_work_order:
        _validate_no_active_expansion_work_order(db, site.id, exclude_id=exclude_work_order_id)

    current_planning = get_current_planning(db, site.id)
    if current_planning is None:
        raise HTTPException(status_code=409, detail="站点没有当前 LLD 规划，无法计算扩容差异")

    current_cells = (
        db.query(SitePlanningCell)
        .filter(SitePlanningCell.site_id == site.id, SitePlanningCell.planning_id == current_planning.id)
        .all()
    )
    if not current_cells:
        raise HTTPException(status_code=409, detail="当前规划没有 Cell 明细，无法计算扩容差异")

    normalized_cells: List[Dict[str, Any]] = []
    target_identity_map: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    duplicate_keys: List[str] = []
    for raw in target_cells_raw or []:
        if not isinstance(raw, dict):
            continue
        cell = normalize_cell_payload(site, raw)
        try:
            key = cell_identity_key(cell)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"目标 LLD 中存在缺少关键字段的 Cell：{exc}")
        if key in target_identity_map:
            duplicate_keys.append(f"{key[0]}/{key[1]}/LCID={key[2]}")
            continue
        target_identity_map[key] = cell
        normalized_cells.append(cell)

    if duplicate_keys:
        raise HTTPException(status_code=400, detail=f"目标 LLD 存在重复 Cell：{', '.join(duplicate_keys[:10])}")

    current_identity_map = {cell_identity_key(cell): cell for cell in current_cells}
    current_keys = set(current_identity_map.keys())
    target_keys = set(target_identity_map.keys())

    deleted = sorted(current_keys - target_keys)
    if deleted:
        sample = ", ".join(f"{k[0]}/{k[1]}/LCID={k[2]}" for k in deleted[:10])
        raise HTTPException(status_code=409, detail=f"扩容目标不能删除已有 Cell：{sample}")

    locked_changes: List[str] = []
    for key in sorted(current_keys & target_keys):
        old = current_identity_map[key]
        new = target_identity_map[key]
        for field in sorted(EXPANSION_LOCKED_FIELDS):
            old_value = _normalize_locked_compare_value(field, getattr(old, field, None))
            new_value = _normalize_locked_compare_value(field, new.get(field))
            if old_value != new_value:
                locked_changes.append(f"{key[0]}/{key[1]}/LCID={key[2]} {field}: {old_value} -> {new_value}")

    if locked_changes:
        raise HTTPException(
            status_code=409,
            detail="扩容目标不能改写已有 Cell 的关键字段：" + "；".join(locked_changes[:10]),
        )

    current_slots = {device_slot_key(cell) for cell in current_cells}
    target_slots = {device_slot_key(cell) for cell in normalized_cells}
    new_slots = sorted(target_slots - current_slots, key=_slot_sort_key)

    if not new_slots:
        raise HTTPException(status_code=409, detail="目标 LLD 没有新增设备位，无法创建扇区扩容工单")

    summary = _build_planning_summary_from_cells(normalized_cells)
    return {
        "site_id": site.id,
        "current_planning_id": current_planning.id,
        "current_planning_version": current_planning.version,
        "current_sector_count": current_planning.sector_count or 0,
        "target_sector_count": summary["sector_count"],
        "current_slots": [serialize_slot(slot) for slot in sorted(current_slots, key=_slot_sort_key)],
        "target_slots": [serialize_slot(slot) for slot in sorted(target_slots, key=_slot_sort_key)],
        "new_slots": [serialize_slot(slot) for slot in new_slots],
        "expansion_targets": [serialize_slot(slot) for slot in new_slots],
        "target_cells": normalized_cells,
        "bands": summary["bands"],
        "target_cell_count": len(normalized_cells),
    }


def create_planning_version_from_expansion(
    db: Session,
    *,
    site: Site,
    target_cells: List[Dict[str, Any]],
    operator_id: int,
    work_order_id: str,
) -> SitePlanning:
    current = get_current_planning(db, site.id)
    if current is None:
        raise HTTPException(status_code=409, detail="站点没有当前 LLD 规划，无法完成扩容规划合并")

    validated = validate_expansion_target_cells(
        db,
        site,
        target_cells,
        check_active_work_order=False,
        exclude_work_order_id=work_order_id,
    )
    normalized_cells = validated["target_cells"]
    summary = _build_planning_summary_from_cells(normalized_cells)
    before_snapshot = _snapshot(current)

    current.is_current = False
    db.flush()

    planning = SitePlanning(
        site_id=site.id,
        version=_max_version(db, site.id) + 1,
        bands=summary["bands"],
        sector_count=summary["sector_count"],
        notes=f"Sector expansion merged from work order {work_order_id}",
        is_current=True,
        created_by=operator_id,
    )
    db.add(planning)
    db.flush()

    for sector in summary["sectors"]:
        db.add(
            SitePlanningSector(
                planning_id=planning.id,
                sector_index=sector["sector_index"],
                azimuth_deg=sector["azimuth_deg"],
                downtilt_deg=sector["downtilt_deg"],
                bands=sector["bands"],
            )
        )

    for cell in normalized_cells:
        db.add(SitePlanningCell(planning_id=planning.id, **cell))

    db.flush()
    after_snapshot = _snapshot(planning)
    db.add(
        PlanningChangeLog(
            site_id=site.id,
            planning_id=planning.id,
            operation="expansion_commit",
            actor_id=operator_id,
            summary=f"Sector expansion work order {work_order_id}",
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            diff={
                "changed_fields": ["cells", "planning", "sectors"],
                "current_planning_version": validated["current_planning_version"],
                "new_slots": validated["new_slots"],
                "target_sector_count": validated["target_sector_count"],
            },
        )
    )

    rebuild_site_progress(
        db,
        site.id,
        reason="sector_expansion_planning_commit",
        operator_id=operator_id,
    )
    planning.updated_at = datetime.utcnow()
    return planning
