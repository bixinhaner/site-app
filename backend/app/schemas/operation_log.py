from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.utils.timezone import to_utc_iso


class OperationLogItem(BaseModel):
    id: str
    occurred_at: datetime

    user_id: Optional[int] = None
    username: Optional[str] = None
    user_role: Optional[str] = None

    client: Optional[str] = None
    ip: Optional[str] = None

    module: Optional[str] = None
    action: Optional[str] = None

    object_type: Optional[str] = None
    object_id: Optional[str] = None
    object_name: Optional[str] = None

    status_code: Optional[int] = None
    is_success: bool = True
    operation_desc: Optional[str] = None

    @field_serializer("occurred_at")
    def _serialize_occurred_at(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class OperationLogDetail(OperationLogItem):
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    path_params: Optional[Dict[str, Any]] = None
    request_body: Optional[Any] = None
    error_message: Optional[str] = None


class OperationLogPageResponse(BaseModel):
    items: List[OperationLogItem]
    total: int
    page: int
    page_size: int


class OperationLogOptionsResponse(BaseModel):
    modules: List[str] = []
    actions: List[str] = []
    clients: List[str] = []


class OperationLogSettings(BaseModel):
    retention_days: int = Field(90, ge=1, le=3650)


class OperationLogCleanupPayload(BaseModel):
    retention_days: Optional[int] = Field(None, ge=1, le=3650)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    module: Optional[str] = None
    action: Optional[str] = None
    client: Optional[str] = None
    user_id: Optional[int] = None
    is_success: Optional[bool] = None
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    keyword: Optional[str] = None


class OperationLogTrackPayload(BaseModel):
    """前端/客户端上报的“功能动作/轨迹”日志（方案A：不记录普通GET）。"""

    module: Optional[str] = Field(None, max_length=100)
    action: str = Field(..., min_length=1, max_length=100)

    object_type: Optional[str] = Field(None, max_length=100)
    object_id: Optional[str] = Field(None, max_length=100)
    object_name: Optional[str] = Field(None, max_length=255)

    # 可选：完全自定义可读描述
    operation_desc: Optional[str] = None

    # 记录筛选条件/提交变更值等
    data: Optional[Any] = None

    # 可选：由客户端传入动作结果（例如导出失败）
    is_success: Optional[bool] = True
    error_message: Optional[str] = Field(None, max_length=2000)
