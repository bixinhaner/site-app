from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user import User as UserModel
from app.models.equipment_binding_history import BindingActionEnum
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.models.inspection import SiteInspection, InspectionStatusEnum
from app.models.site import Site
from app.models.site_group import SiteGroupAssignment, SiteGroupCategory, SiteGroupOption
from app.models.site_progress import SiteProgressSnapshot
from app.models.survey_archive import SiteSurveyArchive
from app.models.equipment import Inventory, Equipment, StockTransaction
from app.models.omc_state import OmcDeviceState
from app.services.cell_expansion import get_expansion_target_slots_from_work_order
from app.services.omc_state import (
    get_bound_slot_rows_for_site,
    summarize_site_binding_slots_for_sites,
)
from app.services.site_progress_service import (
    ensure_site_progress_snapshots,
    get_site_progress_rows,
    resolve_site_progress_field_name,
)
from app.services.authz_service import user_has_any_role_or_permission
from app.services.site_progress_metric_service import get_site_progress_metric_mode
from app.services.site_group_service import (
    get_active_group_categories,
    get_default_group_category,
    serialize_categories,
    serialize_category,
)
from app.utils.timezone import to_utc_iso

router = APIRouter()

_TREND_GRANULARITIES = {"day", "week", "month"}
_TREND_DEFAULT_PERIODS = {"day": 30, "week": 12, "month": 12}
_TREND_MAX_PERIODS = {"day": 180, "week": 104, "month": 60}
_EXPANSION_ACTIVE_STATUSES = {
    WorkOrderStatusEnum.PENDING,
    WorkOrderStatusEnum.ACTIVE,
    WorkOrderStatusEnum.SUBMITTED,
    WorkOrderStatusEnum.UNDER_REVIEW,
    WorkOrderStatusEnum.APPROVED,
    WorkOrderStatusEnum.ACTIVATED,
}


def _to_naive_utc(value: Optional[datetime | str]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # 兼容 "2026-03-10T12:34:56Z" 与 "2026-03-10 12:34:56" 两种常见格式
        candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week(dt: datetime) -> datetime:
    base = _start_of_day(dt)
    return base - timedelta(days=base.weekday())


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(dt: datetime, months: int) -> datetime:
    total_month = (dt.year * 12 + (dt.month - 1)) + months
    year = total_month // 12
    month = total_month % 12 + 1
    return dt.replace(year=year, month=month, day=1)


def _period_start(dt: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return _start_of_day(dt)
    if granularity == "week":
        return _start_of_week(dt)
    return _start_of_month(dt)


def _shift_period(dt: datetime, granularity: str, steps: int) -> datetime:
    if granularity == "day":
        return dt + timedelta(days=steps)
    if granularity == "week":
        return dt + timedelta(weeks=steps)
    return _add_months(dt, steps)


def _build_bucket_starts(
    now_utc: datetime,
    granularity: str,
    periods: int,
) -> Tuple[List[datetime], datetime]:
    end_anchor = _period_start(now_utc, granularity)
    starts = [
        _shift_period(end_anchor, granularity, idx - periods + 1)
        for idx in range(periods)
    ]
    end_exclusive = _shift_period(end_anchor, granularity, 1)
    return starts, end_exclusive


def _bucket_label(start: datetime, granularity: str) -> str:
    if granularity == "day":
        return start.strftime("%m-%d")
    if granularity == "week":
        week_num = int(start.strftime("%W")) + 1
        return f"{start.year}-W{week_num:02d}"
    return start.strftime("%Y-%m")


def _utc_to_local_naive(dt_utc: datetime, tz_offset_minutes: int) -> datetime:
    """将 UTC 时间转换为“浏览器本地”时间（naive）。"""
    return dt_utc - timedelta(minutes=tz_offset_minutes)


def _local_naive_to_utc(dt_local: datetime, tz_offset_minutes: int) -> datetime:
    """将“浏览器本地”时间（naive）转换回 UTC 时间。"""
    return dt_local + timedelta(minutes=tz_offset_minutes)


def _count_events_by_bucket(
    event_rows: Iterable[Tuple[int, Optional[datetime | str]]],
    *,
    granularity: str,
    bucket_starts: List[datetime],
    range_start: datetime,
    range_end: datetime,
    tz_offset_minutes: int,
) -> Tuple[List[int], int]:
    counts = [0 for _ in bucket_starts]
    baseline = 0
    idx_map = {start: idx for idx, start in enumerate(bucket_starts)}

    for _, raw_dt in event_rows:
        event_dt_utc = _to_naive_utc(raw_dt)
        if event_dt_utc is None:
            continue
        event_dt_local = _utc_to_local_naive(event_dt_utc, tz_offset_minutes)

        if event_dt_local < range_start:
            baseline += 1
            continue
        if event_dt_local >= range_end:
            continue

        bucket_start = _period_start(event_dt_local, granularity)
        bucket_idx = idx_map.get(bucket_start)
        if bucket_idx is not None:
            counts[bucket_idx] += 1

    return counts, baseline


def _empty_device_progress_bucket() -> Dict[str, int]:
    return {"sites": 0, "numerator": 0, "denominator": 0}


def _normalize_site_ids(site_ids: Optional[Iterable[int]]) -> Optional[set[int]]:
    if site_ids is None:
        return None
    normalized: set[int] = set()
    for raw_site_id in site_ids:
        try:
            normalized.add(int(raw_site_id))
        except (TypeError, ValueError):
            continue
    return normalized


def _build_site_device_progress_metrics(
    db: Session,
    *,
    site_ids: Optional[Iterable[int]] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    设备分数按开站阶段有效设备位计算。

    summarize_site_binding_slots(opening_only=True) 会优先使用开站检查项里的原始设备位作为分母，
    避免小区扩容合并当前 LLD 后把开站交付进度从 3/3 拉成 3/6。
    """
    requested_site_ids = _normalize_site_ids(site_ids)
    if requested_site_ids is not None and not requested_site_ids:
        return {}

    site_query = db.query(Site.id)
    if requested_site_ids is not None:
        site_query = site_query.filter(Site.id.in_(sorted(requested_site_ids)))

    site_id_rows = [int(site_id) for site_id, in site_query.all()]
    binding_summaries = summarize_site_binding_slots_for_sites(
        db,
        site_id_rows,
        opening_only=True,
    )

    metrics: Dict[int, Dict[str, Any]] = {}
    all_sns: set[str] = set()

    for site_id in site_id_rows:
        binding_summary = binding_summaries.get(site_id) or {}
        slot_check_required = bool(binding_summary.get("slot_check_required"))
        expected_slot_count = int(binding_summary.get("expected_slot_count") or 0)
        bound_slot_count = int(binding_summary.get("bound_slot_count") or 0)
        denominator = expected_slot_count if slot_check_required else bound_slot_count

        rows = list(binding_summary.get("rows") or [])
        slot_sns = [
            sn
            for row in rows
            for sn in [str(getattr(row, "equipment_sn", "") or "").strip()]
            if sn
        ]
        if denominator <= 0:
            denominator = len(slot_sns)

        metrics[int(site_id)] = {
            "denominator": denominator,
            "slot_sns": slot_sns,
            "online_devices": 0,
            "activated_devices": 0,
        }
        all_sns.update(slot_sns)

    state_map: Dict[str, OmcDeviceState] = {}
    if all_sns:
        state_map = {
            state.sn: state
            for state in db.query(OmcDeviceState)
            .filter(OmcDeviceState.sn.in_(sorted(all_sns)))
            .all()
        }

    for info in metrics.values():
        slot_sns = list(info["slot_sns"] or [])
        info["online_devices"] = sum(
            1 for sn in slot_sns if bool(getattr(state_map.get(sn), "ever_online", False))
        )
        info["activated_devices"] = sum(
            1 for sn in slot_sns if bool(getattr(state_map.get(sn), "ever_activated", False))
        )

    return metrics


def _aggregate_site_device_progress(
    metrics: Dict[int, Dict[str, Any]],
    *,
    fully_online_site_ids: Iterable[int],
    fully_activated_site_ids: Iterable[int],
    site_ids: Optional[Iterable[int]] = None,
) -> Dict[str, Dict[str, int]]:
    """按站点集合汇总部分/完全上线激活站点数与设备分数。"""
    scope_ids = _normalize_site_ids(site_ids)
    if scope_ids is None:
        scope_ids = set(metrics.keys())

    fully_online_ids = (_normalize_site_ids(fully_online_site_ids) or set()) & scope_ids
    fully_activated_ids = (_normalize_site_ids(fully_activated_site_ids) or set()) & scope_ids

    result = {
        "partial_online": _empty_device_progress_bucket(),
        "fully_online": _empty_device_progress_bucket(),
        "partial_activated": _empty_device_progress_bucket(),
        "fully_activated": _empty_device_progress_bucket(),
    }
    result["fully_online"]["sites"] = len(fully_online_ids)
    result["fully_activated"]["sites"] = len(fully_activated_ids)

    def add_fraction(bucket: str, numerator: int, denominator: int) -> None:
        result[bucket]["numerator"] += int(numerator)
        result[bucket]["denominator"] += int(denominator)

    def add_partial(bucket: str, numerator: int, denominator: int) -> None:
        result[bucket]["sites"] += 1
        add_fraction(bucket, numerator, denominator)

    for site_id in scope_ids:
        info = metrics.get(site_id)
        if not info:
            continue
        denominator = int(info["denominator"] or 0)
        if denominator <= 0:
            continue

        online_devices = int(info["online_devices"] or 0)
        activated_devices = int(info["activated_devices"] or 0)

        if site_id in fully_online_ids:
            add_fraction("fully_online", online_devices, denominator)
        elif 0 < online_devices < denominator:
            add_partial("partial_online", online_devices, denominator)

        if site_id in fully_activated_ids:
            add_fraction("fully_activated", activated_devices, denominator)
        elif 0 < activated_devices < denominator:
            add_partial("partial_activated", activated_devices, denominator)

    return result


def _build_site_device_progress(
    db: Session,
    *,
    fully_online_site_ids: Iterable[int],
    fully_activated_site_ids: Iterable[int],
) -> Dict[str, Dict[str, int]]:
    """
    汇总 dashboard 站点卡片下方的设备分数。

    站点“完全上线/完全激活”继续沿用 site_progress_snapshots 的口径；
    设备分数和“部分”统计按开站阶段有效设备位计算。
    """
    metrics = _build_site_device_progress_metrics(db)
    return _aggregate_site_device_progress(
        metrics,
        fully_online_site_ids=fully_online_site_ids,
        fully_activated_site_ids=fully_activated_site_ids,
    )


def _empty_cell_expansion_progress() -> Dict[str, Any]:
    return {
        "visible": False,
        "orders": {"total": 0, "active": 0, "completed": 0},
        "sites": {"total": 0, "active": 0, "completed": 0},
        "new_cells": {"total": 0},
        "new_devices": {"total": 0, "bound": 0, "online": 0, "activated": 0},
        "online": {"partial_sites": 0, "full_sites": 0},
        "activated": {"partial_sites": 0, "full_sites": 0},
    }


def _cell_expansion_cell_count(work_order: WorkOrder, target_slot_count: int) -> int:
    extra = work_order.extra_data or {}
    raw_count = extra.get("new_cell_count")
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = 0
    if count > 0:
        return count
    target_cells = extra.get("new_cells") or extra.get("expansion_targets") or []
    if isinstance(target_cells, list) and target_cells:
        return len(target_cells)
    return int(target_slot_count or 0)


def _site_bound_slot_map(db: Session, site_id: int) -> Dict[Tuple[str, str], Any]:
    rows = [
        row
        for row in get_bound_slot_rows_for_site(db, site_id, opening_only=False)
        if row.action != BindingActionEnum.UNBIND and str(row.equipment_sn or "").strip()
    ]
    slot_map: Dict[Tuple[str, str], Any] = {}
    for row in rows:
        sector_id = str(row.sector_id or "").strip()
        band = str(row.band or "").strip().upper()
        if sector_id and band:
            slot_map[(sector_id, band)] = row
    return slot_map


def _build_cell_expansion_progress(db: Session) -> Dict[str, Any]:
    work_orders = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.type == WorkOrderTypeEnum.CELL_EXPANSION,
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
        )
        .all()
    )
    if not work_orders:
        return _empty_cell_expansion_progress()

    site_slot_maps: Dict[int, Dict[Tuple[str, str], Any]] = {}
    order_metrics: List[Dict[str, int]] = []
    all_sns: set[str] = set()

    total_new_cells = 0
    total_new_devices = 0
    total_bound_devices = 0

    for work_order in work_orders:
        target_slots = get_expansion_target_slots_from_work_order(work_order)
        expected_count = len(target_slots)
        total_new_cells += _cell_expansion_cell_count(work_order, expected_count)
        total_new_devices += expected_count

        slot_map = site_slot_maps.get(work_order.site_id)
        if slot_map is None:
            slot_map = _site_bound_slot_map(db, work_order.site_id)
            site_slot_maps[work_order.site_id] = slot_map

        sns: List[str] = []
        for slot in target_slots:
            row = slot_map.get(slot)
            sn = str(getattr(row, "equipment_sn", "") or "").strip() if row else ""
            if not sn:
                continue
            sns.append(sn)
            all_sns.add(sn)

        bound_count = len(sns)
        total_bound_devices += bound_count
        order_metrics.append(
            {
                "site_id": int(work_order.site_id),
                "expected": expected_count,
                "bound": bound_count,
                "online": 0,
                "activated": 0,
            }
        )

    state_map: Dict[str, OmcDeviceState] = {}
    if all_sns:
        state_map = {
            state.sn: state
            for state in db.query(OmcDeviceState)
            .filter(OmcDeviceState.sn.in_(sorted(all_sns)))
            .all()
        }

    total_online_devices = 0
    total_activated_devices = 0
    partial_online_sites: set[int] = set()
    full_online_sites: set[int] = set()
    partial_activated_sites: set[int] = set()
    full_activated_sites: set[int] = set()

    for metric, work_order in zip(order_metrics, work_orders):
        target_slots = get_expansion_target_slots_from_work_order(work_order)
        slot_map = site_slot_maps.get(work_order.site_id) or {}
        sns = [
            str(getattr(slot_map.get(slot), "equipment_sn", "") or "").strip()
            for slot in target_slots
            if slot_map.get(slot) and str(getattr(slot_map.get(slot), "equipment_sn", "") or "").strip()
        ]
        online_count = sum(
            1 for sn in sns if bool(getattr(state_map.get(sn), "ever_online", False))
        )
        activated_count = sum(
            1 for sn in sns if bool(getattr(state_map.get(sn), "ever_activated", False))
        )
        expected_count = int(metric["expected"] or 0)
        metric["online"] = online_count
        metric["activated"] = activated_count
        total_online_devices += online_count
        total_activated_devices += activated_count

        if expected_count <= 0:
            continue
        if online_count >= expected_count:
            full_online_sites.add(int(work_order.site_id))
        elif online_count > 0:
            partial_online_sites.add(int(work_order.site_id))
        if activated_count >= expected_count:
            full_activated_sites.add(int(work_order.site_id))
        elif activated_count > 0:
            partial_activated_sites.add(int(work_order.site_id))

    active_orders = [wo for wo in work_orders if wo.status in _EXPANSION_ACTIVE_STATUSES]
    completed_orders = [wo for wo in work_orders if wo.status == WorkOrderStatusEnum.COMPLETED]

    return {
        "visible": True,
        "orders": {
            "total": len(work_orders),
            "active": len(active_orders),
            "completed": len(completed_orders),
        },
        "sites": {
            "total": len({int(wo.site_id) for wo in work_orders}),
            "active": len({int(wo.site_id) for wo in active_orders}),
            "completed": len({int(wo.site_id) for wo in completed_orders}),
        },
        "new_cells": {"total": total_new_cells},
        "new_devices": {
            "total": total_new_devices,
            "bound": total_bound_devices,
            "online": total_online_devices,
            "activated": total_activated_devices,
        },
        "online": {
            "partial_sites": len(partial_online_sites - full_online_sites),
            "full_sites": len(full_online_sites),
        },
        "activated": {
            "partial_sites": len(partial_activated_sites - full_activated_sites),
            "full_sites": len(full_activated_sites),
        },
    }


@router.get("/summary")
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """仪表盘聚合汇总。

    返回字段设计与前端 Phase 1 保持兼容：
    - work_orders: { total, status }
    - users: { total, active } （非管理员时置为 null）
    - inventory: { low_stock_count, main_device_total_stock, recent_transactions }
    - installed_sites: { count, node }
    - sites: { approx: false, status }
    - site_progress: { total, survey_done, planning_done, install_started, installed, online, activated,
      partial_online, fully_online, partial_activated, fully_activated, device_progress, ssv_passed }
    - cell_expansion_progress: 独立的小区扩容新增设备进度，不混入开站交付概况
    - inspections: { pending_review_count }
    - surveys: { last7d_new }
    - time_range: { from, to }
    """

    # 工单统计
    total_work_orders = db.query(func.count(WorkOrder.id)).scalar() or 0
    status_rows = db.query(WorkOrder.status, func.count(WorkOrder.id)).group_by(WorkOrder.status).all()
    work_order_status = {s.value if hasattr(s, 'value') else str(s): int(c) for s, c in status_rows}

    # 用户统计（仅管理员/经理）
    users_total = None
    users_active = None
    if user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["users:list:read"],
    ):
        users_total = db.query(func.count(UserModel.id)).scalar() or 0
        users_active = db.query(func.count(UserModel.id)).filter(UserModel.is_active == True).scalar() or 0

    # 库存汇总
    low_stock_count = db.query(func.count(Inventory.id)).filter(Inventory.current_stock <= Inventory.min_stock).scalar() or 0
    main_device_total_stock = db.query(func.sum(Inventory.current_stock)).join(Equipment).filter(Equipment.category == "main_device").scalar() or 0
    recent_transactions = db.query(StockTransaction).order_by(desc(StockTransaction.operation_time)).limit(5).all()
    transactions_data = [{
        "id": t.id,
        "type": t.transaction_type,
        "document_number": t.document_number,
        "operator_name": t.operator.full_name if t.operator else None,
        "operation_time": to_utc_iso(t.operation_time) if t.operation_time else None,
        "total_quantity": t.total_quantity,
    } for t in recent_transactions]

    # 站点状态统计（精准）
    site_rows = db.query(Site.status, func.count(Site.id)).group_by(Site.status).all()
    site_status = {str(s or "unknown"): int(c) for s, c in site_rows}

    ensure_result = ensure_site_progress_snapshots(db, reason="dashboard_summary_read")
    if ensure_result["rebuilt_site_ids"]:
        db.commit()
    metric_mode = get_site_progress_metric_mode(db)
    install_started_rows = get_site_progress_rows(db, "install_started")
    install_completed_rows = get_site_progress_rows(db, "install_completed")
    online_rows = get_site_progress_rows(db, "online", metric_mode=metric_mode)
    activated_rows = get_site_progress_rows(db, "activated", metric_mode=metric_mode)
    ssv_rows = get_site_progress_rows(db, "ssv")

    install_started_site_count = len(install_started_rows)
    installed_site_count = len(install_completed_rows)

    # 检查待审统计
    pending_review_count = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status.in_([InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW])
    ).scalar() or 0

    # 勘察近7日
    end = datetime.utcnow()
    start = end - timedelta(days=7)
    from app.models.survey import SiteSurvey
    surveys_last7d = db.query(func.count(SiteSurvey.id)).filter(
        SiteSurvey.created_at >= start,
        SiteSurvey.created_at <= end
    ).scalar() or 0

    # 站点进度统计（精确计算）
    def count_with_status(statuses) -> int:
        return int(
            db.query(func.count(Site.id)).filter(Site.status.in_(statuses)).scalar() or 0
        )

    total_sites = int(db.query(func.count(Site.id)).scalar() or 0)
    survey_done = int(db.query(func.count(func.distinct(SiteSurveyArchive.site_id))).scalar() or 0)
    planning_done = count_with_status([
        "planned", "construction", "pending_online", "online_pending_activation", "operational", "maintenance"
    ])
    online = len(online_rows)
    activated = len(activated_rows)
    ssv_passed_cnt = len(ssv_rows)
    online_site_ids = [int(site_id) for site_id, _ in online_rows]
    activated_site_ids = [int(site_id) for site_id, _ in activated_rows]
    device_progress = _build_site_device_progress(
        db,
        fully_online_site_ids=online_site_ids,
        fully_activated_site_ids=activated_site_ids,
    )

    site_progress: Dict[str, Any] = {
        "total": total_sites,
        "survey_done": survey_done,
        "planning_done": planning_done,
        "install_started": install_started_site_count,
        "installed": installed_site_count,
        # 兼容旧前端字段；新 dashboard 使用 fully_* 命名展示。
        "online": online,
        "activated": activated,
        "partial_online": device_progress["partial_online"]["sites"],
        "fully_online": online,
        "partial_activated": device_progress["partial_activated"]["sites"],
        "fully_activated": activated,
        "device_progress": device_progress,
        "ssv_passed": ssv_passed_cnt,
        "metric_mode": metric_mode,
    }

    return {
        "work_orders": {"total": int(total_work_orders), "status": work_order_status},
        "users": {"total": users_total, "active": users_active},
        "inventory": {
            "low_stock_count": int(low_stock_count),
            "main_device_total_stock": int(main_device_total_stock or 0),
            "recent_transactions": transactions_data,
        },
        "installed_sites": {
            "count": installed_site_count,
            "node": "submitted_or_later",
        },
        "sites": {"approx": False, "status": site_status},
        "site_progress": site_progress,
        "cell_expansion_progress": _build_cell_expansion_progress(db),
        "inspections": {"pending_review_count": int(pending_review_count)},
        "surveys": {"last7d_new": int(surveys_last7d)},
        "time_range": {"from": to_utc_iso(start), "to": to_utc_iso(end)},
    }


@router.get("/install-progress-breakdown")
async def get_install_progress_breakdown(
    category_id: Optional[int] = Query(None, description="站点分组维度 ID；为空时使用默认维度"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按站点分组维度查看安装进度。

    这是通用分组统计：TDD/FDD 只是某个项目在“交付范围”维度下的选项。
    """
    _ = current_user
    categories = get_active_group_categories(db)
    if not categories:
        return {
            "categories": [],
            "category": None,
            "metric_mode": get_site_progress_metric_mode(db),
            "rows": [],
            "totals": {
                "total": 0,
                "install_started": 0,
                "installed": 0,
                "not_installed": 0,
                "partial_online": 0,
                "fully_online": 0,
                "online": 0,
                "partial_activated": 0,
                "fully_activated": 0,
                "activated": 0,
                "device_progress": {
                    "partial_online": _empty_device_progress_bucket(),
                    "fully_online": _empty_device_progress_bucket(),
                    "partial_activated": _empty_device_progress_bucket(),
                    "fully_activated": _empty_device_progress_bucket(),
                },
                "ssv": 0,
            },
        }

    selected_category: Optional[SiteGroupCategory] = None
    if category_id:
        selected_category = (
            db.query(SiteGroupCategory)
            .filter(
                SiteGroupCategory.id == category_id,
                SiteGroupCategory.is_active == True,
            )
            .first()
        )
        if selected_category is None:
            raise HTTPException(status_code=404, detail="分组维度不存在")
    else:
        selected_category = get_default_group_category(db)

    if selected_category is None:
        raise HTTPException(status_code=404, detail="分组维度不存在")

    ensure_result = ensure_site_progress_snapshots(db, reason="dashboard_install_progress_breakdown_read")
    if ensure_result["rebuilt_site_ids"]:
        db.commit()

    metric_mode = get_site_progress_metric_mode(db)
    online_field = resolve_site_progress_field_name("online", metric_mode=metric_mode)
    activated_field = resolve_site_progress_field_name("activated", metric_mode=metric_mode)
    online_col = getattr(SiteProgressSnapshot, online_field)
    activated_col = getattr(SiteProgressSnapshot, activated_field)

    site_rows = (
        db.query(
            Site.id.label("site_id"),
            SiteGroupOption.id.label("option_id"),
            SiteGroupOption.code.label("option_code"),
            SiteGroupOption.name.label("option_name"),
            SiteGroupOption.color.label("option_color"),
            SiteGroupOption.sort_order.label("sort_order"),
            SiteProgressSnapshot.install_started_at.label("install_started_at"),
            SiteProgressSnapshot.install_completed_at.label("install_completed_at"),
            online_col.label("online_at"),
            activated_col.label("activated_at"),
            SiteProgressSnapshot.ssv_at.label("ssv_at"),
        )
        .outerjoin(
            SiteGroupAssignment,
            and_(
                SiteGroupAssignment.site_id == Site.id,
                SiteGroupAssignment.category_id == selected_category.id,
            ),
        )
        .outerjoin(SiteGroupOption, SiteGroupOption.id == SiteGroupAssignment.option_id)
        .outerjoin(SiteProgressSnapshot, SiteProgressSnapshot.site_id == Site.id)
        .all()
    )

    groups: Dict[Optional[int], Dict[str, Any]] = {}
    fully_online_site_ids: set[int] = set()
    fully_activated_site_ids: set[int] = set()

    for row in site_rows:
        site_id = int(row.site_id)
        option_id = row.option_id
        group = groups.get(option_id)
        if group is None:
            group = {
                "option_id": option_id,
                "option_code": row.option_code or "unassigned",
                "option_name": row.option_name or "未分组",
                "option_color": row.option_color,
                "sort_order": int(row.sort_order or 999999),
                "site_ids": [],
                "total": 0,
                "install_started": 0,
                "installed": 0,
                "online": 0,
                "activated": 0,
                "ssv": 0,
                "filter": {
                    "group_category_id": selected_category.id,
                    "group_option_id": option_id,
                    "group_unassigned": option_id is None,
                },
            }
            groups[option_id] = group

        group["site_ids"].append(site_id)
        group["total"] += 1
        if row.install_started_at is not None:
            group["install_started"] += 1
        if row.install_completed_at is not None:
            group["installed"] += 1
        if row.online_at is not None:
            group["online"] += 1
            fully_online_site_ids.add(site_id)
        if row.activated_at is not None:
            group["activated"] += 1
            fully_activated_site_ids.add(site_id)
        if row.ssv_at is not None:
            group["ssv"] += 1

    device_metrics = _build_site_device_progress_metrics(
        db,
        site_ids=[int(row.site_id) for row in site_rows],
    )

    rows = []
    for group in groups.values():
        total = int(group["total"] or 0)
        installed = int(group["installed"] or 0)
        site_ids = list(group.pop("site_ids", []))
        device_progress = _aggregate_site_device_progress(
            device_metrics,
            fully_online_site_ids=fully_online_site_ids,
            fully_activated_site_ids=fully_activated_site_ids,
            site_ids=site_ids,
        )
        group["not_installed"] = max(total - installed, 0)
        group["partial_online"] = device_progress["partial_online"]["sites"]
        group["fully_online"] = int(group["online"] or 0)
        group["partial_activated"] = device_progress["partial_activated"]["sites"]
        group["fully_activated"] = int(group["activated"] or 0)
        group["device_progress"] = device_progress
        group["completion_rate"] = round((installed / total) * 100, 2) if total else 0
        rows.append(group)

    rows.sort(key=lambda item: (item["option_id"] is None, item["sort_order"], item["option_name"]))
    totals_device_progress = {
        key: {
            "sites": sum(item["device_progress"][key]["sites"] for item in rows),
            "numerator": sum(item["device_progress"][key]["numerator"] for item in rows),
            "denominator": sum(item["device_progress"][key]["denominator"] for item in rows),
        }
        for key in ["partial_online", "fully_online", "partial_activated", "fully_activated"]
    }
    totals = {
        "total": sum(item["total"] for item in rows),
        "install_started": sum(item["install_started"] for item in rows),
        "installed": sum(item["installed"] for item in rows),
        "not_installed": sum(item["not_installed"] for item in rows),
        "partial_online": sum(item["partial_online"] for item in rows),
        "fully_online": sum(item["fully_online"] for item in rows),
        "online": sum(item["online"] for item in rows),
        "partial_activated": sum(item["partial_activated"] for item in rows),
        "fully_activated": sum(item["fully_activated"] for item in rows),
        "activated": sum(item["activated"] for item in rows),
        "device_progress": totals_device_progress,
        "ssv": sum(item["ssv"] for item in rows),
    }

    return {
        "categories": serialize_categories(categories),
        "category": serialize_category(selected_category),
        "metric_mode": metric_mode,
        "rows": rows,
        "totals": totals,
    }


@router.get("/site-progress-trend")
async def get_site_progress_trend(
    granularity: str = Query("day", description="时间粒度：day/week/month"),
    periods: Optional[int] = Query(None, ge=1, description="时间粒度对应的周期数"),
    tz_offset_minutes: int = Query(
        0,
        ge=-840,
        le=840,
        description="浏览器本地时区偏移（分钟），直接使用 JS Date.getTimezoneOffset()",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    仪表盘站点阶段趋势。

    事件口径（按站点“首次发生时间”统计）：
    - install_started: 有效开站工单关联下的设备首次 bind/rebind
    - install_completed: 有效开站工单首次 submitted_at
    - online: 根据全局口径开关读取“流程口径 activated_at”或“设备事实口径 first_online_at(max)”
    - activated: 根据全局口径开关读取“流程口径 completed_at”或“设备事实口径 first_activated_at(max)”
    - ssv: 有效 SSV 工单首次 completed_at

    统计直接读取站点生命周期快照；当快照不存在时会自动补建。

    返回每周期新增（incremental）以及区间前基线（baseline），前端可切换“新增/累计”。
    """
    _ = current_user

    g = str(granularity or "day").strip().lower()
    if g not in _TREND_GRANULARITIES:
        raise HTTPException(status_code=400, detail="granularity 仅支持 day/week/month")

    default_periods = _TREND_DEFAULT_PERIODS[g]
    max_periods = _TREND_MAX_PERIODS[g]
    safe_periods = int(periods or default_periods)
    if safe_periods > max_periods:
        raise HTTPException(
            status_code=400,
            detail=f"{g} 粒度最多支持 {max_periods} 个周期",
        )

    now_local = _utc_to_local_naive(datetime.utcnow(), tz_offset_minutes)
    bucket_starts, range_end = _build_bucket_starts(now_local, g, safe_periods)
    range_start = bucket_starts[0]

    ensure_result = ensure_site_progress_snapshots(db, reason="dashboard_trend_read")
    if ensure_result["rebuilt_site_ids"]:
        db.commit()
    metric_mode = get_site_progress_metric_mode(db)
    install_started_rows = get_site_progress_rows(db, "install_started")
    install_completed_rows = get_site_progress_rows(db, "install_completed")
    online_rows = get_site_progress_rows(db, "online", metric_mode=metric_mode)
    activated_rows = get_site_progress_rows(db, "activated", metric_mode=metric_mode)
    ssv_rows = get_site_progress_rows(db, "ssv")

    install_started_counts, install_started_baseline = _count_events_by_bucket(
        install_started_rows,
        granularity=g,
        bucket_starts=bucket_starts,
        range_start=range_start,
        range_end=range_end,
        tz_offset_minutes=tz_offset_minutes,
    )
    install_completed_counts, install_completed_baseline = _count_events_by_bucket(
        install_completed_rows,
        granularity=g,
        bucket_starts=bucket_starts,
        range_start=range_start,
        range_end=range_end,
        tz_offset_minutes=tz_offset_minutes,
    )
    online_counts, online_baseline = _count_events_by_bucket(
        online_rows,
        granularity=g,
        bucket_starts=bucket_starts,
        range_start=range_start,
        range_end=range_end,
        tz_offset_minutes=tz_offset_minutes,
    )
    activated_counts, activated_baseline = _count_events_by_bucket(
        activated_rows,
        granularity=g,
        bucket_starts=bucket_starts,
        range_start=range_start,
        range_end=range_end,
        tz_offset_minutes=tz_offset_minutes,
    )
    ssv_counts, ssv_baseline = _count_events_by_bucket(
        ssv_rows,
        granularity=g,
        bucket_starts=bucket_starts,
        range_start=range_start,
        range_end=range_end,
        tz_offset_minutes=tz_offset_minutes,
    )

    buckets = [
        {
            "start_at": to_utc_iso(_local_naive_to_utc(start, tz_offset_minutes)),
            "end_at": to_utc_iso(_local_naive_to_utc(_shift_period(start, g, 1), tz_offset_minutes)),
            "label": _bucket_label(start, g),
        }
        for start in bucket_starts
    ]

    return {
        "granularity": g,
        "periods": safe_periods,
        "metric_mode": metric_mode,
        "tz_offset_minutes": tz_offset_minutes,
        "range": {
            "from": to_utc_iso(_local_naive_to_utc(range_start, tz_offset_minutes)),
            "to": to_utc_iso(_local_naive_to_utc(range_end, tz_offset_minutes)),
        },
        "buckets": buckets,
        "series": {
            "install_started": {
                "label": "安装开始站点",
                "incremental": install_started_counts,
                "baseline": install_started_baseline,
            },
            "install_completed": {
                "label": "安装完成站点",
                "incremental": install_completed_counts,
                "baseline": install_completed_baseline,
            },
            "online": {
                "label": "上线站点",
                "incremental": online_counts,
                "baseline": online_baseline,
            },
            "activated": {
                "label": "激活站点",
                "incremental": activated_counts,
                "baseline": activated_baseline,
            },
            "ssv": {
                "label": "SSV站点",
                "incremental": ssv_counts,
                "baseline": ssv_baseline,
            },
        },
    }
