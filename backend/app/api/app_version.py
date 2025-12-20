"""
App版本管理API
提供版本检测、版本管理和文件上传功能
"""
import os
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.user import User
from app.models.app_version import AppVersion, AppVersionDownloadLog
from app.schemas.app_version import (
    AppVersionCheckRequest, AppVersionCheckResponse, AppVersionInfo,
    AppVersionCreate, AppVersionUpdate, AppVersionResponse, AppVersionListResponse,
    DownloadStartRequest, DownloadCompleteRequest, DownloadStartResponse,
    FileUploadResponse
)

router = APIRouter()

# APK上传目录
APK_UPLOAD_DIR = "uploads/apk"


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
    db: Session = Depends(get_db)
):
    """检测App是否有新版本
    
    - 查询当前启用的最新版本
    - 比较版本号，判断是否需要更新
    - 检查灰度发布配置
    """
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
        ip_address=client_ip
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
    log.completed_at = datetime.now()
    
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
