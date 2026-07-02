from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.site_group import SiteGroupAssignment, SiteGroupCategory, SiteGroupOption
from app.models.system_config import SystemConfig
from app.models.user_subcontractor import UserSubcontractorAssignment
from app.services.site_group_service import upsert_site_group_assignment

WORK_ORDER_ASSIGNMENT_SETTINGS_KEY = "work_order_assignment_settings"


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def get_subcontractor_category(
    db: Session,
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[SiteGroupCategory]:
    resolved_settings = settings or load_work_order_assignment_settings(db)
    category_id = _optional_int(resolved_settings.get("subcontractor_category_id"))
    if not category_id:
        return None
    return (
        db.query(SiteGroupCategory)
        .filter(
            SiteGroupCategory.id == category_id,
            SiteGroupCategory.is_active == True,
        )
        .first()
    )


def get_subcontractor_options(db: Session) -> List[Dict[str, Any]]:
    category = get_subcontractor_category(db)
    if not category:
        return []
    rows = (
        db.query(SiteGroupOption)
        .filter(
            SiteGroupOption.category_id == category.id,
            SiteGroupOption.is_active == True,
        )
        .order_by(SiteGroupOption.sort_order.asc(), SiteGroupOption.id.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "category_id": row.category_id,
            "code": row.code,
            "name": row.name,
            "color": row.color,
        }
        for row in rows
    ]


def serialize_subcontractor_option(option: Optional[SiteGroupOption]) -> Optional[Dict[str, Any]]:
    if not option:
        return None
    return {
        "option_id": option.id,
        "option_code": option.code,
        "option_name": option.name,
        "option_color": option.color,
        "category_id": option.category_id,
    }


def get_user_subcontractor_assignment(
    db: Session,
    user_id: Optional[int],
) -> Optional[UserSubcontractorAssignment]:
    if not user_id:
        return None
    category = get_subcontractor_category(db)
    if not category:
        return None
    return (
        db.query(UserSubcontractorAssignment)
        .join(SiteGroupOption, SiteGroupOption.id == UserSubcontractorAssignment.option_id)
        .filter(
            UserSubcontractorAssignment.user_id == int(user_id),
            SiteGroupOption.category_id == category.id,
            SiteGroupOption.is_active == True,
        )
        .first()
    )


def serialize_user_subcontractor_assignment(
    assignment: Optional[UserSubcontractorAssignment],
) -> Optional[Dict[str, Any]]:
    if not assignment or not assignment.option:
        return None
    return serialize_subcontractor_option(assignment.option)


def set_user_subcontractor_assignment(
    db: Session,
    *,
    user_id: int,
    option_id: Optional[int],
    operator_id: Optional[int],
) -> Tuple[str, Optional[UserSubcontractorAssignment]]:
    category = get_subcontractor_category(db)
    assignment = (
        db.query(UserSubcontractorAssignment)
        .filter(UserSubcontractorAssignment.user_id == int(user_id))
        .first()
    )

    if option_id is None:
        if assignment is None:
            return "noop", None
        db.delete(assignment)
        return "cleared", None

    if not category:
        raise ValueError("系统尚未配置分包商站点分组维度")
    option = (
        db.query(SiteGroupOption)
        .filter(
            SiteGroupOption.id == int(option_id),
            SiteGroupOption.category_id == category.id,
            SiteGroupOption.is_active == True,
        )
        .first()
    )
    if option is None:
        raise ValueError("分包商不存在或已停用")

    if assignment is None:
        assignment = UserSubcontractorAssignment(
            user_id=int(user_id),
            option_id=option.id,
            is_primary=True,
            updated_by=operator_id,
        )
        db.add(assignment)
        return "created", assignment

    if assignment.option_id == option.id:
        return "noop", assignment

    assignment.option_id = option.id
    assignment.is_primary = True
    assignment.updated_by = operator_id
    return "updated", assignment


def get_site_subcontractor_assignment(db: Session, site_id: int) -> Optional[SiteGroupAssignment]:
    category = get_subcontractor_category(db)
    if not category:
        return None
    return (
        db.query(SiteGroupAssignment)
        .join(SiteGroupOption, SiteGroupOption.id == SiteGroupAssignment.option_id)
        .filter(
            SiteGroupAssignment.site_id == int(site_id),
            SiteGroupAssignment.category_id == category.id,
            SiteGroupOption.is_active == True,
        )
        .first()
    )


def normalize_work_order_assignment_settings(raw: Any) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    try:
        config_version = int(data.get("config_version") or 1)
    except (TypeError, ValueError):
        config_version = 1
    return {
        "config_version": max(config_version, 1),
        "subcontractor_category_id": _optional_int(data.get("subcontractor_category_id")),
        "auto_sync_site_subcontractor_on_assignment": bool(
            data.get("auto_sync_site_subcontractor_on_assignment", False)
        ),
    }


def load_work_order_assignment_settings(db: Session) -> Dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_ASSIGNMENT_SETTINGS_KEY).first()
    if not row:
        return normalize_work_order_assignment_settings(None)
    return normalize_work_order_assignment_settings(row.value)


def save_work_order_assignment_settings(db: Session, settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_work_order_assignment_settings(settings)
    category_id = normalized.get("subcontractor_category_id")
    if normalized["auto_sync_site_subcontractor_on_assignment"] and not category_id:
        raise ValueError("请先选择用于分包商的站点分组分类")
    if category_id:
        category = (
            db.query(SiteGroupCategory)
            .filter(
                SiteGroupCategory.id == int(category_id),
                SiteGroupCategory.is_active == True,
            )
            .first()
        )
        if category is None:
            raise ValueError("分包商分类不存在或已停用")
    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_ASSIGNMENT_SETTINGS_KEY).first()
    if row is None:
        row = SystemConfig(key=WORK_ORDER_ASSIGNMENT_SETTINGS_KEY, value=normalized)
        db.add(row)
    else:
        row.value = normalized
        flag_modified(row, "value")
    db.commit()
    return normalized


def sync_site_subcontractor_from_assignee(
    db: Session,
    *,
    site_id: int,
    assignee_id: Optional[int],
    operator_id: Optional[int],
) -> Dict[str, Any]:
    settings = load_work_order_assignment_settings(db)
    if not settings["auto_sync_site_subcontractor_on_assignment"] or not assignee_id:
        return {"action": "disabled"}

    category = get_subcontractor_category(db)
    if not category:
        return {"action": "no_subcontractor_category"}

    user_assignment = get_user_subcontractor_assignment(db, assignee_id)
    if not user_assignment or not user_assignment.option:
        return {"action": "assignee_without_subcontractor"}

    site_assignment = get_site_subcontractor_assignment(db, site_id)
    target_option = user_assignment.option
    if site_assignment and site_assignment.option_id == target_option.id:
        return {
            "action": "noop",
            "option": serialize_subcontractor_option(target_option),
        }

    if site_assignment and site_assignment.option_id != target_option.id:
        current_name = site_assignment.option.name if site_assignment.option else str(site_assignment.option_id)
        raise ValueError(
            f"站点已关联分包商 {current_name}，与所选执行人的分包商 {target_option.name} 不一致；请先手工确认站点分包商后再指派。"
        )

    action, _ = upsert_site_group_assignment(
        db,
        site_id=int(site_id),
        category_id=int(category.id),
        option_id=int(target_option.id),
        operator_id=operator_id,
        source="work_order_assignment",
    )
    return {
        "action": action,
        "option": serialize_subcontractor_option(target_option),
    }
