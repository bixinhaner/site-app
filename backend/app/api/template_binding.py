"""
模板绑定管理API
提供模板绑定的增删改查和解析功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.models.inspection import (
    InspectionTemplate, TemplateBinding, SiteInspection
)
from app.models.work_order import WorkOrder, WorkOrderStatusEnum
from app.models.user_log import UserLog
from app.schemas.template_binding import (
    TemplateBindingCreate, TemplateBindingUpdate, TemplateBindingResponse,
    TemplateBindingBatchUpdate, ResolveContextSchema, TemplateResolveResponse,
    TemplateMatchResultSchema, InspectionTemplateCreate, InspectionTemplateUpdate,
    InspectionTemplateResponse, TemplateExportResponse, TemplateImportPayload
)
from app.api.auth import get_current_user
from app.services.authz_service import user_has_any_role_or_permission
from app.services.template_resolver import (
    TemplateResolver, ResolveContext, create_resolver
)
from app.utils.template_validator import validate_template_changes, summarize_changes
from app.services.inspection_template_sync import (
    get_template_usage_counts,
    get_template_revision,
    sync_template_to_editable_inspections,
)
from app.utils.timezone import to_utc_iso

router = APIRouter()


def _ensure_template_read_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager", "inspector", "surveyor"],
        permission_codes=["inspection:template:read"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足",
        )


def _ensure_template_write_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["inspection:template:write"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足",
        )


@router.get("/templates", response_model=List[InspectionTemplateResponse])
async def get_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    site_id: Optional[int] = Query(None),
    site_type: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="搜索关键字"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查模板列表"""
    # 权限检查：管理员/经理可管理，检查员可读
    _ensure_template_read_access(current_user)
    
    query = db.query(InspectionTemplate).options(
        joinedload(InspectionTemplate.creator)
    )
    
    # 关键字搜索
    if q:
        query = query.filter(InspectionTemplate.template_name.contains(q))
    

    # 按更新时间排序
    query = query.order_by(desc(InspectionTemplate.updated_at))
    
    templates = query.offset(skip).limit(limit).all()
    
    # 获取绑定统计信息
    result = []
    for template in templates:
        bindings_count = db.query(TemplateBinding).filter(
            TemplateBinding.template_id == template.id
        ).count()
        
        active_bindings_count = db.query(TemplateBinding).filter(
            TemplateBinding.template_id == template.id,
            TemplateBinding.active == True
        ).count()

        work_orders_count = db.query(func.count(func.distinct(WorkOrder.id))).join(
            SiteInspection,
            or_(
                SiteInspection.work_order_id == WorkOrder.id,
                SiteInspection.id == WorkOrder.inspection_id,
            ),
        ).filter(
            SiteInspection.template_id == template.id,
        ).scalar() or 0

        active_work_orders_count = db.query(func.count(func.distinct(WorkOrder.id))).join(
            SiteInspection,
            or_(
                SiteInspection.work_order_id == WorkOrder.id,
                SiteInspection.id == WorkOrder.inspection_id,
            ),
        ).filter(
            SiteInspection.template_id == template.id,
            WorkOrder.status != WorkOrderStatusEnum.COMPLETED,
        ).scalar() or 0
        
        template_response = InspectionTemplateResponse(
            id=template.id,
            template_name=template.template_name,
            template_data=template.template_data,
            revision=get_template_revision(template),
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
            creator_name=template.creator.full_name if template.creator else None,
            bindings_count=bindings_count,
            active_bindings_count=active_bindings_count,
            work_orders_count=work_orders_count,
            active_work_orders_count=active_work_orders_count,
        )
        result.append(template_response)
    
    return result


@router.post("/templates", response_model=InspectionTemplateResponse)
async def create_template(
    template_data: InspectionTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建检查模板"""
    # 权限检查
    _ensure_template_write_access(current_user)
    
    # 创建模板
    template = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name=template_data.template_name,
        template_data=template_data.template_data,
        created_by=current_user.id
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        revision=get_template_revision(template),
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=current_user.full_name,
        bindings_count=0,
        active_bindings_count=0,
        work_orders_count=0,
        active_work_orders_count=0,
    )


@router.get("/templates/{template_id}", response_model=InspectionTemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取模板详情"""
    # 权限检查
    _ensure_template_read_access(current_user)
    
    template = db.query(InspectionTemplate).options(
        joinedload(InspectionTemplate.creator)
    ).filter(InspectionTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 获取绑定统计信息
    bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id
    ).count()
    
    active_bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id,
        TemplateBinding.active == True
    ).count()

    work_orders_count = db.query(func.count(func.distinct(WorkOrder.id))).join(
        SiteInspection,
        or_(
            SiteInspection.work_order_id == WorkOrder.id,
            SiteInspection.id == WorkOrder.inspection_id,
        ),
    ).filter(
        SiteInspection.template_id == template.id,
    ).scalar() or 0

    active_work_orders_count = db.query(func.count(func.distinct(WorkOrder.id))).join(
        SiteInspection,
        or_(
            SiteInspection.work_order_id == WorkOrder.id,
            SiteInspection.id == WorkOrder.inspection_id,
        ),
    ).filter(
        SiteInspection.template_id == template.id,
        WorkOrder.status != WorkOrderStatusEnum.COMPLETED,
    ).scalar() or 0
    
    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        revision=get_template_revision(template),
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=template.creator.full_name if template.creator else None,
        bindings_count=bindings_count,
        active_bindings_count=active_bindings_count,
        work_orders_count=work_orders_count,
        active_work_orders_count=active_work_orders_count,
    )


@router.get("/templates/{template_id}/usage")
async def get_template_usage(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取模板使用情况（简化版）"""
    
    # 权限检查
    _ensure_template_read_access(current_user)
    
    # 验证模板存在
    from app.models.inspection import SiteInspection, InspectionStatusEnum
    
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    usage_counts = get_template_usage_counts(db, template_id)
    
    # 获取前10个检查记录详情
    inspections = db.query(SiteInspection).options(
        joinedload(SiteInspection.site),
        joinedload(SiteInspection.inspector)
    ).filter(
        SiteInspection.template_id == template_id
    ).limit(10).all()
    
    details = [
        {
            "inspection_id": insp.id,
            "site_name": insp.site.site_name if insp.site else "未知",
            "status": insp.status.value,
            "inspector": insp.inspector.full_name if insp.inspector else "未知",
            "created_at": to_utc_iso(insp.created_at)
        }
        for insp in inspections
    ]
    
    return {
        "template_id": template_id,
        "is_used": usage_counts["total"] > 0,
        "total_inspections": usage_counts["total"],
        "active_inspections": usage_counts["immediate"] + usage_counts["pending"],
        "completed_inspections": usage_counts["frozen"],
        "immediate_sync_inspections": usage_counts["immediate"],
        "pending_resubmit_inspections": usage_counts["pending"],
        "frozen_inspections": usage_counts["frozen"],
        "inspection_details": details
    }


@router.get("/templates/{template_id}/export", response_model=TemplateExportResponse)
async def export_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出检查模板为 JSON（不含绑定规则）"""
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["inspection:template:write"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员或项目经理可以导出模板",
        )

    template = (
        db.query(InspectionTemplate)
        .options(joinedload(InspectionTemplate.creator))
        .filter(InspectionTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )

    metadata: Dict[str, Any] = {
        "template_id": template.id,
        "created_by": template.created_by,
        "creator_name": template.creator.full_name if template.creator else None,
        "created_at": to_utc_iso(template.created_at) if template.created_at else None,
        "updated_at": to_utc_iso(template.updated_at) if template.updated_at else None,
        "exported_by": current_user.id,
        "exported_username": current_user.username,
        "exported_at": to_utc_iso(datetime.utcnow()),
        "version": "1.0",
    }

    # 记录导出日志
    try:
        log = UserLog(
            session_id="template-export",
            user_id=current_user.id,
            username=current_user.username,
            timestamp=datetime.utcnow(),
            action="template_export",
            level="INFO",
            page_route="web-admin/inspections/templates",
            page_options=None,
            action_data={
                "template_id": template.id,
                "template_name": template.template_name,
            },
            device_platform="web-admin",
            device_model="browser",
            screen_width=None,
            screen_height=None,
            error_message=None,
            error_stack=None,
            error_context=None,
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

    return TemplateExportResponse(
        template_name=template.template_name,
        template_data=template.template_data,
        description=template.template_data.get("description") if isinstance(template.template_data, dict) else None,
        metadata=metadata,
    )


@router.post("/templates/import", response_model=InspectionTemplateResponse)
async def import_template(
    payload: TemplateImportPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从 JSON 导入检查模板（始终新建一个模板，不覆盖现有）"""
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["inspection:template:write"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员或项目经理可以导入模板",
        )

    # 名称必填且需唯一
    template_name = payload.template_name.strip()
    if not template_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板名称不能为空",
        )

    exists = (
        db.query(InspectionTemplate)
        .filter(InspectionTemplate.template_name == template_name)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板名称已存在，请修改后再导入",
        )

    template_json = payload.template
    template_data = template_json.get("template_data") or {}
    description = template_json.get("description") or template_data.get("description") or ""

    # 生成新的模板 ID
    new_id = str(uuid.uuid4())

    # 创建模板记录
    template = InspectionTemplate(
        id=new_id,
        template_name=template_name,
        template_data={
            **template_data,
            "description": description,
        },
        created_by=current_user.id,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    # 记录导入日志
    try:
        log = UserLog(
            session_id="template-import",
            user_id=current_user.id,
            username=current_user.username,
            timestamp=datetime.utcnow(),
            action="template_import",
            level="INFO",
            page_route="web-admin/inspections/templates",
            page_options=None,
            action_data={
                "template_id": template.id,
                "template_name": template.template_name,
            },
            device_platform="web-admin",
            device_model="browser",
            screen_width=None,
            screen_height=None,
            error_message=None,
            error_stack=None,
            error_context=None,
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        revision=get_template_revision(template),
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=current_user.full_name,
        bindings_count=0,
        active_bindings_count=0,
        work_orders_count=0,
        active_work_orders_count=0,
    )


@router.put("/templates/{template_id}", response_model=dict)
async def update_template(
    template_id: str,
    template_update: InspectionTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新检查模板（带自动级联更新）"""
    
    # 权限检查
    _ensure_template_write_access(current_user)
    
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 保存旧数据（用于后端验证和变更分析）
    old_template_data = template.template_data
    new_template_data = template_update.template_data
    
    # 只有当模板已被检查记录引用时，才限制结构性变更
    is_used = (db.query(func.count(SiteInspection.id))
                 .filter(SiteInspection.template_id == template_id)
                 .scalar() or 0) > 0

    if is_used and old_template_data is not None and new_template_data is not None:
        # 后端验证：检查是否有禁止的结构性变更
        validation_result = validate_template_changes(old_template_data, new_template_data)
        if not validation_result['valid']:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "检测到禁止的结构性变更",
                    "message": "该模板已被使用，仍禁止修改高风险结构字段（如检查级别、检查类型、字段类型等）",
                    "violations": validation_result['violations']
                }
            )

    update_fields = template_update.dict(exclude_unset=True)
    template_changed = False
    for field, value in update_fields.items():
        if getattr(template, field) != value:
            setattr(template, field, value)
            template_changed = True

    if not template_changed:
        return {
            "success": True,
            "message": "模板未发生变化",
            "template_id": template_id,
            "template_name": template.template_name,
            "template_revision": get_template_revision(template),
            "cascaded_updates_count": 0,
            "sync_summary": {
                "synced_inspections": 0,
                "pending_inspections": 0,
                "frozen_inspections": 0,
                "created_items": 0,
                "updated_items": 0,
                "removed_items": 0,
                "reopened_items": 0,
            },
            "change_summary": summarize_changes(
                old_template_data or {},
                (new_template_data if new_template_data is not None else old_template_data) or {},
            ),
            "updated_at": to_utc_iso(template.updated_at)
        }

    template_data_changed = new_template_data is not None and old_template_data != new_template_data

    try:
        if template_data_changed:
            template.revision = get_template_revision(template) + 1

        template.updated_at = datetime.utcnow()
        db.flush()

        sync_summary = {
            "synced_inspections": 0,
            "pending_inspections": 0,
            "frozen_inspections": 0,
            "created_items": 0,
            "updated_items": 0,
            "removed_items": 0,
            "reopened_items": 0,
        }
        if template_data_changed:
            sync_summary = sync_template_to_editable_inspections(db, template)

        change_summary = summarize_changes(
            old_template_data or {},
            (new_template_data if new_template_data is not None else old_template_data) or {},
        )
        db.commit()
        db.refresh(template)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"模板更新失败：{e}",
        )

    cascaded_count = (
        int(sync_summary.get("created_items") or 0)
        + int(sync_summary.get("updated_items") or 0)
        + int(sync_summary.get("removed_items") or 0)
    )
    message = "模板更新成功"
    if template_data_changed:
        message += (
            f"，已同步 {sync_summary.get('synced_inspections', 0)} 个进行中检查"
            f"，{sync_summary.get('pending_inspections', 0)} 个待下次重提生效"
        )

    return {
        "success": True,
        "message": message,
        "template_id": template_id,
        "template_name": template.template_name,
        "template_revision": get_template_revision(template),
        "cascaded_updates_count": cascaded_count,
        "sync_summary": sync_summary,
        "change_summary": change_summary,
        "updated_at": to_utc_iso(template.updated_at)
    }


@router.delete("/templates/{template_id}", response_model=dict)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除检查模板（物理删除）

    规则：
    - 已被绑定（template_bindings）或已被任何检查/档案引用时，禁止删除。
    """
    _ensure_template_write_access(current_user)

    template = db.query(InspectionTemplate).filter(InspectionTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )

    bindings_count = (
        db.query(func.count(TemplateBinding.id))
        .filter(TemplateBinding.template_id == template_id)
        .scalar()
        or 0
    )
    inspections_count = (
        db.query(func.count(SiteInspection.id))
        .filter(SiteInspection.template_id == template_id)
        .scalar()
        or 0
    )

    from app.models.opening_archive import SiteOpeningArchive
    from app.models.survey_archive import SiteSurveyArchive
    from app.models.ssv_archive import SiteSSVArchive

    opening_archives_count = (
        db.query(func.count(SiteOpeningArchive.id))
        .filter(SiteOpeningArchive.template_id == template_id)
        .scalar()
        or 0
    )
    survey_archives_count = (
        db.query(func.count(SiteSurveyArchive.id))
        .filter(SiteSurveyArchive.template_id == template_id)
        .scalar()
        or 0
    )
    ssv_archives_count = (
        db.query(func.count(SiteSSVArchive.id))
        .filter(SiteSSVArchive.template_id == template_id)
        .scalar()
        or 0
    )

    if any(
        count > 0
        for count in [
            bindings_count,
            inspections_count,
            opening_archives_count,
            survey_archives_count,
            ssv_archives_count,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "模板已被绑定或已被使用，禁止删除",
                "bindings_count": bindings_count,
                "inspections_count": inspections_count,
                "opening_archives_count": opening_archives_count,
                "survey_archives_count": survey_archives_count,
                "ssv_archives_count": ssv_archives_count,
            },
        )

    try:
        db.delete(template)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"删除失败：{exc}",
        )

    return {"message": "模板删除成功", "template_id": template_id}


@router.get("/templates/{template_id}/bindings", response_model=List[TemplateBindingResponse])
async def get_template_bindings(
    template_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取模板绑定列表"""
    # 权限检查
    _ensure_template_read_access(current_user)
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    query = db.query(TemplateBinding).options(
        joinedload(TemplateBinding.site),
        joinedload(TemplateBinding.creator)
    ).filter(TemplateBinding.template_id == template_id)
    
    if active_only:
        query = query.filter(TemplateBinding.active == True)
    
    # 按优先级降序、更新时间降序排序
    query = query.order_by(desc(TemplateBinding.priority), desc(TemplateBinding.updated_at))
    
    bindings = query.offset(skip).limit(limit).all()
    
    result = []
    for binding in bindings:
        binding_response = TemplateBindingResponse(
            id=binding.id,
            template_id=binding.template_id,
            site_id=binding.site_id,
            site_type=binding.site_type,
            task_type=None,
            region=binding.region,
            customer=binding.customer,
            tags=binding.tags,
            priority=binding.priority,
            active=binding.active,
            valid_from=binding.valid_from,
            valid_to=binding.valid_to,
            notes=binding.notes,
            created_by=binding.created_by,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
            template_name=template.template_name,
            site_name=binding.site.site_name if binding.site else None,
            creator_name=binding.creator.full_name if binding.creator else None
        )
        result.append(binding_response)
    
    return result


@router.post("/templates/{template_id}/bindings", response_model=TemplateBindingResponse)
async def create_template_binding(
    template_id: str,
    binding_data: TemplateBindingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建模板绑定"""
    # 权限检查
    _ensure_template_write_access(current_user)
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 验证绑定条件
    resolver = create_resolver(db)
    errors = resolver.validate_binding_conditions(binding_data.dict())
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"绑定条件验证失败: {'; '.join(errors)}"
        )
    
    # 创建绑定
    binding = TemplateBinding(
        template_id=template_id,
        site_id=binding_data.site_id,
        site_type=binding_data.site_type,
        task_type=binding_data.task_type,
        region=binding_data.region,
        customer=binding_data.customer,
        tags=binding_data.tags,
        priority=binding_data.priority,
        active=binding_data.active,
        valid_from=binding_data.valid_from,
        valid_to=binding_data.valid_to,
        notes=binding_data.notes,
        created_by=current_user.id
    )
    
    db.add(binding)
    db.commit()
    db.refresh(binding)
    
    # 获取关联信息
    site = None
    if binding.site_id:
        site = db.query(Site).filter(Site.id == binding.site_id).first()
    
    return TemplateBindingResponse(
        id=binding.id,
        template_id=binding.template_id,
        site_id=binding.site_id,
        site_type=binding.site_type,
        task_type=binding.task_type,
        region=binding.region,
        customer=binding.customer,
        tags=binding.tags,
        priority=binding.priority,
        active=binding.active,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        notes=binding.notes,
        created_by=binding.created_by,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
        template_name=template.template_name,
        site_name=site.site_name if site else None,
        creator_name=current_user.full_name
    )


@router.put("/templates/{template_id}/bindings/{binding_id}", response_model=TemplateBindingResponse)
async def update_template_binding(
    template_id: str,
    binding_id: int,
    binding_update: TemplateBindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模板绑定"""
    # 权限检查
    _ensure_template_write_access(current_user)
    
    binding = db.query(TemplateBinding).filter(
        TemplateBinding.id == binding_id,
        TemplateBinding.template_id == template_id
    ).first()
    
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="绑定不存在"
        )
    
    # 验证绑定条件
    update_data = binding_update.dict(exclude_unset=True)
    if update_data:
        # 合并现有数据和更新数据进行验证
        current_data = {
            'site_id': binding.site_id,
            'site_type': binding.site_type,
            'task_type': binding.task_type.value if binding.task_type else None,
            'region': binding.region,
            'customer': binding.customer,
            'tags': binding.tags,
            'priority': binding.priority
        }
        current_data.update(update_data)
        
        resolver = create_resolver(db)
        errors = resolver.validate_binding_conditions(current_data)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"绑定条件验证失败: {'; '.join(errors)}"
            )
    
    # 更新字段
    for field, value in update_data.items():
        setattr(binding, field, value)
    
    binding.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(binding)
    
    # 获取关联信息
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    site = None
    if binding.site_id:
        site = db.query(Site).filter(Site.id == binding.site_id).first()
    
    creator = db.query(User).filter(User.id == binding.created_by).first()
    
    return TemplateBindingResponse(
        id=binding.id,
        template_id=binding.template_id,
        site_id=binding.site_id,
        site_type=binding.site_type,
        task_type=binding.task_type,
        region=binding.region,
        customer=binding.customer,
        tags=binding.tags,
        priority=binding.priority,
        active=binding.active,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        notes=binding.notes,
        created_by=binding.created_by,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
        template_name=template.template_name if template else None,
        site_name=site.site_name if site else None,
        creator_name=creator.full_name if creator else None
    )


@router.delete("/templates/{template_id}/bindings/{binding_id}")
async def delete_template_binding(
    template_id: str,
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模板绑定"""
    # 权限检查
    _ensure_template_write_access(current_user)
    
    binding = db.query(TemplateBinding).filter(
        TemplateBinding.id == binding_id,
        TemplateBinding.template_id == template_id
    ).first()
    
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="绑定不存在"
        )
    
    db.delete(binding)
    db.commit()
    
    return {"message": "绑定已删除"}


@router.post("/templates/{template_id}/bindings/batch-update")
async def batch_update_binding_priority(
    template_id: str,
    batch_update: TemplateBindingBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量更新绑定优先级（用于拖拽排序）"""
    # 权限检查
    _ensure_template_write_access(current_user)
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 批量更新
    updated_count = 0
    for update_data in batch_update.binding_updates:
        binding = db.query(TemplateBinding).filter(
            TemplateBinding.id == update_data['id'],
            TemplateBinding.template_id == template_id
        ).first()
        
        if binding:
            binding.priority = update_data['priority']
            binding.updated_at = datetime.utcnow()
            updated_count += 1
    
    db.commit()
    
    return {
        "message": f"成功更新 {updated_count} 个绑定的优先级",
        "updated_count": updated_count
    }


@router.post("/templates/resolve", response_model=TemplateResolveResponse)
async def resolve_template(
    context: ResolveContextSchema,
    show_all: bool = Query(False, description="是否显示所有匹配结果"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """解析最匹配的模板"""
    # 权限检查
    _ensure_template_read_access(current_user)
    
    # 创建解析上下文
    resolve_context = ResolveContext(
        site_id=context.site_id,
        site_type=context.site_type,
        task_id=context.task_id,
        task_type=context.task_type,
        region=context.region,
        customer=context.customer,
        tags=context.tags
    )
    
    # 创建解析器
    resolver = create_resolver(db)
    
    if show_all:
        # 获取所有匹配结果
        all_matches = resolver.get_matching_bindings(resolve_context)
        
        all_match_schemas = []
        for match in all_matches:
            # 获取绑定详情
            binding_response = TemplateBindingResponse(
                id=match.binding.id,
                template_id=match.binding.template_id,
                site_id=match.binding.site_id,
                site_type=match.binding.site_type,
                task_type=match.binding.task_type,
                region=match.binding.region,
                customer=match.binding.customer,
                tags=match.binding.tags,
                priority=match.binding.priority,
                active=match.binding.active,
                valid_from=match.binding.valid_from,
                valid_to=match.binding.valid_to,
                notes=match.binding.notes,
                created_by=match.binding.created_by,
                created_at=match.binding.created_at,
                updated_at=match.binding.updated_at
            )
            
            match_schema = TemplateMatchResultSchema(
                template_id=match.template_id,
                binding_id=match.binding_id,
                match_score=match.match_score,
                priority=match.priority,
                explain=match.explain,
                template_name=match.template.template_name,
                template_data=match.template.template_data,
                binding_details=binding_response
            )
            all_match_schemas.append(match_schema)
        
        return TemplateResolveResponse(
            success=True,
            result=all_match_schemas[0] if all_match_schemas else None,
            message=f"找到 {len(all_match_schemas)} 个匹配结果" if all_match_schemas else "未找到匹配的模板",
            all_matches=all_match_schemas
        )
    else:
        # 只获取最佳匹配
        result = resolver.resolve_template(resolve_context)
        
        if result:
            # 获取绑定详情
            binding_response = TemplateBindingResponse(
                id=result.binding.id,
                template_id=result.binding.template_id,
                site_id=result.binding.site_id,
                site_type=result.binding.site_type,
                task_type=result.binding.task_type,
                region=result.binding.region,
                customer=result.binding.customer,
                tags=result.binding.tags,
                priority=result.binding.priority,
                active=result.binding.active,
                valid_from=result.binding.valid_from,
                valid_to=result.binding.valid_to,
                notes=result.binding.notes,
                created_by=result.binding.created_by,
                created_at=result.binding.created_at,
                updated_at=result.binding.updated_at
            )
            
            result_schema = TemplateMatchResultSchema(
                template_id=result.template_id,
                binding_id=result.binding_id,
                match_score=result.match_score,
                priority=result.priority,
                explain=result.explain,
                template_name=result.template.template_name,
                template_data=result.template.template_data,
                binding_details=binding_response
            )
            
            return TemplateResolveResponse(
                success=True,
                result=result_schema,
                message="成功找到匹配的模板"
            )
        else:
            return TemplateResolveResponse(
                success=False,
                message="未找到匹配的模板，将使用默认模板"
            )
