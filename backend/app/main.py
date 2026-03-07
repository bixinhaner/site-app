from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from sqlalchemy.exc import IntegrityError
from email_validator import EmailNotValidError, validate_email

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.security import get_password_hash
from app.services.authz_service import ensure_builtin_roles_and_permissions, set_user_roles_by_codes
from app.utils.stock_schema import ensure_stock_schema
from app.utils.authz_schema import ensure_authz_schema
from app.utils.geocode_schema import ensure_geocode_schema
from app.utils.site_schema import ensure_site_schema
from app.utils.planning_schema import ensure_planning_schema
from app.utils.app_version_schema import ensure_app_version_schema
from app.utils.inspection_schema import ensure_inspection_schema
from app.utils.work_order_schema import ensure_work_order_schema
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
from app.models import ai_call_log as _ai_call_log_models  # noqa: F401
from app.models import authz as _authz_models  # noqa: F401
from app.models import geocode_cache as _geocode_cache_models  # noqa: F401
from app.models import omc_state as _omc_state_models  # noqa: F401
from app.models import app_version as _app_version_models  # noqa: F401
from app.models import mobile_client_log as _mobile_client_log_models  # noqa: F401
from app.models.user import User
from app.api import auth, authz, users, sites, inspections, equipment, stock, template_binding, work_orders, geocode, ai, ai_management
from app.api import site_planning, logs, site_surveys, dashboard, survey_archives, opening_archives, ssv_archives, omc, omc_push, system_backup, mobile_settings, geocode_cache
from app.api import operation_logs, app_version
from app.api import mobile_client_logs
from app.api import mock_omc_proxy
from app.api import work_order_execution_settings
from app.services.omc_monitor import start_background_omc_monitor
from app.services.backup_scheduler import start_backup_scheduler
from app.services.mobile_client_log_retention_scheduler import start_mobile_client_log_retention_scheduler
from app.middleware.operation_log import OperationLogMiddleware

# 创建数据库表
Base.metadata.create_all(bind=engine)
# 轻量迁移：RBAC users.role -> user_roles（SQLite 友好）
ensure_authz_schema(engine)
# 初始化内置角色与权限定义
_seed_db = SessionLocal()
try:
    ensure_builtin_roles_and_permissions(_seed_db)
finally:
    _seed_db.close()
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
# 轻量迁移：为 work_orders 旧表补列（SQLite 友好）
ensure_work_order_schema(engine)

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
app.include_router(authz.router, prefix="/api/authz", tags=["权限管理"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(sites.router, prefix="/api/sites", tags=["站点管理"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["检查管理"])
app.include_router(template_binding.router, prefix="/api/inspections", tags=["模板绑定"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["设备管理"])
app.include_router(stock.router, prefix="/api/stock", tags=["库存管理"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])
app.include_router(geocode.router, prefix="/api", tags=["地理编码"])
app.include_router(site_planning.router, prefix="/api/sites", tags=["站点规划"])
app.include_router(work_orders.router, prefix="/api/work-orders", tags=["工单管理"])
app.include_router(logs.router, prefix="/api", tags=["用户日志"])
app.include_router(operation_logs.router, prefix="/api", tags=["操作日志"])
app.include_router(mobile_client_logs.router, prefix="/api", tags=["移动端日志"])
app.include_router(mobile_settings.router, prefix="/api/system", tags=["系统配置"])
app.include_router(work_order_execution_settings.router, prefix="/api/system", tags=["系统配置"])
app.include_router(geocode_cache.router, prefix="/api/system", tags=["地理编码缓存"])
app.include_router(ai_management.router, prefix="/api/system/ai", tags=["AI管理"])
app.include_router(site_surveys.router, prefix="/api/site-surveys", tags=["站点勘察"])
app.include_router(survey_archives.router, prefix="/api/survey-archives", tags=["勘察档案"])
app.include_router(opening_archives.router, prefix="/api/opening-archives", tags=["开站档案"])
app.include_router(ssv_archives.router, prefix="/api/ssv-archives", tags=["SSV档案"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(omc.router, prefix="/api/omc", tags=["OMC配置"])
app.include_router(omc_push.router, prefix="/api/omc", tags=["OMC状态上报告"])
app.include_router(mock_omc_proxy.router, prefix="/api/mock-omc", tags=["Mock OMC"])
app.include_router(system_backup.router, prefix="/api/system/backup", tags=["系统备份"])
app.include_router(app_version.router, prefix="/api/app-version", tags=["App版本管理"])

def _is_valid_email(value: str) -> bool:
    try:
        if not value:
            return False
        validate_email(value, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def _ensure_default_admin_user() -> None:
    """启动时确保存在默认管理员账号。

    - 仅当用户不存在时创建；
    - 已存在时不会重置密码；
    - 若管理员邮箱不合法（会导致响应模型 EmailStr 校验 500），则自动修复。
    """
    if not settings.AUTO_CREATE_ADMIN:
        return

    username = (settings.DEFAULT_ADMIN_USERNAME or "admin").strip() or "admin"
    password = settings.DEFAULT_ADMIN_PASSWORD or "admin123"
    full_name = settings.DEFAULT_ADMIN_FULL_NAME or "系统管理员"
    admin_email = settings.DEFAULT_ADMIN_EMAIL or "admin@example.com"
    if not _is_valid_email(admin_email):
        admin_email = "admin@example.com"

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing is None:
            if password == "admin123":
                print("⚠️ DEFAULT_ADMIN_PASSWORD 使用默认值 admin123，生产环境请在 backend/.env 中显式修改。")

            user = User(
                username=username,
                email=admin_email,
                hashed_password=get_password_hash(password),
                full_name=full_name,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            set_user_roles_by_codes(db, user, ["admin"])
            print(f"✅ 默认管理员已创建: {username}")
            return

        # 已存在：admin 不重置密码；仅修复不合法邮箱，避免响应模型校验失败导致 500
        if existing.email and not _is_valid_email(existing.email):
            target_email = admin_email
            # 若默认邮箱已被其他用户占用，生成一个唯一兜底邮箱
            occupied = (
                db.query(User)
                .filter(User.email == target_email, User.id != existing.id)
                .first()
            )
            if occupied is not None:
                target_email = f"{username}.{existing.id}@example.com"
                if not _is_valid_email(target_email):
                    target_email = "admin@example.com"

            existing.email = target_email
            db.commit()
            print(f"⚠️ 已修复管理员邮箱为: {existing.email}")
        # 保证 admin 账号具备 admin 角色
        if not existing.has_role("admin"):
            target_roles = sorted(set((existing.role_codes or []) + ["admin"]))
            set_user_roles_by_codes(db, existing, target_roles)
    except IntegrityError as e:
        db.rollback()
        print(f"❌ 默认管理员初始化失败（IntegrityError）: {e}")
    except Exception as e:
        db.rollback()
        print(f"❌ 默认管理员初始化失败: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _startup_ensure_default_admin():
    _ensure_default_admin_user()

@app.on_event("startup")
def _startup_apply_ai_config():
    """
    启动时从 DB 读取 AI 配置，并热更新到运行中的 settings。

    - 支持“后台页面修改后即时生效”
    - DB 未配置时不影响启动
    """
    db = SessionLocal()
    try:
        from app.services.ai_config_service import apply_ai_config_to_settings, load_ai_config

        cfg = load_ai_config(db)
        apply_ai_config_to_settings(cfg)
    except Exception as e:
        print(f"⚠️ AI 配置加载失败: {e}")
    finally:
        db.close()


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


@app.on_event("startup")
def _startup_mobile_log_retention_scheduler():
  """
  启动移动端日志保留清理线程（按配置 retention_days 定期删除过期数据）。
  """
  start_mobile_client_log_retention_scheduler()

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
