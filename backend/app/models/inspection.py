from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class InspectionStatusEnum(str, enum.Enum):
    DRAFT = "draft"                    # 草稿
    IN_PROGRESS = "in_progress"        # 进行中
    SUBMITTED = "submitted"            # 已提交
    UNDER_REVIEW = "under_review"      # 审核中
    APPROVED = "approved"              # 已通过
    REJECTED = "rejected"              # 已驳回
    COMPLETED = "completed"            # 已完成
    VOIDED = "voided"                  # 已作废

class InspectionTypeEnum(str, enum.Enum):
    OPENING = "OPENING"               # 新站点设备安装
    MAINTENANCE = "MAINTENANCE"        # 维护检查

class TaskTypeEnum(str, enum.Enum):
    OPENING_INSPECTION = "opening_inspection"
    MAINTENANCE = "maintenance"
    POWER_ISSUE = "power_issue"
    TRANSMISSION_ISSUE = "transmission_issue"
    GPS_ISSUE = "gps_issue"
    SIGNAL_ISSUE = "signal_issue"

class BaseStationStatusEnum(str, enum.Enum):
    OFFLINE = "offline"               # 未开通
    ONLINE = "online"                 # 开通未激活
    ACTIVATED = "activated"           # 开通激活

class CheckItemStatusEnum(str, enum.Enum):
    PENDING = "pending"               # 待处理
    IN_PROGRESS = "in_progress"       # 进行中
    COMPLETED = "completed"           # 已完成
    FAILED = "failed"                # 失败
    SKIPPED = "skipped"              # 跳过

class InspectionTemplate(Base):
    """检查模板表"""
    __tablename__ = "inspection_templates"
    
    id = Column(String(32), primary_key=True)
    template_name = Column(String(100), nullable=False)
    template_data = Column(JSON, nullable=False)  # 存储完整的检查模板JSON
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    inspections = relationship("SiteInspection", back_populates="template")
    bindings = relationship("TemplateBinding", back_populates="template", cascade="all, delete-orphan")

class TemplateBinding(Base):
    """模板绑定表"""
    __tablename__ = "template_bindings"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(32), ForeignKey("inspection_templates.id"), nullable=False)
    
    # 条件维度字段（可空，多维组合）
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    site_type = Column(String(50), nullable=True)  # macro, micro, indoor, etc.
    task_type = Column(Enum(TaskTypeEnum), nullable=True)  # 任务类型
    region = Column(String(100), nullable=True)
    customer = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)  # 数组[str]
    
    # 绑定配置
    priority = Column(Integer, default=50)  # 数值越大优先级越高
    active = Column(Boolean, default=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # 系统字段
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    template = relationship("InspectionTemplate", back_populates="bindings")
    site = relationship("Site", foreign_keys=[site_id])
    creator = relationship("User", foreign_keys=[created_by])

class SiteInspection(Base):
    """站点检查记录表"""
    __tablename__ = "site_inspections"
    
    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    work_order_id = Column(String(32), ForeignKey("work_orders.id"), nullable=True)  # 关联工单ID
    template_id = Column(String(32), ForeignKey("inspection_templates.id"), nullable=False)
    applied_template_revision = Column(Integer, nullable=False, default=1, server_default="1")
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 检查基本信息
    inspection_type = Column(Enum(InspectionTypeEnum), default=InspectionTypeEnum.OPENING)
    status = Column(Enum(InspectionStatusEnum), default=InspectionStatusEnum.DRAFT)
    
    # 时间信息
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    submitted_at = Column(DateTime)
    
    # 位置信息
    location = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    gps_accuracy = Column(Float)  # GPS精度（米）
    address = Column(Text)  # 逆地理编码地址
    
    # 环境信息
    weather = Column(String(50))
    temperature = Column(String(20))
    
    # 检查结果
    completion_rate = Column(Float, default=0)  # 完成率（百分比）
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    # 评分和审核
    score = Column(Float)  # 质量评分（0-100）
    result = Column(String(20))  # pass, fail, warning
    
    # 审核信息
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    review_comments = Column(Text)
    review_comments_i18n = Column(JSON)
    
    # 备注
    notes = Column(Text)
    issues_found = Column(Text)
    recommendations = Column(Text)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    site = relationship("Site")
    work_order = relationship("WorkOrder", foreign_keys=[work_order_id])  # 关联的工单
    template = relationship("InspectionTemplate", back_populates="inspections")
    inspector = relationship("User", foreign_keys=[inspector_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    check_items = relationship("InspectionCheckItem", back_populates="inspection", cascade="all, delete-orphan")
    photos = relationship("InspectionPhoto", back_populates="inspection", cascade="all, delete-orphan")

class InspectionCheckItem(Base):
    """检查项记录表"""
    __tablename__ = "inspection_check_items"
    
    id = Column(String(32), primary_key=True)
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), nullable=False)
    
    # 检查项信息
    item_id = Column(String(50), nullable=False)  # 对应模板中的item_id
    template_item_id = Column(String(50), nullable=True)  # 对应模板中的基础 item_id（不带 sector/cell 后缀）
    item_name = Column(String(200), nullable=False)
    description = Column(Text)  # 检查项描述，用于说明填写要求和示例
    category_id = Column(String(50))  # site_level, sector_level
    category_name = Column(String(100))
    
    # 小区信息（支持小区级检查）
    sector_id = Column(String(10))  # 扇区编号
    band = Column(String(20))       # 频段，如 n41, n78, n3
    cell_id = Column(String(20))    # 小区ID，格式：sector_band (如: 1_n41, 2_n78)
    equipment_sn = Column(String(100))  # 绑定的设备序列号
    
    # 检查类型和状态
    required_type = Column(String(20))  # photo, data, both
    status = Column(Enum(CheckItemStatusEnum), default=CheckItemStatusEnum.PENDING)
    
    # 检查数据
    data_value = Column(JSON)  # 存储填写的数据
    validation_result = Column(JSON)  # 验证结果
    fields = Column(JSON)  # 字段配置（从模板继承）
    notes = Column(Text)  # 检查项备注（前端填写，需持久化）
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    removed_by_template = Column(Boolean, nullable=False, default=False, server_default="0")
    removed_at = Column(DateTime)
    
    # 检查人员和时间
    checked_by = Column(Integer, ForeignKey("users.id"))
    checked_at = Column(DateTime)
    
    # 审核信息
    review_status = Column(String(20))  # pass, fail, warning
    review_comments = Column(Text)
    review_comments_i18n = Column(JSON)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)

    # AI 检查（建议项；需人工确认采纳后才写回审核结果）
    ai_status = Column(String(20))  # none, queued, running, done, failed, canceled
    ai_mode = Column(String(10))  # auto, text, vision
    ai_model = Column(String(100))
    ai_input_hash = Column(String(64))
    ai_result = Column(JSON)
    ai_error = Column(Text)
    ai_checked_by = Column(Integer, ForeignKey("users.id"))
    ai_checked_at = Column(DateTime)
    ai_applied_by = Column(Integer, ForeignKey("users.id"))
    ai_applied_at = Column(DateTime)
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    inspection = relationship("SiteInspection", back_populates="check_items")
    checker = relationship("User", foreign_keys=[checked_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    photos = relationship("InspectionPhoto", back_populates="check_item")

class InspectionPhoto(Base):
    """检查照片表"""
    __tablename__ = "inspection_photos"
    
    id = Column(String(32), primary_key=True)
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), nullable=False)
    check_item_id = Column(String(32), ForeignKey("inspection_check_items.id"))
    # 字段级照片归属：对应检查项 fields 中的 field_id；无 dataFields 的检查项可为空
    field_id = Column(String(100))
    
    # 照片信息
    original_name = Column(String(255))
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # GPS信息
    latitude = Column(Float)
    longitude = Column(Float)
    gps_accuracy = Column(Float)
    address = Column(Text)
    
    # 拍摄信息
    taken_at = Column(DateTime, nullable=False)
    camera_info = Column(JSON)  # 相机参数信息
    
    # 水印和验证
    content_hash = Column(String(64))  # 实际上传文件哈希（通常为加水印后的文件）
    original_content_hash = Column(String(64))  # 原图哈希（APP 预检票据链路）
    content_phash = Column(String(16))  # 内容感知哈希（用于相似图片识别）
    content_vector = Column(JSON)  # 内容向量（用于相似图片二次判定）
    content_vector_backend = Column(String(32))  # 向量后端：clip / fallback
    has_watermark = Column(Boolean, default=False)
    watermark_data = Column(JSON)  # 水印信息
    hash_value = Column(String(64))  # 文件哈希值，用于防篡改
    digital_signature = Column(Text)  # 数字签名
    is_duplicate_global = Column(Boolean, default=False)  # 是否命中“全局重复图片”
    duplicate_info = Column(JSON)  # 全局重复提示信息（首次上传来源）
    is_similar_risk = Column(Boolean, default=False)  # 是否命中“高相似风险”
    similar_info = Column(JSON)  # 高相似风险来源信息
    
    # 审核状态
    review_status = Column(String(20))  # approved, rejected, pending
    review_comments = Column(Text)
    
    # 上传信息
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    upload_ip = Column(String(45))
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    inspection = relationship("SiteInspection", back_populates="photos")
    check_item = relationship("InspectionCheckItem", back_populates="photos")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class GlobalPhotoHashRegistry(Base):
    """检查项照片全局哈希首传索引（仅记录首次上传）。"""

    __tablename__ = "global_photo_hash_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String(64), index=True, nullable=False)

    source_type = Column(String(50), nullable=False)  # inspection_photo / *_archive_photo / *_archive_temp_photo
    source_id = Column(String(64), nullable=False)

    site_id = Column(Integer, ForeignKey("sites.id"), index=True)
    site_name = Column(String(100))

    uploader_id = Column(Integer, ForeignKey("users.id"))
    uploader_name = Column(String(100))
    uploaded_at = Column(DateTime, server_default=func.now(), index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    site = relationship("Site")
    uploader = relationship("User", foreign_keys=[uploader_id])

class InspectionAuditLog(Base):
    """检查审核日志表"""
    __tablename__ = "inspection_audit_logs"
    
    id = Column(String(32), primary_key=True)
    inspection_id = Column(String(32), ForeignKey("site_inspections.id"), nullable=False)
    
    # 操作信息
    action = Column(String(50), nullable=False)  # submit, approve, reject, update
    from_status = Column(String(20))
    to_status = Column(String(20))
    
    # 操作人员
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operator_ip = Column(String(45))
    
    # 操作详情
    comments = Column(Text)
    details = Column(JSON)  # 详细的操作数据
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    inspection = relationship("SiteInspection")
    operator = relationship("User")

class BaseStationDevice(Base):
    """基站设备表"""
    __tablename__ = "base_station_devices"
    
    id = Column(String(32), primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # 设备信息
    device_name = Column(String(100), nullable=False)  # 设备名称
    device_type = Column(String(50), nullable=False)   # 设备类型
    device_model = Column(String(100))                 # 设备型号
    device_sn = Column(String(100))                    # 设备序列号
    
    # 设备状态
    status = Column(Enum(BaseStationStatusEnum), default=BaseStationStatusEnum.OFFLINE)
    
    # OMC系统相关
    omc_device_id = Column(String(100))                # OMC系统中的设备ID
    last_online_time = Column(DateTime)                # 最后上线时间
    last_activated_time = Column(DateTime)             # 最后激活时间
    last_sync_time = Column(DateTime)                  # 最后同步时间
    
    # 设备配置
    frequency_bands = Column(JSON)                     # 频段配置
    power_config = Column(JSON)                        # 功率配置
    network_config = Column(JSON)                      # 网络配置
    
    # 维护信息
    maintenance_notes = Column(Text)                   # 维护记录
    issues_history = Column(JSON)                     # 问题历史
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    site = relationship("Site")


class OMCSystemLog(Base):
    """OMC系统同步日志表"""
    __tablename__ = "omc_system_logs"
    
    id = Column(String(32), primary_key=True)
    
    # 操作信息
    operation_type = Column(String(50), nullable=False)  # sync_status, query_device, update_config
    operation_target = Column(String(100))               # 操作目标（设备ID等）
    
    # 请求和响应
    request_data = Column(JSON)                          # 请求数据
    response_data = Column(JSON)                         # 响应数据
    
    # 结果
    is_success = Column(Boolean, default=False)
    error_message = Column(Text)
    response_time = Column(Integer)                      # 响应时间（毫秒）
    
    # 操作人员
    operator_id = Column(Integer, ForeignKey("users.id"))
    operator_ip = Column(String(45))
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    operator = relationship("User")

class OfflineInspectionData(Base):
    """离线检查数据表（用于数据同步）"""
    __tablename__ = "offline_inspection_data"
    
    id = Column(String(32), primary_key=True)
    device_id = Column(String(100), nullable=False)  # 设备标识
    local_id = Column(String(100), nullable=False)   # 本地记录ID
    
    # 数据类型
    data_type = Column(String(50))  # inspection, check_item, photo
    data_content = Column(JSON, nullable=False)  # 离线数据内容
    
    # 同步状态
    sync_status = Column(String(20), default="pending")  # pending, synced, failed
    sync_attempts = Column(Integer, default=0)
    last_sync_attempt = Column(DateTime)
    sync_error = Column(Text)
    
    # 用户信息
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # 系统字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User")


# 保持向后兼容的原始Inspection模型
class Inspection(Base):
    __tablename__ = "inspections"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    inspection_type = Column(String(50))  # routine, emergency, maintenance
    status = Column(String(20), default="pending")  # pending, in_progress, completed, failed
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(String(255))
    latitude = Column(String(20))
    longitude = Column(String(20))
    weather = Column(String(50))
    temperature = Column(String(20))
    notes = Column(Text)
    photos = Column(JSON)  # 存储照片路径数组
    equipment_status = Column(JSON)  # 设备状态检查结果
    safety_check = Column(JSON)  # 安全检查结果
    result = Column(String(20))  # pass, fail, warning
    issues_found = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    site = relationship("Site")
    inspector = relationship("User")
