"""
App版本管理API
提供版本检测、版本管理和文件上传功能
"""
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

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
    today = datetime.now().strftime("%Y-%m-%d")
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
            # 如果已有记录但没有用户信息，补充用户信息
            if request.user_id and not existing_log.user_id:
                existing_log.user_id = request.user_id
                existing_log.username = username_val
                existing_log.user_role = user_role_val
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
        user_id=request.user_id,
        username=request.username,
        user_role=request.user_role
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
        published_at=datetime.now() if version_data.is_active else None
    )
    
    # 如果是最新版本，更新is_latest标志
    latest = db.query(AppVersion).order_by(desc(AppVersion.version_code)).first()
    if not latest or version_data.version_code > latest.version_code:
        version.is_latest = True
        # 清除其他版本的is_latest标志
        db.query(AppVersion).filter(AppVersion.is_latest == True).update({"is_latest": False})
    
    db.add(version)
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
    for field, value in update_data.items():
        setattr(version, field, value)
    
    # 如果激活状态变更为True，设置发布时间
    if version_data.is_active is True and not version.published_at:
        version.published_at = datetime.now()
    
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
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    start_date = today - timedelta(days=days)
    
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
    
    # 版本分布（最近30天的活跃设备）
    version_dist = db.query(
        AppVersionUsageLog.version_code,
        func.count(distinct(AppVersionUsageLog.device_id)).label("device_count")
    ).filter(
        AppVersionUsageLog.logged_date >= month_ago
    ).group_by(
        AppVersionUsageLog.version_code
    ).order_by(desc("device_count")).all()
    
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
        AppVersionUsageLog.logged_date >= start_date.strftime("%Y-%m-%d")
    ).group_by(
        AppVersionUsageLog.logged_date
    ).order_by(AppVersionUsageLog.logged_date).all()
    
    daily_active_trend = [{"date": d, "count": c} for d, c in daily_trend]
    
    # 设备品牌分布
    brand_dist = db.query(
        AppVersionUsageLog.device_brand,
        func.count(distinct(AppVersionUsageLog.device_id)).label("device_count")
    ).filter(
        AppVersionUsageLog.logged_date >= month_ago,
        AppVersionUsageLog.device_brand.isnot(None)
    ).group_by(
        AppVersionUsageLog.device_brand
    ).order_by(desc("device_count")).limit(10).all()
    
    brand_distribution = [{"brand": b or "Unknown", "count": c} for b, c in brand_dist]
    
    # 系统版本分布
    os_dist = db.query(
        AppVersionUsageLog.os_version,
        func.count(distinct(AppVersionUsageLog.device_id)).label("device_count")
    ).filter(
        AppVersionUsageLog.logged_date >= month_ago,
        AppVersionUsageLog.os_version.isnot(None)
    ).group_by(
        AppVersionUsageLog.os_version
    ).order_by(desc("device_count")).limit(10).all()
    
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


def _ensure_release_notes_image_dir():
    """确保Release Notes图片上传目录存在"""
    if not os.path.exists(RELEASE_NOTES_IMAGE_DIR):
        os.makedirs(RELEASE_NOTES_IMAGE_DIR)


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
        item = AppVersionReleaseNoteItem(
            release_note_id=release_note.id,
            sort_order=item_data.sort_order,
            item_type=item_data.item_type,
            content=item_data.content,
            content_en=item_data.content_en,
            image_url=item_data.image_url,
            image_caption=item_data.image_caption,
            image_caption_en=item_data.image_caption_en
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
            "created_at": item.created_at
        } for item in items],
        created_at=release_note.created_at,
        updated_at=release_note.updated_at
    )


@router.get("/release-notes/{version_id}", response_model=ReleaseNoteResponse)
async def get_release_note(
    version_id: int,
    db: Session = Depends(get_db)
):
    """获取版本的Release Note（公开接口，无需登录）"""
    release_note = db.query(AppVersionReleaseNote).filter(
        AppVersionReleaseNote.version_id == version_id
    ).first()
    
    if not release_note:
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
            item = AppVersionReleaseNoteItem(
                release_note_id=release_note_id,
                sort_order=item_data.sort_order,
                item_type=item_data.item_type,
                content=item_data.content,
                content_en=item_data.content_en,
                image_url=item_data.image_url,
                image_caption=item_data.image_caption,
                image_caption_en=item_data.image_caption_en
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
