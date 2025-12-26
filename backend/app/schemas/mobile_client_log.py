from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, field_serializer

from app.utils.timezone import to_utc_iso


class MobileClientLogCreate(BaseModel):
    ts: datetime = Field(..., description="客户端时间（ISO8601 或毫秒时间戳）")
    level: str = Field("INFO", max_length=10)
    message: str = Field(..., min_length=1, max_length=20000)

    tag: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=255)

    device_id: Optional[str] = Field(None, max_length=80)
    app_version_name: Optional[str] = Field(None, max_length=50)
    app_version_code: Optional[int] = None
    platform: Optional[str] = Field(None, max_length=50)
    network_type: Optional[str] = Field(None, max_length=50)
    env: Optional[str] = Field(None, max_length=20)

    api_url: Optional[str] = Field(None, max_length=500)
    api_method: Optional[str] = Field(None, max_length=10)
    api_status: Optional[int] = None
    duration_ms: Optional[int] = None
    error_msg: Optional[str] = Field(None, max_length=20000)

    context: Optional[Any] = None

    @field_validator("ts", mode="before")
    @classmethod
    def _parse_ts(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(float(v) / 1000.0, tz=timezone.utc)
        if isinstance(v, str):
            s = v.strip()
            # 兼容 2020-01-01T00:00:00Z
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        return v

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, v):
        s = str(v or "INFO").strip().upper()
        if s not in ("DEBUG", "INFO", "WARN", "ERROR"):
            return "INFO"
        return s


class MobileClientLogBatchCreate(BaseModel):
    logs: List[MobileClientLogCreate] = Field(..., min_length=1, max_length=1000)


class MobileClientLogItem(BaseModel):
    id: int
    occurred_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    level: str
    tag: Optional[str] = None
    message: str
    route: Optional[str] = None
    at: Optional[str] = None

    user_id: Optional[int] = None
    username: Optional[str] = None

    device_id: Optional[str] = None
    app_version_name: Optional[str] = None
    app_version_code: Optional[int] = None
    platform: Optional[str] = None
    network_type: Optional[str] = None
    env: Optional[str] = None

    api_url: Optional[str] = None
    api_method: Optional[str] = None
    api_status: Optional[int] = None
    duration_ms: Optional[int] = None
    error_msg: Optional[str] = None

    @field_serializer('occurred_at', 'created_at')
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return to_utc_iso(dt)

    class Config:
        from_attributes = True


class MobileClientLogDetail(MobileClientLogItem):
    context: Optional[Any] = None


class MobileClientLogPageResponse(BaseModel):
    items: List[MobileClientLogItem]
    total: int
    page: int
    page_size: int


class MobileClientLogSettings(BaseModel):
    retention_days: int = Field(7, ge=1, le=3650)


class MobileClientLogCleanupPayload(BaseModel):
    retention_days: Optional[int] = Field(None, ge=1, le=3650)

    keyword: Optional[str] = None
    level: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    device_id: Optional[str] = None
    route: Optional[str] = None
    tag: Optional[str] = None
    app_version_code: Optional[int] = None
    api_status: Optional[int] = None
    api_url: Optional[str] = None

    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
