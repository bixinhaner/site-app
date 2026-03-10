from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user import User as UserModel
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.models.inspection import SiteInspection, InspectionStatusEnum
from app.models.site import Site
from app.models.survey_archive import SiteSurveyArchive
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.equipment import Inventory, Equipment, StockTransaction
from app.services.authz_service import user_has_any_role_or_permission
from app.utils.timezone import to_utc_iso

router = APIRouter()

_TREND_GRANULARITIES = {"day", "week", "month"}
_TREND_DEFAULT_PERIODS = {"day": 30, "week": 12, "month": 12}
_TREND_MAX_PERIODS = {"day": 180, "week": 104, "month": 60}


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
    - site_progress: { total, survey_done, planning_done, install_started, installed, online, activated, ssv_passed }
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

    # 安装开始站点统计（按“首次开始绑定设备SN”口径）：
    # 只要站点出现过 bind/rebind 记录即记为已开始，按站点去重统计。
    install_started_site_count = int(
        db.query(func.count(func.distinct(EquipmentBindingHistory.site_id)))
        .filter(
            EquipmentBindingHistory.action.in_(
                [BindingActionEnum.BIND, BindingActionEnum.REBIND]
            )
        )
        .scalar()
        or 0
    )

    # 安装完成站点统计（按“相片全部提交”节点）：
    # 开站工单达到已提交及以上阶段（含已完成），按站点去重统计。
    installed_site_count = int(
        db.query(func.count(func.distinct(WorkOrder.site_id)))
        .filter(
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status.in_(
                [
                    WorkOrderStatusEnum.SUBMITTED,
                    WorkOrderStatusEnum.UNDER_REVIEW,
                    WorkOrderStatusEnum.APPROVED,
                    WorkOrderStatusEnum.ACTIVATED,
                    WorkOrderStatusEnum.COMPLETED,
                ]
            ),
        )
        .scalar()
        or 0
    )

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
    online = count_with_status(["pending_online", "online_pending_activation", "operational", "maintenance"])
    activated = count_with_status(["operational", "maintenance"])
    ssv_passed_cnt = int(db.query(func.count(Site.id)).filter(Site.ssv_passed == True).scalar() or 0)

    site_progress: Dict[str, int] = {
        "total": total_sites,
        "survey_done": survey_done,
        "planning_done": planning_done,
        "install_started": install_started_site_count,
        "installed": installed_site_count,
        "online": online,
        "activated": activated,
        "ssv_passed": ssv_passed_cnt,
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
        "inspections": {"pending_review_count": int(pending_review_count)},
        "surveys": {"last7d_new": int(surveys_last7d)},
        "time_range": {"from": to_utc_iso(start), "to": to_utc_iso(end)},
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
    - install_started: 设备绑定历史首次 bind/rebind
    - install_completed: 开站工单首次 submitted_at
    - online: 开站工单首次 activated_at
    - activated: 开站工单首次 completed_at
    - ssv: SSV 工单首次 completed_at

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

    opening_filter = (
        WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
        WorkOrder.site_id.isnot(None),
        WorkOrder.status != WorkOrderStatusEnum.VOIDED,
    )

    install_started_rows = (
        db.query(
            EquipmentBindingHistory.site_id,
            func.min(EquipmentBindingHistory.operated_at).label("event_at"),
        )
        .filter(
            EquipmentBindingHistory.site_id.isnot(None),
            EquipmentBindingHistory.action.in_([BindingActionEnum.BIND, BindingActionEnum.REBIND]),
        )
        .group_by(EquipmentBindingHistory.site_id)
        .all()
    )
    install_completed_rows = (
        db.query(
            WorkOrder.site_id,
            func.min(WorkOrder.submitted_at).label("event_at"),
        )
        .filter(
            *opening_filter,
            WorkOrder.submitted_at.isnot(None),
        )
        .group_by(WorkOrder.site_id)
        .all()
    )
    online_rows = (
        db.query(
            WorkOrder.site_id,
            func.min(WorkOrder.activated_at).label("event_at"),
        )
        .filter(
            *opening_filter,
            WorkOrder.activated_at.isnot(None),
        )
        .group_by(WorkOrder.site_id)
        .all()
    )
    activated_rows = (
        db.query(
            WorkOrder.site_id,
            func.min(WorkOrder.completed_at).label("event_at"),
        )
        .filter(
            *opening_filter,
            WorkOrder.completed_at.isnot(None),
        )
        .group_by(WorkOrder.site_id)
        .all()
    )
    ssv_rows = (
        db.query(
            WorkOrder.site_id,
            func.min(WorkOrder.completed_at).label("event_at"),
        )
        .filter(
            WorkOrder.type == WorkOrderTypeEnum.SSV,
            WorkOrder.site_id.isnot(None),
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
            WorkOrder.completed_at.isnot(None),
        )
        .group_by(WorkOrder.site_id)
        .all()
    )

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
