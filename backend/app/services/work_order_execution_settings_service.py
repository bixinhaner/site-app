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
WEB_LOGIN_PERMISSION_CODE = 'auth:web-login'
WEB_ADMIN_CLIENT = 'web-admin'

WORK_ORDER_EXECUTION_CAPABILITY_ENABLED = 'enabled'
WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD = 'allow_photo_upload'
WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING = 'allow_device_binding'
WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT = 'allow_submit'
WORK_ORDER_EXECUTION_CAPABILITY_RECALL = 'allow_recall'
WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO = 'allow_local_upload_without_geo'
WORK_ORDER_EXECUTION_LOCAL_UPLOAD_WITHOUT_GEO_POLICY_KEY = 'local_upload_without_geo_policy'
WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY = 'visible_work_order_types'
WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY = 'editable_work_order_types'

LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY = 'deny'
LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK = 'allow_with_watermark'
LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK = 'allow_without_watermark'
LOCAL_UPLOAD_WITHOUT_GEO_POLICY_VALUES = (
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK,
    LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK,
)

WEB_WORK_ORDER_ACCESS_HIDDEN = 'hidden'
WEB_WORK_ORDER_ACCESS_READONLY = 'readonly'
WEB_WORK_ORDER_ACCESS_EDITABLE = 'editable'

_BOOL_RULE_KEYS = (
    WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
    WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
    WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING,
    WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT,
    WORK_ORDER_EXECUTION_CAPABILITY_RECALL,
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


def _try_parse_local_upload_without_geo_policy(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return (
            LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK
            if value
            else LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
        )
    raw = getattr(value, 'value', value)
    text = str(raw or '').strip().lower()
    if text in LOCAL_UPLOAD_WITHOUT_GEO_POLICY_VALUES:
        return text
    return None


def normalize_local_upload_without_geo_policy(
    value: Any,
    *,
    default: str = LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
) -> str:
    parsed = _try_parse_local_upload_without_geo_policy(value)
    if parsed:
        return parsed
    return default


def is_local_upload_without_geo_allowed(policy: Any) -> bool:
    normalized = normalize_local_upload_without_geo_policy(policy)
    return normalized != LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY


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


def _normalize_bool_rule(raw_rule: Any, *, default: bool, allow_overrides: bool = True) -> Dict[str, Any]:
    rule = raw_rule if isinstance(raw_rule, dict) else {}
    per_role: Dict[str, bool] = {}
    if allow_overrides:
        for role_code, value in (rule.get('per_role') or {}).items():
            key = _normalize_role_key(role_code)
            if not key:
                continue
            per_role[key] = bool(value)

    per_user: Dict[str, bool] = {}
    if allow_overrides:
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


def _normalize_local_upload_without_geo_policy_rule(
    raw_rule: Any,
    *,
    default: str,
    allow_overrides: bool = True,
) -> Dict[str, Any]:
    rule = raw_rule if isinstance(raw_rule, dict) else {}

    per_role: Dict[str, str] = {}
    if allow_overrides:
        for role_code, value in (rule.get('per_role') or {}).items():
            key = _normalize_role_key(role_code)
            policy = _try_parse_local_upload_without_geo_policy(value)
            if not key or not policy:
                continue
            per_role[key] = policy

    per_user: Dict[str, str] = {}
    if allow_overrides:
        for user_id, value in (rule.get('per_user') or {}).items():
            key = _normalize_user_key(user_id)
            policy = _try_parse_local_upload_without_geo_policy(value)
            if not key or not policy:
                continue
            per_user[key] = policy

    default_policy = normalize_local_upload_without_geo_policy(
        rule.get('default'),
        default=default,
    )
    return {
        'default': default_policy,
        'per_role': per_role,
        'per_user': per_user,
    }


def _bool_rule_to_local_upload_without_geo_policy_rule(bool_rule: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        'default': LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
        'per_role': {},
        'per_user': {},
    }
    out['default'] = (
        LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK
        if bool(bool_rule.get('default'))
        else LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
    )
    out['per_role'] = {
        key: (
            LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK
            if bool(value)
            else LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
        )
        for key, value in (bool_rule.get('per_role') or {}).items()
        if _normalize_role_key(key)
    }
    out['per_user'] = {
        key: (
            LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK
            if bool(value)
            else LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY
        )
        for key, value in (bool_rule.get('per_user') or {}).items()
        if _normalize_user_key(key)
    }
    return out


def _local_upload_without_geo_policy_rule_to_bool_rule(policy_rule: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'default': is_local_upload_without_geo_allowed(policy_rule.get('default')),
        'per_role': {
            _normalize_role_key(key): is_local_upload_without_geo_allowed(value)
            for key, value in (policy_rule.get('per_role') or {}).items()
            if _normalize_role_key(key)
        },
        'per_user': {
            _normalize_user_key(key): is_local_upload_without_geo_allowed(value)
            for key, value in (policy_rule.get('per_user') or {}).items()
            if _normalize_user_key(key)
        },
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


def _intersect_type_lists(primary: Iterable[Any], secondary: Iterable[Any]) -> list[str]:
    secondary_set = set(normalize_work_order_type_list(secondary))
    return [item for item in normalize_work_order_type_list(primary) if item in secondary_set]


def _sanitize_editable_type_rule(
    visible_rule: Dict[str, Any],
    editable_rule: Dict[str, Any],
) -> Dict[str, Any]:
    default_visible = normalize_work_order_type_list(visible_rule.get('default') or [])
    visible_per_role = visible_rule.get('per_role') or {}
    visible_per_user = visible_rule.get('per_user') or {}

    sanitized_per_role: Dict[str, list[str]] = {}
    for role_code, value in (editable_rule.get('per_role') or {}).items():
        visible_scope = visible_per_role.get(role_code)
        sanitized_per_role[role_code] = _intersect_type_lists(
            value or [],
            visible_scope if visible_scope is not None else default_visible,
        )

    sanitized_per_user: Dict[str, list[str]] = {}
    for user_id, value in (editable_rule.get('per_user') or {}).items():
        # 用户覆盖页当前仅支持“跟随全局默认/用户显式可见类型”两种来源，
        # 因此这里按相同口径做后端兜底，避免保存出“可编辑不在可见里”的脏配置。
        visible_scope = visible_per_user.get(user_id)
        sanitized_per_user[user_id] = _intersect_type_lists(
            value or [],
            visible_scope if visible_scope is not None else default_visible,
        )

    return {
        'default': _intersect_type_lists(editable_rule.get('default') or [], default_visible),
        'per_role': sanitized_per_role,
        'per_user': sanitized_per_user,
    }


def sanitize_work_order_execution_settings(raw_settings: Any) -> Dict[str, Any]:
    raw = raw_settings if isinstance(raw_settings, dict) else {}
    defaults = build_default_work_order_execution_settings()
    sanitized = {'config_version': max(1, int(raw.get('config_version') or defaults['config_version']))}

    for key in _BOOL_RULE_KEYS:
        sanitized[key] = _normalize_bool_rule(
            raw.get(key),
            default=bool(defaults[key]['default']),
            allow_overrides=key != WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
        )

    default_policy = normalize_local_upload_without_geo_policy(
        (defaults.get(WORK_ORDER_EXECUTION_LOCAL_UPLOAD_WITHOUT_GEO_POLICY_KEY) or {}).get('default'),
        default=LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
    )
    policy_rule_raw = raw.get(WORK_ORDER_EXECUTION_LOCAL_UPLOAD_WITHOUT_GEO_POLICY_KEY)
    if policy_rule_raw is not None:
        policy_rule = _normalize_local_upload_without_geo_policy_rule(
            policy_rule_raw,
            default=default_policy,
            allow_overrides=True,
        )
    else:
        legacy_local_upload_rule = _normalize_bool_rule(
            raw.get(WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO),
            default=bool(
                (defaults.get(WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO) or {}).get('default', False)
            ),
            allow_overrides=True,
        )
        policy_rule = _bool_rule_to_local_upload_without_geo_policy_rule(legacy_local_upload_rule)

    sanitized[WORK_ORDER_EXECUTION_LOCAL_UPLOAD_WITHOUT_GEO_POLICY_KEY] = policy_rule
    sanitized[WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO] = (
        _local_upload_without_geo_policy_rule_to_bool_rule(policy_rule)
    )

    legacy_type_rule = raw.get('allowed_work_order_types')
    visible_rule_raw = raw.get(WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY)
    editable_rule_raw = raw.get(WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY)

    visible_rule = _normalize_type_rule(
        visible_rule_raw if visible_rule_raw is not None else legacy_type_rule
    )
    editable_rule = _normalize_type_rule(
        editable_rule_raw if editable_rule_raw is not None else (
            legacy_type_rule if legacy_type_rule is not None else visible_rule_raw
        )
    )
    sanitized[WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY] = visible_rule
    sanitized[WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY] = _sanitize_editable_type_rule(
        visible_rule,
        editable_rule,
    )
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


def _resolve_type_list_for_user(settings: Dict[str, Any], key: str, user: Optional[User]) -> list[str]:
    rule = settings.get(key) or {}
    override = _resolve_rule_override_for_user(rule, user)
    if override is not None:
        return normalize_work_order_type_list(override)
    return normalize_work_order_type_list(rule.get('default') or SUPPORTED_WEB_EXECUTION_WORK_ORDER_TYPES)


def _resolve_local_upload_without_geo_policy_for_user(
    settings: Dict[str, Any],
    user: Optional[User],
) -> str:
    rule = settings.get(WORK_ORDER_EXECUTION_LOCAL_UPLOAD_WITHOUT_GEO_POLICY_KEY) or {}
    override = _resolve_rule_override_for_user(rule, user)
    if override is not None:
        return normalize_local_upload_without_geo_policy(override)
    return normalize_local_upload_without_geo_policy(rule.get('default'))


def get_effective_work_order_execution_settings(db: Session, user: Optional[User]) -> Dict[str, Any]:
    settings = load_work_order_execution_settings(db)
    local_upload_without_geo_policy = _resolve_local_upload_without_geo_policy_for_user(settings, user)
    visible_work_order_types = _resolve_type_list_for_user(
        settings,
        WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY,
        user,
    )
    editable_work_order_types = _intersect_type_lists(
        _resolve_type_list_for_user(settings, WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY, user),
        visible_work_order_types,
    )
    return {
        'enabled': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_ENABLED, user),
        'allow_photo_upload': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD, user),
        'allow_device_binding': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING, user),
        'allow_submit': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT, user),
        'allow_recall': _resolve_bool_for_user(settings, WORK_ORDER_EXECUTION_CAPABILITY_RECALL, user),
        'local_upload_without_geo_policy': local_upload_without_geo_policy,
        'allow_local_upload_without_geo': is_local_upload_without_geo_allowed(local_upload_without_geo_policy),
        'visible_work_order_types': visible_work_order_types,
        'editable_work_order_types': editable_work_order_types,
    }


def resolve_web_work_order_access_mode(
    db: Session,
    user: Optional[User],
    *,
    work_order_type: Any = None,
) -> str:
    if user is None:
        return WEB_WORK_ORDER_ACCESS_HIDDEN
    if not user_has_permission(user, WEB_LOGIN_PERMISSION_CODE):
        return WEB_WORK_ORDER_ACCESS_HIDDEN
    if not user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE):
        return WEB_WORK_ORDER_ACCESS_HIDDEN

    effective = get_effective_work_order_execution_settings(db, user)
    if not bool(effective.get('enabled')):
        return WEB_WORK_ORDER_ACCESS_HIDDEN

    normalized_type = _normalize_work_order_type(work_order_type)
    visible_types = set(effective.get(WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY) or [])
    editable_types = set(effective.get(WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY) or [])

    if normalized_type:
        if normalized_type not in visible_types:
            return WEB_WORK_ORDER_ACCESS_HIDDEN
        if normalized_type in editable_types:
            return WEB_WORK_ORDER_ACCESS_EDITABLE
        return WEB_WORK_ORDER_ACCESS_READONLY

    if editable_types:
        return WEB_WORK_ORDER_ACCESS_EDITABLE
    if visible_types:
        return WEB_WORK_ORDER_ACCESS_READONLY
    return WEB_WORK_ORDER_ACCESS_HIDDEN


def get_work_order_execution_access_summary(db: Session, user: Optional[User]) -> Dict[str, Any]:
    effective = get_effective_work_order_execution_settings(db, user)
    settings = load_work_order_execution_settings(db)
    global_enabled = bool(
        (settings.get(WORK_ORDER_EXECUTION_CAPABILITY_ENABLED) or {}).get('default', False)
    )
    has_web_login_permission = bool(user and user_has_permission(user, WEB_LOGIN_PERMISSION_CODE))
    has_execute_permission = bool(user and user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE))
    is_user_active = bool(user and getattr(user, 'is_active', True))
    has_any_visible_type = bool(effective.get(WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY))
    has_any_editable_type = bool(effective.get(WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY))
    can_open_entry = bool(
        is_user_active
        and has_web_login_permission
        and has_execute_permission
        and global_enabled
        and has_any_visible_type
    )

    reasons: list[str] = []
    if not is_user_active:
        reasons.append('用户已被禁用，无法登录 Web 管理端执行工单')
    if not has_web_login_permission:
        reasons.append('当前角色未授予 Web 登录权限（auth:web-login）')
    if not has_execute_permission:
        reasons.append('当前角色未授予 Web 工单执行权限（workorder:execute:web）')
    if not global_enabled:
        reasons.append('Web 工单执行总开关已关闭，角色和用户覆盖不会生效')
    if global_enabled and not has_any_visible_type:
        reasons.append('当前没有放开任何可在 Web 端查看的工单类型')
    if global_enabled and has_any_visible_type and not has_any_editable_type:
        reasons.append('当前只放开了 Web 只读查看，填写和提交仍需在 App 处理')

    return {
        'can_open_entry': can_open_entry,
        'is_user_active': is_user_active,
        'has_web_login_permission': has_web_login_permission,
        'has_execute_permission': has_execute_permission,
        'global_enabled': global_enabled,
        'allow_photo_upload': bool(effective.get('allow_photo_upload')),
        'allow_device_binding': bool(effective.get('allow_device_binding')),
        'allow_submit': bool(effective.get('allow_submit')),
        'allow_recall': bool(effective.get('allow_recall')),
        'local_upload_without_geo_policy': normalize_local_upload_without_geo_policy(
            effective.get('local_upload_without_geo_policy'),
        ),
        'allow_local_upload_without_geo': bool(effective.get('allow_local_upload_without_geo')),
        'visible_work_order_types': normalize_work_order_type_list(
            effective.get(WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY) or []
        ),
        'editable_work_order_types': normalize_work_order_type_list(
            effective.get(WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY) or []
        ),
        'has_any_visible_type': has_any_visible_type,
        'has_any_editable_type': has_any_editable_type,
        'reasons': reasons,
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
    require_editable_type: Optional[bool] = None,
) -> bool:
    if user is None:
        return False
    if not bool(getattr(user, 'is_active', True)):
        return False
    if not user_has_permission(user, WEB_LOGIN_PERMISSION_CODE):
        return False
    if not user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE):
        return False

    effective = get_effective_work_order_execution_settings(db, user)
    if not bool(effective.get('enabled')):
        return False

    if require_editable_type is None:
        require_editable_type = capability != WORK_ORDER_EXECUTION_CAPABILITY_ENABLED

    normalized_type = _normalize_work_order_type(work_order_type)
    allowed_type_key = (
        WORK_ORDER_EXECUTION_EDITABLE_TYPES_KEY
        if require_editable_type
        else WORK_ORDER_EXECUTION_VISIBLE_TYPES_KEY
    )
    allowed_types = normalize_work_order_type_list(effective.get(allowed_type_key) or [])
    if normalized_type:
        if normalized_type not in set(allowed_types):
            return False
    elif not allowed_types:
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
    require_editable_type: Optional[bool] = None,
    detail: Optional[str] = None,
) -> None:
    if not is_web_admin_request(request):
        return

    if user is None or not bool(getattr(user, 'is_active', True)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='当前用户状态不允许在 Web 端执行工单',
        )

    if not user_has_permission(user, WEB_LOGIN_PERMISSION_CODE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='当前用户没有 Web 登录权限',
        )

    if not user_has_permission(user, WORK_ORDER_WEB_EXECUTION_PERMISSION_CODE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='当前用户没有 Web 工单执行权限',
        )

    if not can_use_web_work_order_execution(
        db,
        user,
        work_order_type=work_order_type,
        capability=capability,
        require_editable_type=require_editable_type,
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
