from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.site import Site
from app.models.site_group import SiteGroupAssignment, SiteGroupCategory, SiteGroupOption
from app.models.user import User
from app.schemas.site_group import (
    SiteGroupAssignmentResponse,
    SiteGroupAssignmentUpsert,
    SiteGroupBatchAssignmentRequest,
    SiteGroupBatchAssignmentResponse,
    SiteGroupCategoryCreate,
    SiteGroupCategoryResponse,
    SiteGroupCategoryUpdate,
    SiteGroupDerivedSyncRequest,
    SiteGroupDerivedSyncResponse,
    SiteGroupOptionCreate,
    SiteGroupOptionResponse,
    SiteGroupOptionUpdate,
    SiteGroupSeedDeliveryScopeRequest,
    SiteGroupSeedDeliveryScopeResponse,
    SiteGroupSourceFieldResponse,
)
from app.services.authz_service import user_has_any_role_or_permission
from app.services.site_group_service import (
    DELIVERY_SCOPE_CATEGORY_NAME,
    LLD_DUPLEX_SOURCE,
    apply_derived_group_sync_plan,
    build_derived_group_sync_plan,
    build_delivery_scope_seed_plan,
    ensure_delivery_scope_category,
    get_group_source_field_definitions,
    make_group_code,
    serialize_assignment,
    serialize_categories,
    serialize_category,
    upsert_site_group_assignment,
    validate_group_source_settings,
)

router = APIRouter()


def _ensure_group_manage_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager", "planner"],
        permission_codes=["sites:update:write", "sites:create:write"],
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def _get_category(db: Session, category_id: int) -> SiteGroupCategory:
    category = (
        db.query(SiteGroupCategory)
        .options(joinedload(SiteGroupCategory.options))
        .filter(SiteGroupCategory.id == category_id)
        .first()
    )
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组维度不存在")
    return category


def _get_option(db: Session, option_id: int) -> SiteGroupOption:
    option = db.query(SiteGroupOption).filter(SiteGroupOption.id == option_id).first()
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组选项不存在")
    return option


def _commit_or_400(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _derived_response(
    *,
    dry_run: bool,
    plan: dict,
) -> SiteGroupDerivedSyncResponse:
    category = plan["category"]
    return SiteGroupDerivedSyncResponse(
        dry_run=dry_run,
        category_id=category.id,
        category_name=category.name,
        source_type=plan.get("source_type"),
        source_field=plan.get("source_field"),
        requested_count=int(plan.get("requested_count") or 0),
        suggested_count=int(plan.get("suggested_count") or 0),
        assigned_count=int(plan.get("assigned_count") or 0),
        unchanged_count=int(plan.get("unchanged_count") or 0),
        conflict_count=int(plan.get("conflict_count") or 0),
        skipped_count=int(plan.get("skipped_count") or 0),
        created_option_count=int(plan.get("created_option_count") or 0),
        by_option=plan.get("by_option") or {},
        warnings=plan.get("warnings") or [],
        samples=plan.get("samples") or [],
    )


@router.get("/source-fields", response_model=List[SiteGroupSourceFieldResponse])
async def list_group_source_fields(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return get_group_source_field_definitions()


@router.get("/categories", response_model=List[SiteGroupCategoryResponse])
async def list_group_categories(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    query = db.query(SiteGroupCategory).options(joinedload(SiteGroupCategory.options))
    if not include_inactive:
        query = query.filter(SiteGroupCategory.is_active == True)
    categories = query.order_by(SiteGroupCategory.sort_order.asc(), SiteGroupCategory.id.asc()).all()
    return serialize_categories(categories, include_inactive_options=include_inactive)


@router.post("/categories", response_model=SiteGroupCategoryResponse)
async def create_group_category(
    payload: SiteGroupCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)

    if payload.is_active and payload.is_default:
        db.query(SiteGroupCategory).update({SiteGroupCategory.is_default: False})

    try:
        assignment_mode, source_type, source_field, source_config = validate_group_source_settings(
            assignment_mode=payload.assignment_mode,
            source_type=payload.source_type,
            source_field=payload.source_field,
            source_config=payload.source_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    category = SiteGroupCategory(
        code=make_group_code(payload.code or payload.name, "category"),
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        sort_order=int(payload.sort_order or 0),
        is_active=bool(payload.is_active),
        is_default=bool(payload.is_active and payload.is_default),
        assignment_mode=assignment_mode,
        source_type=source_type,
        source_field=source_field,
        source_config=source_config,
        created_by=current_user.id,
    )
    db.add(category)
    db.flush()

    for idx, option_payload in enumerate(payload.options or [], start=1):
        option = SiteGroupOption(
            category_id=category.id,
            code=make_group_code(option_payload.code or option_payload.name, "option"),
            name=option_payload.name.strip(),
            color=(option_payload.color or "").strip() or None,
            sort_order=int(option_payload.sort_order or idx * 10),
            is_active=bool(option_payload.is_active),
        )
        db.add(option)

    _commit_or_400(db, "分组维度编码或选项编码重复")
    return serialize_category(_get_category(db, category.id))


@router.put("/categories/{category_id}", response_model=SiteGroupCategoryResponse)
async def update_group_category(
    category_id: int,
    payload: SiteGroupCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    category = _get_category(db, category_id)
    update_data = payload.dict(exclude_unset=True)

    if update_data.get("is_default") is True:
        db.query(SiteGroupCategory).filter(SiteGroupCategory.id != category.id).update(
            {SiteGroupCategory.is_default: False}
        )

    if "code" in update_data and update_data["code"]:
        category.code = make_group_code(update_data["code"], "category")
    if "name" in update_data and update_data["name"]:
        category.name = str(update_data["name"]).strip()
    if "description" in update_data:
        category.description = str(update_data["description"] or "").strip() or None
    if "sort_order" in update_data:
        category.sort_order = int(update_data["sort_order"] or 0)
    if "is_active" in update_data:
        category.is_active = bool(update_data["is_active"])
    if "is_default" in update_data:
        category.is_default = bool(update_data["is_default"])
        if category.is_default:
            category.is_active = True
    if not category.is_active:
        category.is_default = False
    if any(key in update_data for key in ("assignment_mode", "source_type", "source_field", "source_config")):
        try:
            assignment_mode, source_type, source_field, source_config = validate_group_source_settings(
                assignment_mode=update_data.get("assignment_mode", category.assignment_mode),
                source_type=update_data.get("source_type", category.source_type),
                source_field=update_data.get("source_field", category.source_field),
                source_config=update_data.get("source_config", category.source_config),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        category.assignment_mode = assignment_mode
        category.source_type = source_type
        category.source_field = source_field
        category.source_config = source_config

    _commit_or_400(db, "分组维度编码重复")
    return serialize_category(_get_category(db, category.id))


@router.post("/categories/{category_id}/options", response_model=SiteGroupOptionResponse)
async def create_group_option(
    category_id: int,
    payload: SiteGroupOptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    category = _get_category(db, category_id)
    option = SiteGroupOption(
        category_id=category.id,
        code=make_group_code(payload.code or payload.name, "option"),
        name=payload.name.strip(),
        color=(payload.color or "").strip() or None,
        sort_order=int(payload.sort_order or 0),
        is_active=bool(payload.is_active),
    )
    db.add(option)
    _commit_or_400(db, "分组选项编码重复")
    db.refresh(option)
    return SiteGroupOptionResponse.from_orm(option)


@router.put("/options/{option_id}", response_model=SiteGroupOptionResponse)
async def update_group_option(
    option_id: int,
    payload: SiteGroupOptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    option = _get_option(db, option_id)
    update_data = payload.dict(exclude_unset=True)

    if "code" in update_data and update_data["code"]:
        option.code = make_group_code(update_data["code"], "option")
    if "name" in update_data and update_data["name"]:
        option.name = str(update_data["name"]).strip()
    if "color" in update_data:
        option.color = str(update_data["color"] or "").strip() or None
    if "sort_order" in update_data:
        option.sort_order = int(update_data["sort_order"] or 0)
    if "is_active" in update_data:
        option.is_active = bool(update_data["is_active"])

    _commit_or_400(db, "分组选项编码重复")
    db.refresh(option)
    return SiteGroupOptionResponse.from_orm(option)


@router.post("/categories/{category_id}/derive", response_model=SiteGroupDerivedSyncResponse)
async def derive_group_assignments(
    category_id: int,
    payload: SiteGroupDerivedSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    category = _get_category(db, category_id)
    has_preview_overrides = any(
        value is not None
        for value in (
            payload.assignment_mode,
            payload.source_type,
            payload.source_field,
            payload.source_config,
        )
    )
    if has_preview_overrides and not payload.dry_run:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同步前请先保存维度配置")
    try:
        plan = build_derived_group_sync_plan(
            db,
            category,
            overwrite=payload.overwrite,
            create_missing_options=payload.create_missing_options,
            assignment_mode=payload.assignment_mode if payload.dry_run else None,
            source_type=payload.source_type if payload.dry_run else None,
            source_field=payload.source_field if payload.dry_run else None,
            source_config=payload.source_config if payload.dry_run else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if payload.dry_run:
        return _derived_response(dry_run=True, plan=plan)

    applied_plan = apply_derived_group_sync_plan(db, plan, operator_id=current_user.id)
    db.commit()
    return _derived_response(dry_run=False, plan=applied_plan)


@router.get("/sites/{site_id}/assignments", response_model=List[SiteGroupAssignmentResponse])
async def list_site_group_assignments(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    site = (
        db.query(Site)
        .options(
            joinedload(Site.group_assignments).joinedload(SiteGroupAssignment.category),
            joinedload(Site.group_assignments).joinedload(SiteGroupAssignment.option),
        )
        .filter(Site.id == site_id)
        .first()
    )
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="站点不存在")
    return [serialize_assignment(row) for row in site.group_assignments or []]


@router.put("/sites/{site_id}/assignments", response_model=List[SiteGroupAssignmentResponse])
async def upsert_site_group_assignment_endpoint(
    site_id: int,
    payload: SiteGroupAssignmentUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="站点不存在")

    try:
        upsert_site_group_assignment(
            db,
            site_id=site_id,
            category_id=payload.category_id,
            option_id=payload.option_id,
            operator_id=current_user.id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return await list_site_group_assignments(site_id, db, current_user)


@router.post("/assignments/batch", response_model=SiteGroupBatchAssignmentResponse)
async def batch_upsert_site_group_assignments(
    payload: SiteGroupBatchAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    site_ids = list(dict.fromkeys(int(site_id) for site_id in payload.site_ids or []))
    if not site_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择站点")

    existing_site_ids = {
        site_id
        for (site_id,) in db.query(Site.id).filter(Site.id.in_(site_ids)).all()
    }
    updated_count = 0
    cleared_count = 0
    skipped_count = 0
    errors: List[str] = []

    for site_id in site_ids:
        if site_id not in existing_site_ids:
            errors.append(f"站点不存在: {site_id}")
            skipped_count += 1
            continue
        try:
            action, _ = upsert_site_group_assignment(
                db,
                site_id=site_id,
                category_id=payload.category_id,
                option_id=payload.option_id,
                operator_id=current_user.id,
            )
        except ValueError as exc:
            errors.append(str(exc))
            skipped_count += 1
            continue
        if action == "cleared":
            cleared_count += 1
        elif action in {"created", "updated"}:
            updated_count += 1
        else:
            skipped_count += 1

    db.commit()

    return SiteGroupBatchAssignmentResponse(
        requested_count=len(site_ids),
        updated_count=updated_count,
        cleared_count=cleared_count,
        skipped_count=skipped_count,
        errors=errors,
    )


@router.post("/delivery-scope/seed-from-lld-duplex", response_model=SiteGroupSeedDeliveryScopeResponse)
async def seed_delivery_scope_from_lld_duplex(
    payload: SiteGroupSeedDeliveryScopeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_group_manage_access(current_user)
    plan = build_delivery_scope_seed_plan(db, overwrite=payload.overwrite)
    category = plan["category"]

    if payload.dry_run:
        return SiteGroupSeedDeliveryScopeResponse(
            dry_run=True,
            category_id=getattr(category, "id", None),
            category_name=DELIVERY_SCOPE_CATEGORY_NAME,
            requested_count=int(plan["requested_count"]),
            suggested_count=int(plan["suggested_count"]),
            assigned_count=int(plan["assigned_count"]),
            unchanged_count=int(plan["unchanged_count"]),
            conflict_count=int(plan["conflict_count"]),
            skipped_count=int(plan["skipped_count"]),
            by_option=plan["by_option"],
            warnings=plan["warnings"],
            samples=plan["samples"],
        )

    category, option_map = ensure_delivery_scope_category(db, operator_id=current_user.id)
    assigned_count = 0
    unchanged_count = 0
    conflict_count = 0
    skipped_count = 0

    for row in plan["plan"]:
        target = row.get("target")
        action = row.get("action")
        if target not in option_map:
            skipped_count += 1
            continue
        if action in {"assign", "overwrite"}:
            upsert_site_group_assignment(
                db,
                site_id=int(row["site_id"]),
                category_id=category.id,
                option_id=option_map[target].id,
                operator_id=current_user.id,
                source=LLD_DUPLEX_SOURCE,
            )
            assigned_count += 1
        elif action == "unchanged":
            unchanged_count += 1
        elif action == "conflict":
            conflict_count += 1
        else:
            skipped_count += 1

    db.commit()

    return SiteGroupSeedDeliveryScopeResponse(
        dry_run=False,
        category_id=category.id,
        category_name=category.name,
        requested_count=int(plan["requested_count"]),
        suggested_count=int(plan["suggested_count"]),
        assigned_count=assigned_count,
        unchanged_count=unchanged_count,
        conflict_count=conflict_count,
        skipped_count=skipped_count,
        by_option=plan["by_option"],
        warnings=plan["warnings"],
        samples=plan["samples"],
    )
