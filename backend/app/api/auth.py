from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserResponse, UserCreate, UserPasswordChange
from app.services.authz_service import (
    get_user_data_scopes,
    get_user_permission_codes,
    get_user_with_authz,
    set_user_roles_by_codes,
    user_has_permission,
)
from app.services.warehouse_access_service import build_inventory_access_profile

router = APIRouter()
security = HTTPBearer()
LOGIN_CLIENT_ALIASES = {
    'web': 'web',
    'web-admin': 'web',
    'web_admin': 'web',
    'webadmin': 'web',
    'browser': 'web',
    'app': 'app',
    'mobile': 'app',
    'mobile-app': 'app',
    'uniapp': 'app',
}
LOGIN_CLIENT_RULES = {
    'web': {
        'permission': 'auth:web-login',
        'detail': 'WEB_LOGIN_FORBIDDEN',
    },
    'app': {
        'permission': 'auth:app-login',
        'detail': 'APP_LOGIN_FORBIDDEN',
    },
}

def get_user_by_username(db: Session, username: str):
    return get_user_with_authz(db, username)


def _attach_authz_payload(user: User) -> User:
    permissions = get_user_permission_codes(user)
    data_scopes = get_user_data_scopes(user)
    try:
        setattr(user, "permissions", permissions)
        setattr(user, "permission_codes", permissions)
        setattr(user, "data_scopes", data_scopes)
    except Exception:
        pass
    return user


def _attach_inventory_access_payload(db: Session, user: User) -> User:
    if not user:
        return user
    profile = build_inventory_access_profile(db, user)
    try:
        setattr(user, "inventory_scope", str(profile.get("inventory_scope") or "self"))
        setattr(user, "managed_warehouse_ids", list(profile.get("managed_warehouse_ids") or []))
        setattr(user, "managed_warehouse_count", int(profile.get("managed_warehouse_count") or 0))
        setattr(user, "has_managed_warehouses", bool(profile.get("has_managed_warehouses")))
    except Exception:
        pass
    return user


def _normalize_login_client(raw_value: str | None) -> str | None:
    code = str(raw_value or '').strip().lower()
    if not code:
        return None
    return LOGIN_CLIENT_ALIASES.get(code)


def _resolve_login_client(request: Request, raw_client_type: str | None) -> str:
    for candidate in (
        raw_client_type,
        request.headers.get('X-Client'),
        request.headers.get('x-client'),
    ):
        normalized = _normalize_login_client(candidate)
        if normalized:
            return normalized
    return 'web'

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    user = _attach_authz_payload(user)
    return _attach_inventory_access_payload(db, user)

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None:
            raise credentials_exception
        if token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username=username)
    # 用户不存在或已被禁用，都视为凭证无效
    if user is None or not user.is_active:
        raise credentials_exception
    user = _attach_authz_payload(user)
    user = _attach_inventory_access_payload(db, user)
    # 供中间件/审计日志使用
    try:
        request.state.current_user = user
        request.state.raw_user = user
    except Exception:
        pass
    return user

@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 禁用用户：登录时返回专门提示，状态仍为401，方便现有客户端复用错误处理
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ACCOUNT_DISABLED",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_client = _resolve_login_client(request, user_credentials.client_type)
    login_rule = LOGIN_CLIENT_RULES.get(login_client)
    if login_rule and not user_has_permission(user, login_rule['permission']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=login_rule['detail'],
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(subject=user.username, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(subject=user.username, expires_delta=refresh_token_expires)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user)
    }

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # 检查邮箱是否已存在
    db_email = db.query(User).filter(User.email == user_data.email).first()
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建新用户
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

    role_codes = sorted(set(user_data.roles or ([] if not user_data.role else [user_data.role]) or ["user"]))
    try:
        set_user_roles_by_codes(db, db_user, role_codes)
    except ValueError as exc:
        db.delete(db_user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    db_user = get_user_by_username(db, db_user.username)
    db_user = _attach_authz_payload(db_user)
    db_user = _attach_inventory_access_payload(db, db_user)
    return UserResponse.from_orm(db_user)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前用户信息（含 roles/permissions）。"""
    refreshed = get_user_by_username(db, current_user.username)
    if not refreshed:
        raise HTTPException(status_code=404, detail="User not found")
    refreshed = _attach_authz_payload(refreshed)
    refreshed = _attach_inventory_access_payload(db, refreshed)
    return UserResponse.from_orm(refreshed)


@router.post("/refresh", response_model=Token)
async def refresh_token(request: dict):
    """使用 refresh_token 换取新的 access_token（支持滚动刷新）。"""
    refresh_token = request.get("refresh_token") if isinstance(request, dict) else None
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 refresh_token")
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token 类型")
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的 refresh_token")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_access = create_access_token(subject=username, expires_delta=access_token_expires)
    new_refresh = create_refresh_token(subject=username, expires_delta=refresh_token_expires)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/change-password")
async def change_password(
    payload: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """允许当前登录用户修改自己的密码。

    - 需要提交当前密码用于校验；
    - 新密码做最小长度校验（8位）；
    - 成功后仅更新当前用户密码。
    """
    user = get_user_by_username(db, current_user.username)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive",
        )

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    if not payload.new_password or len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    return {"message": "Password changed successfully"}
