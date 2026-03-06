from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.data_scopes import (
    BUILTIN_DATA_SCOPE_DEFINITIONS,
    BUILTIN_ROLE_DATA_SCOPE_TEMPLATE,
    build_builtin_role_data_scope_mapping,
    build_default_data_scope_mapping,
    list_data_scope_resources,
    normalize_data_scope_mapping,
)
from app.models.authz import Role, RoleDataScope
from app.models.user import ROLE_PRIORITY, User


_ROLE_PRIORITY_INDEX = {code: idx for idx, code in enumerate(ROLE_PRIORITY)}
_CUSTOM_ROLE_PRIORITY = _ROLE_PRIORITY_INDEX.get("user", 999) - 0.5


def list_data_scope_definitions() -> List[Dict[str, object]]:
    return [dict(item) for item in BUILTIN_DATA_SCOPE_DEFINITIONS]


def get_role_data_scopes(role: Optional[Role]) -> Dict[str, str]:
    if not role:
        return {}
    out: Dict[str, str] = {}
    for link in getattr(role, "data_scope_links", None) or []:
        resource_code = str(getattr(link, "resource_code", "") or "").strip()
        scope_code = str(getattr(link, "scope_code", "") or "").strip()
        if not resource_code or not scope_code:
            continue
        out[resource_code] = scope_code
    return out


def get_role_legacy_data_scopes(role_code: str) -> Dict[str, str]:
    code = str(role_code or "").strip()
    if code in BUILTIN_ROLE_DATA_SCOPE_TEMPLATE:
        return build_builtin_role_data_scope_mapping(code)
    return build_default_data_scope_mapping()


def get_role_effective_data_scopes(role: Optional[Role]) -> Dict[str, str]:
    if not role:
        return {}
    base = get_role_legacy_data_scopes(getattr(role, "code", None))
    base.update(get_role_data_scopes(role))
    return base


def get_user_effective_data_scopes(user: Optional[User]) -> Dict[str, str]:
    if not user:
        return {}

    role_map: Dict[str, Role] = {}
    for link in getattr(user, "role_links", None) or []:
        role = getattr(link, "role", None)
        if not role or getattr(role, "is_active", True) is False:
            continue
        code = str(getattr(role, "code", "") or "").strip()
        if code:
            role_map[code] = role

    sorted_role_codes = sorted(
        role_map.keys(),
        key=lambda code: (_ROLE_PRIORITY_INDEX.get(code, _CUSTOM_ROLE_PRIORITY), code),
    )

    resolved: Dict[str, str] = {}
    remaining_resources = set(list_data_scope_resources())
    for role_code in sorted_role_codes:
        role_scopes = get_role_effective_data_scopes(role_map.get(role_code))
        for resource in list(remaining_resources):
            scope_code = str(role_scopes.get(resource) or "").strip()
            if not scope_code:
                continue
            resolved[resource] = scope_code
            remaining_resources.discard(resource)
        if not remaining_resources:
            break

    if remaining_resources:
        fallback = build_default_data_scope_mapping()
        for resource in remaining_resources:
            scope_code = str(fallback.get(resource) or "").strip()
            if scope_code:
                resolved[resource] = scope_code
    return resolved


def get_user_data_scope(user: Optional[User], resource: str) -> Optional[str]:
    resource_code = str(resource or "").strip()
    if not resource_code:
        return None
    return str(get_user_effective_data_scopes(user).get(resource_code) or "").strip() or None


def user_has_data_scope(user: Optional[User], resource: str, scope_codes: Iterable[str]) -> bool:
    current_scope = get_user_data_scope(user, resource)
    if not current_scope:
        return False
    return current_scope in {
        str(scope_code or "").strip()
        for scope_code in (scope_codes or [])
        if str(scope_code or "").strip()
    }


def set_role_data_scopes_by_mapping(
    db: Session,
    role: Role,
    data_scopes: Dict[str, str],
) -> Dict[str, str]:
    normalized = normalize_data_scope_mapping(data_scopes)

    db.query(RoleDataScope).filter(RoleDataScope.role_id == role.id).delete()
    db.flush()
    for resource_code, scope_code in sorted(normalized.items()):
        db.add(
            RoleDataScope(
                role_id=role.id,
                resource_code=resource_code,
                scope_code=scope_code,
            )
        )
    db.commit()
    db.refresh(role)
    return normalized
