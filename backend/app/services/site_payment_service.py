from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.inspection import InspectionCheckItem
from app.models.site import Site
from app.models.system_config import SystemConfig
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum
from app.services.site_progress_metric_service import get_site_progress_metric_mode
from app.services.site_progress_service import get_site_progress_milestone_at, get_site_progress_snapshot

SITE_PAYMENT_SETTINGS_KEY = "site_payment_settings"
SITE_PAYMENT_MILESTONE_OPTIONS = [
    "install_started",
    "install_completed",
    "online",
    "activated",
    "ssv",
    "customer_approved",
    "pac",
]

DEFAULT_SITE_PAYMENT_SETTINGS: Dict[str, Any] = {
    "config_version": 1,
    "currency": "USD",
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


def _clone_default_settings() -> Dict[str, Any]:
    rules = [dict(rule) for rule in DEFAULT_SITE_PAYMENT_SETTINGS["rules"]]
    return {
        "config_version": int(DEFAULT_SITE_PAYMENT_SETTINGS["config_version"]),
        "currency": str(DEFAULT_SITE_PAYMENT_SETTINGS["currency"]),
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


def normalize_site_payment_settings(raw_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = raw_settings if isinstance(raw_settings, dict) else {}
    rules = src.get("rules")
    normalized_rules = []
    if isinstance(rules, list):
        for index, rule in enumerate(rules):
            normalized_rules.append(normalize_site_payment_rule(rule, index))
    else:
        normalized_rules = [normalize_site_payment_rule(rule, index) for index, rule in enumerate(_clone_default_settings()["rules"])]

    try:
        config_version = int(src.get("config_version") or DEFAULT_SITE_PAYMENT_SETTINGS["config_version"])
    except (TypeError, ValueError):
        config_version = int(DEFAULT_SITE_PAYMENT_SETTINGS["config_version"])

    currency = str(src.get("currency") or DEFAULT_SITE_PAYMENT_SETTINGS["currency"]).strip().upper() or "USD"

    normalized_rules.sort(key=lambda item: (int(item.get("sort_order") or 0), item.get("name") or ""))

    return {
        "config_version": max(config_version, 1),
        "currency": currency,
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


def build_site_payment_records(db: Session, site: Site) -> Dict[str, Any]:
    settings = load_site_payment_settings(db)
    snapshot = get_site_progress_snapshot(db, site.id)
    metric_mode = get_site_progress_metric_mode(db)
    opening_work_order = _resolve_primary_opening_work_order(db, site.id)
    warning_count = _get_opening_warning_count(db, opening_work_order)
    opening_approved = bool(opening_work_order and opening_work_order.status == WorkOrderStatusEnum.APPROVED)

    items: List[Dict[str, Any]] = []
    for rule in settings["rules"]:
        milestone_code = rule["milestone_code"]
        milestone_at = None
        if snapshot is not None:
            milestone_at = get_site_progress_milestone_at(snapshot, milestone_code, metric_mode=metric_mode)
        milestone_reached = milestone_at is not None

        base_amount, amount_error = _get_amounts(
            contract_amount=float(site.contract_amount) if getattr(site, "contract_amount", None) is not None else None,
            amount_type=rule["amount_type"],
            amount_value=float(rule["amount_value"]),
        )

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
        "opening_work_order": {
            "id": opening_work_order.id if opening_work_order else None,
            "status": opening_work_order.status.value if opening_work_order else None,
            "warning_count": warning_count,
        },
        "items": items,
    }
