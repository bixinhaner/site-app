from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.equipment_binding_history import BindingActionEnum, EquipmentBindingHistory
from app.models.inspection import SiteInspection
from app.models.omc_state import OmcDeviceState
from app.models.site import Site
from app.models.site_progress import SiteProgressEvent, SiteProgressSnapshot
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.omc_state import summarize_site_binding_slots
from app.services.site_progress_metric_service import (
    SITE_PROGRESS_METRIC_MODE_DEVICE_FACT,
    SITE_PROGRESS_METRIC_MODE_WORKFLOW,
    normalize_site_progress_metric_mode,
)


CURRENT_SITE_PROGRESS_SNAPSHOT_VERSION = 3

MILESTONE_FIELD_MAP = {
    "install_started": "install_started_at",
    "install_completed": "install_completed_at",
    "online": "online_at",
    "activated": "activated_at",
    "ssv": "ssv_at",
}

DEVICE_FACT_MILESTONE_FIELD_MAP = {
    "install_started": "install_started_at",
    "install_completed": "install_completed_at",
    "online": "online_at_device_fact",
    "activated": "activated_at_device_fact",
    "ssv": "ssv_at",
}


@dataclass
class MilestoneFact:
    effective_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None


def _normalize_site_ids(site_ids: Optional[Iterable[int]]) -> List[int]:
    if site_ids is None:
        return []

    normalized: List[int] = []
    seen = set()
    for raw_site_id in site_ids:
        try:
            site_id = int(raw_site_id)
        except (TypeError, ValueError):
            continue
        if site_id in seen:
            continue
        seen.add(site_id)
        normalized.append(site_id)
    return normalized


def _get_site(db: Session, site_id: int) -> Optional[Site]:
    return db.query(Site).filter(Site.id == site_id).first()


def _get_first_binding_fact(db: Session, site_id: int) -> MilestoneFact:
    row = (
        db.query(EquipmentBindingHistory)
        .join(SiteInspection, SiteInspection.id == EquipmentBindingHistory.inspection_id)
        .join(WorkOrder, WorkOrder.id == SiteInspection.work_order_id)
        .filter(
            EquipmentBindingHistory.site_id == site_id,
            EquipmentBindingHistory.action.in_([BindingActionEnum.BIND, BindingActionEnum.REBIND]),
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
        )
        .order_by(EquipmentBindingHistory.operated_at.asc(), EquipmentBindingHistory.id.asc())
        .first()
    )
    if row is None:
        return MilestoneFact()
    return MilestoneFact(
        effective_at=row.operated_at,
        source_type="equipment_binding_history",
        source_id=str(row.id),
    )


def _get_first_work_order_fact(
    db: Session,
    *,
    site_id: int,
    work_order_type: WorkOrderTypeEnum,
    datetime_field: str,
) -> MilestoneFact:
    event_column = getattr(WorkOrder, datetime_field)
    row = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.site_id == site_id,
            WorkOrder.type == work_order_type,
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            event_column.isnot(None),
        )
        .order_by(event_column.asc(), WorkOrder.created_at.asc(), WorkOrder.id.asc())
        .first()
    )
    if row is None:
        return MilestoneFact()
    return MilestoneFact(
        effective_at=getattr(row, datetime_field),
        source_type="work_order",
        source_id=str(row.id),
    )


def _get_effective_opening_binding_rows(db: Session, site_id: int) -> List[EquipmentBindingHistory]:
    binding_summary = summarize_site_binding_slots(db, site_id, opening_only=True)
    if not bool(binding_summary.get("ready_for_status")):
        return []
    return list(binding_summary.get("rows") or [])


def _get_device_fact_milestone_fact(
    db: Session,
    *,
    site_id: int,
    datetime_field: str,
    milestone_code: str,
) -> MilestoneFact:
    binding_rows = _get_effective_opening_binding_rows(db, site_id)
    if not binding_rows:
        return MilestoneFact()

    sns = list({
        str(row.equipment_sn).strip()
        for row in binding_rows
        if str(row.equipment_sn or "").strip()
    })
    if not sns:
        return MilestoneFact()

    state_rows = (
        db.query(OmcDeviceState)
        .filter(OmcDeviceState.sn.in_(sns))
        .all()
    )
    state_map = {str(state.sn or "").strip(): state for state in state_rows}

    effective_times: List[datetime] = []
    for row in binding_rows:
        sn = str(row.equipment_sn or "").strip()
        if not sn:
            return MilestoneFact()
        state = state_map.get(sn)
        if state is None:
            return MilestoneFact()
        effective_at = getattr(state, datetime_field, None)
        if effective_at is None:
            return MilestoneFact()
        effective_times.append(effective_at)

    if not effective_times:
        return MilestoneFact()

    return MilestoneFact(
        effective_at=max(effective_times),
        source_type="omc_device_state",
        source_id=f"site:{site_id}:{milestone_code}",
    )


def calculate_site_progress_facts(db: Session, site_id: int) -> Dict[str, MilestoneFact]:
    return {
        "install_started": _get_first_binding_fact(db, site_id),
        "install_completed": _get_first_work_order_fact(
            db,
            site_id=site_id,
            work_order_type=WorkOrderTypeEnum.OPENING_INSPECTION,
            datetime_field="submitted_at",
        ),
        "online": _get_first_work_order_fact(
            db,
            site_id=site_id,
            work_order_type=WorkOrderTypeEnum.OPENING_INSPECTION,
            datetime_field="activated_at",
        ),
        "activated": _get_first_work_order_fact(
            db,
            site_id=site_id,
            work_order_type=WorkOrderTypeEnum.OPENING_INSPECTION,
            datetime_field="completed_at",
        ),
        "ssv": _get_first_work_order_fact(
            db,
            site_id=site_id,
            work_order_type=WorkOrderTypeEnum.SSV,
            datetime_field="completed_at",
        ),
    }


def calculate_site_progress_device_fact_facts(db: Session, site_id: int) -> Dict[str, MilestoneFact]:
    return {
        "online": _get_device_fact_milestone_fact(
            db,
            site_id=site_id,
            datetime_field="first_online_at",
            milestone_code="online_device_fact",
        ),
        "activated": _get_device_fact_milestone_fact(
            db,
            site_id=site_id,
            datetime_field="first_activated_at",
            milestone_code="activated_device_fact",
        ),
    }


def _derive_current_opening_stage(site: Site, facts: Dict[str, MilestoneFact]) -> str:
    if facts["ssv"].effective_at or getattr(site, "ssv_passed", False):
        return "ssv"
    if facts["activated"].effective_at:
        return "activated"
    if facts["online"].effective_at:
        return "online"
    if facts["install_completed"].effective_at:
        return "install_completed"
    if facts["install_started"].effective_at:
        return "install_started"
    return str(getattr(site, "status", None) or "survey_pending")


def _build_snapshot_values(
    site: Site,
    workflow_facts: Dict[str, MilestoneFact],
    device_fact_facts: Dict[str, MilestoneFact],
) -> Dict[str, Optional[datetime] | str | int]:
    return {
        "install_started_at": workflow_facts["install_started"].effective_at,
        "install_completed_at": workflow_facts["install_completed"].effective_at,
        "online_at": workflow_facts["online"].effective_at,
        "activated_at": workflow_facts["activated"].effective_at,
        "online_at_device_fact": device_fact_facts["online"].effective_at,
        "activated_at_device_fact": device_fact_facts["activated"].effective_at,
        "ssv_at": workflow_facts["ssv"].effective_at,
        "current_opening_stage": _derive_current_opening_stage(site, workflow_facts),
        "snapshot_version": CURRENT_SITE_PROGRESS_SNAPSHOT_VERSION,
    }


def _create_progress_event(
    db: Session,
    *,
    site_id: int,
    milestone_code: str,
    previous_effective_at: Optional[datetime],
    effective_at: Optional[datetime],
    source_type: Optional[str],
    source_id: Optional[str],
    operator_id: Optional[int],
    reason: Optional[str],
) -> None:
    if previous_effective_at == effective_at:
        return

    if previous_effective_at is None and effective_at is not None:
        event_type = "reach"
    elif previous_effective_at is not None and effective_at is None:
        event_type = "rollback"
    else:
        event_type = "rebuild"

    db.add(
        SiteProgressEvent(
            site_id=site_id,
            milestone_code=milestone_code,
            event_type=event_type,
            effective_at=effective_at,
            previous_effective_at=previous_effective_at,
            source_type=source_type,
            source_id=source_id,
            operator_id=operator_id,
            reason=reason,
            details={
                "previous_effective_at": previous_effective_at.isoformat() if previous_effective_at else None,
                "effective_at": effective_at.isoformat() if effective_at else None,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
    )


def rebuild_site_progress(
    db: Session,
    site_id: int,
    *,
    reason: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> Optional[SiteProgressSnapshot]:
    site = _get_site(db, site_id)
    if site is None:
        return None

    facts = calculate_site_progress_facts(db, site_id)
    device_fact_facts = calculate_site_progress_device_fact_facts(db, site_id)
    snapshot_values = _build_snapshot_values(site, facts, device_fact_facts)
    snapshot = db.query(SiteProgressSnapshot).filter(SiteProgressSnapshot.site_id == site_id).first()
    if snapshot is None:
        snapshot = SiteProgressSnapshot(site_id=site_id)
        db.add(snapshot)
        db.flush()

    for milestone_code, field_name in MILESTONE_FIELD_MAP.items():
        old_value = getattr(snapshot, field_name)
        new_value = snapshot_values[field_name]
        fact = facts[milestone_code]
        _create_progress_event(
            db,
            site_id=site_id,
            milestone_code=milestone_code,
            previous_effective_at=old_value,
            effective_at=new_value,
            source_type=fact.source_type,
            source_id=fact.source_id,
            operator_id=operator_id,
            reason=reason,
        )
        setattr(snapshot, field_name, new_value)

    snapshot.online_at_device_fact = snapshot_values["online_at_device_fact"]
    snapshot.activated_at_device_fact = snapshot_values["activated_at_device_fact"]

    old_stage = getattr(snapshot, "current_opening_stage", None)
    new_stage = str(snapshot_values["current_opening_stage"] or "survey_pending")
    if old_stage != new_stage:
        db.add(
            SiteProgressEvent(
                site_id=site_id,
                milestone_code="current_opening_stage",
                event_type="rebuild",
                operator_id=operator_id,
                reason=reason,
                details={"previous_stage": old_stage, "current_stage": new_stage},
            )
        )
    snapshot.current_opening_stage = new_stage
    snapshot.snapshot_version = int(snapshot_values["snapshot_version"] or CURRENT_SITE_PROGRESS_SNAPSHOT_VERSION)
    snapshot.last_rebuilt_at = datetime.utcnow()
    snapshot.last_rebuild_reason = (reason or "").strip() or None

    # 让旧字段继续可用，但其值由统一快照反推，不再各处手工维护。
    site.ssv_passed = bool(snapshot.ssv_at)

    db.flush()
    return snapshot


def rebuild_site_progress_for_sites(
    db: Session,
    site_ids: Optional[Iterable[int]] = None,
    *,
    reason: Optional[str] = None,
    operator_id: Optional[int] = None,
    force: bool = False,
) -> Dict[str, object]:
    requested_site_ids = _normalize_site_ids(site_ids)
    if not requested_site_ids:
        requested_site_ids = [
            site_id for site_id, in db.query(Site.id).order_by(Site.id.asc()).all()
        ]

    if force:
        target_site_ids = requested_site_ids
    else:
        existing_snapshot_versions = {
            int(site_id): int(snapshot_version or 0)
            for site_id, snapshot_version in db.query(
                SiteProgressSnapshot.site_id,
                SiteProgressSnapshot.snapshot_version,
            )
            .filter(SiteProgressSnapshot.site_id.in_(requested_site_ids))
            .all()
        }
        target_site_ids = [
            site_id
            for site_id in requested_site_ids
            if int(existing_snapshot_versions.get(site_id, 0)) < CURRENT_SITE_PROGRESS_SNAPSHOT_VERSION
        ]

    rebuilt_site_ids: List[int] = []
    for site_id in target_site_ids:
        snapshot = rebuild_site_progress(
            db,
            site_id,
            reason=reason,
            operator_id=operator_id,
        )
        if snapshot is not None:
            rebuilt_site_ids.append(site_id)

    return {
        "requested_site_ids": requested_site_ids,
        "rebuilt_site_ids": rebuilt_site_ids,
        "skipped_count": max(len(requested_site_ids) - len(rebuilt_site_ids), 0),
    }


def ensure_site_progress_snapshots(
    db: Session,
    site_ids: Optional[Iterable[int]] = None,
    *,
    reason: Optional[str] = None,
) -> Dict[str, object]:
    return rebuild_site_progress_for_sites(
        db,
        site_ids,
        reason=reason or "auto_backfill_site_progress_snapshot",
        force=False,
    )


def get_site_progress_snapshot(db: Session, site_id: int) -> Optional[SiteProgressSnapshot]:
    return (
        db.query(SiteProgressSnapshot)
        .filter(SiteProgressSnapshot.site_id == site_id)
        .first()
    )


def get_site_progress_rows(
    db: Session,
    milestone_code: str,
    *,
    metric_mode: str = SITE_PROGRESS_METRIC_MODE_WORKFLOW,
) -> List[Tuple[int, datetime]]:
    field_name = resolve_site_progress_field_name(milestone_code, metric_mode=metric_mode)
    event_column = getattr(SiteProgressSnapshot, field_name)
    return [
        (site_id, event_at)
        for site_id, event_at in db.query(SiteProgressSnapshot.site_id, event_column)
        .filter(event_column.isnot(None))
        .all()
    ]


def resolve_site_progress_field_name(
    milestone_code: str,
    *,
    metric_mode: str = SITE_PROGRESS_METRIC_MODE_WORKFLOW,
) -> str:
    normalized_mode = normalize_site_progress_metric_mode(metric_mode)
    if normalized_mode == SITE_PROGRESS_METRIC_MODE_DEVICE_FACT:
        return DEVICE_FACT_MILESTONE_FIELD_MAP[milestone_code]
    return MILESTONE_FIELD_MAP[milestone_code]


def get_site_progress_milestone_at(
    snapshot: SiteProgressSnapshot,
    milestone_code: str,
    *,
    metric_mode: str = SITE_PROGRESS_METRIC_MODE_WORKFLOW,
) -> Optional[datetime]:
    if snapshot is None:
        return None
    field_name = resolve_site_progress_field_name(milestone_code, metric_mode=metric_mode)
    return getattr(snapshot, field_name, None)
