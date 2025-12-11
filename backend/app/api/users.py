from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
import math

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import (
    UserResponse, UserUpdate, UserCreate, UserListResponse, 
    UserPasswordReset, UserBatchOperation, UserSearchParams
)
from app.api.auth import get_current_user

router = APIRouter()

@router.get("/search", response_model=UserListResponse)
async def search_users(
    keyword: Optional[str] = Query(None, description="搜索关键词(用户名、姓名、邮箱)"),
    role: Optional[str] = Query(None, description="角色筛选"),
    department: Optional[str] = Query(None, description="部门筛选"),
    is_active: Optional[bool] = Query(None, description="状态筛选"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=100, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(User)
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                User.username.contains(keyword),
                User.full_name.contains(keyword),
                User.email.contains(keyword)
            )
        )
    
    # 角色筛选
    if role:
        query = query.filter(User.role == role)
    
    # 部门筛选
    if department:
        query = query.filter(User.department.contains(department))
    
    # 状态筛选
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # 计算总数
    total = query.count()
    
    # 分页查询
    users = query.offset(skip).limit(limit).all()
    
    # 计算分页信息
    page = (skip // limit) + 1
    pages = math.ceil(total / limit)
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        size=limit,
        pages=pages
    )

@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.from_orm(user) for user in users]

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 只有admin可以创建用户
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create users"
        )
    
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
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
        role=user_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse.from_orm(db_user)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 权限检查
    if current_user.role not in ["admin", "manager"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # 角色变更只有admin可以操作
    if user_update.role is not None and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can change user roles"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 检查邮箱唯一性
    if user_update.email and user_update.email != user.email:
        if db.query(User).filter(User.email == user_update.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse.from_orm(user)

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保留向后兼容的用户“删除”接口，实际行为为禁用用户。

    - 仅 admin（含运行时视为 admin 的 manager）可以操作；
    - 禁止对当前登录用户自身调用；
    - 等价于将 `is_active` 置为 False。
    """
    # 只有admin可以删除/禁用用户
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete users"
        )
    
    # 不能删除/禁用自己
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 软删除 - 标记为不活跃（禁用）
    user.is_active = False
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.post("/reset-password")
async def reset_user_password(
    password_reset: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 只有admin可以重置密码
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can reset passwords"
        )
    
    user = db.query(User).filter(User.id == password_reset.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 更新密码
    user.hashed_password = get_password_hash(password_reset.new_password)
    db.commit()
    
    return {"message": "Password reset successfully"}

@router.post("/batch-operation")
async def batch_user_operation(
    operation: UserBatchOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 只有admin可以批量操作
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can perform batch operations"
        )
    
    if not operation.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user IDs provided"
        )
    
    # 不能操作自己
    if current_user.id in operation.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot perform batch operation on yourself"
        )
    
    users = db.query(User).filter(User.id.in_(operation.user_ids)).all()
    
    if len(users) != len(operation.user_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some users not found"
        )
    
    # 执行批量操作
    updated_count = 0
    for user in users:
        if operation.operation == "activate":
            user.is_active = True
            updated_count += 1
        elif operation.operation == "deactivate":
            user.is_active = False
            updated_count += 1
        elif operation.operation == "delete":
            user.is_active = False
            updated_count += 1
        elif operation.operation == "change_role" and operation.value:
            user.role = operation.value
            updated_count += 1
    
    db.commit()
    
    return {"message": f"Batch operation completed, {updated_count} users updated"}

@router.get("/stats/summary")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = total_users - active_users
    
    # 按角色统计
    role_stats = {}
    roles = ["admin", "manager", "inspector", "user"]
    for role in roles:
        count = db.query(User).filter(User.role == role).count()
        role_stats[role] = count
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "role_stats": role_stats
    }
