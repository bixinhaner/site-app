from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class AiCallLog(Base):
    """AI 调用日志（用于监控/统计/审计）。"""

    __tablename__ = "ai_call_logs"

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # 业务维度
    operation = Column(String(50), nullable=False, index=True)  # translate, check_item_analyze, ...
    mode = Column(String(10), nullable=False, index=True)  # text, vision
    model = Column(String(100), nullable=True, index=True)
    base_url = Column(String(255), nullable=True)

    # 结果
    success = Column(Boolean, default=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # 过程数据（可用于复盘）
    request_messages = Column(JSON, nullable=True)  # 保存 prompt（支持多模态，图片 URL 会脱敏）
    request_input = Column(JSON, nullable=True)  # 原始输入（如检查项字段/照片元数据、翻译入参等）
    response_content = Column(Text, nullable=True)  # 模型输出 content（原始）
    response_raw = Column(JSON, nullable=True)  # 原始响应 JSON
    error = Column(Text, nullable=True)

    # 关联上下文（如 check_item_id / inspection_id 等）
    context = Column(JSON, nullable=True)

