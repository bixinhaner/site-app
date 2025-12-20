"""
App版本管理数据模型
用于App升级系统的版本信息存储
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger
from sqlalchemy.sql import func
from app.core.database import Base


class AppVersion(Base):
    """App版本信息表"""
    __tablename__ = "app_versions"

    id = Column(Integer, primary_key=True, index=True)
    
    # 版本信息
    version_name = Column(String(20), nullable=False, comment="版本号，如 1.2.0")
    version_code = Column(Integer, nullable=False, index=True, comment="版本数字码，如 10200")
    
    # 更新类型: force(强制), recommend(推荐), silent(静默)
    update_type = Column(String(20), default="recommend", comment="更新类型")
    
    # 文件信息
    download_url = Column(String(500), nullable=False, comment="APK下载URL")
    file_size = Column(BigInteger, default=0, comment="文件大小(字节)")
    file_md5 = Column(String(32), comment="文件MD5校验值")
    file_name = Column(String(255), comment="原始文件名")
    
    # 更新说明
    release_notes = Column(Text, comment="更新日志")
    release_notes_en = Column(Text, comment="更新日志(英文)")
    
    # 版本控制
    min_version_code = Column(Integer, default=0, comment="最低兼容版本码")
    
    # 灰度发布
    gray_scale_percent = Column(Integer, default=100, comment="灰度发布百分比(0-100)")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_latest = Column(Boolean, default=False, comment="是否为最新版本")
    
    # 统计
    download_count = Column(Integer, default=0, comment="下载次数")
    install_count = Column(Integer, default=0, comment="安装次数")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    published_at = Column(DateTime, comment="发布时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AppVersion(id={self.id}, version={self.version_name}, code={self.version_code})>"


class AppVersionDownloadLog(Base):
    """App版本下载日志表"""
    __tablename__ = "app_version_download_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    version_id = Column(Integer, index=True, comment="版本ID")
    version_code = Column(Integer, comment="版本码")
    
    # 设备信息
    device_id = Column(String(100), comment="设备唯一标识")
    device_model = Column(String(100), comment="设备型号")
    device_brand = Column(String(50), comment="设备品牌")
    os_version = Column(String(20), comment="系统版本")
    
    # 下载信息
    from_version_code = Column(Integer, comment="升级前版本码")
    download_status = Column(String(20), default="started", comment="下载状态: started/completed/failed")
    download_progress = Column(Integer, default=0, comment="下载进度")
    error_message = Column(Text, comment="错误信息")
    
    # 网络信息
    ip_address = Column(String(50), comment="IP地址")
    network_type = Column(String(20), comment="网络类型: wifi/4g/5g")
    
    # 时间戳
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    def __repr__(self):
        return f"<AppVersionDownloadLog(id={self.id}, version_id={self.version_id}, status={self.download_status})>"
