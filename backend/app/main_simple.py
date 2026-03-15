from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
import os

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.models import site_progress as _site_progress_models  # noqa: F401
from app.schemas.user import UserLogin, Token, UserResponse
from app.utils.inspection_schema import ensure_inspection_schema

# 导入基本API
from app.api import auth, users, sites, inspections

# 创建数据库表
Base.metadata.create_all(bind=engine)
# 轻量迁移：为 inspection_check_items 旧表补列（SQLite 友好）
ensure_inspection_schema(engine)

app = FastAPI(
    title="站点信息管理系统 API",
    description="现代化的站点信息管理系统后端接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
uploads_dir = "uploads"
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 路由注册 - 只包含基本功能
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(sites.router, prefix="/api/sites", tags=["站点管理"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["检查管理"])

@app.get("/")
async def root():
    return {
        "message": "站点信息管理系统 API", 
        "version": "1.0.0",
        "docs": "/docs",
        "status": "运行正常"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 添加简单的用户列表接口用于调试
@app.get("/api/debug/users")
async def debug_users(db: Session = Depends(get_db)):
    """调试用户列表"""
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
    print("启动站点管理系统服务器...")
    print("访问 http://localhost:8000 查看状态")
    print("访问 http://localhost:8000/docs 查看API文档")
    print("测试用户: admin / admin123")
    
    uvicorn.run("app.main_simple:app", host="0.0.0.0", port=8000, reload=True)
