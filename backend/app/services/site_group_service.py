import re
import uuid
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.planning import SitePlanning, SitePlanningCell
from app.models.site import Site
from app.models.site_group import SiteGroupAssignment, SiteGroupCategory, SiteGroupOption
from app.schemas.site_group import (
    SiteGroupAssignmentResponse,
    SiteGroupCategoryResponse,
    SiteGroupOptionResponse,
)


DELIVERY_SCOPE_CATEGORY_CODE = "delivery_scope"
DELIVERY_SCOPE_CATEGORY_NAME = "交付范围"
GROUP_EXPORT_PREFIX = "group:"
LLD_DUPLEX_SOURCE = "lld_duplex_seed"
ASSIGNMENT_MODE_MANUAL = "manual"
ASSIGNMENT_MODE_DERIVED = "derived"
SOURCE_TYPE_SITE_FIELD = "site_field"
SOURCE_TYPE_LLD_CELL_FIELD = "lld_cell_field"
FIELD_DERIVED_SOURCE = "field_derived"
GROUP_SYNC_SAMPLE_LIMIT = 500
GROUP_SYNC_ACTION_PRIORITY = {
    "overwrite": 0,
    "conflict": 1,
    "skipped": 2,
    "assign": 3,
    "unchanged": 4,
}

SITE_DERIVED_FIELDS = {
    "province": ("省份", "站点基础信息中的省份"),
    "city": ("城市", "站点基础信息中的城市"),
    "district": ("区县", "站点基础信息中的区县"),
    "site_type": ("站点类型", "站点基础信息中的类型"),
    "status": ("站点状态", "站点当前状态"),
    "priority": ("优先级", "站点优先级"),
}

LLD_CELL_DERIVED_FIELDS = {
    "duplex_mode": ("LLD Duplex Mode", "当前 LLD 小区明细中的 Duplex Mode"),
    "band_code": ("LLD Band", "当前 LLD 小区明细中的归一化 Band"),
    "rat": ("LLD RAT", "当前 LLD 小区明细中的 RAT"),
    "city": ("LLD 城市", "当前 LLD 小区明细中的城市"),
    "county": ("LLD 区县", "当前 LLD 小区明细中的 County"),
    "cluster": ("LLD Cluster", "当前 LLD 小区明细中的 Cluster"),
    "scenario": ("LLD Scenario", "当前 LLD 小区明细中的 Scenario"),
    "tower_id": ("LLD Tower ID", "当前 LLD 小区明细中的 Tower ID"),
}

DELIVERY_SCOPE_SOURCE_CONFIG = {
    "strategy": "rules",
    "create_missing_options": False,
    "rules": [
        {"option_name": "TDD", "keywords": ["TDD"], "match": "contains"},
        {"option_name": "FDD", "keywords": ["FDD"], "match": "contains"},
    ],
}


def get_group_source_field_definitions() -> List[Dict[str, object]]:
    fields: List[Dict[str, object]] = []
    for source_field, (label, description) in SITE_DERIVED_FIELDS.items():
        fields.append(
            {
                "source_type": SOURCE_TYPE_SITE_FIELD,
                "source_field": source_field,
                "label": label,
                "description": description,
                "value_mode": "single",
            }
        )
    for source_field, (label, description) in LLD_CELL_DERIVED_FIELDS.items():
        fields.append(
            {
                "source_type": SOURCE_TYPE_LLD_CELL_FIELD,
                "source_field": source_field,
                "label": label,
                "description": description,
                "value_mode": "multi",
            }
        )
    return fields


def normalize_assignment_mode(value: Optional[str]) -> str:
    mode = str(value or ASSIGNMENT_MODE_MANUAL).strip().lower()
    if mode not in {ASSIGNMENT_MODE_MANUAL, ASSIGNMENT_MODE_DERIVED}:
        return ASSIGNMENT_MODE_MANUAL
    return mode


def normalize_source_config(value: object) -> Dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def validate_group_source_settings(
    *,
    assignment_mode: Optional[str],
    source_type: Optional[str],
    source_field: Optional[str],
    source_config: object,
) -> Tuple[str, Optional[str], Optional[str], Optional[Dict[str, object]]]:
    mode = normalize_assignment_mode(assignment_mode)
    if mode != ASSIGNMENT_MODE_DERIVED:
        return ASSIGNMENT_MODE_MANUAL, None, None, None

    normalized_source_type = str(source_type or "").strip()
    normalized_source_field = str(source_field or "").strip()
    if normalized_source_type == SOURCE_TYPE_SITE_FIELD:
        valid_fields = SITE_DERIVED_FIELDS
    elif normalized_source_type == SOURCE_TYPE_LLD_CELL_FIELD:
        valid_fields = LLD_CELL_DERIVED_FIELDS
    else:
        raise ValueError("请选择有效的派生来源类型")

    if normalized_source_field not in valid_fields:
        raise ValueError("请选择有效的派生来源字段")

    config = normalize_source_config(source_config)
    strategy = str(config.get("strategy") or "field_value").strip()
    if strategy not in {"field_value", "rules"}:
        strategy = "field_value"
    config["strategy"] = strategy
    config["create_missing_options"] = bool(config.get("create_missing_options", strategy == "field_value"))

    normalized_rules = []
    for raw_rule in list(config.get("rules") or []):
        if not isinstance(raw_rule, dict):
            continue
        keywords = raw_rule.get("keywords")
        if isinstance(keywords, str):
            keywords = [part.strip() for part in keywords.split(",")]
        if not isinstance(keywords, list):
            keywords = []
        cleaned_keywords = [str(item or "").strip() for item in keywords if str(item or "").strip()]
        if not cleaned_keywords:
            continue
        normalized_rules.append(
            {
                "option_id": raw_rule.get("option_id"),
                "option_code": str(raw_rule.get("option_code") or "").strip(),
                "option_name": str(raw_rule.get("option_name") or "").strip(),
                "keywords": cleaned_keywords,
                "match": "exact" if str(raw_rule.get("match") or "").strip() == "exact" else "contains",
            }
        )
    config["rules"] = normalized_rules
    return mode, normalized_source_type, normalized_source_field, config


def make_group_code(value: Optional[str], prefix: str) -> str:
    raw = str(value or "").strip().lower()
    code = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not code:
        code = f"{prefix}_{uuid.uuid4().hex[:8]}"
    return code[:80]


def group_column_name(category: SiteGroupCategory) -> str:
    return f"{GROUP_EXPORT_PREFIX}{category.name}"


def get_active_group_categories(db: Session) -> List[SiteGroupCategory]:
    return (
        db.query(SiteGroupCategory)
        .options(joinedload(SiteGroupCategory.options))
        .filter(SiteGroupCategory.is_active == True)
        .order_by(SiteGroupCategory.sort_order.asc(), SiteGroupCategory.id.asc())
        .all()
    )


def get_default_group_category(db: Session) -> Optional[SiteGroupCategory]:
    category = (
        db.query(SiteGroupCategory)
        .options(joinedload(SiteGroupCategory.options))
        .filter(SiteGroupCategory.is_active == True, SiteGroupCategory.is_default == True)
        .order_by(SiteGroupCategory.sort_order.asc(), SiteGroupCategory.id.asc())
        .first()
    )
    if category:
        return category
    return (
        db.query(SiteGroupCategory)
        .options(joinedload(SiteGroupCategory.options))
        .filter(SiteGroupCategory.is_active == True)
        .order_by(SiteGroupCategory.sort_order.asc(), SiteGroupCategory.id.asc())
        .first()
    )


def serialize_category(
    category: SiteGroupCategory,
    *,
    include_inactive_options: bool = False,
) -> SiteGroupCategoryResponse:
    options = [
        option
        for option in list(category.options or [])
        if include_inactive_options or getattr(option, "is_active", True)
    ]
    clone = SiteGroupCategoryResponse.from_orm(category)
    clone.options = [SiteGroupOptionResponse.from_orm(option) for option in options]
    return clone


def serialize_categories(
    categories: Iterable[SiteGroupCategory],
    *,
    include_inactive_options: bool = False,
) -> List[SiteGroupCategoryResponse]:
    return [
        serialize_category(category, include_inactive_options=include_inactive_options)
        for category in categories
    ]


def serialize_assignment(assignment: SiteGroupAssignment) -> SiteGroupAssignmentResponse:
    category = assignment.category
    option = assignment.option
    return SiteGroupAssignmentResponse(
        category_id=assignment.category_id,
        category_code=category.code if category else "",
        category_name=category.name if category else "",
        option_id=assignment.option_id,
        option_code=option.code if option else "",
        option_name=option.name if option else "",
        option_color=option.color if option else None,
        source=assignment.source,
    )


def serialize_site_assignments(site: Site) -> List[SiteGroupAssignmentResponse]:
    assignments = [
        assignment
        for assignment in list(getattr(site, "group_assignments", []) or [])
        if getattr(assignment.category, "is_active", True)
        and getattr(assignment.option, "is_active", True)
    ]
    assignments.sort(
        key=lambda item: (
            getattr(item.category, "sort_order", 0),
            getattr(item.category, "id", 0),
        )
    )
    return [serialize_assignment(assignment) for assignment in assignments]


def find_group_column_categories(db: Session, columns: Iterable[str]) -> Dict[str, SiteGroupCategory]:
    column_set = {str(col).strip() for col in columns}
    result: Dict[str, SiteGroupCategory] = {}
    for category in get_active_group_categories(db):
        col_name = group_column_name(category)
        if col_name in column_set:
            result[col_name] = category
    return result


def find_option_by_name(category: SiteGroupCategory, value: str) -> Optional[SiteGroupOption]:
    needle = str(value or "").strip().lower()
    if not needle:
        return None
    for option in list(category.options or []):
        if not getattr(option, "is_active", True):
            continue
        if str(option.name or "").strip().lower() == needle:
            return option
        if str(option.code or "").strip().lower() == needle:
            return option
    return None


def _normalize_source_value(value: object) -> str:
    return str(value or "").strip()


def _normalize_match_value(value: object) -> str:
    return _normalize_source_value(value).lower()


def _collect_derived_source_values(
    db: Session,
    *,
    source_type: str,
    source_field: str,
) -> Dict[int, Dict[str, object]]:
    grouped: Dict[int, Dict[str, object]] = {}

    if source_type == SOURCE_TYPE_SITE_FIELD:
        if source_field not in SITE_DERIVED_FIELDS:
            raise ValueError("派生来源字段不支持")
        column = getattr(Site, source_field)
        rows = db.query(Site.id, Site.site_code, Site.site_name, column).order_by(Site.id.asc()).all()
        for site_id, site_code, site_name, raw_value in rows:
            values = set()
            normalized = _normalize_source_value(raw_value)
            if normalized:
                values.add(normalized)
            grouped[int(site_id)] = {
                "site_id": int(site_id),
                "site_code": site_code,
                "site_name": site_name,
                "values": values,
            }
        return grouped

    if source_type == SOURCE_TYPE_LLD_CELL_FIELD:
        if source_field not in LLD_CELL_DERIVED_FIELDS:
            raise ValueError("派生来源字段不支持")
        column = getattr(SitePlanningCell, source_field)
        site_rows = db.query(Site.id, Site.site_code, Site.site_name).order_by(Site.id.asc()).all()
        for site_id, site_code, site_name in site_rows:
            grouped[int(site_id)] = {
                "site_id": int(site_id),
                "site_code": site_code,
                "site_name": site_name,
                "values": set(),
            }
        rows = (
            db.query(SitePlanningCell.site_id, column)
            .join(SitePlanning, SitePlanning.id == SitePlanningCell.planning_id)
            .filter(SitePlanning.is_current == True)
            .all()
        )
        for site_id, raw_value in rows:
            entry = grouped.get(int(site_id))
            if entry is None:
                continue
            normalized = _normalize_source_value(raw_value)
            if normalized:
                entry["values"].add(normalized)
        return grouped

    raise ValueError("派生来源类型不支持")


def _find_option_for_rule(
    options: Iterable[SiteGroupOption],
    rule: Dict[str, object],
) -> Optional[SiteGroupOption]:
    option_id = rule.get("option_id")
    try:
        option_id_int = int(option_id) if option_id is not None else None
    except (TypeError, ValueError):
        option_id_int = None
    option_code = _normalize_match_value(rule.get("option_code"))
    option_name = _normalize_match_value(rule.get("option_name"))
    for option in options:
        if not getattr(option, "is_active", True):
            continue
        if option_id_int and option.id == option_id_int:
            return option
        if option_code and _normalize_match_value(option.code) == option_code:
            return option
        if option_name and _normalize_match_value(option.name) == option_name:
            return option
    return None


def _matches_rule(value: str, rule: Dict[str, object]) -> bool:
    candidate = _normalize_match_value(value)
    if not candidate:
        return False
    match_type = str(rule.get("match") or "contains").strip()
    for keyword in list(rule.get("keywords") or []):
        needle = _normalize_match_value(keyword)
        if not needle:
            continue
        if match_type == "exact" and candidate == needle:
            return True
        if match_type != "exact" and needle in candidate:
            return True
    return False


def _active_option_maps(category: SiteGroupCategory) -> Tuple[Dict[int, SiteGroupOption], Dict[str, SiteGroupOption]]:
    by_id: Dict[int, SiteGroupOption] = {}
    by_name_or_code: Dict[str, SiteGroupOption] = {}
    for option in list(category.options or []):
        if not getattr(option, "is_active", True):
            continue
        by_id[int(option.id)] = option
        for key in (option.name, option.code):
            normalized = _normalize_match_value(key)
            if normalized:
                by_name_or_code[normalized] = option
    return by_id, by_name_or_code


def _prioritized_group_plan_samples(rows: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return sorted(
        list(rows),
        key=lambda row: (
            GROUP_SYNC_ACTION_PRIORITY.get(str(row.get("action") or ""), 99),
            str(row.get("site_code") or ""),
            int(row.get("site_id") or 0),
        ),
    )[:GROUP_SYNC_SAMPLE_LIMIT]


def build_derived_group_sync_plan(
    db: Session,
    category: SiteGroupCategory,
    *,
    overwrite: bool,
    create_missing_options: Optional[bool] = None,
    assignment_mode: Optional[str] = None,
    source_type: Optional[str] = None,
    source_field: Optional[str] = None,
    source_config: object = None,
) -> Dict[str, object]:
    mode = normalize_assignment_mode(
        assignment_mode if assignment_mode is not None else getattr(category, "assignment_mode", None)
    )
    if mode != ASSIGNMENT_MODE_DERIVED:
        raise ValueError("当前维度不是字段派生维度")

    source_type = str(
        source_type if source_type is not None else getattr(category, "source_type", None) or ""
    ).strip()
    source_field = str(
        source_field if source_field is not None else getattr(category, "source_field", None) or ""
    ).strip()
    raw_source_config = (
        source_config
        if source_config is not None
        else getattr(category, "source_config", None)
    )
    config = normalize_source_config(raw_source_config)
    _, source_type, source_field, config = validate_group_source_settings(
        assignment_mode=mode,
        source_type=source_type,
        source_field=source_field,
        source_config=config,
    )
    strategy = str(config.get("strategy") or "field_value").strip()
    should_create_missing = (
        bool(create_missing_options)
        if create_missing_options is not None
        else bool(config.get("create_missing_options", strategy == "field_value"))
    )

    category_options = list(category.options or [])
    _, option_by_name_or_code = _active_option_maps(category)
    source_rows = _collect_derived_source_values(
        db,
        source_type=source_type,
        source_field=source_field,
    )
    existing_assignments = {
        int(row.site_id): row
        for row in (
            db.query(SiteGroupAssignment)
            .filter(SiteGroupAssignment.category_id == category.id)
            .all()
        )
    }

    normalized_rules = []
    warnings: List[str] = []
    for raw_rule in list(config.get("rules") or []):
        if not isinstance(raw_rule, dict):
            continue
        option = _find_option_for_rule(category_options, raw_rule)
        if option is None:
            label = raw_rule.get("option_name") or raw_rule.get("option_code") or raw_rule.get("option_id")
            warnings.append(f"规则目标选项不存在或已停用：{label}")
            continue
        normalized_rules.append({"option": option, "rule": raw_rule})

    plan_rows: List[Dict[str, object]] = []
    by_option: Dict[str, int] = {}
    requested_count = 0
    suggested_count = 0
    assigned_count = 0
    unchanged_count = 0
    conflict_count = 0
    skipped_count = 0
    planned_create_option_names = set()

    for site_id in sorted(source_rows.keys()):
        row = source_rows[site_id]
        values = sorted(str(item) for item in (row.get("values") or set()) if str(item or "").strip())
        requested_count += 1

        target_options: Dict[int, SiteGroupOption] = {}
        target_new_names = set()
        reasons: List[str] = []

        if not values:
            reasons.append("来源字段为空")
        else:
            for value in values:
                matched_options: Dict[int, SiteGroupOption] = {}
                if normalized_rules:
                    for rule_item in normalized_rules:
                        if _matches_rule(value, rule_item["rule"]):
                            option = rule_item["option"]
                            matched_options[int(option.id)] = option

                if matched_options:
                    target_options.update(matched_options)
                    continue

                if strategy == "field_value":
                    existing_option = option_by_name_or_code.get(_normalize_match_value(value))
                    if existing_option is not None:
                        target_options[int(existing_option.id)] = existing_option
                    elif should_create_missing:
                        target_new_names.add(value)
                    else:
                        reasons.append(f"没有匹配选项：{value}")
                elif not normalized_rules:
                    reasons.append("未配置匹配规则")
                else:
                    reasons.append(f"没有匹配规则：{value}")

        option_id: Optional[int] = None
        option_name: Optional[str] = None
        create_option_name: Optional[str] = None
        action = "skipped"
        existing = existing_assignments.get(site_id)

        if len(target_options) + len(target_new_names) > 1:
            action = "conflict"
            reasons.append("同一站点匹配到多个分组选项")
        elif target_options:
            option = next(iter(target_options.values()))
            option_id = int(option.id)
            option_name = str(option.name or "")
            suggested_count += 1
        elif target_new_names:
            create_option_name = next(iter(target_new_names))
            option_name = create_option_name
            suggested_count += 1

        if option_name:
            by_option[option_name] = by_option.get(option_name, 0) + 1

        if action != "conflict" and option_name:
            if existing is not None and option_id is not None and int(existing.option_id) == option_id:
                action = "unchanged"
            elif existing is not None and not overwrite:
                action = "conflict"
                reasons.append("站点已有分组，未启用覆盖")
            elif existing is not None:
                action = "overwrite"
            else:
                action = "assign"

        if action in {"assign", "overwrite"}:
            assigned_count += 1
            if create_option_name:
                planned_create_option_names.add(_normalize_match_value(create_option_name))
        elif action == "unchanged":
            unchanged_count += 1
        elif action == "conflict":
            conflict_count += 1
        else:
            skipped_count += 1

        plan_rows.append(
            {
                "site_id": int(site_id),
                "site_code": row.get("site_code"),
                "site_name": row.get("site_name"),
                "source_values": values,
                "option_id": option_id,
                "option_name": option_name,
                "create_option_name": create_option_name,
                "action": action,
                "reason": "；".join(reasons),
                "existing_option_id": int(existing.option_id) if existing else None,
            }
        )

    return {
        "category": category,
        "source_type": source_type,
        "source_field": source_field,
        "requested_count": requested_count,
        "suggested_count": suggested_count,
        "assigned_count": assigned_count,
        "unchanged_count": unchanged_count,
        "conflict_count": conflict_count,
        "skipped_count": skipped_count,
        "by_option": by_option,
        "warnings": warnings,
        "plan": plan_rows,
        "samples": _prioritized_group_plan_samples(plan_rows),
        "create_missing_options": should_create_missing,
        "created_option_count": len(planned_create_option_names),
    }


def apply_derived_group_sync_plan(
    db: Session,
    plan: Dict[str, object],
    *,
    operator_id: Optional[int],
) -> Dict[str, object]:
    category: SiteGroupCategory = plan["category"]
    option_by_name_or_code = _active_option_maps(category)[1]
    created_option_count = 0
    assigned_count = 0
    unchanged_count = 0
    conflict_count = 0
    skipped_count = 0

    for row in list(plan.get("plan") or []):
        action = row.get("action")
        if action == "unchanged":
            unchanged_count += 1
            continue
        if action == "conflict":
            conflict_count += 1
            continue
        if action not in {"assign", "overwrite"}:
            skipped_count += 1
            continue

        option_id = row.get("option_id")
        create_option_name = str(row.get("create_option_name") or "").strip()
        if option_id is None and create_option_name:
            normalized = _normalize_match_value(create_option_name)
            option = option_by_name_or_code.get(normalized)
            if option is None:
                option = SiteGroupOption(
                    category_id=category.id,
                    code=make_group_code(create_option_name, "option"),
                    name=create_option_name,
                    is_active=True,
                    sort_order=(len(option_by_name_or_code) + 1) * 10,
                )
                db.add(option)
                db.flush()
                created_option_count += 1
                option_by_name_or_code[normalized] = option
                if _normalize_match_value(option.code):
                    option_by_name_or_code[_normalize_match_value(option.code)] = option
            option_id = option.id

        if option_id is None:
            skipped_count += 1
            continue

        upsert_site_group_assignment(
            db,
            site_id=int(row["site_id"]),
            category_id=category.id,
            option_id=int(option_id),
            operator_id=operator_id,
            source=FIELD_DERIVED_SOURCE,
        )
        assigned_count += 1

    return {
        **plan,
        "assigned_count": assigned_count,
        "unchanged_count": unchanged_count,
        "conflict_count": conflict_count,
        "skipped_count": skipped_count,
        "created_option_count": created_option_count,
    }


def upsert_site_group_assignment(
    db: Session,
    *,
    site_id: int,
    category_id: int,
    option_id: Optional[int],
    operator_id: Optional[int],
    source: str = "manual",
) -> Tuple[str, Optional[SiteGroupAssignment]]:
    assignment = (
        db.query(SiteGroupAssignment)
        .filter(
            SiteGroupAssignment.site_id == site_id,
            SiteGroupAssignment.category_id == category_id,
        )
        .first()
    )

    if option_id is None:
        if assignment is None:
            return "noop", None
        db.delete(assignment)
        return "cleared", None

    option = (
        db.query(SiteGroupOption)
        .filter(
            SiteGroupOption.id == option_id,
            SiteGroupOption.category_id == category_id,
            SiteGroupOption.is_active == True,
        )
        .first()
    )
    if option is None:
        raise ValueError("分组选项不存在或不属于该维度")

    if assignment is None:
        assignment = SiteGroupAssignment(
            site_id=site_id,
            category_id=category_id,
            option_id=option_id,
            source=source,
            updated_by=operator_id,
        )
        db.add(assignment)
        return "created", assignment

    if assignment.option_id == option_id and assignment.source == source:
        return "noop", assignment

    assignment.option_id = option_id
    assignment.source = source
    assignment.updated_by = operator_id
    return "updated", assignment


def ensure_delivery_scope_category(
    db: Session,
    *,
    operator_id: Optional[int],
) -> Tuple[SiteGroupCategory, Dict[str, SiteGroupOption]]:
    category = (
        db.query(SiteGroupCategory)
        .options(joinedload(SiteGroupCategory.options))
        .filter(SiteGroupCategory.code == DELIVERY_SCOPE_CATEGORY_CODE)
        .first()
    )
    if category is None:
        existing_default = db.query(SiteGroupCategory.id).filter(SiteGroupCategory.is_default == True).first()
        category = SiteGroupCategory(
            code=DELIVERY_SCOPE_CATEGORY_CODE,
            name=DELIVERY_SCOPE_CATEGORY_NAME,
            description="用于按业务交付范围查看站点安装进度，例如 Savanna 的 TDD/FDD 分批交付。",
            is_active=True,
            is_default=existing_default is None,
            sort_order=0,
            assignment_mode=ASSIGNMENT_MODE_DERIVED,
            source_type=SOURCE_TYPE_LLD_CELL_FIELD,
            source_field="duplex_mode",
            source_config=DELIVERY_SCOPE_SOURCE_CONFIG,
            created_by=operator_id,
        )
        db.add(category)
        db.flush()
    elif not getattr(category, "source_type", None) and category.code == DELIVERY_SCOPE_CATEGORY_CODE:
        category.assignment_mode = ASSIGNMENT_MODE_DERIVED
        category.source_type = SOURCE_TYPE_LLD_CELL_FIELD
        category.source_field = "duplex_mode"
        category.source_config = DELIVERY_SCOPE_SOURCE_CONFIG

    option_map: Dict[str, SiteGroupOption] = {
        str(option.name or "").strip().upper(): option
        for option in list(category.options or [])
    }
    defaults = [
        ("TDD", "#2563eb", 10),
        ("FDD", "#16a34a", 20),
    ]
    for name, color, sort_order in defaults:
        if name in option_map:
            continue
        option = SiteGroupOption(
            category_id=category.id,
            code=name.lower(),
            name=name,
            color=color,
            is_active=True,
            sort_order=sort_order,
        )
        db.add(option)
        db.flush()
        option_map[name] = option

    db.refresh(category)
    return category, option_map


def classify_current_lld_duplex_by_site(db: Session) -> Dict[int, Dict[str, object]]:
    rows = (
        db.query(
            SitePlanningCell.site_id,
            func.upper(func.trim(func.coalesce(SitePlanningCell.duplex_mode, ""))).label("duplex_mode"),
        )
        .join(SitePlanning, SitePlanning.id == SitePlanningCell.planning_id)
        .filter(SitePlanning.is_current == True)
        .all()
    )

    grouped: Dict[int, Dict[str, object]] = {}
    for site_id, duplex_mode in rows:
        entry = grouped.setdefault(site_id, {"has_tdd": False, "has_fdd": False, "values": set()})
        value = str(duplex_mode or "").strip().upper()
        if value:
            entry["values"].add(value)
        if "TDD" in value:
            entry["has_tdd"] = True
        if "FDD" in value:
            entry["has_fdd"] = True
    return grouped


def build_delivery_scope_seed_plan(
    db: Session,
    *,
    overwrite: bool,
) -> Dict[str, object]:
    sites = db.query(Site.id, Site.site_code, Site.site_name).order_by(Site.id.asc()).all()
    site_duplex = classify_current_lld_duplex_by_site(db)
    category = (
        db.query(SiteGroupCategory)
        .filter(SiteGroupCategory.code == DELIVERY_SCOPE_CATEGORY_CODE)
        .first()
    )
    existing: Dict[int, SiteGroupAssignment] = {}
    if category is not None:
        existing = {
            row.site_id: row
            for row in db.query(SiteGroupAssignment)
            .filter(SiteGroupAssignment.category_id == category.id)
            .all()
        }

    warnings: List[str] = []
    by_option = {"TDD": 0, "FDD": 0}
    suggested_count = 0
    assigned_count = 0
    unchanged_count = 0
    conflict_count = 0
    skipped_count = 0
    plan: List[Dict[str, object]] = []

    for site_id, site_code, site_name in sites:
        info = site_duplex.get(site_id)
        target_name: Optional[str] = None
        reason = ""
        if not info:
            reason = "当前 LLD 没有小区明细"
        elif info.get("has_tdd") and info.get("has_fdd"):
            reason = "当前 LLD 同时包含 TDD/FDD，需要人工确认交付范围"
        elif info.get("has_tdd"):
            target_name = "TDD"
        elif info.get("has_fdd"):
            target_name = "FDD"
        else:
            values = sorted(str(v) for v in info.get("values", set()))
            reason = f"未识别 Duplex Mode: {', '.join(values) if values else '空'}"

        current_assignment = existing.get(site_id)
        if target_name is None:
            skipped_count += 1
            if len(warnings) < 20:
                warnings.append(f"{site_code}: {reason}")
            action = "skipped"
        else:
            suggested_count += 1
            by_option[target_name] += 1
            if current_assignment is not None:
                current_option_name = current_assignment.option.name if current_assignment.option else ""
                if current_option_name == target_name:
                    unchanged_count += 1
                    action = "unchanged"
                elif not overwrite:
                    conflict_count += 1
                    action = "conflict"
                    if len(warnings) < 20:
                        warnings.append(f"{site_code}: 已有分组 {current_option_name}，建议为 {target_name}")
                else:
                    assigned_count += 1
                    action = "overwrite"
            else:
                assigned_count += 1
                action = "assign"

        row = {
            "site_id": site_id,
            "site_code": site_code,
            "site_name": site_name,
            "target": target_name,
            "action": action,
            "reason": reason,
        }
        plan.append(row)

    return {
        "category": category,
        "plan": plan,
        "requested_count": len(sites),
        "suggested_count": suggested_count,
        "assigned_count": assigned_count,
        "unchanged_count": unchanged_count,
        "conflict_count": conflict_count,
        "skipped_count": skipped_count,
        "by_option": by_option,
        "warnings": warnings,
        "samples": _prioritized_group_plan_samples(plan),
    }
