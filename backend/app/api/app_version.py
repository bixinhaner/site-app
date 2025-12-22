"""
App版本管理API
提供版本检测、版本管理和文件上传功能
"""
import os
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.user import User
from app.models.app_version import AppVersion, AppVersionDownloadLog, AppVersionReleaseNote, AppVersionReleaseNoteItem, AppVersionUsageLog
from app.schemas.app_version import (
    AppVersionCheckRequest, AppVersionCheckResponse, AppVersionInfo,
    AppVersionCreate, AppVersionUpdate, AppVersionResponse, AppVersionListResponse,
    DownloadStartRequest, DownloadCompleteRequest, DownloadStartResponse,
    FileUploadResponse,
    ReleaseNoteCreate, ReleaseNoteUpdate, ReleaseNoteResponse, ReleaseNoteImageUploadResponse,
    DownloadLogListResponse, DownloadLogResponse
)

router = APIRouter()

# APK上传目录
APK_UPLOAD_DIR = "uploads/apk"

def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    将数据库取出的 naive datetime 视为 UTC，并规范为 tz-aware UTC。
    FastAPI 序列化 tz-aware datetime 时会带上 +00:00，从而让前端正确按本地时区展示。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _try_get_access_user(req: Request, db: Session) -> Optional[User]:
    """尝试从 Authorization: Bearer <token> 解析当前用户（失败则返回 None，不影响主流程）。"""
    auth = req.headers.get("authorization") or req.headers.get("Authorization")
    if not auth:
        return None

    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        username = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.username == username).first()
    if user is None or not getattr(user, "is_active", True):
        return None
    return user


def _ensure_apk_dir():
    """确保APK上传目录存在"""
    if not os.path.exists(APK_UPLOAD_DIR):
        os.makedirs(APK_UPLOAD_DIR)


def _calculate_md5(file_path: str) -> str:
    """计算文件MD5"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _check_gray_scale(device_id: Optional[str], percent: int) -> bool:
    """检查设备是否命中灰度发布
    
    使用设备ID的哈希值对100取模，判断是否在灰度百分比内
    这样可以确保同一设备每次检测结果一致
    """
    if percent >= 100:
        return True
    if percent <= 0:
        return False
    if not device_id:
        # 无设备ID时使用随机数
        import random
        return random.randint(1, 100) <= percent
    
    # 使用设备ID哈希确保一致性
    hash_val = int(hashlib.md5(device_id.encode()).hexdigest(), 16)
    return (hash_val % 100) < percent


# ============ 公开API（无需认证） ============

@router.post("/check", response_model=AppVersionCheckResponse)
async def check_version(
    request: AppVersionCheckRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """检测App是否有新版本
    
    - 查询当前启用的最新版本
    - 比较版本号，判断是否需要更新
    - 检查灰度发布配置
    - 记录使用日志用于统计
    """
    # 记录使用日志（每个设备每天只记录一次）
    # logged_date 使用 UTC 作为“天”的边界（避免服务器本地时区差异导致前后端对不上）
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if request.device_id:
        # 检查今天是否已记录
        existing_log = db.query(AppVersionUsageLog).filter(
            AppVersionUsageLog.device_id == request.device_id,
            AppVersionUsageLog.logged_date == today
        ).first()
        
        # 准备用户信息
        username_val = request.username or ""
        user_role_val = request.user_role or ""

        if not existing_log:
            # 记录新的使用日志
            client_ip = req.client.host if req.client else None
            usage_log = AppVersionUsageLog(
                device_id=request.device_id,
                device_model=request.device_model,
                device_brand=request.device_brand,
                os_version=request.os_version,
                version_code=request.current_version_code,
                ip_address=client_ip,
                logged_date=today,
                user_id=request.user_id,
                username=username_val,
                user_role=user_role_val
            )
            db.add(usage_log)
            try:
                db.commit()
            except Exception:
                db.rollback()  # 日志记录失败不影响主流程
        else:
            changed = False

            # 方案B：同一设备同一天若升级到更高版本，则更新当天记录为新版本
            # 这样版本分布能反映“当天最新版本”（而不是当天第一次启动的版本）
            try:
                old_vc = int(existing_log.version_code) if existing_log.version_code is not None else None
            except Exception:
                old_vc = None
            new_vc = request.current_version_code
            if old_vc is None or (new_vc and new_vc > old_vc):
                existing_log.version_code = new_vc
                changed = True

            # 如果已有记录但没有用户信息，补充用户信息
            if request.user_id and not existing_log.user_id:
                existing_log.user_id = request.user_id
                existing_log.username = username_val
                existing_log.user_role = user_role_val
                changed = True

            if changed:
                try:
                    db.commit()
                except Exception:
                    db.rollback()  # 日志记录失败不影响主流程
    
    # 查询最新启用版本
    latest_version = db.query(AppVersion).filter(
        AppVersion.is_active == True
    ).order_by(desc(AppVersion.version_code)).first()
    
    if not latest_version:
        return AppVersionCheckResponse(has_update=False)
    
    # 比较版本号
    if latest_version.version_code <= request.current_version_code:
        return AppVersionCheckResponse(has_update=False)
    
    # 检查灰度发布
    if not _check_gray_scale(request.device_id, latest_version.gray_scale_percent):
        return AppVersionCheckResponse(has_update=False)
    
    # 判断更新类型
    # 如果当前版本低于最低兼容版本，强制更新
    update_type = latest_version.update_type
    if latest_version.min_version_code > request.current_version_code:
        update_type = "force"
    
    return AppVersionCheckResponse(
        has_update=True,
        update_type=update_type,
        version_info=AppVersionInfo(
            id=latest_version.id,
            version_name=latest_version.version_name,
            version_code=latest_version.version_code,
            update_type=update_type,
            download_url=latest_version.download_url,
            file_size=latest_version.file_size,
            file_md5=latest_version.file_md5,
            release_notes=latest_version.release_notes,
            release_notes_en=latest_version.release_notes_en,
            show_release_notes=latest_version.show_release_notes or False,
            published_at=latest_version.published_at
        )
    )


@router.get("/latest", response_model=AppVersionInfo)
async def get_latest_version(db: Session = Depends(get_db)):
    """获取最新版本信息（公开接口）"""
    latest_version = db.query(AppVersion).filter(
        AppVersion.is_active == True
    ).order_by(desc(AppVersion.version_code)).first()
    
    if not latest_version:
        raise HTTPException(status_code=404, detail="暂无可用版本")
    
    return AppVersionInfo.from_orm(latest_version)


@router.post("/download-start", response_model=DownloadStartResponse)
async def record_download_start(
    request: DownloadStartRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """记录下载开始事件"""
    # 获取客户端IP
    client_ip = req.client.host if req.client else None

    # 允许在不强制鉴权的前提下，尽可能记录真实用户信息：
    # - App 可能在未登录时也会触发升级；此时保持为空，前端展示为 "-"
    # - 若携带 Bearer Token，则以 token 对应用户为准（比客户端上报更可信）
    token_user = _try_get_access_user(req, db)
    user_id_val = request.user_id
    username_val = request.username
    user_role_val = request.user_role
    if token_user:
        user_id_val = token_user.id
        username_val = token_user.username
        user_role_val = token_user.role
    else:
        # 若客户端只传了部分用户信息（例如仅 user_id），则补齐 username/role，便于 WebAdmin 展示
        if user_id_val is not None and not username_val:
            db_user = db.query(User).filter(User.id == user_id_val).first()
            if db_user:
                username_val = db_user.username
                if not user_role_val:
                    user_role_val = db_user.role
        elif username_val and user_id_val is None:
            db_user = db.query(User).filter(User.username == username_val).first()
            if db_user:
                user_id_val = db_user.id
                if not user_role_val:
                    user_role_val = db_user.role
    
    # 创建下载日志
    log = AppVersionDownloadLog(
        version_id=request.version_id,
        version_code=request.version_code,
        device_id=request.device_id,
        device_model=request.device_model,
        device_brand=request.device_brand,
        os_version=request.os_version,
        from_version_code=request.from_version_code,
        download_status="started",
        network_type=request.network_type,
        ip_address=client_ip,
        user_id=user_id_val,
        username=username_val,
        user_role=user_role_val
    )
    db.add(log)
    
    # 更新版本下载计数
    version = db.query(AppVersion).filter(AppVersion.id == request.version_id).first()
    if version:
        version.download_count = (version.download_count or 0) + 1
    
    db.commit()
    db.refresh(log)
    
    return DownloadStartResponse(log_id=log.id)


@router.post("/download-complete")
async def record_download_complete(
    request: DownloadCompleteRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """记录下载完成事件"""
    log = db.query(AppVersionDownloadLog).filter(
        AppVersionDownloadLog.id == request.log_id
    ).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="下载记录不存在")
    
    log.download_status = request.status
    # started_at（SQLite CURRENT_TIMESTAMP）为 UTC；completed_at 也统一写 UTC，避免前端计算耗时出现 +8h 偏差
    log.completed_at = datetime.utcnow()

    # 若 download-start 阶段未能获取用户信息，这里再补一次（仅在字段为空时）
    token_user = _try_get_access_user(req, db)
    if token_user:
        if getattr(log, "user_id", None) is None:
            log.user_id = token_user.id
        if not getattr(log, "username", None):
            log.username = token_user.username
        if not getattr(log, "user_role", None):
            log.user_role = token_user.role
    # 若仍为部分缺失（例如历史逻辑只写了 user_id），则再兜底补齐
    if getattr(log, "user_id", None) is not None and not getattr(log, "username", None):
        db_user = db.query(User).filter(User.id == log.user_id).first()
        if db_user:
            log.username = db_user.username
            if not getattr(log, "user_role", None):
                log.user_role = db_user.role
    elif getattr(log, "username", None) and getattr(log, "user_id", None) is None:
        db_user = db.query(User).filter(User.username == log.username).first()
        if db_user:
            log.user_id = db_user.id
            if not getattr(log, "user_role", None):
                log.user_role = db_user.role
    
    if request.status == "failed" and request.error_message:
        log.error_message = request.error_message
    
    # 如果下载完成，更新安装计数
    if request.status == "completed":
        version = db.query(AppVersion).filter(AppVersion.id == log.version_id).first()
        if version:
            version.install_count = (version.install_count or 0) + 1
    
    db.commit()
    
    return {"message": "下载状态已更新", "status": request.status}


# ============ 管理API（需要admin权限） ============

def _check_admin(current_user: User):
    """检查管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

def _recalc_latest_active_version(db: Session) -> None:
    """
    重新计算“最新已发布版本”：
    - 仅在 is_active=True 的版本中，选择 version_code 最大者标记为 is_latest=True
    - 其余全部置为 False
    """
    latest_active = db.query(AppVersion).filter(
        AppVersion.is_active == True
    ).order_by(desc(AppVersion.version_code)).first()

    # 先清空
    db.query(AppVersion).filter(AppVersion.is_latest == True).update({"is_latest": False})

    # 再标记最新已发布
    if latest_active:
        db.query(AppVersion).filter(AppVersion.id == latest_active.id).update({"is_latest": True})


@router.get("/versions", response_model=AppVersionListResponse)
async def list_versions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取版本列表（管理员）"""
    _check_admin(current_user)
    
    query = db.query(AppVersion)
    if is_active is not None:
        query = query.filter(AppVersion.is_active == is_active)
    
    total = query.count()
    versions = query.order_by(desc(AppVersion.version_code)).offset(skip).limit(limit).all()

    # 保证返回的 is_latest 表示“最新已发布版本”
    latest_active = db.query(AppVersion).filter(
        AppVersion.is_active == True
    ).order_by(desc(AppVersion.version_code)).first()
    latest_active_id = latest_active.id if latest_active else None
    if latest_active_id:
        for v in versions:
            v.is_latest = (v.id == latest_active_id)
    else:
        for v in versions:
            v.is_latest = False
    
    return AppVersionListResponse(
        versions=[AppVersionResponse.from_orm(v) for v in versions],
        total=total
    )


@router.get("/versions/{version_id}", response_model=AppVersionResponse)
async def get_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取版本详情（管理员）"""
    _check_admin(current_user)
    
    version = db.query(AppVersion).filter(AppVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    return AppVersionResponse.from_orm(version)


@router.post("/versions", response_model=AppVersionResponse)
async def create_version(
    version_data: AppVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新版本（管理员）"""
    _check_admin(current_user)

    # 若立即发布，必须提供APK信息
    if version_data.is_active:
        if not version_data.download_url or not version_data.file_name:
            raise HTTPException(status_code=400, detail="发布版本必须先上传APK文件")

    # 检查版本号是否已存在
    existing = db.query(AppVersion).filter(
        AppVersion.version_code == version_data.version_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="版本号已存在")
    
    # 创建版本
    version = AppVersion(
        version_name=version_data.version_name,
        version_code=version_data.version_code,
        update_type=version_data.update_type,
        download_url=version_data.download_url,
        file_size=version_data.file_size,
        file_md5=version_data.file_md5,
        file_name=version_data.file_name,
        release_notes=version_data.release_notes,
        release_notes_en=version_data.release_notes_en,
        min_version_code=version_data.min_version_code,
        gray_scale_percent=version_data.gray_scale_percent,
        is_active=version_data.is_active,
        show_release_notes=version_data.show_release_notes or False,
        published_at=datetime.now() if version_data.is_active else None
    )

    db.add(version)
    db.flush()

    _recalc_latest_active_version(db)
    db.commit()
    db.refresh(version)
    
    return AppVersionResponse.from_orm(version)


@router.put("/versions/{version_id}", response_model=AppVersionResponse)
async def update_version(
    version_id: int,
    version_data: AppVersionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新版本信息（管理员）"""
    _check_admin(current_user)
    
    version = db.query(AppVersion).filter(AppVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    # 更新字段
    update_data = version_data.dict(exclude_unset=True)

    # 已发布版本禁止替换APK文件信息
    file_fields = {"download_url", "file_size", "file_md5", "file_name"}
    if version.is_active and any(field in update_data for field in file_fields):
        raise HTTPException(status_code=400, detail="已发布版本不允许替换APK文件，请创建新版本或在草稿阶段上传")

    # 草稿发布校验：从草稿变更为发布时，必须具备APK信息
    if version_data.is_active is True and not version.is_active:
        new_download_url = update_data.get("download_url", version.download_url)
        new_file_name = update_data.get("file_name", version.file_name)
        if not new_download_url or not new_file_name:
            raise HTTPException(status_code=400, detail="发布版本必须先上传APK文件")

    for field, value in update_data.items():
        setattr(version, field, value)
    
    # 如果激活状态变更为True，设置发布时间
    if version_data.is_active is True and not version.published_at:
        version.published_at = datetime.now()

    # SessionLocal 默认 autoflush=False，这里显式 flush，确保后续重新计算 is_latest 基于最新状态
    db.flush()
    _recalc_latest_active_version(db)
    db.commit()
    db.refresh(version)
    
    return AppVersionResponse.from_orm(version)


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除版本（管理员）"""
    _check_admin(current_user)
    
    version = db.query(AppVersion).filter(AppVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    # 如果有关联的APK文件，可以选择删除（这里保留文件）
    # if version.file_name:
    #     file_path = os.path.join(APK_UPLOAD_DIR, version.file_name)
    #     if os.path.exists(file_path):
    #         os.remove(file_path)
    
    db.delete(version)
    db.flush()

    _recalc_latest_active_version(db)
    db.commit()
    
    return {"message": "版本已删除", "version_id": version_id}


@router.post("/upload", response_model=FileUploadResponse)
async def upload_apk(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传APK文件（管理员）
    
    返回文件信息，用于后续创建版本记录
    """
    _check_admin(current_user)
    
    # 验证文件类型
    if not file.filename.endswith('.apk'):
        raise HTTPException(status_code=400, detail="只支持APK文件")
    
    _ensure_apk_dir()
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"app_{timestamp}.apk"
    file_path = os.path.join(APK_UPLOAD_DIR, safe_filename)
    
    # 保存文件
    file_size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(chunk)
            file_size += len(chunk)
    
    # 计算MD5
    file_md5 = _calculate_md5(file_path)
    
    # 生成下载URL
    download_url = f"/uploads/apk/{safe_filename}"
    
    return FileUploadResponse(
        file_name=safe_filename,
        file_size=file_size,
        file_md5=file_md5,
        download_url=download_url
    )


@router.get("/stats")
async def get_version_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取版本统计信息（管理员）"""
    _check_admin(current_user)
    
    # 总版本数
    total_versions = db.query(AppVersion).count()
    
    # 活跃版本数
    active_versions = db.query(AppVersion).filter(AppVersion.is_active == True).count()
    
    # 总下载次数
    from sqlalchemy import func
    total_downloads = db.query(func.sum(AppVersion.download_count)).scalar() or 0
    
    # 总安装次数
    total_installs = db.query(func.sum(AppVersion.install_count)).scalar() or 0
    
    # 最新版本
    latest = db.query(AppVersion).filter(
        AppVersion.is_active == True
    ).order_by(desc(AppVersion.version_code)).first()
    
    return {
        "total_versions": total_versions,
        "active_versions": active_versions,
        "total_downloads": total_downloads,
        "total_installs": total_installs,
        "latest_version": latest.version_name if latest else None,
        "latest_version_code": latest.version_code if latest else None
    }


@router.get("/download-logs", response_model=DownloadLogListResponse)
async def get_download_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    version_code: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取下载日志列表（管理员）"""
    _check_admin(current_user)
    
    query = db.query(AppVersionDownloadLog)
    
    if username:
        query = query.filter(AppVersionDownloadLog.username.ilike(f"%{username}%"))
    
    if version_code:
        query = query.filter(AppVersionDownloadLog.version_code == version_code)
        
    total = query.count()
    logs = query.order_by(desc(AppVersionDownloadLog.started_at)).offset(skip).limit(limit).all()
    
    return DownloadLogListResponse(
        logs=[
            DownloadLogResponse.model_validate(log).model_copy(
                update={
                    "started_at": _as_utc(getattr(log, "started_at", None)),
                    "completed_at": _as_utc(getattr(log, "completed_at", None)),
                }
            )
            for log in logs
        ],
        total=total
    )


@router.get("/usage-stats")
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取App使用统计详情（管理员）
    
    返回：
    - 总设备数、日活、月活
    - 版本分布
    - 每日活跃趋势
    - 设备品牌分布
    """
    _check_admin(current_user)
    
    from sqlalchemy import func, distinct
    from datetime import datetime, timedelta, timezone
    
    # 统计窗口与 logged_date 统一按 UTC 计算，避免时区差异导致数据错位
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days)
    start_date_str = start_date.strftime("%Y-%m-%d")
    
    # 总独立设备数
    total_devices = db.query(func.count(distinct(AppVersionUsageLog.device_id))).scalar() or 0
    
    # 今日活跃设备数 (DAU)
    today_str = today.strftime("%Y-%m-%d")
    dau = db.query(func.count(distinct(AppVersionUsageLog.device_id))).filter(
        AppVersionUsageLog.logged_date == today_str
    ).scalar() or 0
    
    # 最近7日活跃设备数 (WAU)
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    wau = db.query(func.count(distinct(AppVersionUsageLog.device_id))).filter(
        AppVersionUsageLog.logged_date >= week_ago
    ).scalar() or 0
    
    # 最近30日活跃设备数 (MAU)
    month_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    mau = db.query(func.count(distinct(AppVersionUsageLog.device_id))).filter(
        AppVersionUsageLog.logged_date >= month_ago
    ).scalar() or 0
    
    # 方案C：版本/品牌/系统版本分布均以“窗口内每设备一条快照”为准，避免同一设备多次上报导致重复计数
    # 取法：
    # - 每个 device_id 取窗口内 version_code 最大的那条记录
    # - 若 version_code 相同，取 logged_at 最新的一条；再按 id 兜底
    ranked = db.query(
        AppVersionUsageLog.device_id.label("device_id"),
        AppVersionUsageLog.version_code.label("version_code"),
        AppVersionUsageLog.device_brand.label("device_brand"),
        AppVersionUsageLog.os_version.label("os_version"),
        func.row_number().over(
            partition_by=AppVersionUsageLog.device_id,
            order_by=(
                AppVersionUsageLog.version_code.desc(),
                AppVersionUsageLog.logged_at.desc(),
                AppVersionUsageLog.id.desc(),
            ),
        ).label("rn"),
    ).filter(
        AppVersionUsageLog.logged_date >= start_date_str
    ).subquery()

    device_snapshot = db.query(
        ranked.c.device_id,
        ranked.c.version_code,
        ranked.c.device_brand,
        ranked.c.os_version,
    ).filter(ranked.c.rn == 1).subquery()

    # 版本分布（最近 N 天，按 device_snapshot 汇总）
    version_dist = db.query(
        device_snapshot.c.version_code,
        func.count(device_snapshot.c.device_id).label("device_count"),
    ).group_by(
        device_snapshot.c.version_code
    ).order_by(
        func.count(device_snapshot.c.device_id).desc()
    ).all()
    
    # 转换版本码为版本名
    version_distribution = []
    version_map = {}
    versions = db.query(AppVersion.version_code, AppVersion.version_name).all()
    for v in versions:
        version_map[v.version_code] = v.version_name
    
    for vc, count in version_dist:
        version_name = version_map.get(vc, f"v{vc // 10000}.{(vc % 10000) // 100}.{vc % 100}")
        version_distribution.append({
            "version_code": vc,
            "version_name": version_name,
            "device_count": count
        })
    
    # 每日活跃趋势
    daily_trend = db.query(
        AppVersionUsageLog.logged_date,
        func.count(distinct(AppVersionUsageLog.device_id)).label("device_count")
    ).filter(
        AppVersionUsageLog.logged_date >= start_date_str
    ).group_by(
        AppVersionUsageLog.logged_date
    ).order_by(AppVersionUsageLog.logged_date).all()
    
    daily_active_trend = [{"date": d, "count": c} for d, c in daily_trend]
    
    # 设备品牌分布
    brand_dist = db.query(
        device_snapshot.c.device_brand,
        func.count(device_snapshot.c.device_id).label("device_count")
    ).filter(
        device_snapshot.c.device_brand.isnot(None)
    ).group_by(
        device_snapshot.c.device_brand
    ).order_by(
        func.count(device_snapshot.c.device_id).desc()
    ).limit(10).all()
    
    brand_distribution = [{"brand": b or "Unknown", "count": c} for b, c in brand_dist]
    
    # 系统版本分布
    os_dist = db.query(
        device_snapshot.c.os_version,
        func.count(device_snapshot.c.device_id).label("device_count")
    ).filter(
        device_snapshot.c.os_version.isnot(None)
    ).group_by(
        device_snapshot.c.os_version
    ).order_by(
        func.count(device_snapshot.c.device_id).desc()
    ).limit(10).all()
    
    os_distribution = [{"os_version": os or "Unknown", "count": c} for os, c in os_dist]
    
    return {
        "summary": {
            "total_devices": total_devices,
            "dau": dau,
            "wau": wau,
            "mau": mau
        },
        "version_distribution": version_distribution,
        "daily_active_trend": daily_active_trend,
        "brand_distribution": brand_distribution,
        "os_distribution": os_distribution
    }


# ============ Release Notes API ============

# Release Notes 图片上传目录
RELEASE_NOTES_IMAGE_DIR = "uploads/release-notes"
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGES_PER_ITEM = 10


def _ensure_release_notes_image_dir():
    """确保Release Notes图片上传目录存在"""
    if not os.path.exists(RELEASE_NOTES_IMAGE_DIR):
        os.makedirs(RELEASE_NOTES_IMAGE_DIR)

def _normalize_release_note_item_images(item_data) -> list:
    """
    统一处理单图/多图输入，输出可存储的 images 列表（按 sort_order 排序并重排为 0..n-1）。
    item_data: ReleaseNoteItemCreate / ReleaseNoteItemBase
    """
    images = []

    # 优先使用新字段 images
    raw_images = getattr(item_data, "images", None) or []
    for img in raw_images:
        image_url = getattr(img, "image_url", None)
        if not image_url:
            continue
        images.append({
            "sort_order": int(getattr(img, "sort_order", 0) or 0),
            "image_url": image_url,
            "image_caption": getattr(img, "image_caption", None),
            "image_caption_en": getattr(img, "image_caption_en", None),
        })

    # 兼容旧字段 image_url
    if not images and getattr(item_data, "image_url", None):
        images = [{
            "sort_order": 0,
            "image_url": item_data.image_url,
            "image_caption": getattr(item_data, "image_caption", None),
            "image_caption_en": getattr(item_data, "image_caption_en", None),
        }]

    if len(images) > MAX_IMAGES_PER_ITEM:
        raise HTTPException(status_code=400, detail=f"每个更新项目最多支持{MAX_IMAGES_PER_ITEM}张图片")

    images.sort(key=lambda x: x.get("sort_order", 0))
    for i, img in enumerate(images):
        img["sort_order"] = i
    return images

def _parse_release_note_item_images(item: AppVersionReleaseNoteItem) -> list:
    """从数据库解析多图信息；若无则兼容旧字段单图。"""
    images = []
    if getattr(item, "images_json", None):
        try:
            parsed = json.loads(item.images_json)
            if isinstance(parsed, list):
                for img in parsed:
                    if not isinstance(img, dict):
                        continue
                    image_url = img.get("image_url")
                    if not image_url:
                        continue
                    images.append({
                        "sort_order": int(img.get("sort_order", 0) or 0),
                        "image_url": image_url,
                        "image_caption": img.get("image_caption"),
                        "image_caption_en": img.get("image_caption_en"),
                    })
        except Exception:
            images = []

    # fallback to legacy fields
    if not images and getattr(item, "image_url", None):
        images = [{
            "sort_order": 0,
            "image_url": item.image_url,
            "image_caption": getattr(item, "image_caption", None),
            "image_caption_en": getattr(item, "image_caption_en", None),
        }]

    images.sort(key=lambda x: x.get("sort_order", 0))
    for i, img in enumerate(images):
        img["sort_order"] = i
    return images


@router.post("/release-notes", response_model=ReleaseNoteResponse)
async def create_release_note(
    data: ReleaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建Release Note（管理员）"""
    _check_admin(current_user)
    
    # 检查版本是否存在
    version = db.query(AppVersion).filter(AppVersion.id == data.version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    # 检查是否已存在Release Note
    existing = db.query(AppVersionReleaseNote).filter(
        AppVersionReleaseNote.version_id == data.version_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该版本已存在Release Note，请使用更新接口")
    
    # 创建Release Note
    release_note = AppVersionReleaseNote(
        version_id=data.version_id,
        title=data.title,
        title_en=data.title_en,
        subtitle=data.subtitle,
        subtitle_en=data.subtitle_en,
        is_enabled=data.is_enabled
    )
    db.add(release_note)
    db.flush()  # 获取ID但不提交
    
    # 创建Release Note Items
    for item_data in data.items:
        images = _normalize_release_note_item_images(item_data)
        first_image = images[0] if images else {}
        images_json = json.dumps(images, ensure_ascii=False) if images else None
        item = AppVersionReleaseNoteItem(
            release_note_id=release_note.id,
            sort_order=item_data.sort_order,
            item_type=item_data.item_type,
            content=item_data.content,
            content_en=item_data.content_en,
            image_url=first_image.get("image_url"),
            image_caption=first_image.get("image_caption"),
            image_caption_en=first_image.get("image_caption_en"),
            images_json=images_json
        )
        db.add(item)
    
    db.commit()
    db.refresh(release_note)
    
    # 查询items
    items = db.query(AppVersionReleaseNoteItem).filter(
        AppVersionReleaseNoteItem.release_note_id == release_note.id
    ).order_by(AppVersionReleaseNoteItem.sort_order).all()
    
    return ReleaseNoteResponse(
        id=release_note.id,
        version_id=release_note.version_id,
        title=release_note.title,
        title_en=release_note.title_en,
        subtitle=release_note.subtitle,
        subtitle_en=release_note.subtitle_en,
        is_enabled=release_note.is_enabled,
        items=[{
            "id": item.id,
            "release_note_id": item.release_note_id,
            "sort_order": item.sort_order,
            "item_type": item.item_type,
            "content": item.content,
            "content_en": item.content_en,
            "image_url": item.image_url,
            "image_caption": item.image_caption,
            "image_caption_en": item.image_caption_en,
            "images": _parse_release_note_item_images(item),
            "created_at": item.created_at
        } for item in items],
        created_at=release_note.created_at,
        updated_at=release_note.updated_at
    )


@router.get("/release-notes/{version_id}", response_model=ReleaseNoteResponse)
async def get_release_note(
    version_id: int,
    req: Request,
    db: Session = Depends(get_db)
):
    """获取版本的Release Note

    - 已发布且启用：公开可访问
    - 草稿版本或禁用：仅管理员（携带 Bearer Token）可访问
    """
    version = db.query(AppVersion).filter(AppVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Release Note不存在")

    token_user = _try_get_access_user(req, db)
    is_admin = bool(token_user and token_user.role == "admin")

    release_note = db.query(AppVersionReleaseNote).filter(
        AppVersionReleaseNote.version_id == version_id
    ).first()
    
    if not release_note:
        raise HTTPException(status_code=404, detail="Release Note不存在")

    if not is_admin:
        if not version.is_active:
            raise HTTPException(status_code=404, detail="Release Note不存在")
        if not release_note.is_enabled:
            raise HTTPException(status_code=404, detail="Release Note不存在")
    
    # 查询items
    items = db.query(AppVersionReleaseNoteItem).filter(
        AppVersionReleaseNoteItem.release_note_id == release_note.id
    ).order_by(AppVersionReleaseNoteItem.sort_order).all()
    
    return ReleaseNoteResponse(
        id=release_note.id,
        version_id=release_note.version_id,
        title=release_note.title,
        title_en=release_note.title_en,
        subtitle=release_note.subtitle,
        subtitle_en=release_note.subtitle_en,
        is_enabled=release_note.is_enabled,
        items=[{
            "id": item.id,
            "release_note_id": item.release_note_id,
            "sort_order": item.sort_order,
            "item_type": item.item_type,
            "content": item.content,
            "content_en": item.content_en,
            "image_url": item.image_url,
            "image_caption": item.image_caption,
            "image_caption_en": item.image_caption_en,
            "images": _parse_release_note_item_images(item),
            "created_at": item.created_at
        } for item in items],
        created_at=release_note.created_at,
        updated_at=release_note.updated_at
    )


@router.put("/release-notes/{release_note_id}", response_model=ReleaseNoteResponse)
async def update_release_note(
    release_note_id: int,
    data: ReleaseNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新Release Note（管理员）"""
    _check_admin(current_user)
    
    release_note = db.query(AppVersionReleaseNote).filter(
        AppVersionReleaseNote.id == release_note_id
    ).first()
    
    if not release_note:
        raise HTTPException(status_code=404, detail="Release Note不存在")
    
    # 更新基本字段
    if data.title is not None:
        release_note.title = data.title
    if data.title_en is not None:
        release_note.title_en = data.title_en
    if data.subtitle is not None:
        release_note.subtitle = data.subtitle
    if data.subtitle_en is not None:
        release_note.subtitle_en = data.subtitle_en
    if data.is_enabled is not None:
        release_note.is_enabled = data.is_enabled
    
    # 如果提供了items，重新创建
    if data.items is not None:
        # 删除旧的items
        db.query(AppVersionReleaseNoteItem).filter(
            AppVersionReleaseNoteItem.release_note_id == release_note_id
        ).delete()
        
        # 创建新的items
        for item_data in data.items:
            images = _normalize_release_note_item_images(item_data)
            first_image = images[0] if images else {}
            images_json = json.dumps(images, ensure_ascii=False) if images else None
            item = AppVersionReleaseNoteItem(
                release_note_id=release_note_id,
                sort_order=item_data.sort_order,
                item_type=item_data.item_type,
                content=item_data.content,
                content_en=item_data.content_en,
                image_url=first_image.get("image_url"),
                image_caption=first_image.get("image_caption"),
                image_caption_en=first_image.get("image_caption_en"),
                images_json=images_json
            )
            db.add(item)
    
    db.commit()
    db.refresh(release_note)
    
    # 查询items
    items = db.query(AppVersionReleaseNoteItem).filter(
        AppVersionReleaseNoteItem.release_note_id == release_note.id
    ).order_by(AppVersionReleaseNoteItem.sort_order).all()
    
    return ReleaseNoteResponse(
        id=release_note.id,
        version_id=release_note.version_id,
        title=release_note.title,
        title_en=release_note.title_en,
        subtitle=release_note.subtitle,
        subtitle_en=release_note.subtitle_en,
        is_enabled=release_note.is_enabled,
        items=[{
            "id": item.id,
            "release_note_id": item.release_note_id,
            "sort_order": item.sort_order,
            "item_type": item.item_type,
            "content": item.content,
            "content_en": item.content_en,
            "image_url": item.image_url,
            "image_caption": item.image_caption,
            "image_caption_en": item.image_caption_en,
            "images": _parse_release_note_item_images(item),
            "created_at": item.created_at
        } for item in items],
        created_at=release_note.created_at,
        updated_at=release_note.updated_at
    )


@router.delete("/release-notes/{release_note_id}")
async def delete_release_note(
    release_note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除Release Note（管理员）"""
    _check_admin(current_user)
    
    release_note = db.query(AppVersionReleaseNote).filter(
        AppVersionReleaseNote.id == release_note_id
    ).first()
    
    if not release_note:
        raise HTTPException(status_code=404, detail="Release Note不存在")
    
    # 删除关联的items
    db.query(AppVersionReleaseNoteItem).filter(
        AppVersionReleaseNoteItem.release_note_id == release_note_id
    ).delete()
    
    # 删除Release Note
    db.delete(release_note)
    db.commit()
    
    return {"message": "Release Note已删除", "id": release_note_id}


@router.post("/release-notes/upload-image", response_model=ReleaseNoteImageUploadResponse)
async def upload_release_note_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传Release Note图片（管理员）
    
    - 支持 jpg, jpeg, png, gif, webp 格式
    - 最大 5MB
    """
    _check_admin(current_user)
    
    # 验证文件类型
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="只支持 jpg, jpeg, png, gif, webp 格式的图片")
    
    _ensure_release_notes_image_dir()
    
    # 读取文件内容
    content = await file.read()
    file_size = len(content)
    
    # 检查文件大小
    if file_size > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"图片大小不能超过 {MAX_IMAGE_SIZE // (1024*1024)}MB")
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(file.filename)[1].lower()
    safe_filename = f"rn_{timestamp}_{hashlib.md5(content[:1024]).hexdigest()[:8]}{ext}"
    file_path = os.path.join(RELEASE_NOTES_IMAGE_DIR, safe_filename)
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    # 生成URL
    image_url = f"/uploads/release-notes/{safe_filename}"
    
    return ReleaseNoteImageUploadResponse(
        image_url=image_url,
        file_name=safe_filename,
        file_size=file_size
    )
