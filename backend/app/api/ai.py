import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.inspection import (
    CheckItemStatusEnum,
    InspectionAuditLog,
    InspectionCheckItem,
    InspectionStatusEnum,
    SiteInspection,
)
from app.models.work_order import WorkOrder, WorkOrderStatusEnum
from app.models.user import User
from app.schemas.ai import (
    AiCheckItemAnalyzeRequest,
    AiCheckItemAnalyzeResponse,
    AiCheckItemApplyResponse,
    AiTranslateBatchRequest,
    AiTranslateBatchResponse,
    AiTranslateBatchResultItem,
    AiTranslateRequest,
    AiTranslateResponse,
)
from app.services.ai_check_item_service import AiCheckItemService
from app.services.ai_translate_service import AiTranslateService
from app.services.ai_call_log_service import create_ai_call_log
from app.services.authz_service import user_has_any_role_or_permission
from app.utils.timezone import to_utc_iso

router = APIRouter()


def _ensure_ai_operator(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager", "reviewer"],
        permission_codes=["system:ai:write", "system:ai:read"],
    ):
        raise HTTPException(status_code=403, detail="权限不足")


def _ensure_ai_configured() -> None:
    if not (settings.AI_BASE_URL or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_BASE_URL 为空")
    if not (settings.AI_API_KEY or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_API_KEY 为空")
    if not (settings.AI_MODEL or "").strip():
        raise HTTPException(status_code=400, detail="AI 未配置：AI_MODEL 为空")


def _ensure_check_item_not_voided(db: Session, check_item: InspectionCheckItem) -> None:
    inspection = db.query(SiteInspection).filter(SiteInspection.id == check_item.inspection_id).first()
    if inspection and inspection.status == InspectionStatusEnum.VOIDED:
        raise HTTPException(status_code=409, detail="检查记录已作废，不能继续执行 AI 检查或采纳")

    work_order = None
    if inspection and inspection.work_order_id:
        work_order = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()
    if work_order and work_order.status == WorkOrderStatusEnum.VOIDED:
        raise HTTPException(status_code=409, detail="工单已作废，不能继续执行 AI 检查或采纳")


@router.post("/translate", response_model=AiTranslateResponse)
def translate_text(
    payload: AiTranslateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_operator(current_user)
    _ensure_ai_configured()

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    svc = AiTranslateService()
    try:
        translation, trace = svc.translate_with_trace(
            text=text,
            target_locale=payload.target_locale,
            source_locale=payload.source_locale,
        )
        create_ai_call_log(
            db,
            operator_id=current_user.id,
            operation="translate",
            mode="text",
            model=settings.AI_MODEL,
            base_url=settings.AI_BASE_URL,
            success=True,
            duration_ms=trace.get("duration_ms"),
            messages=trace.get("messages"),
            request_input=trace.get("input"),
            response_content=trace.get("content"),
            response_raw=trace.get("raw"),
            usage=trace.get("usage"),
            error=None,
            context={"api": "/api/ai/translate"},
        )
    except Exception as exc:
        # 失败也写日志（尽量保留输入，避免无迹可查）
        try:
            create_ai_call_log(
                db,
                operator_id=current_user.id,
                operation="translate",
                mode="text",
                model=settings.AI_MODEL,
                base_url=settings.AI_BASE_URL,
                success=False,
                duration_ms=None,
                messages=None,
                request_input={"text": text, "source_locale": payload.source_locale, "target_locale": payload.target_locale},
                response_content=None,
                response_raw=None,
                usage=None,
                error=str(exc)[:500],
                context={"api": "/api/ai/translate"},
            )
        except Exception:
            pass
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_operator(current_user)
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

    svc = AiTranslateService()
    try:
        translations, traces = svc.translate_batch_with_traces(items=req_items)
        for tr in traces:
            create_ai_call_log(
                db,
                operator_id=current_user.id,
                operation="translate_batch",
                mode="text",
                model=settings.AI_MODEL,
                base_url=settings.AI_BASE_URL,
                success=True,
                duration_ms=tr.get("duration_ms"),
                messages=tr.get("messages"),
                request_input=tr.get("input"),
                response_content=tr.get("content"),
                response_raw=tr.get("raw"),
                usage=tr.get("usage"),
                error=None,
                context={"api": "/api/ai/translate/batch"},
            )
    except Exception as exc:
        try:
            create_ai_call_log(
                db,
                operator_id=current_user.id,
                operation="translate_batch",
                mode="text",
                model=settings.AI_MODEL,
                base_url=settings.AI_BASE_URL,
                success=False,
                duration_ms=None,
                messages=None,
                request_input={"items": [it.model_dump() for it in items]},
                response_content=None,
                response_raw=None,
                usage=None,
                error=str(exc)[:500],
                context={"api": "/api/ai/translate/batch"},
            )
        except Exception:
            pass
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


def _format_ai_review_comment(ai_result: Dict[str, Any]) -> str:
    if not isinstance(ai_result, dict):
        return ""

    suggested_status = str(ai_result.get("suggested_review_status") or "").strip()
    suggested_score = ai_result.get("suggested_score")
    summary = str(ai_result.get("summary") or "").strip()
    analysis = ai_result.get("analysis") or []
    missing = ai_result.get("missing_evidence") or []

    lines = []
    header = "【AI建议】"
    if suggested_status:
        header += f" 结论={suggested_status}"
    if suggested_score is not None and str(suggested_score).strip() != "":
        header += f" 分数={suggested_score}"
    lines.append(header)

    if summary:
        lines.append(summary)

    if isinstance(analysis, list):
        for it in analysis[:20]:
            s = str(it or "").strip()
            if s:
                lines.append(f"- {s}")

    if isinstance(missing, list) and missing:
        miss = [str(x or "").strip() for x in missing]
        miss = [x for x in miss if x]
        if miss:
            lines.append("缺材料/需补充：")
            for x in miss[:20]:
                lines.append(f"- {x}")

    return "\n".join(lines).strip()


@router.post("/check-items/{check_item_id}/analyze", response_model=AiCheckItemAnalyzeResponse)
def analyze_check_item(
    check_item_id: str,
    payload: AiCheckItemAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_operator(current_user)

    check_item = db.query(InspectionCheckItem).filter(InspectionCheckItem.id == check_item_id).first()
    if not check_item:
        raise HTTPException(status_code=404, detail="检查项不存在")
    _ensure_check_item_not_voided(db, check_item)

    try:
        svc = AiCheckItemService()
        ai_mode, ai_model, input_hash, result = svc.analyze_check_item(
            db=db,
            check_item=check_item,
            mode=payload.mode,
            force=payload.force,
            max_images=payload.max_images,
            image_detail=payload.image_detail,
            operator_user_id=current_user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 检查失败: {exc}") from exc

    return AiCheckItemAnalyzeResponse(
        check_item_id=check_item_id,
        ai_status=str(check_item.ai_status or "done"),
        ai_mode=str(ai_mode),
        ai_model=str(ai_model or ""),
        ai_input_hash=input_hash,
        ai_result=result,
        ai_error=check_item.ai_error,
        ai_checked_by=check_item.ai_checked_by,
        ai_checked_at=to_utc_iso(check_item.ai_checked_at) if check_item.ai_checked_at else None,
    )


@router.post("/check-items/{check_item_id}/apply", response_model=AiCheckItemApplyResponse)
def apply_check_item_ai_suggestion(
    check_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_operator(current_user)

    check_item = db.query(InspectionCheckItem).filter(InspectionCheckItem.id == check_item_id).first()
    if not check_item:
        raise HTTPException(status_code=404, detail="检查项不存在")
    _ensure_check_item_not_voided(db, check_item)

    if check_item.review_status in ("pass", "warning", "fail"):
        raise HTTPException(status_code=400, detail="该检查项已有人为审核结果，无法采纳 AI 建议")

    item_status_value = getattr(check_item.status, "value", check_item.status)
    if str(item_status_value) != CheckItemStatusEnum.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"检查项未完成提交，无法采纳（当前状态：{item_status_value}）")

    if (check_item.ai_status or "") != "done" or not check_item.ai_result:
        raise HTTPException(status_code=400, detail="AI 建议未生成，无法采纳")

    ai_result = dict(check_item.ai_result or {})
    suggested = str(ai_result.get("suggested_review_status") or "").strip()
    if suggested not in ("pass", "warning", "fail"):
        raise HTTPException(status_code=400, detail="AI 建议缺少可用的 suggested_review_status")

    comments = _format_ai_review_comment(ai_result)
    if not comments:
        raise HTTPException(status_code=400, detail="AI 建议内容为空，无法采纳")

    now = datetime.utcnow()
    try:
        check_item.review_status = suggested
        check_item.review_comments = comments
        check_item.review_comments_manual = None
        check_item.review_comments_i18n = None
        check_item.field_issue_comments = None
        check_item.field_review_results = None
        check_item.reviewed_by = current_user.id
        check_item.reviewed_at = now
        check_item.updated_at = now
        check_item.ai_applied_by = current_user.id
        check_item.ai_applied_at = now

        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=check_item.inspection_id,
            action="item_review",
            from_status=None,
            to_status=None,
            operator_id=current_user.id,
            comments=comments,
            details={"item_id": check_item_id, "result": suggested, "source": "ai"},
        )
        db.add(audit_log)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"采纳失败: {exc}") from exc

    # 同步 inspection.result（不影响工单审核逻辑，但便于列表/统计展示）
    try:
        from app.api.inspections import _update_inspection_result_from_item_reviews

        _update_inspection_result_from_item_reviews(db, check_item.inspection_id)
    except Exception:
        # 不阻塞采纳结果
        pass

    return AiCheckItemApplyResponse(
        check_item_id=check_item_id,
        applied=True,
        review_status=check_item.review_status,
        review_comments=check_item.review_comments,
        reviewed_at=to_utc_iso(check_item.reviewed_at) if check_item.reviewed_at else None,
    )
