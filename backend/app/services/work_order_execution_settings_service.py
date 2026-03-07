from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.system_config import SystemConfig
from app.models.user import User
from app.schemas.work_order_execution_settings import (
    SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES,
    WorkOrderExecutionSettingsPayload,
    WorkOrderExecutionSettingsUpdatePayload,
)
from app.services.authz_service import user_has_permission


WORK_ORDER_EXECUTION_SETTINGS_KEY = 'workorder_execution_settings'
WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE = 'workorder:execute:web'
WEB_ADMIN_CLIENT = 'web-admin'

WORK_ORDER_EXECUTION_CAPABILITY_ENABLED = 'enabled'
WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD = 'allow_photo_upload'
WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING = 'allow_device_binding'
WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT = 'allow_submit'
WORK_ORDER_EXECUTION_CAPABILITY_RECALL = 'allow_recall'
WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO = 'allow_local_upload_without_geo'

_BOOL_RULE_KEYS = (
    WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
    WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
    WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING,
    WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT,
    WORK_ORDER_EXECUTION_CAPABILITY_RECALL,
    WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO,
)


def _supported_type_set() -> set[str]:
    return set(SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES)


def _normalize_role_key(value: Any) -> str:
    return str(value or '').strip()


def _normalize_user_key(value: Any) -> str:
    return str(value or '').strip()


def _normalize_work_order_type(value: Any) -> str:
    raw = getattr(value, 'value', value)
    text = str(raw or '').strip()
    return text


def normalize_work_order_type_list(values: Iterable[Any]) -> list[str]:
    supported = _supported_type_set()
    normalized: list[str] = []
    for value in values or []:
        item = _normalize_work_order_type(value)
        if not item or item not in supported or item in normalized:
            continue
        normalized.append(item)
    return normalized


def build_default_work_order_execution_settings() -> Dict[str, Any]:
    defaults = WorkOrderExecutionSettingsPayload()
    return defaults.model_dump()


def _normalize_bool_rule(raw_rule: Any, *, default: bool) -> Dict[str, Any]:
    rule = raw_rule if isinstance(raw_rule, dict) else {}
    per_role: Dict[str, bool] = {}
    for role_code, value in (rule.get('per_role') or {}).items():
        key = _normalize_role_key(role_code)
        if not key:
            continue
        per_role[key] = bool(value)

    per_user: Dict[str, bool] = {}
    for user_id, value in (rule.get('per_user') or {}).items():
        key = _normalize_user_key(user_id)
        if not key:
            continue
        per_user[key] = bool(value)

    return {
        'default': bool(rule.get('default', default)),
        'per_role': per_role,
        'per_user': per_user,
    }


def _normalize_type_rule(raw_rule: Any) -> Dict[str, Any]:
    rule = raw_rule if isinstance(raw_rule, dict) else {}
    per_role: Dict[str, list[str]] = {}
    for role_code, value in (rule.get('per_role') or {}).items():
        key = _normalize_role_key(role_code)
        if not key:
            continue
        per_role[key] = normalize_work_order_type_list(value or [])

    per_user: Dict[str, list[str]] = {}
    for user_id, value in (rule.get('per_user') or {}).items():
        key = _normalize_user_key(user_id)
        if not key:
            continue
        per_user[key] = normalize_work_order_type_list(value or [])

    default_list = normalize_work_order_type_list(
        rule.get('default') or SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES,
    )
    if not default_list:
        default_list = list(SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES)

    return {
        'default': default_list,
        'per_role': per_role,
        'per_user': per_user,
    }


def sanitize_work_order_execution_settings(raw_settings: Any) -> Dict[str, Any]:
    raw = raw_settings if isinstance(raw_settings, dict) else {}
    defaults = build_default_work_order_execution_settings()
    sanitized = {'config_version': max(1, int(raw.get('config_version') or defaults['config_version']))}

    for key in _BOOL_RULE_KEYS:
        sanitized[key] = _normalize_bool_rule(
            raw.get(key),
            default=bool(defaults[key]['default']),
        )

    sanitized['allowed_work_order_types'] = _normalize_type_rule(raw.get('allowed_work_order_types'))
    return sanitized


def get_work_order_execution_settings_version(settings: Dict[str, Any]) -> int:
    try:
        return max(1, int((settings or {}).get('config_version') or 1))
    except Exception:
        return 1


def load_work_order_execution_settings(db: Session) -> Dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_EXECUTION_SETTINGS_KEY).first()
    if not row or not row.value:
        return build_default_work_order_execution_settings()
    return sanitize_work_order_execution_settings(row.value)


def save_work_order_execution_settings(db: Session, settings: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = sanitize_work_order_execution_settings(settings)
    row = db.query(SystemConfig).filter(SystemConfig.key == WORK_ORDER_EXECUTION_SETTINGS_KEY).first()
    if not row:
        row = SystemConfig(key=WORK_ORDER_EXECUTION_SETTINGS_KEY, value=sanitized)
        db.add(row)
    else:
        row.value = sanitized
        flag_modified(row, 'value')
    db.commit()
    return sanitized


def build_work_order_execution_settings_from_payload(
    payload: WorkOrderExecutionSettingsUpdatePayload,
    *,
    version_after: int,
) -> Dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    data['config_version'] = max(1, int(version_after))
    return sanitize_work_order_execution_settings(data)


def _resolve_rule_override_for_user(rule: Dict[str, Any], user: Optional[User]) -> Any:
    if user is None:
        return None

    per_user = rule.get('per_user') or {}
    user_key = _normalize_user_key(getattr(user, 'id', None))
    if user_key and user_key in per_user:
        return per_user[user_key]

    per_role = rule.get('per_role') or {}
    for role_code in getattr(user, 'role_codes', []) or []:
        key = _normalize_role_key(role_code)
        if key and key in per_role:
            return per_role[key]

    return None


def _resolve_bool_for_user(settings: Dict[str, Any], key: str, user: Optional[User]) -> bool:
    rule = settings.get(key) or {}
    override = _resolve_rule_override_for_user(rule, user)
    if override is not None:
        return bool(override)
    return bool(rule.get('default', False))


def _resolve_type_list_for_user(settings: Dict[str, Any], user: Optional[User]) -> list[str]:
    rule = settings.get('allowed_work_order_types') or {}
    override = _resolve_rule_override_for_user(rule, user)
    if override is not None:
        return normalize_work_order_type_list(override)
    return normalize_work_order_type_list(rule.get('default') or SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES)


def get_effective_work_order_execution_settings(db: Session, user: Optional[User]) -> Dict[str, Any]:
    settings = load_work_order_execution_settings(db)
    return {
        'enabled': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_ENABLED, user),
        'allow_photo_upload': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD, user),
        'allow_device_binding': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING, user),
        'allow_submit': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT, user),
        'allow_recall': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_RECALL, user),
        'allow_local_upload_without_geo': _resolve_bool_for_user(
            settings,
            WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO,
            user,
        ),
        'allowed_work_order_types': _resolve_type_list_for_user(settings, user),
    }


def is_web_admin_request(request: Optional[Request]) -> bool:
    client = str((getattr(request, 'headers', {}) or {}).get('X-Client') or '').strip().lower()
    return client == WEB_ADMIN_CLIENT


def can_use_web_work_order_execution(
    db: Session,
    user: Optional[User],
    *,
    work_order_type: Any = None,
    capability: str = WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
) -> bool:
    if user is None:
        return False
    if not user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE):
        return False

    effective = get_effective_work_order_execution_settings(db, user)
    if not bool(effective.get('enabled')):
        return False

    normalized_type = _normalize_work_order_type(work_order_type)
    if normalized_type and normalized_type not in set(effective.get('allowed_work_order_types') or []):
        return False

    if capability == WORK_ORDER_EXECUTION_CAPABILITY_ENABLED:
        return True
    return bool(effective.get(capability))


def ensure_web_work_order_execution_allowed(
    request: Optional[Request],
    db: Session,
    user: Optional[User],
    *,
    work_order_type: Any = None,
    capability: str = WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
    detail: Optional[str] = None,
) -> None:
    if not is_web_admin_request(request):
        return

    if user is None or not user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='当前用户没有 Web 工单执行权限',
        )

    if not can_use_web_work_order_execution(
        db,
        user,
        work_order_type=work_order_type,
        capability=capability,
    ):
        if detail:
            message = detail
        elif capability == WORK_ORDER_EXECUTION_CAPABILITY_ENABLED:
            message = '当前未启用 Web 工单填写'
        else:
            message = f'当前未启用 Web 工单执行能力：{capability}'
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message,
        )
