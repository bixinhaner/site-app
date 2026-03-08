from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import math

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.authz import Role, UserRole
from app.models.user import User
from app.schemas.user import (
    UserResponse, UserUpdate, UserCreate, UserListResponse,
    UserPasswordReset, UserBatchOperation
)
from app.api.auth import get_current_user
from app.services.authz_service import (
    get_user_data_scopes,
    get_user_permission_codes,
    set_user_roles_by_codes,
    user_has_any_role_or_permission,
    user_has_permission,
)
from app.services.warehouse_access_service import build_inventory_access_profile

router = APIRouter()


def _assert_access(
    current_user: User,
    *,
    role_codes: Optional[List[str]] = None,
    permission_codes: Optional[List[str]] = None,
    detail: str = 'Not enough permissions',
) -> None:
    if user_has_any_role_or_permission(
        current_user,
        role_codes=role_codes or [],
        permission_codes=permission_codes or [],
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def _with_authz_payload(db: Session, user: User) -> User:
    if not user:
        return user
    try:
        permissions = get_user_permission_codes(user)
        data_scopes = get_user_data_scopes(user)
        inventory_profile = build_inventory_access_profile(db, user)
        setattr(user, 'permissions', permissions)
        setattr(user, 'permission_codes', permissions)
        setattr(user, 'data_scopes', data_scopes)
        setattr(user, 'inventory_scope', str(inventory_profile.get('inventory_scope') or 'self'))
        setattr(user, 'managed_warehouse_ids', list(inventory_profile.get('managed_warehouse_ids') or []))
        setattr(user, 'managed_warehouse_count', int(inventory_profile.get('managed_warehouse_count') or 0))
        setattr(user, 'has_managed_warehouses', bool(inventory_profile.get('has_managed_warehouses')))
    except Exception:
        pass
    return user


def _resolve_role_codes(primary_role: Optional[str], roles: Optional[List[str]], default_role: str = 'user') -> List[str]:
    vals = sorted(set([str(x).strip() for x in (roles or []) if str(x).strip()]))
    if vals:
        return vals
    if primary_role and str(primary_role).strip():
        return [str(primary_role).strip()]
    return [default_role]


@router.get('/search', response_model=UserListResponse)
async def search_users(
    keyword: Optional[str] = Query(None, description='搜索关键词(用户名、姓名、邮箱)'),
    role: Optional[str] = Query(None, description='角色筛选'),
    department: Optional[str] = Query(None, description='部门筛选'),
    is_active: Optional[bool] = Query(None, description='状态筛选'),
    skip: int = Query(0, ge=0, description='跳过记录数'),
    limit: int = Query(50, ge=1, le=100, description='每页记录数'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin', 'manager', 'warehouse_manager'],
        permission_codes=['users:list:read'],
    )

    query = db.query(User)

    if keyword:
        query = query.filter(
            or_(
                User.username.contains(keyword),
                User.full_name.contains(keyword),
                User.email.contains(keyword)
            )
        )

    if role:
        query = (
            query
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.code == role)
            .distinct()
        )

    if department:
        query = query.filter(User.department.contains(department))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users = query.offset(skip).limit(limit).all()

    page = (skip // limit) + 1
    pages = math.ceil(total / limit) if total > 0 else 0

    return UserListResponse(
        users=[UserResponse.from_orm(_with_authz_payload(db, user)) for user in users],
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get('/', response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin', 'manager'],
        permission_codes=['users:list:read'],
    )

    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.from_orm(_with_authz_payload(db, user)) for user in users]


@router.post('/', response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin'],
        permission_codes=['users:create:write'],
        detail='Only admin can create users',
    )

    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Username already exists'
        )

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Email already exists'
        )

    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        phone=user_data.phone,
        department=user_data.department,
        position=user_data.position,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    role_codes = _resolve_role_codes(user_data.role, user_data.roles)
    try:
        set_user_roles_by_codes(db, db_user, role_codes)
    except ValueError as exc:
        db.delete(db_user)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    db.refresh(db_user)
    return UserResponse.from_orm(_with_authz_payload(db, db_user))


@router.get('/{user_id}', response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    can_view_any_user = user_has_any_role_or_permission(
        current_user,
        role_codes=['admin', 'manager'],
        permission_codes=['users:profile:read'],
    )
    if not can_view_any_user and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not enough permissions'
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    return UserResponse.from_orm(_with_authz_payload(db, user))


@router.put('/{user_id}', response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    can_update_any_user = user_has_any_role_or_permission(
        current_user,
        role_codes=['admin', 'manager'],
        permission_codes=['users:update:write'],
    )
    if not can_update_any_user and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not enough permissions'
        )

    requested_roles: Optional[List[str]] = None
    if user_update.roles is not None:
        requested_roles = _resolve_role_codes(None, user_update.roles)
    elif user_update.role is not None:
        requested_roles = _resolve_role_codes(user_update.role, None)

    if requested_roles is not None:
        _assert_access(
            current_user,
            role_codes=['admin'],
            permission_codes=['authz:manage:all'],
            detail='Only admin can change user roles',
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    if user_update.email and user_update.email != user.email:
        if db.query(User).filter(User.email == user_update.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Email already exists'
            )

    update_data = user_update.dict(exclude_unset=True, exclude={'role', 'roles'})

    if not can_update_any_user and current_user.id == user_id:
        disallowed_fields = {'is_active'}
        if any(field in update_data for field in disallowed_fields):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Not enough permissions'
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    if requested_roles is not None:
        try:
            set_user_roles_by_codes(db, user, requested_roles)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        db.refresh(user)

    return UserResponse.from_orm(_with_authz_payload(db, user))


@router.delete('/{user_id}')
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保留向后兼容的用户“删除”接口，实际行为为禁用用户。"""
    _assert_access(
        current_user,
        role_codes=['admin'],
        permission_codes=['users:delete:write'],
        detail='Only admin can delete users',
    )

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot delete yourself'
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    user.is_active = False
    db.commit()

    return {'message': 'User deleted successfully'}


@router.post('/reset-password')
async def reset_user_password(
    password_reset: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin'],
        permission_codes=['users:password:write'],
        detail='Only admin can reset passwords',
    )

    user = db.query(User).filter(User.id == password_reset.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    user.hashed_password = get_password_hash(password_reset.new_password)
    db.commit()

    return {'message': 'Password reset successfully'}


@router.post('/batch-operation')
async def batch_user_operation(
    operation: UserBatchOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin'],
        permission_codes=['users:batch:write'],
        detail='Only admin can perform batch operations',
    )

    if not operation.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No user IDs provided'
        )

    if current_user.id in operation.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot perform batch operation on yourself'
        )

    users = db.query(User).filter(User.id.in_(operation.user_ids)).all()

    if len(users) != len(operation.user_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Some users not found'
        )

    updated_count = 0
    for user in users:
        if operation.operation == 'activate':
            user.is_active = True
            updated_count += 1
        elif operation.operation == 'deactivate':
            user.is_active = False
            updated_count += 1
        elif operation.operation == 'delete':
            user.is_active = False
            updated_count += 1
        elif operation.operation == 'change_role' and operation.value:
            if not user_has_permission(current_user, 'authz:manage:all'):
                raise HTTPException(status_code=403, detail='Only admin can change user roles')
            try:
                set_user_roles_by_codes(db, user, [operation.value])
                updated_count += 1
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

    db.commit()

    return {'message': f'Batch operation completed, {updated_count} users updated'}


@router.get('/stats/summary')
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _assert_access(
        current_user,
        role_codes=['admin', 'manager'],
        permission_codes=['users:list:read'],
    )

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = total_users - active_users

    role_stats = {}
    roles = db.query(Role).order_by(Role.code.asc()).all()
    for role in roles:
        count = (
            db.query(UserRole)
            .join(User, User.id == UserRole.user_id)
            .filter(UserRole.role_id == role.id)
            .count()
        )
        role_stats[role.code] = count

    return {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'role_stats': role_stats
    }
