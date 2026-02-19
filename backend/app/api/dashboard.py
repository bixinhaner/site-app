from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import Dict

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user import User as UserModel
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.models.inspection import SiteInspection, InspectionStatusEnum
from app.models.site import Site
from app.models.survey_archive import SiteSurveyArchive
from app.models.equipment import Inventory, Equipment, StockTransaction
from app.utils.timezone import to_utc_iso

router = APIRouter()


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
    - site_progress: { total, survey_done, planning_done, installed, online, activated, ssv_passed }
    - inspections: { pending_review_count }
    - surveys: { last7d_new }
    - time_range: { from, to }
    """

    now = func.now()

    # 工单统计
    total_work_orders = db.query(func.count(WorkOrder.id)).scalar() or 0
    status_rows = db.query(WorkOrder.status, func.count(WorkOrder.id)).group_by(WorkOrder.status).all()
    work_order_status = {s.value if hasattr(s, 'value') else str(s): int(c) for s, c in status_rows}

    # 用户统计（仅管理员/经理）
    users_total = None
    users_active = None
    if current_user.role in ["admin", "manager"]:
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

    # 安装站点统计（按“相片全部提交”节点）：
    # 开站工单已提交（含审核中/已通过/已开通），且站点未进入已激活运行。
    installed_site_count = int(
        db.query(func.count(func.distinct(WorkOrder.site_id)))
        .join(Site, Site.id == WorkOrder.site_id)
        .filter(
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status.in_(
                [
                    WorkOrderStatusEnum.SUBMITTED,
                    WorkOrderStatusEnum.UNDER_REVIEW,
                    WorkOrderStatusEnum.APPROVED,
                    WorkOrderStatusEnum.ACTIVATED,
                ]
            ),
            or_(Site.status.is_(None), Site.status.notin_(["operational", "maintenance"])),
        )
        .scalar()
        or 0
    )

    # 检查待审统计
    pending_review_count = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status.in_([InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW])
    ).scalar() or 0

    # 勘察近7日
    from datetime import datetime, timedelta
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
            "node": "submitted",
        },
        "sites": {"approx": False, "status": site_status},
        "site_progress": site_progress,
        "inspections": {"pending_review_count": int(pending_review_count)},
        "surveys": {"last7d_new": int(surveys_last7d)},
        "time_range": {"from": to_utc_iso(start), "to": to_utc_iso(end)},
    }
