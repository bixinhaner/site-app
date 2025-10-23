from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base
# Ensure new models are imported before creating tables
from app.models import work_order as _work_order_models  # noqa: F401
from app.models import user_log as _user_log_models  # noqa: F401
from app.models import survey as _survey_models  # noqa: F401
from app.api import auth, users, sites, inspections, equipment, stock, template_binding, work_orders
from app.api import site_planning, logs, site_surveys

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="站点信息管理系统 API",
    description="现代化的站点信息管理系统后端接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 中间件
# 注意：当 allow_credentials=True 时，不应使用通配符 "*"。为开发环境显式允许本地前端来源。
default_dev_origins = [
    "http://localhost:3030",
    "http://127.0.0.1:3030",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

# 开发模式下简化为允许任意来源，且不携带凭据（前端使用Bearer Token）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 静态文件服务
uploads_dir = "uploads"
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 路由注册
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(sites.router, prefix="/api/sites", tags=["站点管理"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["检查管理"])
app.include_router(template_binding.router, prefix="/api/inspections", tags=["模板绑定"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["设备管理"])
app.include_router(stock.router, prefix="/api/stock", tags=["库存管理"])
app.include_router(site_planning.router, prefix="/api/sites", tags=["站点规划"])
app.include_router(work_orders.router, prefix="/api/work-orders", tags=["工单管理"])
app.include_router(logs.router, prefix="/api", tags=["用户日志"])
app.include_router(site_surveys.router, prefix="/api/site-surveys", tags=["站点勘察"])

@app.get("/")
async def root():
    return {
        "message": "站点信息管理系统 API", 
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
