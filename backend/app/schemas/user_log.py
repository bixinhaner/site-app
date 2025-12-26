"""
用户日志相关的Pydantic模型
"""

from pydantic import BaseModel, field_serializer
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.utils.timezone import to_utc_iso


class UserLogCreate(BaseModel):
    """创建用户日志的请求模型"""
    session_id: str
    timestamp: str  # ISO格式时间字符串
    action: str
    level: str = "INFO"
    user: Optional[Dict[str, Any]] = None
    page: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    device_info: Optional[Dict[str, Any]] = None


class UserLogBatchCreate(BaseModel):
    """批量创建用户日志的请求模型"""
    logs: List[UserLogCreate]


class UserLogResponse(BaseModel):
    """用户日志响应模型"""
    id: int
    session_id: str
    user_id: Optional[int]
    username: Optional[str]
    timestamp: datetime
    action: str
    level: str
    page_route: Optional[str]
    page_options: Optional[Dict[str, Any]]
    action_data: Optional[Dict[str, Any]]
    device_platform: Optional[str]
    device_model: Optional[str]
    screen_width: Optional[int]
    screen_height: Optional[int]
    error_message: Optional[str]
    error_stack: Optional[str]
    error_context: Optional[Dict[str, Any]]
    created_at: datetime

    @field_serializer('timestamp', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class UserLogFilter(BaseModel):
    """用户日志查询过滤器"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    action: Optional[str] = None
    level: Optional[str] = None
    page_route: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class UserLogStats(BaseModel):
    """用户日志统计信息"""
    total_logs: int
    total_sessions: int
    total_users: int
    action_counts: Dict[str, int]
    level_counts: Dict[str, int]
    hourly_activity: Dict[str, int]
    top_pages: List[Dict[str, Any]]
    error_summary: List[Dict[str, Any]]


class UserActivitySummary(BaseModel):
    """用户活动摘要"""
    user_id: int
    username: str
    total_actions: int
    session_count: int
    first_action: datetime
    last_action: datetime
    top_actions: List[Dict[str, int]]
    most_visited_pages: List[Dict[str, int]]
    error_count: int

    @field_serializer('first_action', 'last_action')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)
