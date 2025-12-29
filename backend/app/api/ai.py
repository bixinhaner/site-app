from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.ai import (
    AiTranslateBatchRequest,
    AiTranslateBatchResponse,
    AiTranslateBatchResultItem,
    AiTranslateRequest,
    AiTranslateResponse,
)
from app.services.ai_translate_service import AiTranslateService

router = APIRouter()


def _ensure_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")


def _ensure_ai_configured() -> None:
    if not (settings.AI_BASE_URL or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_BASE_URL 为空")
    if not (settings.AI_API_KEY or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_API_KEY 为空")
    if not (settings.AI_MODEL or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_MODEL 为空")


@router.post("/translate", response_model=AiTranslateResponse)
def translate_text(
    payload: AiTranslateRequest,
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    _ensure_ai_configured()

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    try:
        svc = AiTranslateService()
        translation = svc.translate(
            text=text,
            target_locale=payload.target_locale,
            source_locale=payload.source_locale,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 翻译失败: {exc}") from exc

    return AiTranslateResponse(
        text=payload.text,
        source_locale=payload.source_locale,
        target_locale=payload.target_locale,
        translation=translation,
    )


@router.post("/translate/batch", response_model=AiTranslateBatchResponse)
def translate_text_batch(
    payload: AiTranslateBatchRequest,
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    _ensure_ai_configured()

    items = payload.items or []
    if not items:
        return AiTranslateBatchResponse(items=[])
    if len(items) > 300:
        raise HTTPException(status_code=400, detail="items 数量过多（最多 300）")

    req_items = []
    for it in items:
        text = (it.text or "").strip()
        if not text:
            req_items.append(("", it.target_locale, it.source_locale, it.key))
        else:
            req_items.append((it.text, it.target_locale, it.source_locale, it.key))

    try:
        svc = AiTranslateService()
        translations = svc.translate_batch(items=req_items)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 批量翻译失败: {exc}") from exc

    out = []
    for it, trans in zip(items, translations):
        out.append(
            AiTranslateBatchResultItem(
                key=it.key,
                text=it.text,
                source_locale=it.source_locale,
                target_locale=it.target_locale,
                translation=trans,
            )
        )
    return AiTranslateBatchResponse(items=out)
