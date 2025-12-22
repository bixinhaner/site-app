"""
App版本管理Pydantic模式
用于请求/响应数据验证
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Literal
from datetime import datetime


# ============ 基础模式 ============

class AppVersionBase(BaseModel):
    """版本基础信息"""
    version_name: str
    version_code: int
    update_type: Literal["force", "recommend", "silent"] = "recommend"
    release_notes: Optional[str] = None
    release_notes_en: Optional[str] = None
    min_version_code: int = 0
    gray_scale_percent: int = 100

    @validator('version_name')
    def validate_version_name(cls, v):
        """验证版本号格式 x.y.z"""
        parts = v.split('.')
        if len(parts) < 2 or len(parts) > 3:
            raise ValueError('版本号格式应为 x.y 或 x.y.z')
        for part in parts:
            if not part.isdigit():
                raise ValueError('版本号各部分必须为数字')
        return v

    @validator('gray_scale_percent')
    def validate_gray_scale(cls, v):
        if v < 0 or v > 100:
            raise ValueError('灰度百分比必须在0-100之间')
        return v


# ============ 版本检测 ============

class AppVersionCheckRequest(BaseModel):
    """版本检测请求"""
    current_version_code: int
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    device_brand: Optional[str] = None
    os_version: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_role: Optional[str] = None


class AppVersionInfo(BaseModel):
    """版本信息响应"""
    id: int
    version_name: str
    version_code: int
    update_type: str
    download_url: str
    file_size: int
    file_md5: Optional[str] = None
    release_notes: Optional[str] = None
    release_notes_en: Optional[str] = None
    show_release_notes: bool = False
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AppVersionCheckResponse(BaseModel):
    """版本检测响应"""
    has_update: bool
    update_type: Optional[str] = None
    version_info: Optional[AppVersionInfo] = None


# ============ 版本管理 (CRUD) ============

class AppVersionCreate(AppVersionBase):
    """创建版本"""
    download_url: str
    file_size: int = 0
    file_md5: Optional[str] = None
    file_name: Optional[str] = None
    is_active: bool = True
    show_release_notes: bool = False


class AppVersionUpdate(BaseModel):
    """更新版本"""
    version_name: Optional[str] = None
    update_type: Optional[Literal["force", "recommend", "silent"]] = None
    release_notes: Optional[str] = None
    release_notes_en: Optional[str] = None
    min_version_code: Optional[int] = None
    gray_scale_percent: Optional[int] = None
    is_active: Optional[bool] = None
    show_release_notes: Optional[bool] = None
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    file_md5: Optional[str] = None
    file_name: Optional[str] = None

    @validator('gray_scale_percent')
    def validate_gray_scale(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('灰度百分比必须在0-100之间')
        return v


class AppVersionResponse(AppVersionBase):
    """版本详情响应"""
    id: int
    download_url: str
    file_size: int
    file_md5: Optional[str] = None
    file_name: Optional[str] = None
    is_active: bool
    is_latest: bool
    show_release_notes: bool = False
    download_count: int
    install_count: int
    created_at: datetime
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AppVersionListResponse(BaseModel):
    """版本列表响应"""
    versions: List[AppVersionResponse]
    total: int


# ============ 下载统计 ============

class DownloadStartRequest(BaseModel):
    """下载开始请求"""
    version_id: int
    version_code: int
    from_version_code: int
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    device_brand: Optional[str] = None
    os_version: Optional[str] = None
    network_type: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_role: Optional[str] = None


class DownloadLogResponse(BaseModel):
    """下载日志响应"""
    id: int
    version_id: int
    version_code: int
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    device_brand: Optional[str] = None
    os_version: Optional[str] = None
    from_version_code: Optional[int] = None
    download_status: str
    download_progress: int
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    network_type: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_role: Optional[str] = None

    class Config:
        from_attributes = True


class DownloadLogListResponse(BaseModel):
    """下载日志列表响应"""
    logs: List[DownloadLogResponse]
    total: int


class DownloadCompleteRequest(BaseModel):
    """下载完成请求"""
    log_id: int
    status: Literal["completed", "failed"]
    error_message: Optional[str] = None


class DownloadStartResponse(BaseModel):
    """下载开始响应"""
    log_id: int
    message: str = "下载记录已创建"


# ============ 文件上传 ============

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_name: str
    file_size: int
    file_md5: str
    download_url: str


# ============ Release Notes ============

class ReleaseNoteItemBase(BaseModel):
    """Release Note项目基础"""
    sort_order: int = 0
    item_type: Literal["text", "image"] = "text"
    content: Optional[str] = None
    content_en: Optional[str] = None
    image_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_caption_en: Optional[str] = None


class ReleaseNoteItemCreate(ReleaseNoteItemBase):
    """创建Release Note项目"""
    pass


class ReleaseNoteItemResponse(ReleaseNoteItemBase):
    """Release Note项目响应"""
    id: int
    release_note_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReleaseNoteBase(BaseModel):
    """Release Note基础"""
    title: Optional[str] = None
    title_en: Optional[str] = None
    subtitle: Optional[str] = None
    subtitle_en: Optional[str] = None
    is_enabled: bool = True


class ReleaseNoteCreate(ReleaseNoteBase):
    """创建Release Note"""
    version_id: int
    items: List[ReleaseNoteItemCreate] = []


class ReleaseNoteUpdate(ReleaseNoteBase):
    """更新Release Note"""
    items: Optional[List[ReleaseNoteItemCreate]] = None


class ReleaseNoteResponse(ReleaseNoteBase):
    """Release Note响应"""
    id: int
    version_id: int
    items: List[ReleaseNoteItemResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReleaseNoteImageUploadResponse(BaseModel):
    """Release Note图片上传响应"""
    image_url: str
    file_name: str
    file_size: int
