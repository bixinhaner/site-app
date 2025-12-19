from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.sql import func

from app.core.database import Base


class OperationLog(Base):
    """
    操作日志（功能动作级）

    目标：
    - 覆盖 web-admin / uniapp 的后端 API 操作
    - 记录可读描述 + 提交的变更值（请求参数/请求体）
    - 支持分页筛选、选择性清理与导出
    """

    __tablename__ = "operation_logs"

    id = Column(String(32), primary_key=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # 操作人
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)
    user_role = Column(String(50), nullable=True, index=True)

    # 来源端
    client = Column(String(50), nullable=True, index=True)  # web-admin / uniapp / unknown

    # 请求信息
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(255), nullable=True, index=True)
    query_params = Column(JSON, nullable=True)
    path_params = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)

    # 功能动作信息
    module = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=True, index=True)
    object_type = Column(String(100), nullable=True, index=True)
    object_id = Column(String(100), nullable=True, index=True)
    object_name = Column(String(255), nullable=True)
    operation_desc = Column(Text, nullable=True)

    # 结果
    status_code = Column(Integer, nullable=True, index=True)
    is_success = Column(Boolean, default=True, index=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_operation_logs_user_time", "user_id", "occurred_at"),
        Index("idx_operation_logs_module_action_time", "module", "action", "occurred_at"),
        Index("idx_operation_logs_object_time", "object_type", "object_id", "occurred_at"),
        Index("idx_operation_logs_client_time", "client", "occurred_at"),
    )

