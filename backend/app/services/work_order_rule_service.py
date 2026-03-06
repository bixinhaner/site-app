from typing import Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.system_config import SystemConfig


WORK_ORDER_RULES_KEY = "work_order_rules"
SSV_CREATE_BY_EVER_ACTIVATED_ONLY_KEY = "ssv_create_by_ever_activated_only"

DEFAULT_WORK_ORDER_RULES = {
    SSV_CREATE_BY_EVER_ACTIVATED_ONLY_KEY: False,
}


def load_work_order_rules(db: Session) -> Dict[str, bool]:
    rules = dict(DEFAULT_WORK_ORDER_RULES)
    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_RULES_KEY).first()
    if not row or not isinstance(row.value, dict):
        return rules

    data = row.value or {}
    for key, default_value in DEFAULT_WORK_ORDER_RULES.items():
        rules[key] = bool(data.get(key, default_value))
    return rules


def upsert_work_order_rules(db: Session, rules_patch: Dict[str, bool]) -> Dict[str, bool]:
    rules = load_work_order_rules(db)
    for key in DEFAULT_WORK_ORDER_RULES:
        if key in rules_patch:
            rules[key] = bool(rules_patch[key])

    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_RULES_KEY).first()
    if not row:
        row = SystemConfig(key=WORK_ORDER_RULES_KEY, value=rules)
        db.add(row)
    else:
        row.value = rules
        flag_modified(row, "value")

    return rules


def get_ssv_create_by_ever_activated_only(db: Session) -> bool:
    rules = load_work_order_rules(db)
    return bool(rules.get(SSV_CREATE_BY_EVER_ACTIVATED_ONLY_KEY, False))
