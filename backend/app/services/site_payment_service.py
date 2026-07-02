from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.inspection import InspectionCheckItem
from app.models.site import Site
from app.models.site_group import SiteGroupAssignment, SiteGroupCategory, SiteGroupOption
from app.models.system_config import SystemConfig
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.subcontractor_assignment_service import (
    get_subcontractor_category as get_configured_subcontractor_category,
    load_work_order_assignment_settings,
)
from app.services.site_progress_metric_service import get_site_progress_metric_mode
from app.services.site_progress_service import get_site_progress_milestone_at, get_site_progress_snapshot

SITE_PAYMENT_SETTINGS_KEY = "site_payment_settings"
SUBCONTRACTOR_CATEGORY_CODES = {"subcontractor", "sub_contractor", "contractor"}
SUBCONTRACTOR_CATEGORY_NAMES = {"分包商", "subcontractor", "sub contractor", "contractor"}
SITE_PAYMENT_MILESTONE_OPTIONS = [
    "install_started",
    "install_completed",
    "online",
    "activated",
    "ssv",
    "customer_approved",
    "pac",
]
SITE_PAYMENT_CURRENCY_PRESET_OPTIONS = [
    "USD",
    "CNY",
    "EUR",
    "JPY",
    "IDR",
    "ZAR",
    "NGN",
    "EGP",
    "KES",
    "GHS",
    "TZS",
    "UGX",
    "XOF",
    "XAF",
    "ETB",
]

DEFAULT_SITE_PAYMENT_SETTINGS: Dict[str, Any] = {
    "config_version": 2,
    "currency": "USD",
    "profiles": [
        {
            "id": "default",
            "name": "默认付款方案",
            "scope_type": "default",
            "subcontractor_option_id": None,
            "enabled": True,
            "contract_amount_source": "site",
            "profile_contract_amount": None,
            "sort_order": 0,
            "remark": "",
        }
    ],
    "rules": [
        {
            "id": "install_started_ratio_30",
            "name": "开始安装 30%",
            "milestone_code": "install_started",
            "enabled": True,
            "amount_type": "ratio",
            "amount_value": 30,
            "requires_work_order_approved": False,
            "warning_discount_enabled": False,
            "warning_discount_ratio": 100,
            "sort_order": 10,
            "remark": "",
        },
        {
            "id": "install_completed_ratio_40",
            "name": "安装完成 40%",
            "milestone_code": "install_completed",
            "enabled": True,
            "amount_type": "ratio",
            "amount_value": 40,
            "requires_work_order_approved": True,
            "warning_discount_enabled": True,
            "warning_discount_ratio": 70,
            "sort_order": 20,
            "remark": "",
        },
        {
            "id": "customer_approved_ratio_20",
            "name": "客户审核 20%",
            "milestone_code": "customer_approved",
            "enabled": True,
            "amount_type": "ratio",
            "amount_value": 20,
            "requires_work_order_approved": False,
            "warning_discount_enabled": False,
            "warning_discount_ratio": 100,
            "sort_order": 30,
            "remark": "",
        },
        {
            "id": "pac_ratio_10",
            "name": "PAC 10%",
            "milestone_code": "pac",
            "enabled": True,
            "amount_type": "ratio",
            "amount_value": 10,
            "requires_work_order_approved": False,
            "warning_discount_enabled": False,
            "warning_discount_ratio": 100,
            "sort_order": 40,
            "remark": "",
        },
    ],
}

MILESTONE_LABEL_MAP = {
    "install_started": "开始安装",
    "install_completed": "安装完成",
    "online": "上线",
    "activated": "激活",
    "ssv": "SSV",
    "customer_approved": "客户审批通过",
    "pac": "PAC",
}


def normalize_site_payment_currency(value: Any) -> str:
    currency = str(value or DEFAULT_SITE_PAYMENT_SETTINGS["currency"]).strip().upper() or "USD"
    if len(currency) > 20:
        currency = currency[:20]
    return currency


def _clone_default_settings() -> Dict[str, Any]:
    rules = [dict(rule) for rule in DEFAULT_SITE_PAYMENT_SETTINGS["rules"]]
    profiles = [dict(profile) for profile in DEFAULT_SITE_PAYMENT_SETTINGS["profiles"]]
    profiles[0]["rules"] = [dict(rule) for rule in rules]
    return {
        "config_version": int(DEFAULT_SITE_PAYMENT_SETTINGS["config_version"]),
        "currency": str(DEFAULT_SITE_PAYMENT_SETTINGS["currency"]),
        "profiles": profiles,
        "rules": rules,
    }


def normalize_site_payment_rule(raw_rule: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    rule = raw_rule if isinstance(raw_rule, dict) else {}
    milestone_code = str(rule.get("milestone_code") or "").strip()
    if milestone_code not in SITE_PAYMENT_MILESTONE_OPTIONS:
        milestone_code = "install_started"

    amount_type = str(rule.get("amount_type") or "ratio").strip().lower()
    if amount_type not in {"ratio", "fixed"}:
        amount_type = "ratio"

    try:
        amount_value = float(rule.get("amount_value") or 0)
    except (TypeError, ValueError):
        amount_value = 0.0
    amount_value = max(amount_value, 0.0)

    try:
        warning_discount_ratio = float(rule.get("warning_discount_ratio") or 100)
    except (TypeError, ValueError):
        warning_discount_ratio = 100.0
    warning_discount_ratio = min(max(warning_discount_ratio, 0.0), 100.0)

    try:
        sort_order = int(rule.get("sort_order") or ((index + 1) * 10))
    except (TypeError, ValueError):
        sort_order = (index + 1) * 10

    rule_id = str(rule.get("id") or "").strip() or f"{milestone_code}_{index + 1}"
    name = str(rule.get("name") or "").strip() or MILESTONE_LABEL_MAP.get(milestone_code, milestone_code)

    return {
        "id": rule_id,
        "name": name,
        "milestone_code": milestone_code,
        "enabled": bool(rule.get("enabled", True)),
        "amount_type": amount_type,
        "amount_value": amount_value,
        "requires_work_order_approved": bool(rule.get("requires_work_order_approved", False)),
        "warning_discount_enabled": bool(rule.get("warning_discount_enabled", False)),
        "warning_discount_ratio": warning_discount_ratio,
        "sort_order": sort_order,
        "remark": str(rule.get("remark") or "").strip(),
    }


def _normalize_nullable_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_amount(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return max(amount, 0.0)


def normalize_site_payment_profile(
    raw_profile: Dict[str, Any],
    index: int = 0,
    *,
    default_rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    scope_type = str(profile.get("scope_type") or "default").strip().lower()
    if scope_type not in {"default", "subcontractor"}:
        scope_type = "default"
    if index == 0 and scope_type != "subcontractor":
        scope_type = "default"

    raw_rules = profile.get("rules")
    if isinstance(raw_rules, list):
        rules = [normalize_site_payment_rule(rule, rule_index) for rule_index, rule in enumerate(raw_rules)]
    elif default_rules is not None:
        rules = [normalize_site_payment_rule(rule, rule_index) for rule_index, rule in enumerate(default_rules)]
    else:
        rules = [
            normalize_site_payment_rule(rule, rule_index)
            for rule_index, rule in enumerate(_clone_default_settings()["rules"])
        ]

    try:
        sort_order = int(profile.get("sort_order") or (index * 10))
    except (TypeError, ValueError):
        sort_order = index * 10

    profile_id = str(profile.get("id") or "").strip()
    if not profile_id:
        profile_id = "default" if scope_type == "default" else f"subcontractor_{index + 1}"
    if scope_type == "default":
        profile_id = "default"

    contract_amount_source = str(profile.get("contract_amount_source") or "site").strip().lower()
    if contract_amount_source not in {"site", "profile_fixed"}:
        contract_amount_source = "site"

    name = str(profile.get("name") or "").strip()
    if not name:
        name = "默认付款方案" if scope_type == "default" else "分包商付款方案"

    return {
        "id": profile_id,
        "name": name,
        "scope_type": scope_type,
        "subcontractor_option_id": _normalize_nullable_int(profile.get("subcontractor_option_id")),
        "subcontractor_option_code": str(profile.get("subcontractor_option_code") or "").strip(),
        "subcontractor_option_name": str(profile.get("subcontractor_option_name") or "").strip(),
        "enabled": bool(profile.get("enabled", True)),
        "contract_amount_source": contract_amount_source,
        "profile_contract_amount": _normalize_optional_amount(profile.get("profile_contract_amount")),
        "sort_order": sort_order,
        "remark": str(profile.get("remark") or "").strip(),
        "rules": rules,
    }


def normalize_site_payment_settings(raw_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = raw_settings if isinstance(raw_settings, dict) else {}
    raw_rules = src.get("rules")
    normalized_rules = []
    if isinstance(raw_rules, list):
        for index, rule in enumerate(raw_rules):
            normalized_rules.append(normalize_site_payment_rule(rule, index))
    else:
        normalized_rules = [normalize_site_payment_rule(rule, index) for index, rule in enumerate(_clone_default_settings()["rules"])]

    try:
        config_version = int(src.get("config_version") or DEFAULT_SITE_PAYMENT_SETTINGS["config_version"])
    except (TypeError, ValueError):
        config_version = int(DEFAULT_SITE_PAYMENT_SETTINGS["config_version"])

    currency = normalize_site_payment_currency(src.get("currency"))

    normalized_rules.sort(key=lambda item: (int(item.get("sort_order") or 0), item.get("name") or ""))

    raw_profiles = src.get("profiles")
    normalized_profiles: List[Dict[str, Any]] = []
    if isinstance(raw_profiles, list) and raw_profiles:
        for index, profile in enumerate(raw_profiles):
            normalized_profiles.append(
                normalize_site_payment_profile(profile, index, default_rules=normalized_rules)
            )
    else:
        normalized_profiles.append(
            normalize_site_payment_profile(
                {
                    **_clone_default_settings()["profiles"][0],
                    "rules": normalized_rules,
                },
                0,
                default_rules=normalized_rules,
            )
        )

    has_default = any(profile["scope_type"] == "default" for profile in normalized_profiles)
    if not has_default:
        normalized_profiles.insert(
            0,
            normalize_site_payment_profile(
                {
                    **_clone_default_settings()["profiles"][0],
                    "rules": normalized_rules,
                },
                0,
                default_rules=normalized_rules,
            ),
        )

    normalized_profiles.sort(
        key=lambda item: (
            0 if item.get("scope_type") == "default" else 1,
            int(item.get("sort_order") or 0),
            item.get("name") or "",
        )
    )
    for index, profile in enumerate(normalized_profiles):
        if profile["scope_type"] == "default":
            profile["id"] = "default"
            profile["subcontractor_option_id"] = None
            profile["subcontractor_option_code"] = ""
            profile["subcontractor_option_name"] = ""
        profile["rules"].sort(key=lambda item: (int(item.get("sort_order") or 0), item.get("name") or ""))
    default_profile = next((profile for profile in normalized_profiles if profile["scope_type"] == "default"), None)
    if default_profile is not None:
        normalized_rules = [dict(rule) for rule in default_profile["rules"]]

    return {
        "config_version": max(config_version, 1),
        "currency": currency,
        "profiles": normalized_profiles,
        # 兼容旧前端/API 调用：顶层 rules 始终代表默认方案。
        "rules": normalized_rules,
    }


def load_site_payment_settings(db: Session) -> Dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_PAYMENT_SETTINGS_KEY).first()
    if not row or not isinstance(row.value, dict):
        return normalize_site_payment_settings(None)
    return normalize_site_payment_settings(row.value)


def save_site_payment_settings(db: Session, settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_site_payment_settings(settings)
    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_PAYMENT_SETTINGS_KEY).first()
    if row is None:
        row = SystemConfig(key=SITE_PAYMENT_SETTINGS_KEY, value=normalized)
        db.add(row)
    else:
        row.value = normalized
        flag_modified(row, "value")
    db.commit()
    return normalized


def get_site_payment_milestone_options() -> List[Dict[str, str]]:
    return [
        {"value": code, "label": MILESTONE_LABEL_MAP.get(code, code)}
        for code in SITE_PAYMENT_MILESTONE_OPTIONS
    ]


def get_site_payment_currency_options() -> List[Dict[str, str]]:
    return [
        {"value": code, "label": code}
        for code in SITE_PAYMENT_CURRENCY_PRESET_OPTIONS
    ]


def get_subcontractor_category(db: Session) -> Optional[SiteGroupCategory]:
    assignment_settings = load_work_order_assignment_settings(db)
    if assignment_settings.get("subcontractor_category_id"):
        return get_configured_subcontractor_category(db, assignment_settings)

    categories = (
        db.query(SiteGroupCategory)
        .filter(SiteGroupCategory.is_active == True)
        .order_by(SiteGroupCategory.sort_order.asc(), SiteGroupCategory.id.asc())
        .all()
    )
    for category in categories:
        code = str(category.code or "").strip().lower()
        if code in SUBCONTRACTOR_CATEGORY_CODES:
            return category
    for category in categories:
        name = str(category.name or "").strip().lower()
        if name in SUBCONTRACTOR_CATEGORY_NAMES:
            return category
    return None


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


def get_site_subcontractor_assignment(db: Session, site_id: int) -> Optional[SiteGroupAssignment]:
    category = get_subcontractor_category(db)
    if not category:
        return None
    return (
        db.query(SiteGroupAssignment)
        .join(SiteGroupOption, SiteGroupOption.id == SiteGroupAssignment.option_id)
        .filter(
            SiteGroupAssignment.site_id == site_id,
            SiteGroupAssignment.category_id == category.id,
            SiteGroupOption.is_active == True,
        )
        .first()
    )


def _serialize_subcontractor_assignment(assignment: Optional[SiteGroupAssignment]) -> Optional[Dict[str, Any]]:
    if not assignment or not assignment.option:
        return None
    option = assignment.option
    category = assignment.category
    return {
        "category_id": assignment.category_id,
        "category_code": category.code if category else "",
        "category_name": category.name if category else "",
        "option_id": option.id,
        "option_code": option.code,
        "option_name": option.name,
        "option_color": option.color,
    }


def _profile_matches_subcontractor(profile: Dict[str, Any], assignment: Optional[SiteGroupAssignment]) -> bool:
    if profile.get("scope_type") != "subcontractor" or not assignment or not assignment.option:
        return False
    option = assignment.option
    option_id = profile.get("subcontractor_option_id")
    if option_id is not None and int(option_id) == int(option.id):
        return True
    option_code = str(profile.get("subcontractor_option_code") or "").strip().lower()
    if option_code and option_code == str(option.code or "").strip().lower():
        return True
    option_name = str(profile.get("subcontractor_option_name") or "").strip().lower()
    if option_name and option_name == str(option.name or "").strip().lower():
        return True
    return False


def resolve_site_payment_profile(
    db: Session,
    site: Site,
    settings: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Any], Optional[SiteGroupAssignment]]:
    normalized = settings or load_site_payment_settings(db)
    profiles = list(normalized.get("profiles") or [])
    default_profile = next((profile for profile in profiles if profile.get("scope_type") == "default"), None)
    if default_profile is None:
        default_profile = normalize_site_payment_profile(
            {
                **_clone_default_settings()["profiles"][0],
                "rules": normalized.get("rules") or _clone_default_settings()["rules"],
            },
            0,
        )

    assignment = get_site_subcontractor_assignment(db, site.id)
    for profile in profiles:
        if not profile.get("enabled", True):
            continue
        if _profile_matches_subcontractor(profile, assignment):
            return profile, assignment
    return default_profile, assignment


def _resolve_primary_opening_work_order(db: Session, site_id: int) -> Optional[WorkOrder]:
    return (
        db.query(WorkOrder)
        .filter(
            WorkOrder.site_id == site_id,
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status != WorkOrderStatusEnum.VOIDED,
        )
        .order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
        .first()
    )


def _get_opening_warning_count(db: Session, work_order: Optional[WorkOrder]) -> int:
    if work_order is None or not work_order.inspection_id:
        return 0
    return int(
        db.query(InspectionCheckItem)
        .filter(
            InspectionCheckItem.inspection_id == work_order.inspection_id,
            InspectionCheckItem.is_active.is_(True),
            InspectionCheckItem.review_status == "warning",
        )
        .count()
        or 0
    )


def _get_amounts(
    *,
    contract_amount: Optional[float],
    amount_type: str,
    amount_value: float,
) -> tuple[Optional[float], Optional[str]]:
    if amount_type == "fixed":
        return round(amount_value, 2), None
    if contract_amount is None:
        return None, "站点合同金额未填写，无法计算比例金额"
    return round(contract_amount * amount_value / 100.0, 2), None


def _resolve_amount_base(site: Site, profile: Dict[str, Any]) -> tuple[Optional[float], str, str]:
    source = str(profile.get("contract_amount_source") or "site")
    if source == "profile_fixed":
        amount = profile.get("profile_contract_amount")
        if amount is None:
            return None, "profile_fixed", "分包商付款方案未填写站点单价，无法计算比例金额"
        return float(amount), "profile_fixed", ""
    if getattr(site, "contract_amount", None) is None:
        return None, "site", "站点合同金额未填写，无法计算比例金额"
    return float(site.contract_amount), "site", ""


def build_site_payment_records(db: Session, site: Site) -> Dict[str, Any]:
    settings = load_site_payment_settings(db)
    profile, subcontractor_assignment = resolve_site_payment_profile(db, site, settings)
    snapshot = get_site_progress_snapshot(db, site.id)
    metric_mode = get_site_progress_metric_mode(db)
    opening_work_order = _resolve_primary_opening_work_order(db, site.id)
    warning_count = _get_opening_warning_count(db, opening_work_order)
    opening_approved = bool(opening_work_order and opening_work_order.status == WorkOrderStatusEnum.APPROVED)

    items: List[Dict[str, Any]] = []
    amount_base, amount_base_source, amount_base_error = _resolve_amount_base(site, profile)

    for rule in profile["rules"]:
        milestone_code = rule["milestone_code"]
        milestone_at = None
        if snapshot is not None:
            milestone_at = get_site_progress_milestone_at(snapshot, milestone_code, metric_mode=metric_mode)
        milestone_reached = milestone_at is not None

        base_amount, amount_error = _get_amounts(
            contract_amount=amount_base,
            amount_type=rule["amount_type"],
            amount_value=float(rule["amount_value"]),
        )
        if rule["amount_type"] == "ratio" and amount_base_error:
            amount_error = amount_base_error

        adjusted_amount = base_amount
        warning_discount_applied = False
        if (
            base_amount is not None
            and rule["warning_discount_enabled"]
            and warning_count > 0
        ):
            adjusted_amount = round(base_amount * float(rule["warning_discount_ratio"]) / 100.0, 2)
            warning_discount_applied = True

        reasons: List[str] = []
        status = "disabled"
        if not rule["enabled"]:
            reasons.append("该规则已停用")
        elif not milestone_reached:
            status = "pending_milestone"
            reasons.append(f"{MILESTONE_LABEL_MAP.get(milestone_code, milestone_code)}尚未达成")
        elif rule["requires_work_order_approved"] and not opening_approved:
            status = "pending_work_order_approval"
            reasons.append("开站工单尚未最终审核通过")
        elif amount_error:
            status = "pending_amount_base"
            reasons.append(amount_error)
        else:
            status = "ready"
            reasons.append("已满足当前收款条件")

        if warning_discount_applied:
            reasons.append(
                f"工单审核存在警告，当前节点按 {float(rule['warning_discount_ratio']):.0f}% 计收"
            )
        elif rule["warning_discount_enabled"]:
            reasons.append("当前工单无 warning，不触发折减")

        if rule["remark"]:
            reasons.append(rule["remark"])

        items.append(
            {
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "milestone_code": milestone_code,
                "milestone_label": MILESTONE_LABEL_MAP.get(milestone_code, milestone_code),
                "enabled": rule["enabled"],
                "amount_type": rule["amount_type"],
                "amount_value": float(rule["amount_value"]),
                "base_amount": base_amount,
                "adjusted_amount": adjusted_amount,
                "currency": settings["currency"],
                "milestone_reached": milestone_reached,
                "milestone_at": milestone_at,
                "requires_work_order_approved": rule["requires_work_order_approved"],
                "opening_work_order_id": opening_work_order.id if opening_work_order else None,
                "opening_work_order_status": opening_work_order.status.value if opening_work_order else None,
                "warning_count": warning_count,
                "warning_discount_enabled": rule["warning_discount_enabled"],
                "warning_discount_ratio": float(rule["warning_discount_ratio"]),
                "warning_discount_applied": warning_discount_applied,
                "status": status,
                "reasons": reasons,
            }
        )

    return {
        "config_version": settings["config_version"],
        "currency": settings["currency"],
        "contract_amount": float(site.contract_amount) if getattr(site, "contract_amount", None) is not None else None,
        "amount_base": amount_base,
        "amount_base_source": amount_base_source,
        "payment_profile": {
            "id": profile.get("id"),
            "name": profile.get("name"),
            "scope_type": profile.get("scope_type"),
            "contract_amount_source": profile.get("contract_amount_source"),
            "profile_contract_amount": profile.get("profile_contract_amount"),
            "remark": profile.get("remark"),
        },
        "subcontractor": _serialize_subcontractor_assignment(subcontractor_assignment),
        "opening_work_order": {
            "id": opening_work_order.id if opening_work_order else None,
            "status": opening_work_order.status.value if opening_work_order else None,
            "warning_count": warning_count,
        },
        "items": items,
    }
