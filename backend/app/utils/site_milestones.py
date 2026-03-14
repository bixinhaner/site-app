from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.inspection import SiteInspection
from app.models.work_order import AuditEvent, WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum


SiteEventRows = List[Tuple[int, datetime]]


def _normalize_site_event_rows(
    rows: Iterable[Tuple[int | str | None, Optional[datetime]]],
) -> SiteEventRows:
    normalized: Dict[int, datetime] = {}

    for raw_site_id, event_at in rows:
        if raw_site_id is None or event_at is None:
            continue
        try:
            site_id = int(raw_site_id)
        except (TypeError, ValueError):
            continue

        current = normalized.get(site_id)
        if current is None or event_at < current:
            normalized[site_id] = event_at

    return sorted(normalized.items(), key=lambda item: item[0])


def _opening_work_order_filters(site_id: Optional[int] = None):
    filters = [
        WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
        WorkOrder.site_id.isnot(None),
        WorkOrder.status != WorkOrderStatusEnum.VOIDED,
    ]
    if site_id is not None:
        filters.append(WorkOrder.site_id == site_id)
    return filters


def _get_opening_work_order_time_rows(
    db: Session,
    column_name: str,
    *,
    site_id: Optional[int] = None,
) -> SiteEventRows:
    event_column = getattr(WorkOrder, column_name)
    rows = (
        db.query(
            WorkOrder.site_id,
            func.min(event_column).label("event_at"),
        )
        .filter(
            *_opening_work_order_filters(site_id),
            event_column.isnot(None),
        )
        .group_by(WorkOrder.site_id)
        .all()
    )
    return _normalize_site_event_rows(rows)


def _get_site_status_change_rows(
    db: Session,
    to_statuses: Sequence[str],
    *,
    site_id: Optional[int] = None,
) -> SiteEventRows:
    filters = [
        AuditEvent.resource_type == "site",
        AuditEvent.action == "status_change",
        AuditEvent.to_status.in_(list(to_statuses)),
    ]
    if site_id is not None:
        filters.append(AuditEvent.resource_id == str(site_id))

    rows = (
        db.query(
            AuditEvent.resource_id,
            func.min(AuditEvent.created_at).label("event_at"),
        )
        .filter(*filters)
        .group_by(AuditEvent.resource_id)
        .all()
    )
    return _normalize_site_event_rows(rows)


def _merge_primary_with_fallback(
    primary_rows: SiteEventRows,
    fallback_rows: SiteEventRows,
) -> SiteEventRows:
    merged: Dict[int, datetime] = {site_id: event_at for site_id, event_at in primary_rows}
    for site_id, event_at in fallback_rows:
        if site_id not in merged:
            merged[site_id] = event_at
    return sorted(merged.items(), key=lambda item: item[0])


def get_install_started_rows(db: Session, site_id: Optional[int] = None) -> SiteEventRows:
    filters = [
        EquipmentBindingHistory.site_id.isnot(None),
        EquipmentBindingHistory.action.in_([BindingActionEnum.BIND, BindingActionEnum.REBIND]),
        WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
        WorkOrder.status != WorkOrderStatusEnum.VOIDED,
    ]
    if site_id is not None:
        filters.append(EquipmentBindingHistory.site_id == site_id)

    rows = (
        db.query(
            EquipmentBindingHistory.site_id,
            func.min(EquipmentBindingHistory.operated_at).label("event_at"),
        )
        .join(SiteInspection, SiteInspection.id == EquipmentBindingHistory.inspection_id)
        .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
        .filter(*filters)
        .group_by(EquipmentBindingHistory.site_id)
        .all()
    )
    return _normalize_site_event_rows(rows)


def get_install_completed_rows(db: Session, site_id: Optional[int] = None) -> SiteEventRows:
    return _get_opening_work_order_time_rows(db, "submitted_at", site_id=site_id)


def get_online_rows(db: Session, site_id: Optional[int] = None) -> SiteEventRows:
    status_rows = _get_site_status_change_rows(
        db,
        ["online_pending_activation"],
        site_id=site_id,
    )
    fallback_rows = _get_opening_work_order_time_rows(db, "activated_at", site_id=site_id)
    return _merge_primary_with_fallback(status_rows, fallback_rows)


def get_activated_rows(db: Session, site_id: Optional[int] = None) -> SiteEventRows:
    status_rows = _get_site_status_change_rows(
        db,
        ["operational", "maintenance"],
        site_id=site_id,
    )
    fallback_rows = _get_opening_work_order_time_rows(db, "completed_at", site_id=site_id)
    return _merge_primary_with_fallback(status_rows, fallback_rows)


def get_ssv_rows(db: Session, site_id: Optional[int] = None) -> SiteEventRows:
    filters = [
        WorkOrder.type == WorkOrderTypeEnum.SSV,
        WorkOrder.site_id.isnot(None),
        WorkOrder.status != WorkOrderStatusEnum.VOIDED,
        WorkOrder.completed_at.isnot(None),
    ]
    if site_id is not None:
        filters.append(WorkOrder.site_id == site_id)

    rows = (
        db.query(
            WorkOrder.site_id,
            func.min(WorkOrder.completed_at).label("event_at"),
        )
        .filter(*filters)
        .group_by(WorkOrder.site_id)
        .all()
    )
    return _normalize_site_event_rows(rows)


def get_site_milestone_timestamps(db: Session, site_id: int) -> Dict[str, Optional[datetime]]:
    return {
        "install_started_at": dict(get_install_started_rows(db, site_id=site_id)).get(site_id),
        "install_completed_at": dict(get_install_completed_rows(db, site_id=site_id)).get(site_id),
        "online_at": dict(get_online_rows(db, site_id=site_id)).get(site_id),
        "activated_at": dict(get_activated_rows(db, site_id=site_id)).get(site_id),
        "ssv_at": dict(get_ssv_rows(db, site_id=site_id)).get(site_id),
    }
