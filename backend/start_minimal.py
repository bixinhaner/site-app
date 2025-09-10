#!/usr/bin/env python3
"""
最小化启动脚本 - 仅启动基础功能用于测试登录
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
import os

# 基本配置
from app.core.config import settings
from app.core.database import engine, Base, get_db

# 认证相关
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserResponse

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="站点管理系统 - 最小版本",
    description="用于测试登录功能的最小版本",
    version="1.0.0"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

@app.get("/")
async def root():
    return {
        "message": "站点管理系统 - 最小版本",
        "status": "运行中",
        "endpoints": ["/api/auth/login", "/health"]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

@app.post("/api/auth/login")
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    print(f"登录尝试: {user_credentials.username}")
    
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        print(f"登录失败: 用户名或密码错误")
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    
    print(f"登录成功: {user.username}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }

@app.get("/api/users")
async def list_users(db: Session = Depends(get_db)):
    """列出用户 - 仅用于调试"""
    users = db.query(User).all()
    return {
        "count": len(users),
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
            for user in users
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("启动最小化服务器...")
    print("访问 http://localhost:8000 查看状态")
    print("访问 http://localhost:8000/api/users 查看用户列表")
    print("使用 POST http://localhost:8000/api/auth/login 登录")
    print("测试用户: admin / admin123")
    
    uvicorn.run("start_minimal:app", host="0.0.0.0", port=8002, reload=True)