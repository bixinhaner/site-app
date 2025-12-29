from pydantic import BaseModel, Field
from typing import List, Optional


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
