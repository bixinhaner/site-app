from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from app.utils.timezone import to_utc_iso


class AiPricingModelRule(BaseModel):
    prompt_per_1k: float = Field(default=0.0, ge=0)
    completion_per_1k: float = Field(default=0.0, ge=0)


class AiPricingConfig(BaseModel):
    currency: str = Field(default="USD", min_length=1)
    models: Dict[str, AiPricingModelRule] = Field(default_factory=dict)


class AiTextConfig(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: Optional[str] = None  # 仅用于写入；读取时不回显
    api_key_masked: Optional[str] = None
    chat_completions_path: str = "/v1/chat/completions"
    timeout_seconds: int = 60
    temperature: float = 0.2
    max_tokens: int = 1024
    batch_chunk_size: int = 20
    domain_hint: str = ""


class AiVisionConfig(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: Optional[str] = None  # 仅用于写入；读取时不回显
    api_key_masked: Optional[str] = None
    chat_completions_path: str = "/v1/chat/completions"
    timeout_seconds: int = 60
    temperature: float = 0.2
    max_tokens: int = 1024


class AiConfigResponse(BaseModel):
    text: AiTextConfig
    vision: AiVisionConfig
    pricing: AiPricingConfig


class AiConfigUpdateRequest(BaseModel):
    text: Optional[AiTextConfig] = None
    vision: Optional[AiVisionConfig] = None
    pricing: Optional[AiPricingConfig] = None


class AiTestRequest(BaseModel):
    mode: str = Field(default="text", pattern="^(text|vision)$")
    prompt: Optional[str] = None


class AiTestResponse(BaseModel):
    mode: str
    model: str
    duration_ms: int
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    content: str


class AiLogListItem(BaseModel):
    id: str
    created_at: datetime
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    operation: str
    mode: str
    model: Optional[str] = None
    success: bool
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: float = 0.0
    currency: str = "USD"
    error: Optional[str] = None

    @field_serializer("created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return to_utc_iso(dt)


class AiLogListResponse(BaseModel):
    total: int
    items: List[AiLogListItem] = Field(default_factory=list)


class AiLogDetailResponse(BaseModel):
    id: str
    created_at: datetime
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    operation: str
    mode: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    success: bool
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: float = 0.0
    currency: str = "USD"
    request_messages: Optional[Any] = None
    request_input: Optional[Any] = None
    response_content: Optional[str] = None
    response_raw: Optional[Any] = None
    error: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    @field_serializer("created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return to_utc_iso(dt)


class AiStatsDailyItem(BaseModel):
    date: str
    calls: int
    success_calls: int
    fail_calls: int
    total_tokens: int
    estimated_cost: float


class AiStatsBreakdownItem(BaseModel):
    key: str
    calls: int
    success_calls: int
    fail_calls: int
    total_tokens: int
    estimated_cost: float


class AiStatsSummary(BaseModel):
    calls: int
    success_calls: int
    fail_calls: int
    success_rate: float
    avg_duration_ms: float
    total_tokens: int
    estimated_cost: float
    currency: str = "USD"


class AiStatsResponse(BaseModel):
    summary: AiStatsSummary
    daily: List[AiStatsDailyItem] = Field(default_factory=list)
    by_model: List[AiStatsBreakdownItem] = Field(default_factory=list)
    by_operation: List[AiStatsBreakdownItem] = Field(default_factory=list)
    by_mode: List[AiStatsBreakdownItem] = Field(default_factory=list)

