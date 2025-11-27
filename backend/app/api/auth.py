from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserResponse, UserCreate


class _EffectiveRoleUser:
    """A lightweight proxy that treats 'manager' as 'admin' for permission checks.

    This avoids touching persisted DB state while making admin/manager identical
    for all `current_user.role` comparisons across the API layer.
    """

    __slots__ = ("_u",)

    def __init__(self, orm_user: User):
        object.__setattr__(self, "_u", orm_user)

    def __getattr__(self, name):
        if name == "role":
            r = getattr(self._u, "role", None)
            # Make 'manager' behave exactly like 'admin' at runtime
            return "admin" if r == "manager" else r
        return getattr(self._u, name)

    def __setattr__(self, name, value):
        # Forward any mutation to the underlying ORM instance
        setattr(self._u, name, value)

router = APIRouter()
security = HTTPBearer()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def get_current_user(
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
    if user is None:
        raise credentials_exception
    # Return a proxy so that role checks treat 'manager' the same as 'admin'
    return _EffectiveRoleUser(user)

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
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
        position=user_data.position
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse.from_orm(db_user)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回真实存储的用户信息（不对role做admin映射），用于前端展示。

    鉴权依然通过上游的 get_current_user 完成；此处仅为展示一致性，
    例如让 manager 在UI上仍显示“项目经理”。
    """
    raw = get_user_by_username(db, current_user.username)
    return UserResponse.from_orm(raw)


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
