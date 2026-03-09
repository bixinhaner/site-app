from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy.orm import Session, joinedload

from app.core.data_scopes import BUILTIN_ROLE_DATA_SCOPE_TEMPLATE
from app.core.permissions import (
    BUILTIN_PERMISSION_DEFINITIONS,
    BUILTIN_ROLE_DEFINITIONS,
    LEGACY_BUILTIN_ROLE_APP_PERMISSION_VARIANTS,
    LEGACY_BUILTIN_ROLE_PERMISSION_VARIANTS,
    TERMINAL_LOGIN_PERMISSION_CODES,
    BUILTIN_ROLE_PERMISSION_TEMPLATE,
    permission_matches,
)
from app.models.authz import Permission, Role, RoleDataScope, RolePermission, UserRole
from app.models.user import User
from app.services.data_scope_service import get_user_effective_data_scopes

LEGACY_DISABLED_PERMISSION_CODES = {
    "system:workorder-execution-settings:read",
    "system:workorder-execution-settings:write",
}


def ensure_builtin_roles_and_permissions(db: Session) -> None:
    role_by_code: Dict[str, Role] = {r.code: r for r in db.query(Role).all()}
    perm_by_code: Dict[str, Permission] = {p.code: p for p in db.query(Permission).all()}
    newly_created_permission_codes: Set[str] = set()

    for item in BUILTIN_ROLE_DEFINITIONS:
        code = str(item["code"]).strip()
        role = role_by_code.get(code)
        if role is None:
            role = Role(
                code=code,
                name=item.get("name") or code,
                description=item.get("description"),
                is_system=bool(item.get("is_system", False)),
                is_active=True,
            )
            db.add(role)
            db.flush()
            role_by_code[code] = role
        else:
            role.name = item.get("name") or role.name
            role.description = item.get("description")
            role.is_system = bool(item.get("is_system", role.is_system))
            if role.is_active is False:
                role.is_active = True

    for item in BUILTIN_PERMISSION_DEFINITIONS:
        code = str(item["code"]).strip()
        perm = perm_by_code.get(code)
        if perm is None:
            perm = Permission(
                code=code,
                name=item.get("name") or code,
                module=item.get("module") or "general",
                description=item.get("description"),
                is_active=True,
            )
            db.add(perm)
            db.flush()
            perm_by_code[code] = perm
            newly_created_permission_codes.add(code)
        else:
            perm.name = item.get("name") or perm.name
            perm.module = item.get("module") or perm.module
            perm.description = item.get("description")
            if perm.is_active is False:
                perm.is_active = True

    for code in LEGACY_DISABLED_PERMISSION_CODES:
        perm = perm_by_code.get(code)
        if perm is not None:
            perm.is_active = False

    db.flush()

    perm_code_by_id: Dict[int, str] = {
        perm.id: str(perm.code).strip()
        for perm in perm_by_code.values()
        if perm.id is not None and str(perm.code or "").strip()
    }
    existing_role_permission_pairs: Set[tuple[int, int]] = set()
    role_permission_codes: Dict[int, Set[str]] = defaultdict(set)
    for role_id, permission_id in (
        db.query(RolePermission.role_id, RolePermission.permission_id).all()
    ):
        key = (int(role_id), int(permission_id))
        existing_role_permission_pairs.add(key)
        code = perm_code_by_id.get(int(permission_id))
        if code:
            role_permission_codes[int(role_id)].add(code)
    initial_role_permission_codes: Dict[int, Set[str]] = {
        int(role_id): set(codes)
        for role_id, codes in role_permission_codes.items()
    }

    def grant_permission(role_id: int, perm_id: int) -> None:
        key = (int(role_id), int(perm_id))
        if key in existing_role_permission_pairs:
            return
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))
        existing_role_permission_pairs.add(key)
        code = perm_code_by_id.get(int(perm_id))
        if code:
            role_permission_codes[int(role_id)].add(code)

    def revoke_permission(role_id: int, perm_id: int) -> None:
        key = (int(role_id), int(perm_id))
        if key not in existing_role_permission_pairs:
            return
        db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == perm_id,
        ).delete(synchronize_session=False)
        existing_role_permission_pairs.discard(key)
        code = perm_code_by_id.get(int(perm_id))
        if code:
            role_permission_codes[int(role_id)].discard(code)

    # 内置角色权限模板：仅在该角色尚未有授权时灌入，避免覆盖人工配置
    for role_code, perms in BUILTIN_ROLE_PERMISSION_TEMPLATE.items():
        role = role_by_code.get(role_code)
        if not role:
            continue
        existing_count = len(role_permission_codes.get(role.id, set()))
        if existing_count > 0:
            continue
        for perm_code in perms:
            perm = perm_by_code.get(perm_code)
            if not perm:
                continue
            grant_permission(role.id, perm.id)

    # App 权限是后补接入的。这里仅修复两类场景：
    # 1) 老库中内置角色还没有任何 app:* 授权；
    # 2) 已命中过往已发布过的内置角色 app 模板（含错误模板/中间模板），
    #    需要按当前默认边界纠正，但不覆盖人工自定义授权。
    for role_code, desired_codes in BUILTIN_ROLE_PERMISSION_TEMPLATE.items():
        role = role_by_code.get(role_code)
        if not role:
            continue
        desired_codes_set = {
            str(code).strip()
            for code in desired_codes or []
            if str(code).strip() and str(code).strip() in perm_by_code
        }
        desired_app_codes = {code for code in desired_codes_set if code.startswith("app:")}
        if not desired_app_codes:
            continue

        existing_codes = set(role_permission_codes.get(role.id, set()))
        existing_app_codes = {code for code in existing_codes if code.startswith("app:")}
        legacy_app_code_variants = [
            {
                str(code).strip()
                for code in codes or []
                if str(code).strip()
            }
            for codes in LEGACY_BUILTIN_ROLE_APP_PERMISSION_VARIANTS.get(role_code, [])
        ]

        should_repair = not existing_app_codes or any(
            variant and existing_app_codes == variant
            for variant in legacy_app_code_variants
        )
        if not should_repair:
            continue

        stale_app_codes = existing_app_codes - desired_app_codes
        if stale_app_codes:
            for code in stale_app_codes:
                perm = perm_by_code.get(code)
                if not perm:
                    continue
                revoke_permission(role.id, perm.id)
            existing_codes = set(role_permission_codes.get(role.id, set()))

        for perm_code in sorted(desired_codes_set - existing_codes):
            perm = perm_by_code.get(perm_code)
            if not perm:
                continue
            grant_permission(role.id, perm.id)

    # 终端登录权限是后补接入的。
    # 仅在该权限码第一次出现在当前库中时，为内置角色补齐默认授权，
    # 避免后续管理员手工移除后被每次启动强行恢复。
    new_terminal_login_codes = TERMINAL_LOGIN_PERMISSION_CODES & newly_created_permission_codes
    if new_terminal_login_codes:
        for role_code, desired_codes in BUILTIN_ROLE_PERMISSION_TEMPLATE.items():
            role = role_by_code.get(role_code)
            if not role:
                continue
            desired_terminal_codes = {
                str(code).strip()
                for code in desired_codes or []
                if str(code).strip() in new_terminal_login_codes
            }
            for perm_code in sorted(desired_terminal_codes):
                perm = perm_by_code.get(perm_code)
                if not perm:
                    continue
                grant_permission(role.id, perm.id)

    # 内置角色历史模板修复：仅当数据库中的系统角色权限集合完全命中已知旧模板时，
    # 才自动修正为当前模板，避免覆盖人工调整过的系统角色。
    for role_code, desired_codes in BUILTIN_ROLE_PERMISSION_TEMPLATE.items():
        role = role_by_code.get(role_code)
        if not role or not bool(getattr(role, "is_system", False)):
            continue

        legacy_variants = [
            {
                str(code).strip()
                for code in variant or []
                if str(code).strip()
            }
            for variant in LEGACY_BUILTIN_ROLE_PERMISSION_VARIANTS.get(role_code, [])
        ]
        if not legacy_variants:
            continue

        initial_codes = set(initial_role_permission_codes.get(int(role.id), set()))
        if not any(variant and initial_codes == variant for variant in legacy_variants):
            continue

        desired_codes_set = {
            str(code).strip()
            for code in desired_codes or []
            if str(code).strip() and str(code).strip() in perm_by_code
        }
        current_codes = set(role_permission_codes.get(int(role.id), set()))

        stale_codes = current_codes - desired_codes_set
        for code in sorted(stale_codes):
            perm = perm_by_code.get(code)
            if not perm:
                continue
            revoke_permission(role.id, perm.id)

        current_codes = set(role_permission_codes.get(int(role.id), set()))
        missing_codes = desired_codes_set - current_codes
        for code in sorted(missing_codes):
            perm = perm_by_code.get(code)
            if not perm:
                continue
            grant_permission(role.id, perm.id)

    role_scope_map: Dict[tuple[int, str], str] = {
        (int(row.role_id), str(row.resource_code).strip()): str(row.scope_code).strip()
        for row in db.query(RoleDataScope.role_id, RoleDataScope.resource_code, RoleDataScope.scope_code).all()
        if row.role_id is not None and str(row.resource_code or "").strip() and str(row.scope_code or "").strip()
    }
    for role_code, desired_scopes in BUILTIN_ROLE_DATA_SCOPE_TEMPLATE.items():
        role = role_by_code.get(role_code)
        if not role:
            continue
        for resource_code, scope_code in desired_scopes.items():
            key = (int(role.id), str(resource_code).strip())
            if key in role_scope_map:
                continue
            db.add(
                RoleDataScope(
                    role_id=role.id,
                    resource_code=str(resource_code).strip(),
                    scope_code=str(scope_code).strip(),
                )
            )
            role_scope_map[key] = str(scope_code).strip()

    db.commit()


def normalize_role_codes(codes: Sequence[str]) -> List[str]:
    vals = []
    for c in codes or []:
        x = str(c or "").strip()
        if not x:
            continue
        vals.append(x)
    return sorted(set(vals))


def get_user_with_authz(db: Session, username: str) -> Optional[User]:
    return (
        db.query(User)
        .options(
            joinedload(User.role_links)
            .joinedload(UserRole.role)
            .joinedload(Role.permission_links)
            .joinedload(RolePermission.permission),
            joinedload(User.role_links)
            .joinedload(UserRole.role)
            .joinedload(Role.data_scope_links),
        )
        .filter(User.username == username)
        .first()
    )


def get_user_role_codes(user: User) -> List[str]:
    if not user:
        return []
    if hasattr(user, "role_codes"):
        return list(getattr(user, "role_codes") or [])
    return []


def get_user_permission_codes(user: User) -> List[str]:
    if not user:
        return []
    role_links = getattr(user, "role_links", None) or []
    out: Set[str] = set()
    for link in role_links:
        role = getattr(link, "role", None)
        if not role or getattr(role, "is_active", True) is False:
            continue
        if str(getattr(role, "code", "")).strip() == "admin":
            out.add("*")
            continue
        for rp in getattr(role, "permission_links", None) or []:
            perm = getattr(rp, "permission", None)
            if not perm or getattr(perm, "is_active", True) is False:
                continue
            code = str(getattr(perm, "code", "") or "").strip()
            if code:
                out.add(code)
    return sorted(out)


def get_user_data_scopes(user: User) -> Dict[str, str]:
    return get_user_effective_data_scopes(user)


def user_has_permission(user: User, permission_code: str) -> bool:
    if not user:
        return False
    role_codes = set(get_user_role_codes(user))
    if "admin" in role_codes:
        return True
    permission_codes = getattr(user, "permission_codes", None)
    if permission_codes is None:
        permission_codes = get_user_permission_codes(user)
        try:
            setattr(user, "permission_codes", permission_codes)
        except Exception:
            pass
    return permission_matches(permission_code, permission_codes)


def user_has_any_permission(user: User, permission_codes: Iterable[str]) -> bool:
    for code in permission_codes or []:
        if user_has_permission(user, str(code or "").strip()):
            return True
    return False


def user_has_role(user: User, role_code: str) -> bool:
    if not user:
        return False
    return str(role_code or "").strip() in set(get_user_role_codes(user))


def user_has_any_role(user: User, role_codes: Iterable[str]) -> bool:
    for code in role_codes or []:
        if user_has_role(user, str(code or "").strip()):
            return True
    return False


def user_has_any_role_or_permission(
    user: User,
    *,
    role_codes: Optional[Iterable[str]] = None,
    permission_codes: Optional[Iterable[str]] = None,
) -> bool:
    if not user:
        return False
    if user_has_any_role(user, role_codes or []):
        return True
    return user_has_any_permission(user, permission_codes or [])


def list_permission_modules(db: Session) -> Dict[str, List[Permission]]:
    rows = db.query(Permission).order_by(Permission.module.asc(), Permission.code.asc()).all()
    out: Dict[str, List[Permission]] = defaultdict(list)
    for row in rows:
        out[str(row.module or "general")].append(row)
    return dict(out)


def set_user_roles_by_codes(db: Session, user: User, role_codes: Sequence[str]) -> List[str]:
    role_codes = normalize_role_codes(role_codes)
    roles = db.query(Role).filter(Role.code.in_(role_codes), Role.is_active == True).all()
    role_map = {r.code: r for r in roles}

    missing = [c for c in role_codes if c not in role_map]
    if missing:
        raise ValueError(f"角色不存在或已停用: {', '.join(missing)}")

    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.flush()
    for code in role_codes:
        role = role_map[code]
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return role_codes


def set_role_permissions_by_codes(db: Session, role: Role, permission_codes: Sequence[str]) -> List[str]:
    permission_codes = sorted(set(str(c or "").strip() for c in (permission_codes or []) if str(c or "").strip()))
    perms = db.query(Permission).filter(Permission.code.in_(permission_codes), Permission.is_active == True).all()
    perm_map = {p.code: p for p in perms}
    missing = [c for c in permission_codes if c not in perm_map]
    if missing:
        raise ValueError(f"权限不存在或已停用: {', '.join(missing)}")

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    db.flush()
    for code in permission_codes:
        perm = perm_map[code]
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.commit()
    db.refresh(role)
    return permission_codes
