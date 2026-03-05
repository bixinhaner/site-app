from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.auth import get_current_user
from app.core.authz import require_permission
from app.core.database import get_db
from app.models.authz import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.schemas.authz import (
    EffectivePermissionsResponse,
    PermissionResponse,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    SetRolePermissionsRequest,
    SetUserRolesRequest,
)
from app.services.authz_service import (
    get_user_permission_codes,
    get_user_role_codes,
    list_permission_modules,
    set_role_permissions_by_codes,
    set_user_roles_by_codes,
)

router = APIRouter()


def _role_permissions(role: Role) -> List[str]:
    values: List[str] = []
    for rp in getattr(role, 'permission_links', None) or []:
        perm = getattr(rp, 'permission', None)
        if not perm or getattr(perm, 'is_active', True) is False:
            continue
        code = str(getattr(perm, 'code', '') or '').strip()
        if code:
            values.append(code)
    return sorted(set(values))


def _role_to_response(role: Role) -> RoleResponse:
    payload = RoleResponse.from_orm(role)
    payload.permissions = _role_permissions(role)
    return payload


def _build_permission_modules(codes: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    for code in sorted(set(codes or [])):
        module = str(code).split(':', 1)[0] if ':' in str(code) else 'general'
        out[module].append(code)
    return dict(out)


@router.get('/permissions', response_model=List[PermissionResponse])
async def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    rows = db.query(Permission).order_by(Permission.module.asc(), Permission.code.asc()).all()
    return [PermissionResponse.from_orm(x) for x in rows]


@router.get('/permissions/modules')
async def list_permissions_by_module(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    grouped = list_permission_modules(db)
    return {
        module: [PermissionResponse.from_orm(x) for x in rows]
        for module, rows in grouped.items()
    }


@router.get('/roles', response_model=List[RoleResponse])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    rows = (
        db.query(Role)
        .options(joinedload(Role.permission_links).joinedload(RolePermission.permission))
        .order_by(Role.is_system.desc(), Role.code.asc())
        .all()
    )
    return [_role_to_response(x) for x in rows]


@router.post('/roles', response_model=RoleResponse)
async def create_role(
    payload: RoleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    code = str(payload.code or '').strip()
    if not code:
        raise HTTPException(status_code=400, detail='角色编码不能为空')

    existed = db.query(Role).filter(Role.code == code).first()
    if existed:
        raise HTTPException(status_code=400, detail='角色编码已存在')

    role = Role(
        code=code,
        name=str(payload.name or '').strip() or code,
        description=payload.description,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    if payload.permissions:
        try:
            set_role_permissions_by_codes(db, role, payload.permissions)
        except ValueError as exc:
            db.delete(role)
            db.commit()
            raise HTTPException(status_code=400, detail=str(exc))

    role = (
        db.query(Role)
        .options(joinedload(Role.permission_links).joinedload(RolePermission.permission))
        .filter(Role.id == role.id)
        .first()
    )
    return _role_to_response(role)


@router.put('/roles/{role_id}', response_model=RoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail='角色不存在')

    if payload.name is not None:
        role.name = str(payload.name or '').strip() or role.name
    if payload.description is not None:
        role.description = payload.description
    if payload.is_active is not None:
        if role.code == 'admin' and payload.is_active is False:
            raise HTTPException(status_code=400, detail='admin 角色不可停用')
        role.is_active = payload.is_active

    db.commit()
    db.refresh(role)

    if payload.permissions is not None:
        try:
            set_role_permissions_by_codes(db, role, payload.permissions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    role = (
        db.query(Role)
        .options(joinedload(Role.permission_links).joinedload(RolePermission.permission))
        .filter(Role.id == role.id)
        .first()
    )
    return _role_to_response(role)


@router.put('/roles/{role_id}/permissions', response_model=RoleResponse)
async def set_role_permissions(
    role_id: int,
    payload: SetRolePermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail='角色不存在')

    try:
        set_role_permissions_by_codes(db, role, payload.permissions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    role = (
        db.query(Role)
        .options(joinedload(Role.permission_links).joinedload(RolePermission.permission))
        .filter(Role.id == role.id)
        .first()
    )
    return _role_to_response(role)


@router.delete('/roles/{role_id}')
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail='角色不存在')

    if role.is_system:
        raise HTTPException(status_code=400, detail='系统内置角色不可删除')

    assigned_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()
    if assigned_count > 0:
        raise HTTPException(status_code=400, detail='角色仍被用户使用，不能删除')

    db.delete(role)
    db.commit()
    return {'message': '角色删除成功'}


@router.get('/users/{user_id}/roles')
async def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')

    return {
        'user_id': user.id,
        'username': user.username,
        'roles': get_user_role_codes(user),
    }


@router.put('/users/{user_id}/roles', response_model=EffectivePermissionsResponse)
async def set_user_roles(
    user_id: int,
    payload: SetUserRolesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')

    role_codes = sorted(set([str(code).strip() for code in (payload.roles or []) if str(code).strip()]))
    if not role_codes:
        raise HTTPException(status_code=400, detail='用户至少需要一个角色')

    if user.username == 'admin' and 'admin' not in role_codes:
        raise HTTPException(status_code=400, detail='admin 账号必须保留 admin 角色')

    try:
        set_user_roles_by_codes(db, user, role_codes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.refresh(user)
    permissions = get_user_permission_codes(user)
    return EffectivePermissionsResponse(
        user_id=user.id,
        username=user.username,
        roles=get_user_role_codes(user),
        permissions=permissions,
        permission_modules=_build_permission_modules(permissions),
    )


@router.get('/users/{user_id}/effective-permissions', response_model=EffectivePermissionsResponse)
async def get_effective_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission('authz:manage:all')),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')

    permissions = get_user_permission_codes(user)
    return EffectivePermissionsResponse(
        user_id=user.id,
        username=user.username,
        roles=get_user_role_codes(user),
        permissions=permissions,
        permission_modules=_build_permission_modules(permissions),
    )


@router.get('/me/effective-permissions', response_model=EffectivePermissionsResponse)
async def get_my_effective_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')

    permissions = get_user_permission_codes(user)
    return EffectivePermissionsResponse(
        user_id=user.id,
        username=user.username,
        roles=get_user_role_codes(user),
        permissions=permissions,
        permission_modules=_build_permission_modules(permissions),
    )
