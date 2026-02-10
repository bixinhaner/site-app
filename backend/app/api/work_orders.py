from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime
import uuid
import json

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.work_order import (
    WorkOrder,
    WorkOrderItem,
    WorkOrderStatusEnum,
    WorkOrderTypeEnum,
    WorkOrderPriorityEnum,
    AuditEvent,
)
from app.models.inspection import (
    SiteInspection,
    InspectionStatusEnum,
    InspectionTypeEnum,
    InspectionTemplate,
    InspectionCheckItem,
    InspectionPhoto,
    CheckItemStatusEnum,
)
from app.models.survey import SiteSurvey, SiteSurveyPhoto
from app.models.survey_archive import SiteSurveyArchive
from app.models.opening_archive import SiteOpeningArchive
from app.models.ssv_archive import SiteSSVArchive
from app.models.equipment import StockTransaction, PickupRecord
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
    WorkOrderItemUpdate,
    WorkOrderItemResponse,
    WorkOrderStatusChangeRequest,
    WorkOrderReviewRequest,
    WorkOrderReviewCommentsI18nUpdateRequest,
    WorkOrderOmcManualConfirmRequest,
    ItemReviewRequest,
    ReviewSummary,
    WorkOrderBatchOperation,
    WorkOrderSearchParams,
    WorkOrderListResponse,
)
from app.services.template_resolver import create_resolver, ResolveContext
from app.services.work_order_sync import get_work_order_sync_service
from app.utils.field_validator import FieldValidator
from app.schemas.inspection_enhanced import FieldDefinition
from app.services.omc_monitor import (
    run_omc_check_for_work_order,
    advance_opening_work_orders_by_ever,
    advance_replacement_work_orders_by_ever,
)
from app.services.omc_client import get_omc_manual_confirm_enabled
from app.services.omc_state import get_bound_sns_for_site, upsert_omc_device_state
from app.utils.timezone import to_utc_iso

router = APIRouter()


# 站点状态自动更新辅助函数
def _audit_site_status_change(db: Session, site_id: int, old_status: str, new_status: str, reason: str):
    """记录站点状态变更的审计日志"""
    try:
        # 获取系统管理员用户ID（用于系统自动操作）
        admin_user = db.query(User).filter(User.username == "admin").first()
        operator_id = admin_user.id if admin_user else 1
        
        audit_log = AuditEvent(
            id=str(uuid.uuid4()),
            resource_type="site",
            resource_id=str(site_id),
            action="status_change",
            operator_id=operator_id,  # 使用系统管理员ID
            from_status=old_status,
            to_status=new_status,
            comments=f"系统自动更新: {reason}",
            details={"reason": reason, "old_status": old_status, "new_status": new_status}
        )
        db.add(audit_log)
    except Exception as e:
        print(f"[警告] 记录站点状态变更审计日志失败: {e}")


# Role helpers
def _is_field_worker(u: User) -> bool:
    r = getattr(u, 'role', None)
    return r in ("inspector", "surveyor")


def _is_surveyor(u: User) -> bool:
    return getattr(u, 'role', None) == "surveyor"


def _ensure_surveyor_wo_type(wo: WorkOrder, u: User):
    if _is_surveyor(u) and wo.type != WorkOrderTypeEnum.SITE_SURVEY:
        raise HTTPException(status_code=403, detail="仅可操作勘察工单")


def _has_bound_device_check_items(db: Session, wo: WorkOrder) -> bool:
    """判断工单是否仍存在“设备级”检查项绑定（equipment_sn 未解绑）。

    与库存侧扫码解绑逻辑保持一致：
    - 仅要求“设备级”检查项解绑
    - 设备级定义：sector_id + band 存在，且 cell_id 为空或等于 f"{sector_id}_{band}"
    """
    from sqlalchemy import or_

    inspection_filters = [SiteInspection.work_order_id == wo.id]
    if getattr(wo, "inspection_id", None):
        inspection_filters.append(SiteInspection.id == wo.inspection_id)
    inspection_cond = (
        or_(*inspection_filters) if len(inspection_filters) > 1 else inspection_filters[0]
    )

    device_key_expr = InspectionCheckItem.sector_id + "_" + InspectionCheckItem.band

    exists_row = (
        db.query(InspectionCheckItem.id)
        .join(SiteInspection, InspectionCheckItem.inspection_id == SiteInspection.id)
        .filter(
            inspection_cond,
            InspectionCheckItem.equipment_sn.isnot(None),
            InspectionCheckItem.equipment_sn != "",
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.sector_id != "",
            InspectionCheckItem.band.isnot(None),
            InspectionCheckItem.band != "",
            or_(
                InspectionCheckItem.cell_id.is_(None),
                InspectionCheckItem.cell_id == "",
                InspectionCheckItem.cell_id == device_key_expr,
            ),
        )
        .first()
    )
    return bool(exists_row)


def _detach_stock_records_from_work_order(db: Session, wo: WorkOrder) -> None:
    """解除库存记录与工单的绑定，保留库存数据（A方案）。

    - StockTransaction.work_order_id 可置空
    - PickupRecord.work_order_id 为非空字段：改写为 MANUAL-{picker_id}（与 scan-checkout 的手工领料一致）
    """
    db.query(StockTransaction).filter(StockTransaction.work_order_id == wo.id).update(
        {StockTransaction.work_order_id: None},
        synchronize_session=False,
    )

    pickup_records = db.query(PickupRecord).filter(PickupRecord.work_order_id == wo.id).all()
    for pr in pickup_records:
        pr.work_order_id = f"MANUAL-{pr.picker_id}"


def _touch_inspection_item_and_clear_review(item: InspectionCheckItem, now: datetime) -> bool:
    """检查项内容有变更时：更新时间，并清空该检查项的审核结果（若已审核过）。

    用于实现“驳回后增量复审”：只让变动的检查项回到待审核，未变动的保留原审核结果。
    """
    had_review = (
        item.review_status is not None
        or item.review_comments is not None
        or getattr(item, "review_comments_i18n", None) is not None
        or item.reviewed_by is not None
        or item.reviewed_at is not None
    )
    if had_review:
        item.review_status = None
        item.review_comments = None
        item.review_comments_i18n = None
        item.reviewed_by = None
        item.reviewed_at = None
    item.updated_at = now
    return had_review


def _normalize_category_level(category: dict) -> str:
    """归一化模板分类的检查维度（与 inspections.py 保持一致）。"""
    lt = (category or {}).get("level_type")
    if lt == "cell":
        return "device"
    if lt in ("site", "sector", "device", "cell_earfcn"):
        return lt

    if (category or {}).get("cell_specific"):
        return "device"
    if (category or {}).get("sector_specific"):
        return "sector"
    return "site"


def _template_requires_lld_cells(template_data: dict) -> bool:
    for cat in (template_data or {}).get("check_categories", []) or []:
        if _normalize_category_level(cat) == "cell_earfcn":
            return True
    return False


def _update_site_status_on_work_order_create(db: Session, site_id: int, work_order_type: WorkOrderTypeEnum):
    """
    工单创建时自动更新站点状态
    - 如果是安装工单(opening_inspection)，将站点状态改为construction
    """
    if work_order_type == WorkOrderTypeEnum.OPENING_INSPECTION:
        site = db.query(Site).filter(Site.id == site_id).first()
        # 允许从 planning 或 planned 进入 construction
        if site and site.status in ("planning", "planned"):
            old_status = site.status
            site.status = "construction"
            print(f"[站点状态自动更新] 站点 {site_id} ({site.site_name}) 状态从 {old_status} 更新为 {site.status}")

            # 记录审计日志
            _audit_site_status_change(
                db, site_id, old_status, site.status,
                "创建安装工单，站点进入建设阶段"
            )


def _update_site_status_on_work_order_complete(db: Session, site_id: int, work_order_type: WorkOrderTypeEnum):
    """
    工单完成时自动更新站点状态
    - 如果是安装工单(opening_inspection)完成，将站点状态改为 operational
    """
    # 勘察工单审核通过 -> 站点进入规划阶段
    if work_order_type == WorkOrderTypeEnum.SITE_SURVEY:
        site = db.query(Site).filter(Site.id == site_id).first()
        if site and site.status == "survey_pending":
            old_status = site.status
            site.status = "planning"
            print(f"[站点状态自动更新] 站点 {site_id} ({site.site_name}) 勘察审核通过，状态从 {old_status} 更新为 {site.status}")

            # 审计
            _audit_site_status_change(
                db, site_id, old_status, site.status,
                "勘察工单审核通过，进入规划阶段"
            )

    if work_order_type == WorkOrderTypeEnum.OPENING_INSPECTION:
        site = db.query(Site).filter(Site.id == site_id).first()
        if site and site.status not in ("operational", "maintenance"):
            old_status = site.status
            site.status = "operational"
            print(f"[站点状态自动更新] 站点 {site_id} ({site.site_name}) 安装工单已完成，状态从 {old_status} 更新为 {site.status}")

            # 记录审计日志
            _audit_site_status_change(
                db, site_id, old_status, site.status,
                "安装工单已完成，站点投入运营"
            )


def _get_template_id_from_extra_data(extra_data):
    """从extra_data中安全地提取template_id"""
    default_template_id = "266d3253-13d8-46af-9fd3-f417566428cf"  # 默认维护模板
    
    if not extra_data:
        return default_template_id
    
    try:
        if isinstance(extra_data, str):
            extra_data_dict = json.loads(extra_data)
        else:
            extra_data_dict = extra_data
        
        template_id = extra_data_dict.get("template_id", default_template_id)
        print(f"DEBUG_WO: 从extra_data解析到template_id: {template_id}")
        return template_id
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        print(f"DEBUG_WO: 解析extra_data失败: {e}, 使用默认模板")
        return default_template_id


@router.get("/search", response_model=WorkOrderListResponse)
async def search_work_orders(
    keyword: Optional[str] = Query(None, description="搜索工单标题/描述/站点名称/编码"),
    status: Optional[WorkOrderStatusEnum] = Query(None),
    type: Optional[WorkOrderTypeEnum] = Query(None),
    assigned_to: Optional[int] = Query(None),
    priority: Optional[WorkOrderPriorityEnum] = Query(None),
    site_id: Optional[int] = Query(None),
    sort_by: Optional[str] = Query(
        None,
        description="排序字段: created_at|updated_at|assigned_at|due_date|priority|status|type|site_code|site_name",
    ),
    sort_order: str = Query("desc", description="排序方向: asc|desc"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=100, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """搜索工单（带分页和筛选）"""
    from sqlalchemy import or_, and_
    import math

    # 权限说明：
    # - 现场人员（inspector/surveyor）仅能查看自己的工单；surveyor 仅能查看勘察工单
    # - 其他角色默认可查看全部（与 /api/work-orders 列表接口保持一致）
    is_admin_or_manager = current_user.role in ["admin", "manager"]
    is_field_worker = current_user.role in ["inspector", "surveyor"]

    query = db.query(WorkOrder).join(Site, WorkOrder.site_id == Site.id, isouter=True)

    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                WorkOrder.title.contains(keyword),
                WorkOrder.description.contains(keyword),
                Site.site_name.contains(keyword),
                Site.site_code.contains(keyword)
            )
        )

    # 状态筛选
    if status:
        query = query.filter(WorkOrder.status == status)

    # 类型筛选
    if type:
        query = query.filter(WorkOrder.type == type)

    # 分配人筛选与角色可见范围
    if is_field_worker:
        query = query.filter(WorkOrder.assigned_to == current_user.id)
        if current_user.role == "surveyor":
            query = query.filter(WorkOrder.type == WorkOrderTypeEnum.SITE_SURVEY)
    elif is_admin_or_manager and assigned_to:
        query = query.filter(WorkOrder.assigned_to == assigned_to)

    # 优先级筛选
    if priority and is_admin_or_manager:
        query = query.filter(WorkOrder.priority == priority)

    # 站点筛选
    if site_id:
        query = query.filter(WorkOrder.site_id == site_id)

    # 计算总数
    total = query.count()

    # 分页查询
    allowed_sort_fields = {
        "created_at": WorkOrder.created_at,
        "updated_at": WorkOrder.updated_at,
        "assigned_at": WorkOrder.assigned_at,
        "due_date": WorkOrder.due_date,
        "priority": WorkOrder.priority,
        "status": WorkOrder.status,
        "type": WorkOrder.type,
        "site_code": Site.site_code,
        "site_name": Site.site_name,
    }

    sort_key = (sort_by or "created_at").strip()
    sort_col = allowed_sort_fields.get(sort_key)
    if not sort_col:
        raise HTTPException(status_code=400, detail="不支持的排序字段")

    order = (sort_order or "desc").strip().lower()
    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="不支持的排序方向")

    primary = sort_col.asc() if order == "asc" else sort_col.desc()
    secondary = WorkOrder.id.asc() if order == "asc" else WorkOrder.id.desc()

    work_orders = query.order_by(primary, secondary).offset(skip).limit(limit).all()

    # 计算分页信息
    page = (skip // limit) + 1
    pages = math.ceil(total / limit) if limit else 1

    return WorkOrderListResponse(
        work_orders=[_enrich_work_order_response(db, wo) for wo in work_orders],
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


def _enrich_work_order_response(db: Session, wo: WorkOrder) -> dict:
    from datetime import datetime
    
    # Build the response manually to avoid validation issues
    current_time = datetime.utcnow()
    data = {
        "id": wo.id,
        "site_id": wo.site_id,
        "inspection_id": wo.inspection_id,
        "title": wo.title,
        "type": wo.type,
        "description": wo.description,
        "priority": wo.priority,
        "status": wo.status,
        "assigned_by": wo.assigned_by,
        "assigned_to": wo.assigned_to,
        "reviewer_id": wo.reviewer_id,
        "review_comments": wo.review_comments,
        "review_comments_i18n": getattr(wo, "review_comments_i18n", None),
        "has_duplicate_photos": False,
        "duplicate_photo_count": 0,
        "assigned_at": wo.assigned_at or current_time,
        "accepted_at": wo.accepted_at,
        "submitted_at": wo.submitted_at,
        "reviewed_at": wo.reviewed_at,
        "completed_at": wo.completed_at,
        "due_date": wo.due_date,
        "extra_data": wo.extra_data or {},
        "created_at": wo.created_at or current_time,
        "updated_at": wo.updated_at or current_time,
    }
    
    # Add enriched fields
    # site fields
    if wo.site_id:
        site = db.query(Site).filter(Site.id == wo.site_id).first()
        if site:
            data["site_name"] = getattr(site, "site_name", None)
            data["site_code"] = getattr(site, "site_code", None)
    
    # users
    if wo.assigned_by:
        u = db.query(User).filter(User.id == wo.assigned_by).first()
        if u:
            data["assigner_name"] = u.full_name or u.username
    if wo.assigned_to:
        u = db.query(User).filter(User.id == wo.assigned_to).first()
        if u:
            data["assignee_name"] = u.full_name or u.username
    if wo.reviewer_id:
        u = db.query(User).filter(User.id == wo.reviewer_id).first()
        if u:
            data["reviewer_name"] = u.full_name or u.username

    if wo.inspection_id:
        duplicate_photo_count = (
            db.query(InspectionPhoto)
            .filter(
                InspectionPhoto.inspection_id == wo.inspection_id,
                InspectionPhoto.is_duplicate_global.is_(True),
            )
            .count()
        )
        data["duplicate_photo_count"] = int(duplicate_photo_count or 0)
        data["has_duplicate_photos"] = data["duplicate_photo_count"] > 0
    
    return data


def _audit(db: Session, resource_type: str, resource_id: str, action: str, operator_id: int,
           from_status: Optional[str] = None, to_status: Optional[str] = None,
           comments: Optional[str] = None, details: Optional[dict] = None):
    ev = AuditEvent(
        id=str(uuid.uuid4()),
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        operator_id=operator_id,
        comments=comments,
        details=details or {}
    )
    db.add(ev)
    db.commit()


@router.post("", response_model=WorkOrderResponse)
@router.post("/", response_model=WorkOrderResponse)
async def create_work_order(
    data: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限创建工单")

    site = db.query(Site).filter(Site.id == data.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="站点不存在")

    normalized_replacement_targets = None

    # 设备更换工单创建规则校验
    if data.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        allowed_site_statuses = {
            "construction",
            "pending_online",
            "online_pending_activation",
            "operational",
            "maintenance",
        }
        if site.status not in allowed_site_statuses:
            raise HTTPException(
                status_code=409,
                detail=f"站点当前状态为 {site.status}，不允许创建设备更换工单",
            )

        # 必须选择要更换的设备位（支持多选）
        raw_targets = getattr(data, "replacement_targets", None) or []
        if not raw_targets:
            raise HTTPException(status_code=400, detail="设备更换工单必须选择要更换的设备位")

        # 归一化/去重
        normalized_targets = []
        seen_keys = set()
        for t in raw_targets:
            sector_id = str(getattr(t, "sector_id", None) or "").strip()
            band = str(getattr(t, "band", None) or "").strip()
            if not sector_id or not band:
                raise HTTPException(status_code=400, detail="设备更换工单设备位参数不完整（sector_id/band）")
            key = f"{sector_id}__{band}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            normalized_targets.append({"sector_id": sector_id, "band": band})

        if not normalized_targets:
            raise HTTPException(status_code=400, detail="设备更换工单必须选择要更换的设备位")

        normalized_replacement_targets = normalized_targets

        # 执行人自发起：仅允许指派给自己（避免越权派单）
        if getattr(current_user, "role", None) == "inspector" and data.assigned_to != current_user.id:
            raise HTTPException(status_code=400, detail="执行人自发起设备更换工单时只能指派给自己")

        # 同一站点仅允许存在一条“进行中的”设备更换工单
        in_progress_statuses = [
            WorkOrderStatusEnum.PENDING,
            WorkOrderStatusEnum.ACTIVE,
            WorkOrderStatusEnum.SUBMITTED,
            WorkOrderStatusEnum.UNDER_REVIEW,
            WorkOrderStatusEnum.APPROVED,
            WorkOrderStatusEnum.ACTIVATED,
        ]
        existing_replacement = db.query(WorkOrder).filter(
            WorkOrder.site_id == data.site_id,
            WorkOrder.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT,
            WorkOrder.status.in_(in_progress_statuses),
        ).order_by(WorkOrder.assigned_at.desc()).first()
        if existing_replacement:
            raise HTTPException(status_code=409, detail="该站点已有进行中的设备更换工单")

    # 勘察工单创建规则校验
    if data.type == WorkOrderTypeEnum.SITE_SURVEY:
        # 0) 站点无需勘察：禁止创建勘察工单
        if getattr(site, "survey_required", True) is False:
            raise HTTPException(status_code=409, detail="该站点已设置为无需勘察，不能创建勘察工单")

        # 1) 站点状态限制：construction/operational 阶段不允许新建勘察工单
        if site.status in ("construction", "operational"):
            raise HTTPException(
                status_code=400,
                detail=f"站点当前状态为 {site.status}，不允许新建勘察工单"
            )

        # 2) 同一站点仅允许存在一条“进行中的”勘察工单
        in_progress_statuses = [
            WorkOrderStatusEnum.PENDING,
            WorkOrderStatusEnum.ACTIVE,
            WorkOrderStatusEnum.SUBMITTED,
            WorkOrderStatusEnum.UNDER_REVIEW,
            WorkOrderStatusEnum.APPROVED,
            WorkOrderStatusEnum.ACTIVATED,
        ]
        existing_survey_wos = db.query(WorkOrder).filter(
            WorkOrder.site_id == data.site_id,
            WorkOrder.type == WorkOrderTypeEnum.SITE_SURVEY,
            WorkOrder.status.in_(in_progress_statuses),
        ).order_by(WorkOrder.assigned_at.desc()).all()

        if existing_survey_wos:
            existing_brief = []
            for e in existing_survey_wos[:10]:
                enriched = _enrich_work_order_response(db, e)
                existing_brief.append({
                    "id": enriched.get("id"),
                    "title": enriched.get("title"),
                    "status": enriched.get("status").value if hasattr(enriched.get("status"), "value") else str(enriched.get("status")),
                    "assigned_to": enriched.get("assigned_to"),
                    "assignee_name": enriched.get("assignee_name"),
                    "assigner_name": enriched.get("assigner_name"),
                    # assigned_at 在 WorkOrder 中使用数据库/utcnow，视为 UTC 输出
                    "assigned_at": to_utc_iso(enriched.get("assigned_at")) if enriched.get("assigned_at") else None,
                })

            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_SURVEY_ORDER",
                    "message": "该站点已存在进行中的勘察工单，不允许重复创建",
                    "site_id": data.site_id,
                    "site_name": getattr(site, "site_name", None),
                    "site_code": getattr(site, "site_code", None),
                    "existing_work_orders": existing_brief,
                },
            )

    # 安装工单创建规则校验：
    # - 当站点仍处于勘察或规划阶段（survey_pending, planning）时，禁止创建安装工单
    if data.type == WorkOrderTypeEnum.OPENING_INSPECTION:
        if site.status in ("survey_pending", "planning"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"站点当前状态为 {site.status}，尚处于勘察/规划阶段，"
                    "不允许创建安装工单，请完成勘察并完成规划确认后再试。"
                ),
            )

    # SSV 工单创建规则校验：站点必须 operational，且同站点仅一条进行中
    if data.type == WorkOrderTypeEnum.SSV:
        if site.status != "operational":
            raise HTTPException(status_code=409, detail="站点尚未运营，不能创建 SSV 工单")
        existing_ssv = db.query(WorkOrder).filter(
            WorkOrder.site_id == data.site_id,
            WorkOrder.type == WorkOrderTypeEnum.SSV,
            WorkOrder.status.in_([
                WorkOrderStatusEnum.PENDING,
                WorkOrderStatusEnum.ACTIVE,
                WorkOrderStatusEnum.SUBMITTED,
                WorkOrderStatusEnum.UNDER_REVIEW,
                WorkOrderStatusEnum.APPROVED,
                WorkOrderStatusEnum.ACTIVATED,
            ])
        ).first()
        if existing_ssv:
            raise HTTPException(status_code=409, detail="该站点已有进行中的 SSV 工单")

    # 开站工单创建规则（去重）：
    # - 同一站点仅允许存在一条“进行中的”开站工单
    # - 若仅存在历史开站工单（已完成/已驳回），则允许前端二次确认后继续创建
    if data.type == WorkOrderTypeEnum.OPENING_INSPECTION:
        in_progress_statuses = [
            WorkOrderStatusEnum.PENDING,
            WorkOrderStatusEnum.ACTIVE,
            WorkOrderStatusEnum.SUBMITTED,
            WorkOrderStatusEnum.UNDER_REVIEW,
            WorkOrderStatusEnum.APPROVED,
            WorkOrderStatusEnum.ACTIVATED,
        ]

        existing_in_progress = db.query(WorkOrder).filter(
            WorkOrder.site_id == data.site_id,
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status.in_(in_progress_statuses),
        ).order_by(WorkOrder.assigned_at.desc()).all()

        if existing_in_progress:
            existing_brief = []
            for e in existing_in_progress[:10]:
                enriched = _enrich_work_order_response(db, e)
                existing_brief.append({
                    "id": enriched.get("id"),
                    "title": enriched.get("title"),
                    "status": enriched.get("status").value if hasattr(enriched.get("status"), 'value') else str(enriched.get("status")),
                    "assigned_to": enriched.get("assigned_to"),
                    "assignee_name": enriched.get("assignee_name"),
                    "assigner_name": enriched.get("assigner_name"),
                    "assigned_at": to_utc_iso(enriched.get("assigned_at")) if enriched.get("assigned_at") else None,
                })
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_OPENING_ORDER_IN_PROGRESS",
                    "message": "该站点已存在进行中的安装工单，不允许重复创建；请先关闭/作废原工单",
                    "site_id": data.site_id,
                    "site_name": getattr(site, "site_name", None),
                    "site_code": getattr(site, "site_code", None),
                    "existing_work_orders": existing_brief,
                },
            )

        if not (getattr(data, "confirm_duplicate", False)):
            existing_history = db.query(WorkOrder).filter(
                WorkOrder.site_id == data.site_id,
                WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
                WorkOrder.status.in_([WorkOrderStatusEnum.COMPLETED, WorkOrderStatusEnum.REJECTED]),
            ).order_by(WorkOrder.assigned_at.desc()).all()
            if existing_history:
                existing_brief = []
                for e in existing_history[:10]:  # 最多返回10条以控制响应体
                    enriched = _enrich_work_order_response(db, e)
                    existing_brief.append({
                        "id": enriched.get("id"),
                        "title": enriched.get("title"),
                        "status": enriched.get("status").value if hasattr(enriched.get("status"), 'value') else str(enriched.get("status")),
                        "assigned_to": enriched.get("assigned_to"),
                        "assignee_name": enriched.get("assignee_name"),
                        "assigner_name": enriched.get("assigner_name"),
                        "assigned_at": to_utc_iso(enriched.get("assigned_at")) if enriched.get("assigned_at") else None,
                    })
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "DUPLICATE_OPENING_ORDER",
                        "message": "该站点存在历史安装工单，确认后仍可继续创建",
                        "site_id": data.site_id,
                        "site_name": getattr(site, "site_name", None),
                        "site_code": getattr(site, "site_code", None),
                        "require_confirm_duplicate": True,
                        "existing_work_orders": existing_brief,
                    }
                )

    # SSV 工单创建规则校验：站点需为 operational，且同一站点同时间只允许一条进行中的 SSV 工单
    if data.type == WorkOrderTypeEnum.SSV:
        if site.status != "operational":
            raise HTTPException(status_code=409, detail="站点尚未运营，不能创建 SSV 工单")
        in_progress_statuses = [
            WorkOrderStatusEnum.PENDING,
            WorkOrderStatusEnum.ACTIVE,
            WorkOrderStatusEnum.SUBMITTED,
            WorkOrderStatusEnum.UNDER_REVIEW,
            WorkOrderStatusEnum.APPROVED,
            WorkOrderStatusEnum.ACTIVATED,
        ]
        existing_ssv = db.query(WorkOrder).filter(
            WorkOrder.site_id == data.site_id,
            WorkOrder.type == WorkOrderTypeEnum.SSV,
            WorkOrder.status.in_(in_progress_statuses)
        ).first()
        if existing_ssv:
            raise HTTPException(status_code=409, detail="该站点已有进行中的 SSV 工单")

    # 分配/审核人：设备更换工单允许执行人自发起，但派单人/审核人应尽量沿用站点负责人（site.assigned_to）
    assigned_by_id = current_user.id
    initiator_id = None
    if data.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT and getattr(current_user, "role", None) == "inspector":
        initiator_id = current_user.id
        assigned_by_id = getattr(site, "assigned_to", None) or None
        if not assigned_by_id:
            admin_user = db.query(User).filter(User.username == "admin").first()
            assigned_by_id = admin_user.id if admin_user else current_user.id

    extra_data = {"template_id": data.template_id} if data.template_id else {}
    if data.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        extra_data["replacement_targets"] = normalized_replacement_targets or []
        if initiator_id:
            extra_data["initiator_id"] = initiator_id

    wo = WorkOrder(
        id=str(uuid.uuid4()),
        site_id=data.site_id,
        title=data.title,
        type=data.type,
        description=data.description,
        priority=data.priority,
        assigned_by=assigned_by_id,
        assigned_to=data.assigned_to,
        assigned_at=datetime.utcnow(),  # 显式设置分配时间
        due_date=data.due_date,
        status=WorkOrderStatusEnum.PENDING,
        extra_data=extra_data,
    )
    db.add(wo)
    db.flush()

    # 工单创建成功，检查实例将在接受时创建
    
    # 自动更新站点状态
    _update_site_status_on_work_order_create(db, data.site_id, data.type)

    db.commit()
    db.refresh(wo)
    _audit(db, "work_order", wo.id, "create", current_user.id, to_status=wo.status.value)
    return _enrich_work_order_response(db, wo)


@router.get("", response_model=List[WorkOrderResponse])
@router.get("/", response_model=List[WorkOrderResponse])
async def list_work_orders(
    status_filter: Optional[WorkOrderStatusEnum] = None,
    assigned_to: Optional[int] = None,
    type_filter: Optional[WorkOrderTypeEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(WorkOrder)
    if status_filter:
        q = q.filter(WorkOrder.status == status_filter)
    if assigned_to:
        q = q.filter(WorkOrder.assigned_to == assigned_to)
    if type_filter:
        q = q.filter(WorkOrder.type == type_filter)

    if _is_field_worker(current_user):
        q = q.filter(WorkOrder.assigned_to == current_user.id)
        if _is_surveyor(current_user):
            q = q.filter(WorkOrder.type == WorkOrderTypeEnum.SITE_SURVEY)

    # 按创建时间降序排序，这样最新的工单在最前面
    # 注意：使用created_at而不是assigned_at，因为assigned_at可能晚于created_at导致排序混乱
    orders = q.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()
    return [_enrich_work_order_response(db, o) for o in orders]


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    _ensure_surveyor_wo_type(wo, current_user)
    return _enrich_work_order_response(db, wo)


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
async def update_work_order(
    work_order_id: str,
    data: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role not in ["admin", "manager"] and current_user.id != wo.assigned_by:
        raise HTTPException(status_code=403, detail="无权限修改工单")

    update = data.dict(exclude_unset=True)

    if "assigned_to" in update:
        if current_user.role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="仅管理员/项目经理可重新分配工单")

        if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
            raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许重新分配")

        new_assignee_id = update.pop("assigned_to")
        if new_assignee_id is None:
            raise HTTPException(status_code=400, detail="分配人不能为空")

        try:
            new_assignee_id = int(new_assignee_id)
        except Exception:
            raise HTTPException(status_code=400, detail="无效的分配人ID")

        assignee = db.query(User).filter(User.id == new_assignee_id).first()
        if not assignee:
            raise HTTPException(status_code=400, detail="分配人不存在")

        old_assignee_id = wo.assigned_to
        if new_assignee_id != old_assignee_id:
            old_assignee = db.query(User).filter(User.id == old_assignee_id).first()

            wo.assigned_to = new_assignee_id
            wo.assigned_by = current_user.id
            wo.assigned_at = datetime.utcnow()

            if wo.inspection_id:
                inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
                if inspection:
                    inspection.inspector_id = new_assignee_id

            db.add(
                AuditEvent(
                    id=str(uuid.uuid4()),
                    resource_type="work_order",
                    resource_id=wo.id,
                    action="change_assignee",
                    operator_id=current_user.id,
                    comments=None,
                    details={
                        "old_assignee_id": old_assignee_id,
                        "old_assignee_name": (old_assignee.full_name or old_assignee.username) if old_assignee else None,
                        "new_assignee_id": new_assignee_id,
                        "new_assignee_name": (assignee.full_name or assignee.username) if assignee else None,
                    },
                )
            )

    for k, v in update.items():
        setattr(wo, k, v)
    db.commit()
    db.refresh(wo)
    return _enrich_work_order_response(db, wo)


@router.delete("/{work_order_id}")
async def delete_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除工单"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有管理员或创建者可以删除
    if current_user.role not in ["admin", "manager"] and current_user.id != wo.assigned_by:
        raise HTTPException(status_code=403, detail="无权限删除工单")
    
    # 检查工单状态：只能删除待分配或已分配状态的工单
    if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
        raise HTTPException(status_code=400, detail=f"无法删除{wo.status}状态的工单")

    # 解绑检查项要求：存在设备级绑定则禁止删除
    if _has_bound_device_check_items(db, wo):
        raise HTTPException(status_code=409, detail="该工单存在已绑定设备检查项，无法删除；请先在APP解绑设备")

    # 记录原始状态用于审计
    old_status = wo.status
    old_wo_type = wo.type
    old_site_id = wo.site_id

    # 若已生成档案，禁止删除（保证可追溯性）
    if db.query(SiteSurveyArchive).filter(SiteSurveyArchive.work_order_id == wo.id).first():
        raise HTTPException(status_code=409, detail="该工单已生成勘察档案，无法删除")
    if db.query(SiteOpeningArchive).filter(SiteOpeningArchive.work_order_id == wo.id).first():
        raise HTTPException(status_code=409, detail="该工单已生成开站档案，无法删除")
    if db.query(SiteSSVArchive).filter(SiteSSVArchive.work_order_id == wo.id).first():
        raise HTTPException(status_code=409, detail="该工单已生成 SSV 档案，无法删除")

    # 删除安装工单时：若是该站点最后一条安装工单，则回滚站点状态到 planned
    remaining_opening_orders = None
    if old_wo_type == WorkOrderTypeEnum.OPENING_INSPECTION:
        remaining_opening_orders = db.query(WorkOrder).filter(
            WorkOrder.site_id == old_site_id,
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.id != wo.id,
        ).count()

    # 设备更换工单：删除时需要回滚站点状态（仅在已接受/站点处于 maintenance 时生效）
    site_status_before = None
    if old_wo_type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        try:
            extra = wo.extra_data or {}
            site_status_before = extra.get("site_status_before")
        except Exception:
            site_status_before = None

    try:
        # 若历史库存记录绑定了工单，先解除绑定（保留库存数据）
        _detach_stock_records_from_work_order(db, wo)

        # 如果有关联的检查记录，需要同时删除
        inspections_to_delete = []
        seen_inspection_ids = set()

        # 1) 通过 work_orders.inspection_id 关联的检查
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspections_to_delete.append(inspection)
                seen_inspection_ids.add(inspection.id)

        # 2) 通过 site_inspections.work_order_id 反向关联的检查（可能存在多条）
        extra_inspections = db.query(SiteInspection).filter(SiteInspection.work_order_id == wo.id).all()
        for insp in extra_inspections:
            if insp.id not in seen_inspection_ids:
                inspections_to_delete.append(insp)
                seen_inspection_ids.add(insp.id)

        # 删除/解绑与工单相关的勘察草稿（SiteSurvey）
        surveys = db.query(SiteSurvey).filter(SiteSurvey.work_order_id == wo.id).all()
        for s in surveys:
            db.delete(s)

        # 删除可能遗留的 work_order_items（历史表）
        db.query(WorkOrderItem).filter(WorkOrderItem.work_order_id == wo.id).delete(synchronize_session=False)

        # 先打断双向外键关联，避免 SQLAlchemy 计算删除依赖时出现环形依赖
        if inspections_to_delete:
            for insp in inspections_to_delete:
                insp.work_order_id = None
            wo.inspection_id = None
            # 先 flush 一次更新外键，再标记删除
            db.flush()
            for insp in inspections_to_delete:
                db.delete(insp)

        # 最后删除工单本身
        db.delete(wo)

        # 站点状态回滚：删除安装工单且不存在其它安装工单
        if old_wo_type == WorkOrderTypeEnum.OPENING_INSPECTION and remaining_opening_orders == 0:
            site = db.query(Site).filter(Site.id == old_site_id).first()
            if site and site.status != "planned":
                old_site_status = site.status
                site.status = "planned"
                _audit_site_status_change(
                    db,
                    old_site_id,
                    old_site_status,
                    site.status,
                    "删除安装工单，站点状态回滚至 planned",
                )

        # 设备更换工单：删除时回滚站点状态到 site_status_before
        if old_wo_type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            site = db.query(Site).filter(Site.id == old_site_id).first()
            before = str(site_status_before or "").strip()
            if site and before and site.status == "maintenance" and site.status != before:
                old_site_status = site.status
                site.status = before
                _audit_site_status_change(
                    db,
                    old_site_id,
                    old_site_status,
                    site.status,
                    "删除设备更换工单，站点状态回滚",
                )

        db.commit()

        # 记录审计日志
        _audit(
            db,
            "work_order",
            work_order_id,
            "delete",
            current_user.id,
            from_status=old_status.value,
            to_status="deleted",
        )

        return {"message": "工单删除成功"}
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="删除失败：该工单存在关联数据，请先处理关联记录后再删除")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="删除失败：服务器内部错误")


@router.post("/{work_order_id}/accept")
async def accept_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """接受工单并创建关联检查实例"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有被分配人才能接受
    if wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="只有被分配人才能接受工单")
    
    if wo.status != WorkOrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail=f"只能接受待处理状态的工单，当前状态：{wo.status}")

    # 勘察人员仅能接受勘察工单
    _ensure_surveyor_wo_type(wo, current_user)

    # 若模板包含“小区级（按EARFCN）”，则必须先导入 LLD 规划明细
    template_id = _get_template_id_from_extra_data(wo.extra_data)
    template = db.query(InspectionTemplate).filter(InspectionTemplate.id == template_id).first()
    template_data = template.template_data if (template and template.template_data) else {}

    carrier_cells = None
    if template_data and _template_requires_lld_cells(template_data):
        from app.services.cell_generator import CellGenerator

        carrier_cells = CellGenerator.generate_cells_from_lld(db, wo.site_id)
        if not carrier_cells:
            raise HTTPException(
                status_code=400,
                detail="该检查模板包含“小区级（按EARFCN）”检查项，请先在站点规划（LLD）中导入规划数据",
            )

    # 设备更换工单：接受时将站点切到 maintenance，并记录原状态用于后续回滚
    if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        site = db.query(Site).filter(Site.id == wo.site_id).first()
        if site:
            extra = wo.extra_data or {}
            if not extra.get("site_status_before"):
                extra["site_status_before"] = site.status
            if site.status != "maintenance":
                old_site_status = site.status
                site.status = "maintenance"
                _audit_site_status_change(
                    db,
                    site.id,
                    old_site_status,
                    site.status,
                    "接受设备更换工单，站点进入维护阶段",
                )
            wo.extra_data = extra

    # 更新工单状态
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.ACTIVE
    wo.accepted_at = datetime.utcnow()
    
    # 创建关联的检查实例
    inspection = SiteInspection(
        id=str(uuid.uuid4()),
        site_id=wo.site_id,
        inspector_id=wo.assigned_to,
        inspection_type=InspectionTypeEnum.OPENING if wo.type.value == "opening_inspection" else InspectionTypeEnum.MAINTENANCE,
        work_order_id=wo.id,  # 关联工单ID
        status=InspectionStatusEnum.DRAFT,
        template_id=template_id
    )
    db.add(inspection)
    db.flush()
    
    # 根据模板创建检查项 - 使用与inspections.py相同的逻辑
    if template_data:
        from app.services.cell_generator import CellGenerator

        total_items = 0
        devices = CellGenerator.generate_devices_from_planning(db, wo.site_id)

        # 设备更换工单：仅生成选中的设备位相关检查项
        target_slots = None
        old_sn_map = {}
        if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            raw_targets = (wo.extra_data or {}).get("replacement_targets") or []
            slots = set()
            for t in raw_targets:
                if not isinstance(t, dict):
                    continue
                sector_id = str(t.get("sector_id") or "").strip()
                band = str(t.get("band") or "").strip()
                if not sector_id or not band:
                    continue
                slots.add((sector_id, band))
            if not slots:
                raise HTTPException(status_code=400, detail="设备更换工单缺少 replacement_targets，无法生成检查项")
            target_slots = slots
            devices = [d for d in devices if (str(d.sector_id), str(d.band)) in target_slots]
            if carrier_cells is not None:
                carrier_cells = [
                    c for c in (carrier_cells or []) if (str(c.sector_id), str(c.band)) in target_slots
                ]

            # 预填旧设备 SN（用于展示与追溯）
            try:
                from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum

                for sector_id, band in sorted(target_slots):
                    cell_id = f"{sector_id}_{band}"
                    row = (
                        db.query(EquipmentBindingHistory)
                        .filter(
                            EquipmentBindingHistory.site_id == wo.site_id,
                            EquipmentBindingHistory.sector_id == sector_id,
                            EquipmentBindingHistory.band == band,
                            EquipmentBindingHistory.cell_id == cell_id,
                        )
                        .order_by(EquipmentBindingHistory.operated_at.desc(), EquipmentBindingHistory.id.desc())
                        .first()
                    )
                    if row and row.action != BindingActionEnum.UNBIND and row.equipment_sn:
                        old_sn_map[(sector_id, band)] = str(row.equipment_sn).strip()
            except Exception:
                old_sn_map = {}

            extra = wo.extra_data or {}
            extra["replacement_old_devices"] = [
                {"sector_id": s, "band": b, "old_sn": old_sn_map.get((s, b))}
                for (s, b) in sorted(target_slots)
            ]
            wo.extra_data = extra

        sectors = sorted({d.sector_id for d in devices})

        print(
            f"DEBUG_WO: 为站点 {wo.site_id} 生成检查项 (工单: {wo.id})，"
            f"设备数={len(devices)}，扇区数={len(sectors)}"
        )
        if carrier_cells is not None:
            print(f"DEBUG_WO: 小区级（按EARFCN）数量={len(carrier_cells)}")

        for category in template_data.get("check_categories", []):
            category_name = category.get("category_name", "未知分类")
            category_id = category.get("category_id", "unknown")
            level_type = _normalize_category_level(category)
            print(
                f"DEBUG_WO: 处理分类: {category_name}, "
                f"level_type(raw)={category.get('level_type')}, level_type(norm)={level_type}"
            )

            for item in category.get("items", []):
                base_item_name = item.get("item_name", "未知检查项")
                base_item_id = item.get("item_id", "unknown")
                required_type = item.get("required_type", "unknown")
                item_description = item.get("description")  # 获取描述
                item_fields = item.get("fields")  # 获取字段配置

                if level_type == "cell_earfcn":
                    cells = carrier_cells or []
                    for cell in cells:
                        cell_item_id = f"{base_item_id}_cell_{cell.cell_id}"
                        cell_item_name = f"{base_item_name} - 小区 {cell.cell_id}"
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=cell_item_id,
                            item_name=cell_item_name,
                            description=item_description,
                            category_id=category_id,
                            category_name=category_name,
                            sector_id=cell.sector_id,
                            band=cell.band,
                            cell_id=cell.cell_id,
                            required_type=required_type,
                            fields=item_fields,
                            status=CheckItemStatusEnum.PENDING,
                        )
                        db.add(check_item)
                        total_items += 1
                elif level_type == "device":
                    for dev in devices:
                        dev_item_id = f"{base_item_id}_cell_{dev.cell_id}"
                        dev_item_name = f"{base_item_name} - 设备 {dev.cell_id}"
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=dev_item_id,
                            item_name=dev_item_name,
                            description=item_description,
                            category_id=category_id,
                            category_name=category_name,
                            sector_id=dev.sector_id,
                            band=dev.band,
                            cell_id=dev.cell_id,
                            equipment_sn=(
                                old_sn_map.get((str(dev.sector_id), str(dev.band)))
                                if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT
                                else None
                            ),
                            required_type=required_type,
                            fields=item_fields,
                            status=CheckItemStatusEnum.PENDING,
                        )
                        db.add(check_item)
                        total_items += 1
                elif level_type == "sector":
                    for sector_id in sectors:
                        sector_item_id = f"{base_item_id}_sector_{sector_id}"
                        sector_item_name = f"{base_item_name} - 扇区 {sector_id}"
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=sector_item_id,
                            item_name=sector_item_name,
                            description=item_description,
                            category_id=category_id,
                            category_name=category_name,
                            sector_id=sector_id,
                            required_type=required_type,
                            fields=item_fields,
                            status=CheckItemStatusEnum.PENDING,
                        )
                        db.add(check_item)
                        total_items += 1
                else:
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=base_item_id,
                        item_name=base_item_name,
                        description=item_description,
                        category_id=category_id,
                        category_name=category_name,
                        required_type=required_type,
                        fields=item_fields,
                        status=CheckItemStatusEnum.PENDING,
                    )
                    db.add(check_item)
                    total_items += 1

        inspection.total_items = total_items
        print(f"DEBUG_WO: 总共创建了 {total_items} 个检查项")
    
    # 更新工单的inspection_id
    wo.inspection_id = inspection.id
    
    # 同步工单状态到检查
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    
    db.commit()
    db.refresh(wo)
    db.refresh(inspection)
    
    _audit(db, "work_order", wo.id, "accept", current_user.id, 
           from_status=old_status.value, to_status=wo.status.value)
    
    # 确保存在档案草稿
    try:
        from app.services.survey_sync import ensure_survey_for_work_order
        ensure_survey_for_work_order(db, wo, current_user)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "message": "工单接受成功",
        "work_order": _enrich_work_order_response(db, wo),
        "inspection_id": inspection.id
    }


@router.get("/{work_order_id}/inspection")
async def get_work_order_inspection(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单关联的检查实例"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    _ensure_surveyor_wo_type(wo, current_user)
    
    if not wo.inspection_id:
        raise HTTPException(status_code=404, detail="工单尚未创建关联检查")
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
    
    # 如果工单被驳回，将检查状态设置为已驳回状态
    if wo.status == WorkOrderStatusEnum.REJECTED and inspection.status != InspectionStatusEnum.REJECTED:
        inspection.status = InspectionStatusEnum.REJECTED
        db.commit()
    
    return {"inspection_id": inspection.id, "status": inspection.status.value}


@router.get("/{work_order_id}/survey")
async def get_work_order_survey(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """确保并返回与工单关联的站点勘察档案（SiteSurvey）。"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    _ensure_surveyor_wo_type(wo, current_user)

    from app.services.survey_sync import ensure_survey_for_work_order
    survey = ensure_survey_for_work_order(db, wo, current_user)
    db.commit()

    # 返回完整响应体（含站点与照片摘要）
    from app.schemas.site_survey import SiteSurveyResponse, SiteSurveyPhotoResponse
    photos = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == survey.id).all()
    photo_items = [SiteSurveyPhotoResponse.model_validate(p) for p in photos]
    return SiteSurveyResponse(
        id=survey.id,
        site_id=survey.site_id,
        site_name=survey.site.site_name if survey.site else None,
        site_code=survey.site.site_code if survey.site else None,
        survey_date=survey.survey_date,
        surveyor_name=survey.surveyor_name,
        surveyor_phone=survey.surveyor_phone,
        latitude=survey.latitude,
        longitude=survey.longitude,
        address=survey.address,
        gps_accuracy=survey.gps_accuracy,
        site_type=survey.site_type,
        tower_type=survey.tower_type,
        available_height_m=survey.available_height_m,
        load_capacity_kg=survey.load_capacity_kg,
        power_available=survey.power_available,
        power_distance_m=survey.power_distance_m,
        power_capacity_kw=survey.power_capacity_kw,
        earthing_feasible=survey.earthing_feasible,
        fiber_available=survey.fiber_available,
        fiber_distance_m=survey.fiber_distance_m,
        duct_notes=survey.duct_notes,
        microwave_los=survey.microwave_los,
        los_azimuth_deg=survey.los_azimuth_deg,
        los_distance_km=survey.los_distance_km,
        sensitive_points=survey.sensitive_points,
        safety_notes=survey.safety_notes,
        permits_constraints=survey.permits_constraints,
        owner_name=survey.owner_name,
        owner_phone=survey.owner_phone,
        access_time_window=survey.access_time_window,
        entry_constraints=survey.entry_constraints,
        feasibility=survey.feasibility,
        risks=survey.risks,
        recommendations=survey.recommendations,
        extra_data=survey.extra_data,
        created_by=survey.created_by,
        created_at=survey.created_at,
        updated_at=survey.updated_at,
        photos=photo_items,
    )


@router.post("/{work_order_id}/complete")
async def complete_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """完成工单（当关联检查完成后调用）"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.assigned_to != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限完成此工单")
    _ensure_surveyor_wo_type(wo, current_user)
    
    if wo.status != WorkOrderStatusEnum.ACTIVE:
        raise HTTPException(status_code=400, detail="只能完成执行中的工单")
    
    # 检查关联的检查是否已完成
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if inspection and inspection.status not in [InspectionStatusEnum.APPROVED, InspectionStatusEnum.COMPLETED]:
            raise HTTPException(status_code=400, detail="关联检查尚未完成")
    
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()
    
    # 自动更新站点状态
    if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        try:
            site = db.query(Site).filter(Site.id == wo.site_id).first()
            extra = wo.extra_data or {}
            before = (extra.get("site_status_before") or "").strip()
            if site and before and site.status != before:
                old_site_status = site.status
                site.status = before
                _audit_site_status_change(
                    db,
                    site.id,
                    old_site_status,
                    site.status,
                    "手工标记设备更换工单完成，站点状态回滚",
                )
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] 标记完成时回滚站点状态失败: {exc}")
    else:
        _update_site_status_on_work_order_complete(db, wo.site_id, wo.type)
    
    db.commit()
    _audit(db, "work_order", wo.id, "complete", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {"message": "工单完成"}


@router.get("/{work_order_id}/items", response_model=List[WorkOrderItemResponse])
async def list_items(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    _ensure_surveyor_wo_type(wo, current_user)
    
    # 完全使用关联检查的检查项，不再使用工单自己的检查项
    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")
    
    from sqlalchemy.orm import joinedload
    
    inspection_items = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.photos)
    ).filter(
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).all()
    
    # 将检查项转换为工单检查项格式返回
    result = []
    for item in inspection_items:
        # 构建符合WorkOrderItemResponse格式的数据
        item_data = {
            "id": item.id,
            "work_order_id": work_order_id,
            "item_id": item.item_id,
            "item_name": item.item_name,
            "category_id": item.category_id,
            "category_name": item.category_name,
            "sector_id": item.sector_id,
            "required_type": item.required_type,
            "status": item.status.value if hasattr(item.status, 'value') else str(item.status),
            "data_value": item.data_value if item.data_value else [],
            "validation_result": None,
            "notes": item.notes,
            "review_status": item.review_status,
            "review_comments": item.review_comments,
            "review_comments_i18n": getattr(item, "review_comments_i18n", None),
            "reviewed_at": item.reviewed_at if hasattr(item, 'reviewed_at') else None,
            "ai_status": getattr(item, "ai_status", None),
            "ai_mode": getattr(item, "ai_mode", None),
            "ai_model": getattr(item, "ai_model", None),
            "ai_input_hash": getattr(item, "ai_input_hash", None),
            "ai_result": getattr(item, "ai_result", None),
            "ai_error": getattr(item, "ai_error", None),
            "ai_checked_by": getattr(item, "ai_checked_by", None),
            "ai_checked_at": getattr(item, "ai_checked_at", None),
            "ai_applied_by": getattr(item, "ai_applied_by", None),
            "ai_applied_at": getattr(item, "ai_applied_at", None),
            "photos": item.photos,  # Include photos
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        result.append(WorkOrderItemResponse(**item_data))
    
    return result


@router.put("/{work_order_id}/items/{item_id}", response_model=WorkOrderItemResponse)
async def update_item(
    work_order_id: str,
    item_id: str,
    data: WorkOrderItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限修改此工单")
    _ensure_surveyor_wo_type(wo, current_user)
    
    # 完全使用关联检查的检查项，不再使用工单自己的检查项
    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")
    
    inspection_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).first()
    
    if not inspection_item:
        raise HTTPException(status_code=404, detail="检查项不存在")
    
    # 检查工单状态是否允许编辑（驳回后应该可以编辑）
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许编辑检查项")
    
    # 更新检查项
    upd = data.dict(exclude_unset=True)
    content_changed = False
    if 'data_value' in upd and upd['data_value'] is not None:
        # 严格要求 field_name 与模板 field_id 一致；
        field_ids = set()
        label_to_id = {}
        if isinstance(inspection_item.fields, list):
            for f in inspection_item.fields:
                fid = f.get('field_id') if isinstance(f, dict) else getattr(f, 'field_id', None)
                lbl = f.get('label') if isinstance(f, dict) else getattr(f, 'label', None)
                if fid:
                    field_ids.add(str(fid))
                if fid and lbl:
                    label_to_id[str(lbl)] = str(fid)

        normalized = []
        invalid = []
        for dv in upd['data_value']:
            d = dv
            if hasattr(dv, 'dict'):
                d = dv.dict()
            raw_name = d.get('field_name') or d.get('field_id') or d.get('key') or d.get('field') or d.get('name')
            if not raw_name:
                invalid.append('(missing field_name)')
                continue
            name = str(raw_name)
            if field_ids and name not in field_ids:
                mapped = label_to_id.get(name)
                if mapped:
                    name = mapped
                else:
                    invalid.append(name)
                    continue
            normalized.append({
                'field_name': name,
                'value': d.get('value'),
                'unit': d.get('unit'),
            })

        if invalid:
            allowed = ','.join(sorted(field_ids)) if field_ids else '无字段定义'
            raise HTTPException(status_code=400, detail=f"存在未定义字段: {invalid}；允许的 field_id: {allowed}")

        if inspection_item.data_value != normalized:
            content_changed = True
        inspection_item.data_value = normalized
    if 'status' in upd:
        # 将字符串状态转换为枚举
        status_str = upd['status']
        before_status = getattr(inspection_item.status, 'value', inspection_item.status)
        if status_str == 'completed':
            inspection_item.status = CheckItemStatusEnum.COMPLETED
            inspection_item.checked_at = datetime.utcnow()
        elif status_str == 'pending':
            inspection_item.status = CheckItemStatusEnum.PENDING
            inspection_item.checked_at = None
        after_status = getattr(inspection_item.status, 'value', inspection_item.status)
        if str(before_status) != str(after_status):
            content_changed = True
    
    now = datetime.utcnow()
    inspection_item.updated_at = now

    # 内容变更：清空该检查项既有审核结果（若已审核过），以便驳回后增量复审
    if content_changed:
        _touch_inspection_item_and_clear_review(inspection_item, now)

    # 可选：按字段定义进行类型校验（非严格，允许部分填写）
    try:
        field_definitions = []
        if isinstance(inspection_item.fields, list):
            for field_dict in inspection_item.fields:
                try:
                    fd = FieldDefinition(**field_dict)
                    field_definitions.append(fd)
                except Exception:
                    pass
        if field_definitions and inspection_item.data_value:
            dv_list = []
            for dv in inspection_item.data_value:
                if hasattr(dv, 'dict'):
                    dv_list.append(dv.dict())
                elif isinstance(dv, dict):
                    dv_list.append(dv)
            _ = FieldValidator.validate_check_item_data(field_definitions, dv_list, strict=False)
    except Exception:
        pass
    
    # 检查是否应该更新工单的检查状态
    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
    if inspection and (wo.status == WorkOrderStatusEnum.REJECTED or inspection.status == InspectionStatusEnum.REJECTED):
        # 当工单被驳回或检查被驳回时，任何编辑操作都应该将检查状态改为进行中
        inspection.status = InspectionStatusEnum.IN_PROGRESS
        # 同步工单状态
        sync_service = get_work_order_sync_service(db)
        sync_service.sync_inspection_to_work_order_status(inspection)
    
    db.commit()
    db.refresh(inspection_item)
    
    # 返回格式化的响应
    item_data = {
        "id": inspection_item.id,
        "work_order_id": work_order_id,
        "item_id": inspection_item.item_id,
        "item_name": inspection_item.item_name,
        "category_id": inspection_item.category_id,
        "category_name": inspection_item.category_name,
        "sector_id": inspection_item.sector_id,
        "required_type": inspection_item.required_type,
        "status": inspection_item.status.value if hasattr(inspection_item.status, 'value') else str(inspection_item.status),
        "data_value": inspection_item.data_value if inspection_item.data_value else [],
        "validation_result": None,
        "notes": inspection_item.notes,
        "review_status": inspection_item.review_status,
        "review_comments": inspection_item.review_comments,
        "reviewed_at": inspection_item.reviewed_at if hasattr(inspection_item, 'reviewed_at') else None,
        "created_at": inspection_item.created_at,
        "updated_at": inspection_item.updated_at
    }
    return WorkOrderItemResponse(**item_data)


@router.post("/{work_order_id}/review/start")
async def start_review(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限认领审核")
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.status != WorkOrderStatusEnum.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"只能从 submitted 认领，当前：{wo.status}")
    old = wo.status
    wo.status = WorkOrderStatusEnum.UNDER_REVIEW
    db.commit()
    _audit(db, "work_order", work_order_id, "review_start", current_user.id, from_status=old.value, to_status=wo.status.value)
    return {"message": "已进入审核中"}


@router.post("/{work_order_id}/items/{item_id}/review")
async def review_item(
    work_order_id: str,
    item_id: str,
    req: ItemReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限执行检查项审核")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or not wo.inspection_id:
        raise HTTPException(status_code=404, detail="工单或关联检查不存在")
    
    item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id, 
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="检查项不存在")

    item_status_value = getattr(item.status, "value", item.status)
    if str(item_status_value) != CheckItemStatusEnum.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"检查项未完成提交，无法审核（当前状态：{item_status_value}）"
        )
    
    item.review_status = req.action
    item.review_comments = req.comments
    item.review_comments_i18n = req.comments_i18n
    item.reviewed_at = datetime.utcnow()
    db.commit()
    _audit(db, "item", item_id, "item_review", current_user.id, comments=req.comments, details={"result": req.action})
    _update_work_order_result(db, work_order_id)
    return {"message": "检查项审核成功"}


@router.post("/{work_order_id}/review/comments-i18n")
async def update_review_comments_i18n(
    work_order_id: str,
    req: WorkOrderReviewCommentsI18nUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限更新审核意见多语言")

    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")

    updated_work_order = False
    updated_items = 0

    # 更新工单审核意见多语言（不改变审核状态/时间）
    if req.comments_i18n is not None:
        wo.review_comments_i18n = req.comments_i18n
        updated_work_order = True

        # 同步到关联检查，避免移动端只读 inspection 时缺失多语言
        inspections = []
        if wo.inspection_id:
            inspections = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).all()
        else:
            inspections = db.query(SiteInspection).filter(SiteInspection.work_order_id == wo.id).all()
        for inspection in inspections:
            inspection.review_comments_i18n = req.comments_i18n

    # 更新检查项审核意见多语言（不改变审核结果/时间）
    item_updates = req.items or []
    if item_updates:
        if not wo.inspection_id:
            raise HTTPException(status_code=400, detail="工单尚未关联检查实例，无法更新检查项审核意见多语言")

        updates_map = {
            it.item_id: it.comments_i18n
            for it in item_updates
            if it and it.item_id and it.comments_i18n is not None
        }
        item_ids = list(updates_map.keys())
        if item_ids:
            db_items = db.query(InspectionCheckItem).filter(
                InspectionCheckItem.inspection_id == wo.inspection_id,
                InspectionCheckItem.id.in_(item_ids),
            ).all()
            found_ids = {i.id for i in db_items}
            missing = [i for i in item_ids if i not in found_ids]
            if missing:
                names = missing[:10]
                extra = f" 等{len(missing)}项" if len(missing) > 10 else ""
                raise HTTPException(
                    status_code=404,
                    detail=f"检查项不存在或不属于当前工单关联检查：{', '.join(names)}{extra}",
                )

            for item in db_items:
                item.review_comments_i18n = updates_map.get(item.id)
            updated_items = len(db_items)

    if not updated_work_order and updated_items == 0:
        return {"message": "没有需要更新的多语言内容", "updated_work_order": False, "updated_items": 0}

    db.commit()
    return {
        "message": "审核意见多语言已更新",
        "updated_work_order": updated_work_order,
        "updated_items": updated_items,
    }


@router.get("/{work_order_id}/review-summary", response_model=ReviewSummary)
async def review_summary(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if not wo.inspection_id:
        return ReviewSummary(total_items=0, pass_count=0, fail_count=0, warning_count=0, pending_count=0)
    
    total = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).count()
    p = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "pass").count()
    f = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "fail").count()
    w = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "warning").count()
    pending = total - p - f - w
    return ReviewSummary(total_items=total, pass_count=p, fail_count=f, warning_count=w, pending_count=pending)


@router.post("/{work_order_id}/review")
async def final_review(
    work_order_id: str,
    req: WorkOrderReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限审核工单")
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.status not in [WorkOrderStatusEnum.SUBMITTED, WorkOrderStatusEnum.UNDER_REVIEW]:
        raise HTTPException(status_code=400, detail=f"当前状态不允许审核：{wo.status}")

    # 检查是否有不合格的检查项，如果有则不能通过
    if req.action == "approve" and wo.inspection_id:
        pending_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == wo.inspection_id,
            (InspectionCheckItem.review_status.is_(None)) | (InspectionCheckItem.review_status.in_(["", "pending"]))
        ).all()
        if pending_items:
            names = [i.item_name for i in pending_items[:10]]
            extra = f" 等{len(pending_items)}项" if len(pending_items) > 10 else ""
            raise HTTPException(
                status_code=400,
                detail=f"不能通过工单审核，仍有 {len(pending_items)} 项检查项未审核：{', '.join(names)}{extra}"
            )

        failed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == wo.inspection_id,
            InspectionCheckItem.review_status == "fail"
        ).all()
        
        if failed_items:
            failed_names = [item.item_name for item in failed_items]
            raise HTTPException(
                status_code=400, 
                detail=f"不能通过工单审核，存在不合格的检查项：{', '.join(failed_names)}"
            )

    old = wo.status
    if req.action == "approve":
        # 勘察类：审核即视为完成；开站类：仅标记为 APPROVED，待 OMC 达标后自动推进
        if wo.type == WorkOrderTypeEnum.SITE_SURVEY:
            wo.status = WorkOrderStatusEnum.COMPLETED
            wo.completed_at = datetime.utcnow()
        elif wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
            wo.status = WorkOrderStatusEnum.APPROVED
            # 站点从 construction/planning/planned 进入 pending_online
            site = db.query(Site).filter(Site.id == wo.site_id).first()
            if site and site.status in ("construction", "planning", "planned"):
                old_site_status = site.status
                site.status = "pending_online"
                print(
                    f"[站点状态自动更新] 站点 {site.id} ({site.site_name}) "
                    f"状态从 {old_site_status} 更新为 {site.status} (开站工单审核通过，待上线)"
                )
        elif wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            # 设备更换：审核通过后进入待上线/待激活推进（复用 OMC ever 推进，不走开站的站点状态分支）
            wo.status = WorkOrderStatusEnum.APPROVED
        elif wo.type == WorkOrderTypeEnum.SSV:
            wo.status = WorkOrderStatusEnum.COMPLETED
            wo.completed_at = datetime.utcnow()
            # SSV 审核完成即视为通过
            site = db.query(Site).filter(Site.id == wo.site_id).first()
            if site:
                site.ssv_passed = True
        else:
            wo.status = WorkOrderStatusEnum.COMPLETED
            wo.completed_at = datetime.utcnow()
        # 同步检查状态与结果
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.APPROVED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = req.comments
                if req.score is not None:
                    inspection.score = req.score
                    inspection.result = "pass" if req.score >= 60 else "fail"
        # 站点状态更新
        if wo.status == WorkOrderStatusEnum.COMPLETED:
            _update_site_status_on_work_order_complete(db, wo.site_id, wo.type)

        # 开站/设备更换工单审核通过后立即触发一次 OMC 检查（单工单）
        if wo.type in (WorkOrderTypeEnum.OPENING_INSPECTION, WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT) and wo.status == WorkOrderStatusEnum.APPROVED:
            try:
                from app.services.omc_monitor import run_omc_check_for_work_order
                run_omc_check_for_work_order(wo.id)
            except Exception as exc:  # pragma: no cover
                print(f"[OMC] 审核后立即检查失败 work_order_id={wo.id}: {exc}")
            # 若已存在“ever”达标（例如提前手工确认），尝试直接推进（不依赖 OMC 实时查询）
            try:
                db.flush()
                if wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
                    advance_opening_work_orders_by_ever(db, wo.site_id)
                else:
                    advance_replacement_work_orders_by_ever(db, wo.site_id)
            except Exception as exc:  # pragma: no cover
                print(f"[OMC] 基于 ever 推进失败 site_id={wo.site_id}: {exc}")
        # 审核通过时建立/追加档案快照
        try:
            if wo.inspection_id:
                if wo.type == WorkOrderTypeEnum.SITE_SURVEY:
                    from app.services.survey_archive_service import create_or_append_archive
                    create_or_append_archive(
                        db,
                        inspection_id=wo.inspection_id,
                        operator_id=current_user.id,
                        change_summary=req.comments or "审核通过"
                    )
                elif wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
                    from app.services.opening_archive_service import create_or_append_archive as create_opening_archive
                    create_opening_archive(
                        db,
                        inspection_id=wo.inspection_id,
                        operator_id=current_user.id,
                        change_summary=req.comments or "审核通过"
                    )
                elif wo.type == WorkOrderTypeEnum.SSV:
                    from app.services.ssv_archive_service import create_or_append_archive as create_ssv_archive
                    create_ssv_archive(
                        db,
                        inspection_id=wo.inspection_id,
                        operator_id=current_user.id,
                        change_summary=req.comments or "审核通过"
                    )
        except Exception as e:
            print(f"[WARN] 创建/追加档案失败(final_review): {e}")
    else:
        wo.status = WorkOrderStatusEnum.REJECTED
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.REJECTED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = req.comments
                inspection.review_comments_i18n = req.comments_i18n

        # 设备更换工单：驳回时回滚站点状态
        if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            try:
                site = db.query(Site).filter(Site.id == wo.site_id).first()
                extra = wo.extra_data or {}
                before = (extra.get("site_status_before") or "").strip()
                if site and before and site.status != before:
                    old_site_status = site.status
                    site.status = before
                    _audit_site_status_change(
                        db,
                        site.id,
                        old_site_status,
                        site.status,
                        "设备更换工单驳回，站点状态回滚",
                    )
            except Exception as exc:  # pragma: no cover
                print(f"[WARN] 设备更换工单驳回回滚站点状态失败: {exc}")

    wo.reviewed_by = current_user.id
    wo.reviewed_at = datetime.utcnow()
    wo.review_comments = req.comments
    wo.review_comments_i18n = req.comments_i18n
    if req.score is not None:
        wo.score = req.score
    db.commit()
    _audit(db, "work_order", work_order_id, "final_review", current_user.id, from_status=old.value, to_status=wo.status.value, comments=req.comments)
    return {"message": "审核完成", "work_order": _enrich_work_order_response(db, wo)}


@router.post("/{work_order_id}/omc/manual-confirm")
async def manual_confirm_opening_omc_status(
    work_order_id: str,
    payload: WorkOrderOmcManualConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开站/设备更换：设备在线/激活状态手工确认。

    仅在 OMC API 配置开启手工确认开关后可用。

    - confirm_online: 标注该 SN 已上线
    - confirm_activated: 标注该 SN 已激活（同时隐式标注已上线）
    """
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限进行手工确认")

    if not get_omc_manual_confirm_enabled(db):
        raise HTTPException(status_code=403, detail="手工确认功能未开启，请在 OMC API 配置中开启")

    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.type not in (WorkOrderTypeEnum.OPENING_INSPECTION, WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT):
        raise HTTPException(status_code=400, detail="仅开站/设备更换工单支持手工确认设备状态")
    if wo.status in (WorkOrderStatusEnum.REJECTED, WorkOrderStatusEnum.COMPLETED):
        raise HTTPException(status_code=409, detail=f"当前工单状态不允许手工确认：{wo.status}")

    sn = (payload.sn or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="设备 SN 不能为空")

    confirm_activated = bool(payload.confirm_activated)
    confirm_online = bool(payload.confirm_online) or confirm_activated
    if not confirm_online and not confirm_activated:
        raise HTTPException(status_code=400, detail="请至少选择确认“已上线”或“已激活”")

    # 校验：只能对当前站点已绑定的设备 SN 进行确认
    bound_sns = get_bound_sns_for_site(db, wo.site_id)
    if sn not in bound_sns:
        raise HTTPException(status_code=400, detail="该设备 SN 未绑定到当前站点，无法确认")

    old_status = wo.status

    status_payload = {
        "manual_confirm": True,
        "work_order_id": wo.id,
        "site_id": wo.site_id,
        "operator_id": current_user.id,
        "confirm_online": bool(confirm_online),
        "confirm_activated": bool(confirm_activated),
        "confirmed_at": datetime.utcnow().isoformat() + "Z",
    }

    upsert_omc_device_state(
        db=db,
        sn=sn,
        online_raw=True if confirm_online else None,
        activated_raw=True if confirm_activated else None,
        source="manual_confirm",
        status_payload=status_payload,
    )

    # autoflush=False：需要显式 flush，保证后续汇总/推进能读到最新写入
    db.flush()

    advance_result = {}
    try:
        if wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
            advance_result = advance_opening_work_orders_by_ever(db, wo.site_id)
        else:
            advance_result = advance_replacement_work_orders_by_ever(db, wo.site_id)
    except Exception as exc:  # pragma: no cover
        print(f"[OMC] 手工确认后推进工单/站点失败 site_id={wo.site_id}: {exc}")

    # 审计日志（记录手工确认行为，并捕获可能的状态变化）
    audit = AuditEvent(
        id=str(uuid.uuid4()),
        resource_type="work_order",
        resource_id=work_order_id,
        action="omc_manual_confirm",
        from_status=str(getattr(old_status, "value", old_status)),
        to_status=str(getattr(wo.status, "value", wo.status)),
        operator_id=current_user.id,
        comments=None,
        details={
            "sn": sn,
            "confirm_online": bool(confirm_online),
            "confirm_activated": bool(confirm_activated),
            "advance_result": advance_result,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "message": "手工确认成功",
        "work_order": _enrich_work_order_response(db, wo),
        "advance_result": advance_result,
    }


def _update_work_order_result(db: Session, work_order_id: str):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or not wo.inspection_id:
        return
    
    items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).all()
    result = None
    if any(i.review_status == "fail" for i in items):
        result = "fail"
    elif any(i.review_status == "warning" for i in items):
        result = "warning"
    elif items and all(i.review_status == "pass" for i in items if i.review_status is not None):
        result = "pass"
    
    wo.result = result
    db.commit()


def _resolve_template_for_work_order(db: Session, wo: WorkOrder):
    site = db.query(Site).filter(Site.id == wo.site_id).first()
    resolver = create_resolver(db)
    ctx = ResolveContext(
        site_id=wo.site_id,
        site_type=getattr(site, 'site_type', None),
        task_type=wo.type.value,
        region=getattr(site, 'region', None),
        customer=getattr(site, 'customer', None),
        tags=[]
    )
    match = resolver.resolve_template(ctx)
    return match.template if match else None


@router.get("/{work_order_id}/items/field-schema")
async def get_item_field_schema(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """返回每个检查项的字段定义（若模板未定义，返回通用字段）"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_field_worker(current_user) and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该工单")
    _ensure_surveyor_wo_type(wo, current_user)

    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")

    template = _resolve_template_for_work_order(db, wo)
    items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).all()

    # 构建模板 items 索引（按基础 item_id）
    tpl_index = {}
    if template:
        for cat in template.template_data.get("check_categories", []):
            for it in cat.get("items", []):
                base_id = it.get("item_id")
                if base_id:
                    tpl_index[base_id] = it

    def default_fields(required_type: str):
        fields = []
        # 提供一个通用备注字段
        fields.append({
            "field_id": "note",
            "label": "备注",
            "type": "text",
            "required": False,
        })
        # 可扩展更多默认字段
        return fields

    result = []
    for it in items:
        base_id = it.item_id.split("_sector_")[0] if "_sector_" in it.item_id else it.item_id
        tpl_item = tpl_index.get(base_id)
        fields = []
        if tpl_item and isinstance(tpl_item, dict) and tpl_item.get("fields"):
            fields = tpl_item.get("fields")
        else:
            fields = default_fields(it.required_type)
        result.append({
            "item_id": it.id,
            "base_item_id": base_id,
            "fields": fields
        })

    return result


@router.post("/{work_order_id}/submit")
async def submit_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交工单等待审核"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有被分配人才能提交
    if wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="只有被分配人才能提交工单")
    _ensure_surveyor_wo_type(wo, current_user)
    
    # 允许从ACTIVE或REJECTED状态提交
    is_resubmit = wo.status == WorkOrderStatusEnum.REJECTED
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"只能提交活跃或驳回状态的工单，当前状态：{wo.status}")
    
    # 检查关联的检查是否完成
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if not inspection:
            raise HTTPException(status_code=400, detail="未找到关联的检查实例")
        
        # 检查所有检查项是否完成
        total_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id
        ).count()
        
        completed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id,
            InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
        ).count()
        
        if completed_items < total_items:
            raise HTTPException(
                status_code=400, 
                detail=f"检查未完成，已完成 {completed_items}/{total_items} 项"
            )
        
        # 同步检查状态
        inspection.status = InspectionStatusEnum.SUBMITTED
        inspection.submitted_at = datetime.utcnow()
    
    # 更新工单状态
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.SUBMITTED
    wo.submitted_at = datetime.utcnow()
    
    # 如果是重新提交（从驳回状态），清除工单/检查级别的旧审核信息（检查项采用“增量复审”，不再全量清空）
    if is_resubmit:
        print(f"[重新提交] 工单 {work_order_id} 从驳回状态重新提交，清除工单/检查级审核信息")
        
        # 1. 清除工单级别的审核信息
        wo.review_comments = None
        wo.review_comments_i18n = None
        wo.reviewed_by = None
        wo.reviewed_at = None
        
        # 2. 清除关联检查的审核信息
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(
                SiteInspection.id == wo.inspection_id
            ).first()
            if inspection:
                inspection.review_comments = None
                inspection.review_comments_i18n = None
                inspection.reviewed_by = None
                inspection.reviewed_at = None
    
    # 分配审核人（默认分配给分配人，即管理员）
    wo.reviewer_id = wo.assigned_by
    
    # 同步状态
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    sync_service.sync_work_order_review_info(wo)
    
    db.commit()

    # 同步检查内容至勘察档案（提交时不覆盖已存在字段）
    try:
        from app.services.survey_sync import sync_inspection_to_survey, SyncOptions, PhotoPolicy
        sync_inspection_to_survey(
            db,
            inspection.id,
            SyncOptions(mode='on_submit', overwrite_fields=False, photo_policy=PhotoPolicy.first_per_item)
        )
        db.commit()
    except Exception:
        db.rollback()
    
    _audit(db, "work_order", wo.id, "submit" if not is_resubmit else "resubmit", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {
        "message": "工单提交成功",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/{work_order_id}/recall")
def recall_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """撤回已提交但未完成审核的工单，回到可编辑状态。
    允许状态：SUBMITTED、UNDER_REVIEW。
    权限：工单指派人（assigned_to）或管理员/经理。
    动作：
      - WorkOrder.status -> ACTIVE，submitted_at 置空
      - 同步 SiteInspection.status -> IN_PROGRESS，submitted_at 置空
      - 记录审计日志（action=recall）
    """
    wo: WorkOrder = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")

    # 权限校验：指派人或 admin/manager
    role = getattr(current_user, 'role', None)
    if not (wo.assigned_to == current_user.id or role in ("admin", "manager")):
        raise HTTPException(status_code=403, detail="仅指派人或管理员可撤回")

    # 状态校验
    if wo.status not in (WorkOrderStatusEnum.SUBMITTED, WorkOrderStatusEnum.UNDER_REVIEW):
        raise HTTPException(status_code=409, detail="当前状态不可撤回")

    old_status = wo.status
    wo.status = WorkOrderStatusEnum.ACTIVE
    wo.submitted_at = None
    wo.updated_at = datetime.utcnow()

    # 同步到检查
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if inspection:
            inspection.status = InspectionStatusEnum.IN_PROGRESS
            inspection.submitted_at = None
            inspection.updated_at = datetime.utcnow()

    # 审计日志
    audit = AuditEvent(
        id=str(uuid.uuid4()),
        resource_type="work_order",
        resource_id=work_order_id,
        action="recall",
        from_status=str(old_status.value if hasattr(old_status, 'value') else old_status),
        to_status=str(wo.status.value if hasattr(wo.status, 'value') else wo.status),
        operator_id=current_user.id,
        comments="用户撤回提交",
        details={}
    )
    db.add(audit)

    # 使用同步服务进行状态一致性同步
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)

    db.commit()
    db.refresh(wo)

    return {
        "message": "撤回成功，已回到可编辑状态",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/{work_order_id}/review")
async def review_work_order(
    work_order_id: str,
    review_data: WorkOrderReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """审核工单"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有管理员、项目经理或指定审核人才能审核
    if (current_user.role not in ["admin", "manager"] and 
        wo.reviewer_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权限审核此工单")
    
    if wo.status != WorkOrderStatusEnum.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"只能审核已提交的工单，当前状态：{wo.status}")
    
    # 更新工单状态
    old_status = wo.status
    
    if review_data.action == "approve":
        # 审核通过：对于普通工单仍视为“已完成”，
        # 对于开站工单则仅进入“待上线”阶段，后续由 OMC 状态推进。
        if wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
            wo.status = WorkOrderStatusEnum.APPROVED  # 80%：待上线
            # 站点状态：从 construction 进入 pending_online（待上线）
            site = db.query(Site).filter(Site.id == wo.site_id).first()
            if site and site.status in ("construction", "planning", "planned"):
                old_site_status = site.status
                site.status = "pending_online"
                print(
                    f"[站点状态自动更新] 站点 {site.id} ({site.site_name}) "
                    f"状态从 {old_site_status} 更新为 {site.status} (开站工单审核通过，待上线)"
                )
        elif wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            wo.status = WorkOrderStatusEnum.APPROVED  # 80%：待上线
        else:
            wo.status = WorkOrderStatusEnum.COMPLETED
            wo.completed_at = datetime.utcnow()
            
            # 自动更新站点状态（勘察/其他工单沿用原有逻辑）
            _update_site_status_on_work_order_complete(db, wo.site_id, wo.type)
        
        # 同步检查状态
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.APPROVED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = review_data.comments
                inspection.review_comments_i18n = review_data.comments_i18n
                if review_data.score:
                    inspection.score = review_data.score
                    inspection.result = "pass" if review_data.score >= 60 else "fail"
        
    elif review_data.action == "reject":
        wo.status = WorkOrderStatusEnum.REJECTED  # 驳回状态
        
        # 同步检查状态
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.REJECTED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = review_data.comments
                inspection.review_comments_i18n = review_data.comments_i18n
                inspection.result = "fail"

        # 设备更换工单：驳回时回滚站点状态
        if wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            try:
                site = db.query(Site).filter(Site.id == wo.site_id).first()
                extra = wo.extra_data or {}
                before = (extra.get("site_status_before") or "").strip()
                if site and before and site.status != before:
                    old_site_status = site.status
                    site.status = before
                    _audit_site_status_change(
                        db,
                        site.id,
                        old_site_status,
                        site.status,
                        "设备更换工单驳回，站点状态回滚",
                    )
            except Exception as exc:  # pragma: no cover
                print(f"[WARN] 设备更换工单驳回回滚站点状态失败: {exc}")
    
    # 更新审核信息
    wo.reviewed_at = datetime.utcnow()
    wo.review_comments = review_data.comments
    wo.review_comments_i18n = review_data.comments_i18n
    
    # 同步状态
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    sync_service.sync_work_order_review_info(wo)
    
    db.commit()

    # 审核通过后：
    # 1) 旧链路：最终同步到旧site_surveys（允许覆盖）
    # 2) 新链路：创建/追加“勘察档案快照”版本（严格跟随模板结构）
    if review_data.action == "approve" and wo.inspection_id:
        try:
            from app.services.survey_sync import sync_inspection_to_survey, SyncOptions, PhotoPolicy
            survey = sync_inspection_to_survey(
                db,
                wo.inspection_id,
                SyncOptions(mode='on_approve', overwrite_fields=True, photo_policy=PhotoPolicy.categorized_best, per_category_limit=8)
            )
            if survey:
                review_info = {
                    'status': 'approved',
                    'score': getattr(wo, 'score', None),
                    'reviewed_by': current_user.id,
                    # 审核时间按 UTC ISO 输出，便于前端统一解析
                    'reviewed_at': to_utc_iso(datetime.utcnow()),
                    'comments': review_data.comments,
                }
                try:
                    extra = survey.extra_data or {}
                    extra['review'] = review_info
                    survey.extra_data = extra
                    db.commit()
                except Exception:
                    db.rollback()
        except Exception:
            db.rollback()

        # 新档案：仅在审核通过时建立/追加快照版本
        try:
            from app.services.survey_archive_service import create_or_append_archive
            create_or_append_archive(
                db,
                inspection_id=wo.inspection_id,
                operator_id=current_user.id,
                change_summary=review_data.comments or "审核通过"
            )
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[WARN] 创建/追加勘察档案失败: {e}")
    
    _audit(
        db,
        "work_order",
        wo.id,
        f"review_{review_data.action}",
        current_user.id,
        from_status=old_status.value,
        to_status=wo.status.value,
        comments=review_data.comments,
    )
    
    # 对于开站/设备更换工单：审核通过后触发一次后台 OMC 状态检查
    if review_data.action == "approve" and wo.type in (WorkOrderTypeEnum.OPENING_INSPECTION, WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT):
        try:
            run_omc_check_for_work_order(wo.id)
        except Exception as exc:  # pragma: no cover - OMC 故障不影响审核主流程
            print(f"[OMC] 审核后触发开站工单检查失败 work_order_id={wo.id}: {exc}")
    
    return {
        "message": f"工单{review_data.action}成功",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/batch-operation")
async def batch_work_order_operation(
    operation: WorkOrderBatchOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量工单操作"""
    # 只有admin和manager可以批量操作
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and manager can perform batch operations"
        )
    
    if not operation.work_order_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No work order IDs provided"
        )
    
    work_orders = db.query(WorkOrder).filter(WorkOrder.id.in_(operation.work_order_ids)).all()
    
    if len(work_orders) != len(operation.work_order_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some work orders not found"
        )
    
    # 执行批量操作
    updated_count = 0
    error_count = 0
    errors = []
    rolled_back_site_ids = set()
    rolled_back_replacement_site_ids = set()
    
    for wo in work_orders:
        try:
            if operation.operation == "delete":
                # 检查工单状态：只能删除待分配或已分配状态的工单
                if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
                    errors.append(f"工单 {wo.id} 状态不允许删除: {wo.status}")
                    error_count += 1
                    continue

                # 解绑检查项要求：存在设备级绑定则禁止删除
                if _has_bound_device_check_items(db, wo):
                    errors.append(f"工单 {wo.id} 存在已绑定设备检查项，无法删除；请先在APP解绑设备")
                    error_count += 1
                    continue

                # 若已生成档案，禁止删除（保证可追溯性）
                if db.query(SiteSurveyArchive).filter(SiteSurveyArchive.work_order_id == wo.id).first():
                    errors.append(f"工单 {wo.id} 已生成勘察档案，无法删除")
                    error_count += 1
                    continue
                if db.query(SiteOpeningArchive).filter(SiteOpeningArchive.work_order_id == wo.id).first():
                    errors.append(f"工单 {wo.id} 已生成开站档案，无法删除")
                    error_count += 1
                    continue
                if db.query(SiteSSVArchive).filter(SiteSSVArchive.work_order_id == wo.id).first():
                    errors.append(f"工单 {wo.id} 已生成 SSV 档案，无法删除")
                    error_count += 1
                    continue

                # 记录原始状态用于审计
                old_status = wo.status
                old_wo_type = wo.type
                old_site_id = wo.site_id
                site_status_before = None
                if old_wo_type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
                    try:
                        extra = wo.extra_data or {}
                        site_status_before = extra.get("site_status_before")
                    except Exception:
                        site_status_before = None

                # 删除安装工单时：若该站点删除后无安装工单，则回滚站点状态到 planned（批量删除：按“删除集合后”计算）
                remaining_opening_orders = None
                if (
                    old_wo_type == WorkOrderTypeEnum.OPENING_INSPECTION
                    and old_site_id not in rolled_back_site_ids
                ):
                    remaining_opening_orders = db.query(WorkOrder).filter(
                        WorkOrder.site_id == old_site_id,
                        WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
                        ~WorkOrder.id.in_(operation.work_order_ids),
                    ).count()

                # 若历史库存记录绑定了工单，先解除绑定（保留库存数据）
                _detach_stock_records_from_work_order(db, wo)

                # 删除/解绑与工单相关的勘察草稿（SiteSurvey）
                surveys = db.query(SiteSurvey).filter(SiteSurvey.work_order_id == wo.id).all()
                for s in surveys:
                    db.delete(s)

                # 删除可能遗留的 work_order_items（历史表）
                db.query(WorkOrderItem).filter(WorkOrderItem.work_order_id == wo.id).delete(synchronize_session=False)

                # 如果有关联的检查记录，需要同时删除，逻辑与单条删除保持一致
                inspections_to_delete = []
                seen_inspection_ids = set()

                if wo.inspection_id:
                    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
                    if inspection:
                        inspections_to_delete.append(inspection)
                        seen_inspection_ids.add(inspection.id)

                extra_inspections = db.query(SiteInspection).filter(SiteInspection.work_order_id == wo.id).all()
                for insp in extra_inspections:
                    if insp.id not in seen_inspection_ids:
                        inspections_to_delete.append(insp)
                        seen_inspection_ids.add(insp.id)

                if inspections_to_delete:
                    for insp in inspections_to_delete:
                        insp.work_order_id = None
                    wo.inspection_id = None
                    db.flush()
                    for insp in inspections_to_delete:
                        db.delete(insp)

                # 删除工单
                db.delete(wo)

                # 站点状态回滚：删除安装工单且删除后不存在其它安装工单
                if (
                    old_wo_type == WorkOrderTypeEnum.OPENING_INSPECTION
                    and remaining_opening_orders == 0
                    and old_site_id not in rolled_back_site_ids
                ):
                    site = db.query(Site).filter(Site.id == old_site_id).first()
                    if site and site.status != "planned":
                        old_site_status = site.status
                        site.status = "planned"
                        _audit_site_status_change(
                            db,
                            old_site_id,
                            old_site_status,
                            site.status,
                            "批量删除安装工单，站点状态回滚至 planned",
                        )
                    rolled_back_site_ids.add(old_site_id)

                # 设备更换工单：批量删除时回滚站点状态到 site_status_before
                if (
                    old_wo_type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT
                    and old_site_id not in rolled_back_replacement_site_ids
                ):
                    site = db.query(Site).filter(Site.id == old_site_id).first()
                    before = str(site_status_before or "").strip()
                    if site and before and site.status == "maintenance" and site.status != before:
                        old_site_status = site.status
                        site.status = before
                        _audit_site_status_change(
                            db,
                            old_site_id,
                            old_site_status,
                            site.status,
                            "批量删除设备更换工单，站点状态回滚",
                        )
                    rolled_back_replacement_site_ids.add(old_site_id)

                _audit(db, "work_order", wo.id, "batch_delete", current_user.id,
                       from_status=old_status.value, to_status="deleted")
                updated_count += 1
                
            elif operation.operation == "change_status" and operation.value:
                try:
                    new_status = WorkOrderStatusEnum(operation.value)
                    old_status = wo.status
                    wo.status = new_status
                    _audit(db, "work_order", wo.id, "batch_status_change", current_user.id,
                           from_status=old_status.value, to_status=new_status.value)
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效状态: {operation.value}")
                    error_count += 1
                    
            elif operation.operation == "change_assignee" and operation.value:
                try:
                    # 检查工单状态：只能重新分配待分配或已分配状态的工单
                    if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
                        errors.append(f"工单 {wo.id} 状态不允许重新分配: {wo.status}")
                        error_count += 1
                        continue
                    
                    new_assignee_id = int(operation.value)
                    # 检查用户是否存在
                    assignee = db.query(User).filter(User.id == new_assignee_id).first()
                    if not assignee:
                        errors.append(f"工单 {wo.id} 分配人不存在: {new_assignee_id}")
                        error_count += 1
                        continue
                    
                    old_assignee_id = wo.assigned_to
                    old_assignee = db.query(User).filter(User.id == old_assignee_id).first()

                    wo.assigned_to = new_assignee_id
                    wo.assigned_by = current_user.id
                    wo.assigned_at = datetime.utcnow()

                    if wo.inspection_id:
                        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
                        if inspection:
                            inspection.inspector_id = new_assignee_id

                    _audit(db, "work_order", wo.id, "batch_assignee_change", current_user.id,
                           details={
                               "old_assignee_id": old_assignee_id,
                               "old_assignee_name": (old_assignee.full_name or old_assignee.username) if old_assignee else None,
                               "new_assignee_id": new_assignee_id,
                               "new_assignee_name": (assignee.full_name or assignee.username) if assignee else None,
                           })
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效分配人ID: {operation.value}")
                    error_count += 1
                    
            elif operation.operation == "change_priority" and operation.value:
                try:
                    new_priority = WorkOrderPriorityEnum(operation.value)
                    wo.priority = new_priority
                    _audit(db, "work_order", wo.id, "batch_priority_change", current_user.id,
                           details={"new_priority": new_priority.value})
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效优先级: {operation.value}")
                    error_count += 1
                    
        except Exception as e:
            errors.append(f"工单 {wo.id} 操作失败: {str(e)}")
            error_count += 1
    
    db.commit()
    
    result = {
        "message": f"批量操作完成，成功 {updated_count} 个，失败 {error_count} 个",
        "updated_count": updated_count,
        "error_count": error_count
    }
    
    if errors:
        result["errors"] = errors
    
    return result


@router.get("/stats/summary")
async def get_work_order_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单统计信息"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    total_work_orders = db.query(WorkOrder).count()
    
    # 按状态统计
    status_stats = {}
    for status_enum in WorkOrderStatusEnum:
        count = db.query(WorkOrder).filter(WorkOrder.status == status_enum).count()
        status_stats[status_enum.value] = count
    
    # 按类型统计
    type_stats = {}
    for type_enum in WorkOrderTypeEnum:
        count = db.query(WorkOrder).filter(WorkOrder.type == type_enum).count()
        type_stats[type_enum.value] = count
    
    # 按优先级统计
    priority_stats = {}
    for priority_enum in WorkOrderPriorityEnum:
        count = db.query(WorkOrder).filter(WorkOrder.priority == priority_enum).count()
        priority_stats[priority_enum.value] = count
    
    return {
        "total_work_orders": total_work_orders,
        "status_stats": status_stats,
        "type_stats": type_stats,
        "priority_stats": priority_stats
    }


@router.post("/{work_order_id}/check-activation")
async def check_equipment_activation(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发设备开通检测"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限执行设备开通检测")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.status != WorkOrderStatusEnum.APPROVED:
        raise HTTPException(
            status_code=400, 
            detail=f"只有审核通过的工单才能进行设备开通检测，当前状态：{wo.status}"
        )
    
    from app.services.equipment_activation_service import EquipmentActivationService
    
    service = EquipmentActivationService(db)
    result = await service.trigger_equipment_activation_check(work_order_id)
    
    return result


@router.get("/{work_order_id}/activation-status")
async def get_activation_status(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单设备开通状态"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    activation_check = wo.extra_data.get("activation_check") if wo.extra_data else None
    
    return {
        "work_order_id": work_order_id,
        "status": wo.status.value,
        "activation_check": activation_check,
        "last_check_time": wo.extra_data.get("activation_check_time") if wo.extra_data else None,
        # activated_at 使用 utcnow 写入，视为 UTC 输出
        "activated_at": to_utc_iso(wo.activated_at) if wo.activated_at else None
    }


@router.post("/{work_order_id}/mark-completed")
async def mark_work_order_completed(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将已开通的工单标记为完成"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限完成工单")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.status != WorkOrderStatusEnum.ACTIVATED:
        raise HTTPException(
            status_code=400,
            detail=f"只有已开通的工单才能标记为完成，当前状态：{wo.status}"
        )
    
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()
    
    # 自动更新站点状态
    _update_site_status_on_work_order_complete(db, wo.site_id, wo.type)
    
    db.commit()
    
    _audit(db, "work_order", work_order_id, "mark_completed", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {
        "message": "工单已标记为完成",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/{work_order_id}/finalize-survey")
async def finalize_survey_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将勘察类工单从 APPROVED 升级为 COMPLETED，并补建勘察档案快照。

    用于老逻辑已将审核通过置为 APPROVED(85%) 的存量工单修正为 100%。
    """
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限执行该操作")

    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.type != WorkOrderTypeEnum.SITE_SURVEY:
        raise HTTPException(status_code=400, detail="仅支持勘察类工单")
    if wo.status not in [WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.UNDER_REVIEW, WorkOrderStatusEnum.SUBMITTED]:
        raise HTTPException(status_code=400, detail=f"当前状态不需要或不允许完成：{wo.status}")

    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()

    # 更新检查记录状态（若存在）
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if inspection:
            inspection.status = InspectionStatusEnum.APPROVED
            inspection.reviewed_by = current_user.id
            inspection.reviewed_at = datetime.utcnow()

    # 建立/追加档案
    try:
        from app.services.survey_archive_service import create_or_append_archive
        if wo.inspection_id:
            create_or_append_archive(db, inspection_id=wo.inspection_id, operator_id=current_user.id, change_summary="Finalize补建")
    except Exception as e:
        print(f"[WARN] finalize-survey 建档失败: {e}")

    db.commit()
    _audit(db, "work_order", work_order_id, "finalize_survey", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)

    return {"message": "已完成并补建档案", "work_order": _enrich_work_order_response(db, wo)}


@router.get("/{work_order_id}/progress")
async def get_work_order_progress(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单进度信息"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    from app.utils.work_order_progress import WorkOrderProgressCalculator
    
    progress_info = WorkOrderProgressCalculator.calculate_progress(db, wo)
    
    return {
        "work_order_id": work_order_id,
        "status": wo.status.value,
        "stage_name": WorkOrderProgressCalculator.get_stage_name(wo.status),
        "next_action": WorkOrderProgressCalculator.get_next_action(wo.status),
        "progress_color": WorkOrderProgressCalculator.get_progress_color(progress_info["progress"]),
        **progress_info
    }


@router.get("/{work_order_id}/audit-logs")
async def get_work_order_audit_logs(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单审核历史日志"""
    # 验证工单存在
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：施工员只能查看自己的工单
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单审核历史")
    
    # 查询工单相关的审核日志
    audit_logs = db.query(AuditEvent).filter(
        AuditEvent.resource_type == "work_order",
        AuditEvent.resource_id == work_order_id
    ).order_by(AuditEvent.created_at.desc()).all()

    # 如果有关联的检查，也获取检查的审核日志 + 设备绑定历史
    insp_logs = []
    binding_logs = []
    if wo.inspection_id:
        from app.models.inspection import InspectionAuditLog
        from app.models.equipment_binding_history import EquipmentBindingHistory

        insp_logs = db.query(InspectionAuditLog).filter(
            InspectionAuditLog.inspection_id == wo.inspection_id
        ).order_by(InspectionAuditLog.created_at.desc()).all()

        binding_logs = db.query(EquipmentBindingHistory).filter(
            EquipmentBindingHistory.inspection_id == wo.inspection_id
        ).order_by(EquipmentBindingHistory.operated_at.desc()).all()

    # 一次性查询操作人信息，避免 N+1
    operator_ids = {log.operator_id for log in audit_logs if getattr(log, "operator_id", None)}
    operator_ids |= {log.operator_id for log in insp_logs if getattr(log, "operator_id", None)}
    operator_ids |= {log.operator_id for log in binding_logs if getattr(log, "operator_id", None)}
    users = db.query(User).filter(User.id.in_(list(operator_ids))).all() if operator_ids else []
    user_map = {u.id: u for u in users}

    # 转换为响应格式（保持兼容：work_order_logs / inspection_logs）
    logs_data = []
    for log in audit_logs:
        operator = user_map.get(log.operator_id)
        logs_data.append({
            "id": log.id,
            "action": log.action,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_id": log.operator_id,
            "operator_name": (operator.full_name if operator else None) or (operator.username if operator else None) or "未知",
            "operator_username": operator.username if operator else "unknown",
            "comments": log.comments,
            "details": log.details,
            # 审计日志创建时间来自数据库时间，视为 UTC
            "created_at": to_utc_iso(log.created_at) if log.created_at else None
        })

    inspection_logs = []
    for log in insp_logs:
        operator = user_map.get(log.operator_id)
        inspection_logs.append({
            "id": log.id,
            "action": log.action,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_id": log.operator_id,
            "operator_name": (operator.full_name if operator else None) or (operator.username if operator else None) or "未知",
            "operator_username": operator.username if operator else "unknown",
            "comments": log.comments,
            "details": log.details,
            "created_at": to_utc_iso(log.created_at) if log.created_at else None
        })

    # 统一时间轴（工单 + 检查 + 绑定）
    timeline = []
    for log in audit_logs:
        operator = user_map.get(log.operator_id)
        dt = log.created_at
        timeline.append({
            "id": f"work_order:{log.id}",
            "source": "work_order",
            "source_label": "工单",
            "action": log.action,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_id": log.operator_id,
            "operator_name": (operator.full_name if operator else None) or (operator.username if operator else None) or "未知",
            "operator_username": operator.username if operator else "unknown",
            "comments": log.comments,
            "details": log.details,
            "created_at": to_utc_iso(dt) if dt else None,
            "_sort_dt": dt,
        })

    for log in insp_logs:
        operator = user_map.get(log.operator_id)
        dt = log.created_at
        timeline.append({
            "id": f"inspection:{log.id}",
            "source": "inspection",
            "source_label": "检查",
            "action": log.action,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_id": log.operator_id,
            "operator_name": (operator.full_name if operator else None) or (operator.username if operator else None) or "未知",
            "operator_username": operator.username if operator else "unknown",
            "comments": log.comments,
            "details": log.details,
            "created_at": to_utc_iso(dt) if dt else None,
            "_sort_dt": dt,
        })

    for log in binding_logs:
        operator = user_map.get(log.operator_id)
        dt = getattr(log, "operated_at", None) or getattr(log, "created_at", None)
        action_value = getattr(log.action, "value", log.action)
        timeline.append({
            "id": f"binding:{log.id}",
            "source": "binding",
            "source_label": "绑定",
            "action": str(action_value),
            "from_status": None,
            "to_status": None,
            "operator_id": log.operator_id,
            "operator_name": (operator.full_name if operator else None) or (operator.username if operator else None) or "未知",
            "operator_username": operator.username if operator else "unknown",
            "comments": log.notes,
            "details": {
                "inspection_id": log.inspection_id,
                "check_item_id": log.check_item_id,
                "equipment_sn": log.equipment_sn,
                "previous_equipment_sn": log.previous_equipment_sn,
                "sector_id": log.sector_id,
                "band": log.band,
                "cell_id": log.cell_id,
            },
            "created_at": to_utc_iso(dt) if dt else None,
            "_sort_dt": dt,
        })

    # 默认：按时间倒序（最新在前）
    timeline.sort(key=lambda x: x.get("_sort_dt") or datetime.min, reverse=True)
    for x in timeline:
        x.pop("_sort_dt", None)

    return {
        "work_order_id": work_order_id,
        "work_order_logs": logs_data,
        "inspection_logs": inspection_logs,
        "binding_logs": [t for t in timeline if t.get("source") == "binding"],
        "timeline": timeline,
        "total_count": len(timeline)
    }
