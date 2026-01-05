from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AiTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_locale: str = Field(..., min_length=1)
    source_locale: Optional[str] = None


class AiTranslateResponse(BaseModel):
    text: str
    target_locale: str
    source_locale: Optional[str] = None
    translation: str


class AiTranslateBatchItem(BaseModel):
    key: Optional[str] = None
    text: str = Field(..., min_length=1)
    target_locale: str = Field(..., min_length=1)
    source_locale: Optional[str] = None


class AiTranslateBatchRequest(BaseModel):
    items: List[AiTranslateBatchItem] = Field(default_factory=list)


class AiTranslateBatchResultItem(BaseModel):
    key: Optional[str] = None
    text: str
    target_locale: str
    source_locale: Optional[str] = None
    translation: str


class AiTranslateBatchResponse(BaseModel):
    items: List[AiTranslateBatchResultItem] = Field(default_factory=list)


class AiCheckItemAnalyzeRequest(BaseModel):
    mode: str = Field(default="auto", pattern="^(auto|text|vision)$")
    force: bool = False
    max_images: int = Field(default=5, ge=0, le=5)
    image_detail: str = Field(default="low", pattern="^(low|high)$")


class AiCheckItemAnalyzeResponse(BaseModel):
    check_item_id: str
    ai_status: str
    ai_mode: str
    ai_model: Optional[str] = None
    ai_input_hash: Optional[str] = None
    ai_result: Optional[Dict[str, Any]] = None
    ai_error: Optional[str] = None
    ai_checked_by: Optional[int] = None
    ai_checked_at: Optional[str] = None


class AiCheckItemApplyResponse(BaseModel):
    check_item_id: str
    applied: bool
    review_status: Optional[str] = None
    review_comments: Optional[str] = None
    reviewed_at: Optional[str] = None
