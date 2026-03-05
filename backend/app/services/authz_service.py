from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy.orm import Session, joinedload

from app.core.permissions import (
    BUILTIN_PERMISSION_DEFINITIONS,
    BUILTIN_ROLE_DEFINITIONS,
    BUILTIN_ROLE_PERMISSION_TEMPLATE,
    permission_matches,
)
from app.models.authz import Permission, Role, RolePermission, UserRole
from app.models.user import User


def ensure_builtin_roles_and_permissions(db: Session) -> None:
    role_by_code: Dict[str, Role] = {r.code: r for r in db.query(Role).all()}
    perm_by_code: Dict[str, Permission] = {p.code: p for p in db.query(Permission).all()}

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
        else:
            perm.name = item.get("name") or perm.name
            perm.module = item.get("module") or perm.module
            perm.description = item.get("description")
            if perm.is_active is False:
                perm.is_active = True

    db.flush()

    # 内置角色权限模板：仅在该角色尚未有授权时灌入，避免覆盖人工配置
    for role_code, perms in BUILTIN_ROLE_PERMISSION_TEMPLATE.items():
        role = role_by_code.get(role_code)
        if not role:
            continue
        existing_count = (
            db.query(RolePermission.id)
            .filter(RolePermission.role_id == role.id)
            .count()
        )
        if existing_count > 0:
            continue
        for perm_code in perms:
            perm = perm_by_code.get(perm_code)
            if not perm:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))

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
            .joinedload(RolePermission.permission)
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
