from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class MobileClientLog(Base):
    """
    移动端（UniApp）运行日志

    用途：
    - 收集移动端（UniApp）console 日志（uni.__log__/console.*），便于 web-admin 历史查询与排障
    - 保留部分请求字段仅用于兼容历史数据（移动端已不再上报 request 日志）
    """

    __tablename__ = "mobile_client_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 客户端上报的时间（以客户端为准，可能存在偏差）
    occurred_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # 服务端入库时间（用于保留/清理等策略）
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    level = Column(String(10), nullable=False, index=True)  # DEBUG/INFO/WARN/ERROR
    tag = Column(String(100), nullable=True, index=True)
    message = Column(Text, nullable=False)

    route = Column(String(255), nullable=True, index=True)

    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)

    device_id = Column(String(80), nullable=True, index=True)
    app_version_name = Column(String(50), nullable=True, index=True)
    app_version_code = Column(Integer, nullable=True, index=True)
    platform = Column(String(50), nullable=True, index=True)
    network_type = Column(String(50), nullable=True, index=True)
    env = Column(String(20), nullable=True, index=True)

    # 结构化请求信息（便于筛选）
    api_url = Column(String(500), nullable=True, index=True)
    api_method = Column(String(10), nullable=True, index=True)
    api_status = Column(Integer, nullable=True, index=True)
    duration_ms = Column(Integer, nullable=True, index=True)
    error_msg = Column(Text, nullable=True)

    # 扩展上下文（保留原始对象，SQLite 下会以 TEXT 存储）
    context = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_mobile_client_logs_user_time", "user_id", "occurred_at"),
        Index("idx_mobile_client_logs_device_time", "device_id", "occurred_at"),
        Index("idx_mobile_client_logs_level_time", "level", "occurred_at"),
        Index("idx_mobile_client_logs_api_time", "api_status", "occurred_at"),
    )

    @property
    def at(self):
        """从 context 中提取 uni.__log__ 里的位置信息（例如：at App.vue:141）。"""
        try:
            ctx = getattr(self, "context", None)
            if isinstance(ctx, dict):
                value = ctx.get("at")
                if value is None:
                    return None
                return str(value)
        except Exception:
            return None
        return None
