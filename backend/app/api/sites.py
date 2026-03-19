from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, aliased
from typing import List, Optional, Dict
import uuid
import io
import pandas as pd
from datetime import datetime
import math

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.schemas.site import (
    SiteCreate,
    SiteUpdate,
    SiteResponse,
    SiteBatchUpdateRequest,
    SiteBatchUpdateReport,
    SiteBatchUpdateRowResult,
    BasicBatchImportReport,
    BasicImportRowResult,
    BasicImportHistoryItem,
    SiteListResponse,
)
from app.api.auth import get_current_user
from sqlalchemy import func, or_, and_
from pydantic import BaseModel
from app.models.work_order import AuditEvent, WorkOrder, WorkOrderTypeEnum, WorkOrderStatusEnum
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.planning import SitePlanning, SitePlanningCell
from app.models.inspection import SiteInspection, Inspection as LegacyInspection, BaseStationDevice, TemplateBinding
from app.models.survey import SiteSurvey
from app.models.survey_archive import SiteSurveyArchive
from app.models.opening_archive import SiteOpeningArchive
from app.models.ssv_archive import SiteSSVArchive
from app.services.data_scope_service import get_user_data_scope
from app.services.omc_client import (
    get_omc_client,
    get_omc_manual_confirm_enabled,
    parse_online_flag,
    parse_activated_flag,
    is_success_status_payload,
)
from app.services.omc_state import summarize_site_omc_state, upsert_omc_device_state
from app.services.authz_service import user_has_any_role_or_permission
from app.services.site_progress_service import (
    ensure_site_progress_snapshots,
    get_site_progress_milestone_at,
    get_site_progress_snapshot,
    rebuild_site_progress,
    rebuild_site_progress_for_sites,
)
from app.services.site_progress_metric_service import get_site_progress_metric_mode
from app.utils.timezone import to_utc_iso
from app.services.omc_monitor import (
    advance_opening_work_orders_by_ever,
    advance_replacement_work_orders_by_ever,
)
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


def _ensure_site_manage_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["sites:create:write", "sites:update:write", "sites:survey-stage:write"],
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def _can_view_all_sites(current_user: User) -> bool:
    return str(get_user_data_scope(current_user, "sites") or "all").strip() == "all"


def _apply_site_visibility_filter(query, db: Session, current_user: User):
    """Apply site visibility rules based on the current user's role.

    Rules:
    - admin/manager/planner: can view all sites
    - all other roles: can only view sites that have work orders assigned to them,
      including completed work orders.
    """
    if _can_view_all_sites(current_user):
        return query

    site_ids = (
        db.query(WorkOrder.site_id)
        .filter(WorkOrder.assigned_to == current_user.id)
        .distinct()
    )
    return query.filter(Site.id.in_(site_ids))


def _ensure_site_visible(site_id: int, db: Session, current_user: User) -> None:
    if _can_view_all_sites(current_user):
        return

    exists = (
        db.query(WorkOrder.id)
        .filter(
            WorkOrder.site_id == site_id,
            WorkOrder.assigned_to == current_user.id,
        )
        .first()
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


class SiteDeleteCheckResponse(BaseModel):
    can_delete: bool
    total_related: int
    counts: Dict[str, int]


class SiteSurveySkipRequest(BaseModel):
    reason: Optional[str] = None


class SiteSurveyRequireRequest(BaseModel):
    reason: Optional[str] = None


class SiteMilestonesResponse(BaseModel):
    install_started_at: Optional[str] = None
    install_completed_at: Optional[str] = None
    online_at: Optional[str] = None
    activated_at: Optional[str] = None
    ssv_at: Optional[str] = None


class SiteProgressRebuildRequest(BaseModel):
    site_ids: Optional[List[int]] = None
    force: bool = True
    reason: Optional[str] = None


class SiteProgressRebuildResponse(BaseModel):
    requested_count: int
    rebuilt_count: int
    skipped_count: int
    site_ids: List[int]


class SurveyStageRowResult(BaseModel):
    row_index: int
    site_code: Optional[str] = None
    site_name: Optional[str] = None
    success: bool
    action: Optional[str] = None  # noop|skipped|required|would_skip|would_require
    site_id: Optional[int] = None
    warnings: Optional[List[str]] = []
    errors: Optional[List[str]] = []


class SurveyStageBatchReport(BaseModel):
    batch_id: str
    dry_run: bool
    action: str  # skip|require
    total_rows: int
    success_count: int
    failed_count: int
    results: List[SurveyStageRowResult]


def _get_site_related_counts(db: Session, site_id: int) -> Dict[str, int]:
    def _count(model, field_name: str = "id") -> int:
        col = getattr(model, field_name)
        return int(db.query(func.count(col)).filter(model.site_id == site_id).scalar() or 0)

    counts = {
        "work_orders": _count(WorkOrder),
        "site_inspections": _count(SiteInspection),
        "inspections": _count(LegacyInspection),
        "site_surveys": _count(SiteSurvey),
        "site_survey_archives": _count(SiteSurveyArchive),
        "site_opening_archives": _count(SiteOpeningArchive),
        "site_ssv_archives": _count(SiteSSVArchive),
        "equipment_binding_history": _count(EquipmentBindingHistory),
        "site_planning": _count(SitePlanning),
        "site_planning_cells": _count(SitePlanningCell),
        "base_station_devices": _count(BaseStationDevice),
        "template_bindings": _count(TemplateBinding),
    }
    return counts

@router.post("/", response_model=SiteResponse)
async def create_site(
    site_data: SiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 检查站点编码是否已存在
    existing_site = db.query(Site).filter(Site.site_code == site_data.site_code).first()
    if existing_site:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site code already exists"
        )
    
    # 创建新站点
    db_site = Site(
        **site_data.dict(),
        created_by=current_user.id
    )
    db.add(db_site)
    db.flush()
    rebuild_site_progress(
        db,
        db_site.id,
        reason="create_site",
        operator_id=current_user.id,
    )
    db.commit()
    db.refresh(db_site)
    
    return SiteResponse.from_orm(db_site)

@router.get("/", response_model=List[SiteResponse])
async def get_sites(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None),
    site_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Site)

    # 权限控制：
    # - admin/manager/planner：可查看全部站点
    # - 其他角色：仅可查看“分配给自己”的工单关联站点（包含已完成工单）
    query = _apply_site_visibility_filter(query, db, current_user)

    # 应用过滤条件
    if status:
        query = query.filter(Site.status == status)
    if site_type:
        query = query.filter(Site.site_type == site_type)
    # assigned_to 仍表示 Site.assigned_to，仅允许管理员/规划角色使用该筛选，避免限制角色误过滤
    if assigned_to and _can_view_all_sites(current_user):
        query = query.filter(Site.assigned_to == assigned_to)

    # 固定排序后再分页，避免跨页重复/漏项
    sites = query.order_by(Site.id.asc()).offset(skip).limit(limit).all()
    return [SiteResponse.from_orm(site) for site in sites]


@router.get("/search", response_model=SiteListResponse)
async def search_sites(
    keyword: Optional[str] = Query(None, description="搜索站点名称/编码/城市"),
    status: Optional[str] = Query(None),
    site_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    sort_by: Optional[str] = Query(None, description="排序字段: site_code|site_name|city|status|created_at|updated_at"),
    sort_order: str = Query("desc", description="排序方向: asc|desc"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=100, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """站点搜索与分页列表（返回总数）"""
    query = db.query(Site)

    query = _apply_site_visibility_filter(query, db, current_user)

    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Site.site_name.contains(keyword),
                Site.site_code.contains(keyword),
                Site.city.contains(keyword),
            )
        )

    # 过滤条件
    if status:
        query = query.filter(Site.status == status)
    if site_type:
        query = query.filter(Site.site_type == site_type)
    if assigned_to and _can_view_all_sites(current_user):
        query = query.filter(Site.assigned_to == assigned_to)

    total = query.count()

    allowed_sort_fields = {
        "site_code": Site.site_code,
        "site_name": Site.site_name,
        "city": Site.city,
        "status": Site.status,
        "created_at": Site.created_at,
        "updated_at": Site.updated_at,
    }

    sort_key = (sort_by or "created_at").strip()
    sort_col = allowed_sort_fields.get(sort_key)
    if not sort_col:
        raise HTTPException(status_code=400, detail="不支持的排序字段")

    order = (sort_order or "desc").strip().lower()
    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="不支持的排序方向")

    primary = sort_col.asc() if order == "asc" else sort_col.desc()
    secondary = Site.id.asc() if order == "asc" else Site.id.desc()
    sites = query.order_by(primary, secondary).offset(skip).limit(limit).all()

    page = (skip // limit) + 1
    pages = math.ceil(total / limit) if limit else 1

    return SiteListResponse(
        sites=[SiteResponse.from_orm(site) for site in sites],
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


@router.post("/progress/rebuild", response_model=SiteProgressRebuildResponse)
async def rebuild_site_progress_endpoint(
    payload: SiteProgressRebuildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_site_manage_access(current_user)

    result = rebuild_site_progress_for_sites(
        db,
        payload.site_ids,
        reason=(payload.reason or "").strip() or "manual_site_progress_rebuild",
        operator_id=current_user.id,
        force=bool(payload.force),
    )
    db.commit()

    rebuilt_site_ids = list(result["rebuilt_site_ids"])
    requested_site_ids = list(result["requested_site_ids"])
    return SiteProgressRebuildResponse(
        requested_count=len(requested_site_ids),
        rebuilt_count=len(rebuilt_site_ids),
        skipped_count=int(result["skipped_count"]),
        site_ids=rebuilt_site_ids,
    )


@router.get("/export")
async def export_sites(
    keyword: Optional[str] = Query(None, description="搜索站点名称/编码/城市"),
    status: Optional[str] = Query(None),
    site_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出站点列表 Excel（按筛选条件，不受分页影响）"""
    assigned_user = aliased(User)
    creator_user = aliased(User)

    query = (
        db.query(Site, assigned_user, creator_user)
        .outerjoin(assigned_user, Site.assigned_to == assigned_user.id)
        .outerjoin(creator_user, Site.created_by == creator_user.id)
    )

    query = _apply_site_visibility_filter(query, db, current_user)

    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                Site.site_name.contains(keyword),
                Site.site_code.contains(keyword),
                Site.city.contains(keyword),
            )
        )

    # 过滤条件
    if status:
        query = query.filter(Site.status == status)
    if site_type:
        query = query.filter(Site.site_type == site_type)
    if assigned_to and _can_view_all_sites(current_user):
        query = query.filter(Site.assigned_to == assigned_to)

    records = query.order_by(Site.id.asc()).all()

    def _display_name(user: Optional[User]) -> Optional[str]:
        if not user:
            return None
        return user.full_name or user.username

    rows = []
    for site, assigned, creator in records:
        rows.append(
            {
                "site_id": site.id,
                "site_code": site.site_code,
                "site_name": site.site_name,
                "site_type": site.site_type,
                "province": site.province,
                "city": site.city,
                "district": site.district,
                "address": site.address,
                "latitude": site.latitude,
                "longitude": site.longitude,
                "status": site.status,
                "ssv_passed": bool(site.ssv_passed) if site.ssv_passed is not None else False,
                "priority": site.priority,
                "contact_person": site.contact_person,
                "contact_phone": site.contact_phone,
                "description": site.description,
                "assigned_to": site.assigned_to,
                "assigned_to_name": _display_name(assigned),
                "created_by": site.created_by,
                "created_by_name": _display_name(creator),
                "created_at": to_utc_iso(site.created_at) if site.created_at else None,
                "updated_at": to_utc_iso(site.updated_at) if site.updated_at else None,
            }
        )

    columns = [
        "site_id",
        "site_code",
        "site_name",
        "site_type",
        "province",
        "city",
        "district",
        "address",
        "latitude",
        "longitude",
        "status",
        "ssv_passed",
        "priority",
        "contact_person",
        "contact_phone",
        "description",
        "assigned_to",
        "assigned_to_name",
        "created_by",
        "created_by_name",
        "created_at",
        "updated_at",
    ]

    df = pd.DataFrame(rows, columns=columns)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sites", index=False)

    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=site_list.xlsx"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/survey-stage/batch-template")
async def download_survey_stage_template(
    action: str = Query("skip", description="skip|require"),
):
    """下载勘察阶段批量设置模板（SurveyStage 工作表）。"""
    action_norm = (action or "").strip().lower()
    if action_norm not in ["skip", "require"]:
        raise HTTPException(status_code=400, detail="不支持的action（仅支持 skip|require）")

    if action_norm == "skip":
        sample_reason = "项目无需勘察"
    else:
        sample_reason = "恢复需要勘察"

    df = pd.DataFrame(
        [
            {
                "site_code": "SITE001",
                "site_name": "样例站点A",
                "reason": sample_reason,
            }
        ]
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="SurveyStage", index=False)
    output.seek(0)
    filename = f"site_survey_stage_{action_norm}_template.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/survey-stage/batch-upload", response_model=SurveyStageBatchReport)
async def upload_survey_stage_batch(
    file: UploadFile = File(...),
    action: str = Query("skip", description="skip|require"),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量跳过勘察/恢复需要勘察（支持 dry_run）。"""
    _ensure_site_manage_access(current_user)

    action_norm = (action or "").strip().lower()
    if action_norm not in ["skip", "require"]:
        raise HTTPException(status_code=400, detail="不支持的action（仅支持 skip|require）")

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 Excel(.xlsx/.xls)")

    content = await file.read()
    try:
        excel = pd.ExcelFile(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="解析Excel失败，请确认文件格式正确")

    if "SurveyStage" not in excel.sheet_names:
        raise HTTPException(status_code=400, detail="缺少工作表: SurveyStage")

    df = excel.parse("SurveyStage")
    total_rows = int(len(df.index))
    batch_id = uuid.uuid4().hex

    def _to_str(v) -> Optional[str]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        return s or None

    results: List[SurveyStageRowResult] = []
    success_count = 0
    failed_count = 0

    # 进行中的勘察工单状态集合
    in_progress_survey_statuses = [
        WorkOrderStatusEnum.PENDING,
        WorkOrderStatusEnum.ACTIVE,
        WorkOrderStatusEnum.SUBMITTED,
        WorkOrderStatusEnum.UNDER_REVIEW,
        WorkOrderStatusEnum.APPROVED,
        WorkOrderStatusEnum.ACTIVATED,
    ]

    for i, row in enumerate(df.itertuples(index=False), start=2):  # 表头占第1行
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns.tolist(), list(row)))
        site_code = _to_str(row_dict.get("site_code"))
        site_name = _to_str(row_dict.get("site_name"))
        reason = _to_str(row_dict.get("reason"))

        warnings: List[str] = []
        errors: List[str] = []
        site: Optional[Site] = None

        try:
            if not site_code and not site_name:
                errors.append("site_code/site_name 至少填写一项")
            else:
                if site_code:
                    site = db.query(Site).filter(Site.site_code == site_code).first()
                    if not site:
                        errors.append(f"站点编码不存在: {site_code}")
                else:
                    matches = db.query(Site).filter(Site.site_name == site_name).all()
                    if not matches:
                        errors.append(f"站点名称不存在: {site_name}")
                    elif len(matches) > 1:
                        errors.append(f"站点名称重名: {site_name}，请填写 site_code")
                    else:
                        site = matches[0]

            if errors or not site:
                failed_count += 1
                results.append(
                    SurveyStageRowResult(
                        row_index=i,
                        site_code=site_code,
                        site_name=site_name,
                        success=False,
                        action=None,
                        site_id=None,
                        warnings=warnings,
                        errors=errors or ["未知错误"],
                    )
                )
                continue

            # 统一回填输出字段
            site_code_out = site.site_code
            site_name_out = site.site_name

            if action_norm == "skip":
                if getattr(site, "survey_required", True) is False:
                    warnings.append("已是无需勘察，无需重复跳过")
                    success_count += 1
                    results.append(
                        SurveyStageRowResult(
                            row_index=i,
                            site_code=site_code_out,
                            site_name=site_name_out,
                            success=True,
                            action="noop",
                            site_id=site.id,
                            warnings=warnings,
                            errors=[],
                        )
                    )
                    continue

                if getattr(site, "status", None) != "survey_pending":
                    errors.append(f"站点当前状态为 {getattr(site, 'status', None)}，不能跳过勘察")
                else:
                    existing_wo = (
                        db.query(WorkOrder.id)
                        .filter(
                            WorkOrder.site_id == site.id,
                            WorkOrder.type == WorkOrderTypeEnum.SITE_SURVEY,
                            WorkOrder.status.in_(in_progress_survey_statuses),
                        )
                        .first()
                    )
                    if existing_wo:
                        errors.append("存在进行中的勘察工单，禁止跳过勘察")

                if errors:
                    failed_count += 1
                    results.append(
                        SurveyStageRowResult(
                            row_index=i,
                            site_code=site_code_out,
                            site_name=site_name_out,
                            success=False,
                            action=None,
                            site_id=site.id,
                            warnings=warnings,
                            errors=errors,
                        )
                    )
                    continue

                if dry_run:
                    success_count += 1
                    results.append(
                        SurveyStageRowResult(
                            row_index=i,
                            site_code=site_code_out,
                            site_name=site_name_out,
                            success=True,
                            action="would_skip",
                            site_id=site.id,
                            warnings=warnings,
                            errors=[],
                        )
                    )
                    continue

                # 执行跳过勘察：survey_pending -> planning
                old_status = site.status
                site.survey_required = False
                site.survey_skip_reason = (reason or "").strip() or None
                site.survey_skipped_at = datetime.utcnow()
                site.survey_skipped_by = current_user.id
                site.status = "planning"
                db.add(
                    AuditEvent(
                        id=uuid.uuid4().hex,
                        resource_type="site",
                        resource_id=str(site.id),
                        action="survey_skip",
                        operator_id=current_user.id,
                        from_status=old_status,
                        to_status=site.status,
                        comments="批量跳过勘察阶段",
                        details={"reason": site.survey_skip_reason, "batch_id": batch_id, "row_index": i},
                    )
                )
                rebuild_site_progress(
                    db,
                    site.id,
                    reason="batch_skip_site_survey",
                    operator_id=current_user.id,
                )
                db.commit()
                success_count += 1
                results.append(
                    SurveyStageRowResult(
                        row_index=i,
                        site_code=site_code_out,
                        site_name=site_name_out,
                        success=True,
                        action="skipped",
                        site_id=site.id,
                        warnings=warnings,
                        errors=[],
                    )
                )
                continue

            # action_norm == "require"
            if getattr(site, "survey_required", True) is not False:
                warnings.append("已是需要勘察，无需恢复")
                success_count += 1
                results.append(
                    SurveyStageRowResult(
                        row_index=i,
                        site_code=site_code_out,
                        site_name=site_name_out,
                        success=True,
                        action="noop",
                        site_id=site.id,
                        warnings=warnings,
                        errors=[],
                    )
                )
                continue

            if getattr(site, "status", None) != "planning":
                errors.append("仅允许在规划阶段（planning）恢复需要勘察")
            else:
                planning_exists = db.query(SitePlanning.id).filter(SitePlanning.site_id == site.id).first()
                if planning_exists:
                    errors.append("站点已存在规划版本，禁止恢复需要勘察")

            if errors:
                failed_count += 1
                results.append(
                    SurveyStageRowResult(
                        row_index=i,
                        site_code=site_code_out,
                        site_name=site_name_out,
                        success=False,
                        action=None,
                        site_id=site.id,
                        warnings=warnings,
                        errors=errors,
                    )
                )
                continue

            if dry_run:
                success_count += 1
                results.append(
                    SurveyStageRowResult(
                        row_index=i,
                        site_code=site_code_out,
                        site_name=site_name_out,
                        success=True,
                        action="would_require",
                        site_id=site.id,
                        warnings=warnings,
                        errors=[],
                    )
                )
                continue

            old_status = site.status
            site.survey_required = True
            site.survey_skip_reason = None
            site.survey_skipped_at = None
            site.survey_skipped_by = None
            site.status = "survey_pending"
            reason_clean = (reason or "").strip() or None
            db.add(
                AuditEvent(
                    id=uuid.uuid4().hex,
                    resource_type="site",
                    resource_id=str(site.id),
                    action="survey_require",
                    operator_id=current_user.id,
                    from_status=old_status,
                    to_status=site.status,
                    comments="批量恢复需要勘察",
                    details={"reason": reason_clean, "batch_id": batch_id, "row_index": i},
                )
            )
            rebuild_site_progress(
                db,
                site.id,
                reason="batch_require_site_survey",
                operator_id=current_user.id,
            )
            db.commit()
            success_count += 1
            results.append(
                SurveyStageRowResult(
                    row_index=i,
                    site_code=site_code_out,
                    site_name=site_name_out,
                    success=True,
                    action="required",
                    site_id=site.id,
                    warnings=warnings,
                    errors=[],
                )
            )
        except Exception as e:
            db.rollback()
            failed_count += 1
            results.append(
                SurveyStageRowResult(
                    row_index=i,
                    site_code=site_code or getattr(site, "site_code", None),
                    site_name=site_name or getattr(site, "site_name", None),
                    success=False,
                    action=None,
                    site_id=getattr(site, "id", None),
                    warnings=warnings,
                    errors=[f"执行异常: {str(e)}"],
                )
            )

    return SurveyStageBatchReport(
        batch_id=batch_id,
        dry_run=bool(dry_run),
        action=action_norm,
        total_rows=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


# ===== 基础信息批量导入（模板/上传/历史） =====
@router.get("/basic/batch-template")
async def download_basic_template():
    """下载基础信息批量导入模板（仅 Sites 表）。"""
    sites_df = pd.DataFrame([
        {
            "site_code": "SITE001",
            "site_name": "样例站点A",
            "site_type": "macro",
            "province": "北京",
            "city": "北京",
            "district": "朝阳区",
            "address": "某路1号",
            "latitude": 39.9,
            "longitude": 116.3,
            "priority": "normal",
            "contact_person": "张三",
            "contact_phone": "13800000000",
            "description": "示例备注",
        }
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="Sites", index=False)
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=site_basic_template.xlsx"}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@router.get("/basic/batch-update-template")
async def download_basic_update_template():
    """下载基础信息批量更新模板（支持从站点导出表回写）。"""
    sites_df = pd.DataFrame([
        {
            "site_id": 1,
            "site_code": "SITE001",
            "site_name": "样例站点A-更新",
            "site_type": "macro",
            "province": "北京",
            "city": "北京",
            "district": "朝阳区",
            "address": "某路100号",
            "latitude": 39.901,
            "longitude": 116.301,
            "priority": "normal",
            "contact_person": "李四",
            "contact_phone": "13811112222",
            "description": "更新备注示例",
        }
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="Sites", index=False)
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=site_basic_update_template.xlsx"}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


def _is_excel_blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return isinstance(value, str) and not value.strip()


def _to_optional_str(value) -> Optional[str]:
    if _is_excel_blank(value):
        return None
    return str(value).strip()


def _same_site_field_value(old_value, new_value) -> bool:
    if old_value is None and new_value is None:
        return True
    if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
        return abs(float(old_value) - float(new_value)) < 1e-9
    return old_value == new_value


@router.post("/basic/batch-update-upload", response_model=BasicBatchImportReport)
async def basic_batch_update_upload(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量更新站点基础信息（支持 dry-run）。"""
    _ensure_site_manage_access(current_user)

    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 Excel(.xlsx/.xls)")

    excel = pd.ExcelFile(io.BytesIO(content))
    if "Sites" not in excel.sheet_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少工作表: Sites")

    df = excel.parse("Sites")
    df.columns = [str(col).strip() for col in df.columns]

    has_site_id_col = "site_id" in df.columns
    has_site_code_col = "site_code" in df.columns
    if not has_site_id_col and not has_site_code_col:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少标识列: site_id 或 site_code")

    editable_columns = [
        "site_name",
        "site_type",
        "province",
        "city",
        "district",
        "address",
        "latitude",
        "longitude",
        "priority",
        "contact_person",
        "contact_phone",
        "description",
    ]
    effective_editable_columns = [c for c in editable_columns if c in df.columns]
    if not effective_editable_columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到可更新字段列")

    results: List[BasicImportRowResult] = []
    success_count = 0
    failed_count = 0
    total_rows = int(len(df.index))
    batch_id = uuid.uuid4().hex

    for i, row in enumerate(df.itertuples(index=False), start=2):
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns.tolist(), list(row)))
        errors: List[str] = []
        warnings: List[str] = []
        site_id: Optional[int] = None
        site_code = _to_optional_str(row_dict.get("site_code"))

        site_id_raw = row_dict.get("site_id")
        if has_site_id_col and not _is_excel_blank(site_id_raw):
            try:
                site_id_num = float(site_id_raw)
                if not site_id_num.is_integer():
                    errors.append("site_id 必须为整数")
                else:
                    site_id = int(site_id_num)
            except Exception:
                errors.append("site_id 格式错误")

        if site_id is None and not site_code:
            errors.append("缺少站点标识: site_id 或 site_code 至少填写一个")

        site = None
        if not errors:
            if site_id is not None:
                site = db.query(Site).filter(Site.id == site_id).first()
                if site is None:
                    errors.append(f"站点不存在: site_id={site_id}")
                elif site_code and site.site_code != site_code:
                    errors.append(f"site_id 与 site_code 不匹配: {site_code}")
            elif site_code:
                site = db.query(Site).filter(Site.site_code == site_code).first()
                if site is None:
                    errors.append(f"站点不存在: site_code={site_code}")

        if errors:
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site_code,
                    success=False,
                    action=None,
                    site_id=site_id,
                    warnings=warnings,
                    errors=errors,
                )
            )
            failed_count += 1
            continue

        update_candidate: Dict[str, object] = {}

        if "site_name" in effective_editable_columns:
            site_name_val = _to_optional_str(row_dict.get("site_name"))
            if site_name_val is None:
                errors.append("site_name 不能为空")
            else:
                update_candidate["site_name"] = site_name_val

        for col in ["site_type", "province", "city", "district", "address", "contact_person", "contact_phone", "description"]:
            if col in effective_editable_columns:
                update_candidate[col] = _to_optional_str(row_dict.get(col))

        if "priority" in effective_editable_columns:
            priority_val = _to_optional_str(row_dict.get("priority"))
            if priority_val is not None:
                priority_val = priority_val.lower()
                if priority_val not in ["high", "normal", "low"]:
                    errors.append("priority 仅支持 high/normal/low")
            update_candidate["priority"] = priority_val

        if "latitude" in effective_editable_columns:
            lat_raw = row_dict.get("latitude")
            if _is_excel_blank(lat_raw):
                update_candidate["latitude"] = None
            else:
                try:
                    lat_val = float(lat_raw)
                    if not (-90 <= lat_val <= 90):
                        errors.append("纬度超出范围[-90,90]")
                    else:
                        update_candidate["latitude"] = lat_val
                except Exception:
                    errors.append("纬度格式错误")

        if "longitude" in effective_editable_columns:
            lon_raw = row_dict.get("longitude")
            if _is_excel_blank(lon_raw):
                update_candidate["longitude"] = None
            else:
                try:
                    lon_val = float(lon_raw)
                    if not (-180 <= lon_val <= 180):
                        errors.append("经度超出范围[-180,180]")
                    else:
                        update_candidate["longitude"] = lon_val
                except Exception:
                    errors.append("经度格式错误")

        if errors:
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site.site_code if site else site_code,
                    success=False,
                    action=None,
                    site_id=getattr(site, "id", site_id),
                    warnings=warnings,
                    errors=errors,
                )
            )
            failed_count += 1
            continue

        update_data: Dict[str, object] = {}
        for field, new_value in update_candidate.items():
            old_value = getattr(site, field, None)
            if not _same_site_field_value(old_value, new_value):
                update_data[field] = new_value

        if not update_data:
            success_count += 1
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site.site_code,
                    success=True,
                    action="noop",
                    site_id=site.id,
                    warnings=warnings,
                    errors=[],
                )
            )
            continue

        if dry_run:
            success_count += 1
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site.site_code,
                    success=True,
                    action="would_update",
                    site_id=site.id,
                    warnings=warnings,
                    errors=[],
                )
            )
            continue

        try:
            for field, value in update_data.items():
                setattr(site, field, value)
            db.commit()
            db.refresh(site)
            success_count += 1
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site.site_code,
                    success=True,
                    action="updated",
                    site_id=site.id,
                    warnings=warnings,
                    errors=[],
                )
            )
        except Exception as e:
            db.rollback()
            failed_count += 1
            results.append(
                BasicImportRowResult(
                    row_index=i,
                    site_code=site.site_code if site else site_code,
                    success=False,
                    action=None,
                    site_id=getattr(site, "id", site_id),
                    warnings=warnings,
                    errors=[f"执行异常: {str(e)}"],
                )
            )

    try:
        evt = AuditEvent(
            id=batch_id,
            resource_type="site_basic_update",
            resource_id=batch_id,
            action=("dry_run" if dry_run else "update"),
            operator_id=current_user.id,
            comments=f"{file.filename}",
            details={
                "file_name": file.filename,
                "total_rows": total_rows,
                "success_count": success_count,
                "failed_count": failed_count,
            },
        )
        db.add(evt)
        db.commit()
    except Exception:
        db.rollback()

    return BasicBatchImportReport(
        batch_id=batch_id,
        dry_run=dry_run,
        total_rows=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.post("/basic/batch-upload", response_model=BasicBatchImportReport)
async def basic_batch_upload(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_site_manage_access(current_user)

    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 Excel(.xlsx/.xls)")

    excel = pd.ExcelFile(io.BytesIO(content))
    if "Sites" not in excel.sheet_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少工作表: Sites")

    df = excel.parse("Sites")
    results: List[BasicImportRowResult] = []
    success_count = 0
    failed_count = 0
    total_rows = int(len(df.index))
    batch_id = uuid.uuid4().hex

    # 预取所有已存在的 site_code，便于快速校验
    existing_codes = set([s.site_code for s in db.query(Site.site_code).all()])
    seen_in_file = set()

    for i, row in enumerate(df.itertuples(index=False), start=2):  # 从第2行开始（表头占第1行）
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns.tolist(), list(row)))
        site_code = str(row_dict.get("site_code") or "").strip()
        site_name = str(row_dict.get("site_name") or "").strip()
        errors: List[str] = []
        warnings: List[str] = []

        if not site_code:
            errors.append("缺少必填列: site_code")
        if not site_name:
            errors.append("缺少必填列: site_name")
        # 文件内重复
        if site_code:
            if site_code in seen_in_file:
                errors.append(f"文件内重复的站点编码: {site_code}")
            else:
                seen_in_file.add(site_code)

        # DB 冲突策略：存在即报错，不更新
        if site_code and site_code in existing_codes:
            errors.append(f"站点编码已存在: {site_code}")

        # 经纬度范围
        lat = row_dict.get("latitude")
        lon = row_dict.get("longitude")
        try:
            if lat is not None and str(lat).strip() != "":
                latf = float(lat)
                if not (-90 <= latf <= 90):
                    errors.append("纬度超出范围[-90,90]")
        except Exception:
            errors.append("纬度格式错误")
        try:
            if lon is not None and str(lon).strip() != "":
                lonf = float(lon)
                if not (-180 <= lonf <= 180):
                    errors.append("经度超出范围[-180,180]")
        except Exception:
            errors.append("经度格式错误")

        if errors:
            results.append(BasicImportRowResult(row_index=i, site_code=site_code or None, success=False, action=None, warnings=warnings, errors=errors))
            failed_count += 1
            continue

        # 构造站点对象（不持久化于 dry_run）
        payload = dict(
            site_code=site_code,
            site_name=site_name,
            site_type=(str(row_dict.get("site_type")) if row_dict.get("site_type") is not None else None),
            address=(str(row_dict.get("address")) if row_dict.get("address") is not None else None),
            latitude=(float(row_dict.get("latitude")) if row_dict.get("latitude") not in (None, "") else None),
            longitude=(float(row_dict.get("longitude")) if row_dict.get("longitude") not in (None, "") else None),
            province=(str(row_dict.get("province")) if row_dict.get("province") is not None else None),
            city=(str(row_dict.get("city")) if row_dict.get("city") is not None else None),
            district=(str(row_dict.get("district")) if row_dict.get("district") is not None else None),
            priority=(str(row_dict.get("priority")) if row_dict.get("priority") is not None else "normal"),
            description=(str(row_dict.get("description")) if row_dict.get("description") is not None else None),
            contact_person=(str(row_dict.get("contact_person")) if row_dict.get("contact_person") is not None else None),
            contact_phone=(str(row_dict.get("contact_phone")) if row_dict.get("contact_phone") is not None else None),
        )

        site_id: Optional[int] = None
        if not dry_run:
            site = Site(
                **payload,
                status="survey_pending",
                created_by=current_user.id,
            )
            db.add(site)
            db.flush()  # 获取自增ID
            site_id = site.id
        results.append(BasicImportRowResult(row_index=i, site_code=site_code, success=True, action="created", site_id=site_id, warnings=warnings, errors=[]))
        success_count += 1

    if not dry_run:
        db.commit()

    # 写审计
    try:
        evt = AuditEvent(
            id=batch_id,
            resource_type="site_basic_import",
            resource_id=batch_id,
            action=("dry_run" if dry_run else "import"),
            operator_id=current_user.id,
            comments=f"{file.filename}",
            details={
                "file_name": file.filename,
                "total_rows": total_rows,
                "success_count": success_count,
                "failed_count": failed_count,
            },
        )
        db.add(evt)
        db.commit()
    except Exception:
        db.rollback()

    return BasicBatchImportReport(
        batch_id=batch_id,
        dry_run=dry_run,
        total_rows=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.get("/basic/import-history")
async def list_basic_import_history(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_site_manage_access(current_user)

    query = db.query(AuditEvent).filter(AuditEvent.resource_type == "site_basic_import")
    total = query.count()
    rows = (
        query.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[BasicImportHistoryItem] = []
    for e in rows:
        details = e.details or {}
        items.append(
            BasicImportHistoryItem(
                batch_id=e.id,
                action=e.action,
                operator_id=e.operator_id,
                operator_name=getattr(e.operator, "username", None) if getattr(e, "operator", None) else None,
                file_name=details.get("file_name"),
                created_at=e.created_at,
                total_rows=details.get("total_rows"),
                success_count=details.get("success_count"),
                failed_count=details.get("failed_count"),
            )
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/basic/import-history/{batch_id}")
async def get_basic_import_history_detail(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_site_manage_access(current_user)
    e = db.query(AuditEvent).filter(AuditEvent.id == batch_id, AuditEvent.resource_type == "site_basic_import").first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")
    return {
        "batch_id": e.id,
        "action": e.action,
        "operator_id": e.operator_id,
        "operator_name": getattr(e.operator, "username", None) if getattr(e, "operator", None) else None,
        "file_name": (e.details or {}).get("file_name"),
        "created_at": to_utc_iso(e.created_at) if e.created_at else None,
        "summary": e.details or {},
        # 目前仅存汇总，若后期需要详细逐行结果，可扩展单独持久化
    }

@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    _ensure_site_visible(site_id, db, current_user)

    return SiteResponse.from_orm(site)


@router.get("/{site_id}/milestones", response_model=SiteMilestonesResponse)
async def get_site_milestones(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    _ensure_site_visible(site_id, db, current_user)

    ensure_result = ensure_site_progress_snapshots(db, site_ids=[site_id], reason="site_milestones_read")
    if ensure_result["rebuilt_site_ids"]:
        db.commit()
    snapshot = get_site_progress_snapshot(db, site_id)
    if snapshot is None:
        raise HTTPException(status_code=500, detail="Site progress snapshot not found")
    metric_mode = get_site_progress_metric_mode(db)
    install_started_at = get_site_progress_milestone_at(snapshot, "install_started")
    install_completed_at = get_site_progress_milestone_at(snapshot, "install_completed")
    online_at = get_site_progress_milestone_at(snapshot, "online", metric_mode=metric_mode)
    activated_at = get_site_progress_milestone_at(snapshot, "activated", metric_mode=metric_mode)
    ssv_at = get_site_progress_milestone_at(snapshot, "ssv")

    return SiteMilestonesResponse(
        install_started_at=to_utc_iso(install_started_at) if install_started_at else None,
        install_completed_at=to_utc_iso(install_completed_at) if install_completed_at else None,
        online_at=to_utc_iso(online_at) if online_at else None,
        activated_at=to_utc_iso(activated_at) if activated_at else None,
        ssv_at=to_utc_iso(ssv_at) if ssv_at else None,
    )


@router.post("/{site_id}/survey/skip", response_model=SiteResponse)
async def skip_site_survey(
    site_id: int,
    payload: SiteSurveySkipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跳过勘察阶段：将站点标记为无需勘察，并从 survey_pending 推进到 planning。"""
    _ensure_site_manage_access(current_user)

    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    if getattr(site, "status", None) != "survey_pending":
        raise HTTPException(status_code=400, detail="仅允许在勘察阶段（survey_pending）跳过勘察")

    # 不允许存在“进行中的”勘察工单
    in_progress_statuses = [
        WorkOrderStatusEnum.PENDING,
        WorkOrderStatusEnum.ACTIVE,
        WorkOrderStatusEnum.SUBMITTED,
        WorkOrderStatusEnum.UNDER_REVIEW,
        WorkOrderStatusEnum.APPROVED,
        WorkOrderStatusEnum.ACTIVATED,
    ]
    existing_wo = (
        db.query(WorkOrder.id)
        .filter(
            WorkOrder.site_id == site_id,
            WorkOrder.type == WorkOrderTypeEnum.SITE_SURVEY,
            WorkOrder.status.in_(in_progress_statuses),
        )
        .first()
    )
    if existing_wo:
        raise HTTPException(status_code=409, detail="该站点存在进行中的勘察工单，禁止跳过勘察")

    old_status = site.status
    site.survey_required = False
    site.survey_skip_reason = (payload.reason or "").strip() or None
    site.survey_skipped_at = datetime.utcnow()
    site.survey_skipped_by = current_user.id
    site.status = "planning"

    # 审计
    db.add(
        AuditEvent(
            id=uuid.uuid4().hex,
            resource_type="site",
            resource_id=str(site_id),
            action="survey_skip",
            operator_id=current_user.id,
            from_status=old_status,
            to_status=site.status,
            comments="跳过勘察阶段",
            details={"reason": site.survey_skip_reason, "survey_required": False},
        )
    )
    rebuild_site_progress(
        db,
        site_id,
        reason="skip_site_survey",
        operator_id=current_user.id,
    )

    db.commit()
    db.refresh(site)
    return SiteResponse.from_orm(site)


@router.post("/{site_id}/survey/require", response_model=SiteResponse)
async def require_site_survey(
    site_id: int,
    payload: SiteSurveyRequireRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复需要勘察：仅允许在 planning 且未形成规划版本时，将站点回退到 survey_pending。"""
    _ensure_site_manage_access(current_user)

    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    if getattr(site, "status", None) != "planning":
        raise HTTPException(status_code=400, detail="仅允许在规划阶段（planning）恢复需要勘察")

    # 仅当尚未形成规划基线（无任何规划版本）时允许回退
    planning_exists = db.query(SitePlanning.id).filter(SitePlanning.site_id == site_id).first()
    if planning_exists:
        raise HTTPException(status_code=409, detail="站点已存在规划版本，禁止恢复需要勘察")

    old_status = site.status
    site.survey_required = True
    site.survey_skip_reason = None
    site.survey_skipped_at = None
    site.survey_skipped_by = None
    site.status = "survey_pending"

    reason = (payload.reason or "").strip() or None

    db.add(
        AuditEvent(
            id=uuid.uuid4().hex,
            resource_type="site",
            resource_id=str(site_id),
            action="survey_require",
            operator_id=current_user.id,
            from_status=old_status,
            to_status=site.status,
            comments="恢复需要勘察",
            details={"reason": reason, "survey_required": True},
        )
    )
    rebuild_site_progress(
        db,
        site_id,
        reason="require_site_survey",
        operator_id=current_user.id,
    )

    db.commit()
    db.refresh(site)
    return SiteResponse.from_orm(site)


@router.get("/{site_id}/delete-check", response_model=SiteDeleteCheckResponse)
async def check_site_delete(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除前检查：仅允许删除无任何关联数据的站点。"""
    _ensure_site_manage_access(current_user)

    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    counts = _get_site_related_counts(db, site_id)
    total_related = int(sum(counts.values()))
    return SiteDeleteCheckResponse(
        can_delete=total_related == 0,
        total_related=total_related,
        counts=counts,
    )


@router.put("/batch-update", response_model=SiteBatchUpdateReport)
async def batch_update_sites(
    payload: SiteBatchUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_site_manage_access(current_user)

    updates = list(payload.updates or [])
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未提供批量更新数据")

    seen_site_ids = set()
    results: List[SiteBatchUpdateRowResult] = []
    success_count = 0
    failed_count = 0

    for idx, row in enumerate(updates, start=1):
        row_errors: List[str] = []
        site_id = int(row.site_id)
        update_data = row.dict(exclude_unset=True, exclude={"site_id"})
        site = None

        if site_id in seen_site_ids:
            row_errors.append("site_id 重复")
        else:
            seen_site_ids.add(site_id)

        if not update_data:
            row_errors.append("未提供可更新字段")

        if "site_name" in update_data:
            site_name = str(update_data.get("site_name") or "").strip()
            if not site_name:
                row_errors.append("站点名称不能为空")
            else:
                update_data["site_name"] = site_name

        if "latitude" in update_data and update_data["latitude"] is not None:
            lat_val = float(update_data["latitude"])
            if lat_val < -90 or lat_val > 90:
                row_errors.append("纬度必须在 -90 到 90 之间")

        if "longitude" in update_data and update_data["longitude"] is not None:
            lng_val = float(update_data["longitude"])
            if lng_val < -180 or lng_val > 180:
                row_errors.append("经度必须在 -180 到 180 之间")

        if not row_errors:
            site = db.query(Site).filter(Site.id == site_id).first()
            if site is None:
                row_errors.append("站点不存在")

        if row_errors:
            failed_count += 1
            results.append(
                SiteBatchUpdateRowResult(
                    row_index=idx,
                    site_id=site_id,
                    site_code=getattr(site, "site_code", None),
                    site_name=getattr(site, "site_name", None),
                    success=False,
                    errors=row_errors,
                )
            )
            continue

        try:
            for field, value in update_data.items():
                setattr(site, field, value)
            db.commit()
            db.refresh(site)
            success_count += 1
            results.append(
                SiteBatchUpdateRowResult(
                    row_index=idx,
                    site_id=site.id,
                    site_code=site.site_code,
                    site_name=site.site_name,
                    success=True,
                    errors=[],
                )
            )
        except SQLAlchemyError:
            db.rollback()
            failed_count += 1
            results.append(
                SiteBatchUpdateRowResult(
                    row_index=idx,
                    site_id=site_id,
                    site_code=getattr(site, "site_code", None),
                    site_name=getattr(site, "site_name", None),
                    success=False,
                    errors=["数据库写入失败"],
                )
            )
        except Exception:
            db.rollback()
            failed_count += 1
            results.append(
                SiteBatchUpdateRowResult(
                    row_index=idx,
                    site_id=site_id,
                    site_code=getattr(site, "site_code", None),
                    site_name=getattr(site, "site_name", None),
                    success=False,
                    errors=["更新失败，请稍后重试"],
                )
            )

    return SiteBatchUpdateReport(
        total_rows=len(updates),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )

@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    site_update: SiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # 权限：仅允许 admin/manager 编辑站点基础信息
    _ensure_site_manage_access(current_user)
    
    update_data = site_update.dict(exclude_unset=True)
    # 明确不支持：状态/指派人
    forbidden_fields = [f for f in ["status", "assigned_to"] if f in update_data]
    if forbidden_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不允许修改状态/指派人")
    for field, value in update_data.items():
        setattr(site, field, value)
    
    db.commit()
    db.refresh(site)
    
    return SiteResponse.from_orm(site)

@router.delete("/{site_id}")
async def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ensure_site_manage_access(current_user)
    
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    counts = _get_site_related_counts(db, site_id)
    total_related = int(sum(counts.values()))
    if total_related > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "站点存在关联数据，禁止删除",
                "total_related": total_related,
                "counts": counts,
            },
        )
    
    db.delete(site)
    db.commit()
    
    return {"message": "Site deleted successfully"}


class SiteStatsSummary(BaseModel):
    total_sites: int
    status_stats: dict
    type_stats: dict


class SiteOmcEverDevice(BaseModel):
    sn: str
    ever_online: bool
    ever_activated: bool
    omc_online_raw: Optional[bool] = None
    omc_active_raw: Optional[bool] = None
    last_seen_at: Optional[str] = None


class SiteOmcEverSummary(BaseModel):
    site_id: int
    sns: List[str]
    all_ever_online: bool
    all_ever_activated: bool
    devices: List[SiteOmcEverDevice]


@router.get("/stats/summary", response_model=SiteStatsSummary)
async def get_site_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """站点统计信息（管理员/经理）"""
    _ensure_site_manage_access(current_user)

    total_sites = db.query(func.count(Site.id)).scalar() or 0

    # 按状态统计
    status_rows = db.query(Site.status, func.count(Site.id)).group_by(Site.status).all()
    status_stats = {str(s or "unknown"): int(c) for s, c in status_rows}

    # 按类型统计
    type_rows = db.query(Site.site_type, func.count(Site.id)).group_by(Site.site_type).all()
    type_stats = {str(t or "unknown"): int(c) for t, c in type_rows}

    return SiteStatsSummary(
        total_sites=total_sites,
        status_stats=status_stats,
        type_stats=type_stats,
    )


@router.get("/{site_id}/omc/devices")
async def get_site_omc_devices(
    site_id: int,
    refresh: bool = Query(False, description="是否立即刷新 OMC 状态"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取站点绑定设备的在线/激活状态（统一接口）

    - 设备列表来源：equipment_binding_history 推导当前绑定的 SN
    - 在线状态：OMC /enodeb/infos/status/{sn} 的 connectionStatus
    - 激活状态：OMC /enodeb/infos/status/{sn} 的 cellStatus，第一个数字为 1 视为已激活
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    _ensure_site_visible(site_id, db, current_user)

    # 1. 基于绑定历史推导当前 SN 及扇区信息
    # 取每个 SN 最新一条记录，且 action != UNBIND
    latest_at_subq = (
        db.query(
            EquipmentBindingHistory.equipment_sn.label("sn"),
            func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
        )
        .filter(EquipmentBindingHistory.site_id == site_id)
        .group_by(EquipmentBindingHistory.equipment_sn)
        .subquery()
    )

    latest_id_subq = (
        db.query(
            EquipmentBindingHistory.equipment_sn.label("sn"),
            func.max(EquipmentBindingHistory.id).label("latest_id"),
        )
        .join(
            latest_at_subq,
            and_(
                EquipmentBindingHistory.equipment_sn == latest_at_subq.c.sn,
                EquipmentBindingHistory.operated_at == latest_at_subq.c.latest_at,
            ),
        )
        .filter(EquipmentBindingHistory.site_id == site_id)
        .group_by(EquipmentBindingHistory.equipment_sn)
        .subquery()
    )

    latest_rows: list[EquipmentBindingHistory] = (
        db.query(EquipmentBindingHistory)
        .options(joinedload(EquipmentBindingHistory.operator))
        .join(latest_id_subq, EquipmentBindingHistory.id == latest_id_subq.c.latest_id)
        .all()
    )

    devices = []
    for row in latest_rows:
        if row.action == BindingActionEnum.UNBIND or not row.equipment_sn:
            continue
        installer = row.operator
        installer_name = None
        if installer:
            installer_name = installer.full_name or installer.username
        devices.append(
            {
                "sn": row.equipment_sn,
                "equipment_type": row.equipment_type,
                "equipment_model": row.equipment_model,
                "sector_id": row.sector_id,
                "band": row.band,
                "cell_id": row.cell_id,
                "installer_id": row.operator_id,
                "installer_name": installer_name,
                # operated_at 使用数据库时间，视为 UTC
                "bound_at": to_utc_iso(row.operated_at) if row.operated_at else None,
                "online": None,
                "activated": None,
            }
        )

    if not devices:
        return {
            "site_id": site_id,
            "checked_at": None,
            "devices": [],
            "manual_confirm_enabled": get_omc_manual_confirm_enabled(db),
        }

    sns = [d["sn"] for d in devices]

    # 2. 聚合 ever 状态（曾上线 / 曾激活）
    summary = summarize_site_omc_state(db, site_id)
    ever_map: dict[str, dict] = {}
    for dev in summary.get("devices", []):
        sn_key = dev.get("sn")
        if sn_key:
            ever_map[sn_key] = dev

    checked_at = None
    online_map: dict[str, bool] = {}
    activated_map: dict[str, bool] = {}

    # 3. 如果需要刷新，直接调 OMC 获取“实时状态”
    if refresh:
        client = get_omc_client(db)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OMC 未配置，请先在后台配置 OMC API",
            )
        status_payloads: dict[str, dict] = {}
        for sn in sns:
            try:
                status_payload = client.get_enodeb_status(sn)
                status_payloads[sn] = status_payload
                online_flag = parse_online_flag(status_payload)
                activated_flag = parse_activated_flag(status_payload)
                online_map[sn] = online_flag

                # 将此次观测写入 SN 聚合表，方便在“OMC 设备状态”页面统一查看
                try:
                    upsert_omc_device_state(
                        db=db,
                        sn=sn,
                        online_raw=bool(online_flag),
                        activated_raw=bool(activated_flag),
                        source="api_poll",
                        status_payload=status_payload,
                    )
                except Exception as exc:  # pragma: no cover - 聚合表异常不影响主流程
                    print(f"[OMC] 写入 OmcDeviceState 失败 SN={sn}: {exc}")
            except Exception as exc:  # pragma: no cover
                print(f"[OMC] 查询在线状态失败 SN={sn}: {exc}")
                online_map[sn] = False

        # 只有全部在线时才检查激活（用于当前接口返回的 activated 字段）
        # 直接解析激活状态；若离线或 404，则视为未激活，避免前端显示残留的“已激活”
        for sn in sns:
            try:
                payload = status_payloads.get(sn) or {}
                activated_map[sn] = parse_activated_flag(payload)
            except Exception as exc:  # pragma: no cover
                print(f"[OMC] 查询激活状态失败 SN={sn}: {exc}")
                activated_map[sn] = False
        # 检查时间统一按 UTC ISO 输出
        checked_at = to_utc_iso(datetime.utcnow())
        # 提交本次刷新中写入的 OmcDeviceState 变更
        try:
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            print(f"[OMC] 提交 OmcDeviceState 变更失败 site_id={site_id}: {exc}")

        # 刷新完成后，基于最新聚合表尝试推进工单/站点状态（只升不降，不再二次查询 OMC）
        try:
            advance_opening_work_orders_by_ever(db, site_id)
            advance_replacement_work_orders_by_ever(db, site_id)
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            print(f"[OMC] 手动刷新后推进工单/站点失败 site_id={site_id}: {exc}")

    # 将状态填充到设备列表：实时在线/激活 + ever 在线/激活
    for d in devices:
        sn = d["sn"]
        if sn in online_map:
            d["online"] = bool(online_map[sn])
        # 若未取到激活结果，默认 False，避免保留旧值
        d["activated"] = bool(activated_map.get(sn, False))
        ever_info = ever_map.get(sn) or {}
        d["ever_online"] = bool(ever_info.get("ever_online")) if ever_info else False
        d["ever_activated"] = bool(ever_info.get("ever_activated")) if ever_info else False
        d["ever_last_seen_at"] = ever_info.get("last_seen_at") if ever_info else None

    return {
        "site_id": site_id,
        "checked_at": checked_at,
        "devices": devices,
        "manual_confirm_enabled": get_omc_manual_confirm_enabled(db),
    }


@router.get("/{site_id}/omc/devices/ever", response_model=SiteOmcEverSummary)
async def get_site_omc_devices_ever(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    基于 SN 聚合表 (omc_device_states) 获取站点设备的“ever”在线/激活状态。

    - ever_online: 该 SN 曾经被 OMC 观测为在线
    - ever_activated: 该 SN 曾经被 OMC 观测为激活
    - 仅依赖历史观测记录，不主动调用 OMC 实时接口
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    # 权限规则与 /omc/devices 保持一致
    _ensure_site_visible(site_id, db, current_user)

    summary = summarize_site_omc_state(db, site_id)

    devices = [
        SiteOmcEverDevice(**d)
        for d in summary.get("devices", [])
    ]

    return SiteOmcEverSummary(
        site_id=summary["site_id"],
        sns=summary["sns"],
        all_ever_online=summary["all_ever_online"],
        all_ever_activated=summary["all_ever_activated"],
        devices=devices,
    )
