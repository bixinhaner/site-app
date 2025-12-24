from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.utils.stock_schema import ensure_stock_schema
from app.utils.geocode_schema import ensure_geocode_schema
from app.utils.site_schema import ensure_site_schema
from app.utils.planning_schema import ensure_planning_schema
from app.utils.app_version_schema import ensure_app_version_schema
from app.utils.inspection_schema import ensure_inspection_schema
# Ensure new models are imported before creating tables
from app.models import work_order as _work_order_models  # noqa: F401
from app.models import user_log as _user_log_models  # noqa: F401
from app.models import operation_log as _operation_log_models  # noqa: F401
from app.models import survey as _survey_models  # noqa: F401
from app.models import survey_archive as _survey_archive_models  # noqa: F401
from app.models import opening_archive as _opening_archive_models  # noqa: F401
from app.models import ssv_archive as _ssv_archive_models  # noqa: F401
from app.models import omc_cellname_sync as _omc_cellname_sync_models  # noqa: F401
from app.models import system_config as _system_config_models  # noqa: F401
from app.models import geocode_cache as _geocode_cache_models  # noqa: F401
from app.models import omc_state as _omc_state_models  # noqa: F401
from app.models import app_version as _app_version_models  # noqa: F401
from app.api import auth, users, sites, inspections, equipment, stock, template_binding, work_orders, geocode
from app.api import site_planning, logs, site_surveys, dashboard, survey_archives, opening_archives, ssv_archives, omc, omc_push, system_backup, mobile_settings, geocode_cache
from app.api import operation_logs, app_version
from app.services.omc_monitor import start_background_omc_monitor
from app.services.backup_scheduler import start_backup_scheduler
from app.middleware.operation_log import OperationLogMiddleware

# 创建数据库表
Base.metadata.create_all(bind=engine)
# 轻量迁移：为库存相关旧表补列（SQLite 友好）
ensure_stock_schema(engine)
# 轻量迁移：为 geocode_cache 旧表补列（SQLite 友好）
ensure_geocode_schema(engine)
# 轻量迁移：为 sites 旧表补列（SQLite 友好）
ensure_site_schema(engine)
# 轻量迁移：为 site_planning_cells 旧表补列（SQLite 友好）
ensure_planning_schema(engine)
# 轻量迁移：为 app_versions 旧表补列（SQLite 友好）
ensure_app_version_schema(engine)
# 轻量迁移：为 inspection_check_items 旧表补列（SQLite 友好）
ensure_inspection_schema(engine)

app = FastAPI(
    title="站点信息管理系统 API",
    description="现代化的站点信息管理系统后端接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 操作日志（功能动作级）中间件：需尽早注册以覆盖所有 /api 请求
app.add_middleware(OperationLogMiddleware)

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
app.include_router(geocode.router, prefix="/api", tags=["地理编码"])
app.include_router(site_planning.router, prefix="/api/sites", tags=["站点规划"])
app.include_router(work_orders.router, prefix="/api/work-orders", tags=["工单管理"])
app.include_router(logs.router, prefix="/api", tags=["用户日志"])
app.include_router(operation_logs.router, prefix="/api", tags=["操作日志"])
app.include_router(mobile_settings.router, prefix="/api/system", tags=["系统配置"])
app.include_router(geocode_cache.router, prefix="/api/system", tags=["地理编码缓存"])
app.include_router(site_surveys.router, prefix="/api/site-surveys", tags=["站点勘察"])
app.include_router(survey_archives.router, prefix="/api/survey-archives", tags=["勘察档案"])
app.include_router(opening_archives.router, prefix="/api/opening-archives", tags=["开站档案"])
app.include_router(ssv_archives.router, prefix="/api/ssv-archives", tags=["SSV档案"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(omc.router, prefix="/api/omc", tags=["OMC配置"])
app.include_router(omc_push.router, prefix="/api/omc", tags=["OMC状态上报告"])
app.include_router(system_backup.router, prefix="/api/system/backup", tags=["系统备份"])
app.include_router(app_version.router, prefix="/api/app-version", tags=["App版本管理"])


@app.on_event("startup")
def _startup_omc_monitor():
  """
  启动 OMC 状态轮询线程，用于自动推进开站工单状态。
  """
  start_background_omc_monitor()


@app.on_event("startup")
def _startup_backup_scheduler():
  """
  启动数据备份定时任务调度线程。
  """
  start_backup_scheduler()

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
