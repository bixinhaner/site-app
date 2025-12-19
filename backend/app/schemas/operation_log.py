from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OperationLogItem(BaseModel):
    id: str
    occurred_at: datetime

    user_id: Optional[int] = None
    username: Optional[str] = None
    user_role: Optional[str] = None

    client: Optional[str] = None

    module: Optional[str] = None
    action: Optional[str] = None

    object_type: Optional[str] = None
    object_id: Optional[str] = None
    object_name: Optional[str] = None

    status_code: Optional[int] = None
    is_success: bool = True
    operation_desc: Optional[str] = None

    class Config:
        from_attributes = True


class OperationLogDetail(OperationLogItem):
    ip: Optional[str] = None
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

