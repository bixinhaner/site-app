from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.ai_call_log import AiCallLog
from app.models.user import User
from app.schemas.ai_management import (
    AiConfigResponse,
    AiConfigUpdateRequest,
    AiLogDetailResponse,
    AiLogListItem,
    AiLogListResponse,
    AiPricingConfig,
    AiPricingModelRule,
    AiStatsBreakdownItem,
    AiStatsDailyItem,
    AiStatsResponse,
    AiStatsSummary,
    AiTestRequest,
    AiTestResponse,
    AiTextConfig,
    AiVisionConfig,
)
from app.services.ai_client import OpenAICompatChatClient
from app.services.ai_call_log_service import create_ai_call_log
from app.services.ai_config_service import apply_ai_config_to_settings, get_pricing_config, load_ai_config, upsert_ai_config
from app.utils.secret_crypto import mask_secret


router = APIRouter()


def _ensure_admin_or_manager(user: User) -> None:
    if user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="权限不足")

def _ensure_can_view_monitor(user: User) -> None:
    if user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="权限不足")


def _normalize_pricing(pricing: Any) -> AiPricingConfig:
    if isinstance(pricing, AiPricingConfig):
        return pricing
    if not isinstance(pricing, dict):
        return AiPricingConfig()
    currency = str(pricing.get("currency") or "USD").strip() or "USD"
    models_raw = pricing.get("models") or {}
    models: Dict[str, AiPricingModelRule] = {}
    if isinstance(models_raw, dict):
        for name, v in models_raw.items():
            key = str(name or "").strip()
            if not key:
                continue
            if isinstance(v, AiPricingModelRule):
                models[key] = v
                continue
            if isinstance(v, dict):
                models[key] = AiPricingModelRule(
                    prompt_per_1k=float(v.get("prompt_per_1k") or 0),
                    completion_per_1k=float(v.get("completion_per_1k") or 0),
                )
    return AiPricingConfig(currency=currency, models=models)


def _estimate_cost(
    *,
    pricing: AiPricingConfig,
    model: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: Optional[int],
) -> float:
    if not model:
        return 0.0
    rule = pricing.models.get(model) if pricing and pricing.models else None
    if not rule:
        return 0.0

    p = int(prompt_tokens or 0)
    c = int(completion_tokens or 0)
    t = int(total_tokens or 0)

    # 优先用 prompt/completion 分开计价；若两者都为 0，则使用 total_tokens 兜底
    cost = 0.0
    if p or c:
        cost += (p / 1000.0) * float(rule.prompt_per_1k or 0.0)
        cost += (c / 1000.0) * float(rule.completion_per_1k or 0.0)
        return float(cost)

    if t:
        # 兜底：按 total_tokens * (prompt 单价) 估算
        cost += (t / 1000.0) * float(rule.prompt_per_1k or 0.0)
    return float(cost)


def _build_config_response(db_config: Dict[str, Any]) -> AiConfigResponse:
    pricing_cfg = _normalize_pricing(get_pricing_config(db_config))

    text_api_key = settings.AI_API_KEY or ""
    vision_api_key = settings.AI_VISION_API_KEY or ""

    text = AiTextConfig(
        base_url=settings.AI_BASE_URL or "",
        model=settings.AI_MODEL or "",
        api_key=None,
        api_key_masked=mask_secret(text_api_key) if text_api_key else "",
        chat_completions_path=settings.AI_CHAT_COMPLETIONS_PATH or "",
        timeout_seconds=int(settings.AI_TIMEOUT_SECONDS),
        temperature=float(settings.AI_TEMPERATURE),
        max_tokens=int(settings.AI_MAX_TOKENS),
        batch_chunk_size=int(settings.AI_BATCH_CHUNK_SIZE),
        domain_hint=settings.AI_DOMAIN_HINT or "",
    )
    vision = AiVisionConfig(
        base_url=settings.AI_VISION_BASE_URL or "",
        model=settings.AI_VISION_MODEL or "",
        api_key=None,
        api_key_masked=mask_secret(vision_api_key) if vision_api_key else "",
        chat_completions_path=settings.AI_VISION_CHAT_COMPLETIONS_PATH or "",
        timeout_seconds=int(settings.AI_VISION_TIMEOUT_SECONDS),
        temperature=float(settings.AI_VISION_TEMPERATURE),
        max_tokens=int(settings.AI_VISION_MAX_TOKENS),
    )

    # 将 DB pricing 原样返回（价格配置不进入 settings）
    return AiConfigResponse(text=text, vision=vision, pricing=pricing_cfg)


@router.get("/config", response_model=AiConfigResponse)
def get_ai_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin_or_manager(current_user)
    db_config = load_ai_config(db)
    # 兜底：确保 DB 配置已应用到 settings（例如热重载后）
    apply_ai_config_to_settings(db_config)
    return _build_config_response(db_config)


@router.put("/config", response_model=AiConfigResponse)
def update_ai_config(
    payload: AiConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin_or_manager(current_user)

    update_payload: Dict[str, Any] = {}
    if payload.text is not None:
        update_payload["text"] = payload.text.model_dump(exclude={"api_key_masked"}, exclude_unset=True)
    if payload.vision is not None:
        update_payload["vision"] = payload.vision.model_dump(exclude={"api_key_masked"}, exclude_unset=True)
    if payload.pricing is not None:
        update_payload["pricing"] = payload.pricing.model_dump()

    new_config = upsert_ai_config(db, payload=update_payload)
    return _build_config_response(new_config)


@router.post("/test", response_model=AiTestResponse)
def test_ai(
    payload: AiTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin_or_manager(current_user)

    mode = (payload.mode or "text").strip().lower()
    prompt = (payload.prompt or "").strip() or "ping"

    if mode == "vision":
        if not (settings.AI_VISION_BASE_URL or "").strip() or not (settings.AI_VISION_API_KEY or "").strip() or not (settings.AI_VISION_MODEL or "").strip():
            raise HTTPException(status_code=400, detail="Vision 配置不完整")
        client = OpenAICompatChatClient(
            base_url=settings.AI_VISION_BASE_URL,
            api_key=settings.AI_VISION_API_KEY,
            chat_completions_path=settings.AI_VISION_CHAT_COMPLETIONS_PATH,
            timeout_seconds=settings.AI_VISION_TIMEOUT_SECONDS,
        )
        model = settings.AI_VISION_MODEL
        temperature = settings.AI_VISION_TEMPERATURE
        max_tokens = settings.AI_VISION_MAX_TOKENS
    else:
        if not (settings.AI_BASE_URL or "").strip() or not (settings.AI_API_KEY or "").strip() or not (settings.AI_MODEL or "").strip():
            raise HTTPException(status_code=400, detail="Text 配置不完整")
        client = OpenAICompatChatClient(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            chat_completions_path=settings.AI_CHAT_COMPLETIONS_PATH,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )
        model = settings.AI_MODEL
        temperature = settings.AI_TEMPERATURE
        max_tokens = settings.AI_MAX_TOKENS

    messages = [{"role": "user", "content": prompt}]
    started = time.time()
    try:
        content, usage, raw = client.create_chat_completion_with_meta(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        try:
            create_ai_call_log(
                db,
                operator_id=current_user.id,
                operation="ai_test",
                mode=mode,
                model=model,
                base_url=(settings.AI_VISION_BASE_URL if mode == "vision" else settings.AI_BASE_URL),
                success=False,
                duration_ms=None,
                messages=messages,
                request_input={"prompt": prompt},
                response_content=None,
                response_raw=None,
                usage=None,
                error=str(exc)[:500],
                context={"api": "/api/system/ai/test"},
            )
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"测试失败: {exc}") from exc
    duration_ms = int((time.time() - started) * 1000)

    try:
        create_ai_call_log(
            db,
            operator_id=current_user.id,
            operation="ai_test",
            mode=mode,
            model=model,
            base_url=(settings.AI_VISION_BASE_URL if mode == "vision" else settings.AI_BASE_URL),
            success=True,
            duration_ms=duration_ms,
            messages=messages,
            request_input={"prompt": prompt},
            response_content=str(content or ""),
            response_raw=raw,
            usage=usage,
            error=None,
            context={"api": "/api/system/ai/test"},
        )
    except Exception:
        pass

    return AiTestResponse(
        mode=mode,
        model=model,
        duration_ms=duration_ms,
        prompt_tokens=(usage or {}).get("prompt_tokens"),
        completion_tokens=(usage or {}).get("completion_tokens"),
        total_tokens=(usage or {}).get("total_tokens"),
        content=str(content or ""),
    )


@router.get("/logs", response_model=AiLogListResponse)
def list_ai_logs(
    days: int = Query(7, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    success: Optional[bool] = None,
    mode: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    operator_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_can_view_monitor(current_user)

    since = datetime.utcnow() - timedelta(days=int(days))
    q = db.query(AiCallLog).filter(AiCallLog.created_at >= since)
    if success is not None:
        q = q.filter(AiCallLog.success == bool(success))
    if mode:
        q = q.filter(AiCallLog.mode == mode)
    if model:
        q = q.filter(AiCallLog.model.like(f"%{model}%"))
    if operation:
        q = q.filter(AiCallLog.operation.like(f"%{operation}%"))
    if operator_id is not None:
        q = q.filter(AiCallLog.operator_id == operator_id)

    total = q.count()
    rows = q.order_by(AiCallLog.created_at.desc()).offset(skip).limit(limit).all()

    # pricing
    cfg = load_ai_config(db)
    pricing = _normalize_pricing(get_pricing_config(cfg))

    # 取用户名称（避免 N+1：这里直接查一次映射）
    user_ids = {r.operator_id for r in rows if r.operator_id is not None}
    id_to_name: Dict[int, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(list(user_ids))).all()
        for u in users:
            id_to_name[u.id] = u.full_name or u.username

    items = []
    for r in rows:
        est = _estimate_cost(
            pricing=pricing,
            model=r.model,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
        )
        items.append(
            AiLogListItem(
                id=r.id,
                created_at=r.created_at,
                operator_id=r.operator_id,
                operator_name=id_to_name.get(r.operator_id) if r.operator_id else None,
                operation=r.operation,
                mode=r.mode,
                model=r.model,
                success=bool(r.success),
                duration_ms=r.duration_ms,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens,
                estimated_cost=round(est, 6),
                currency=pricing.currency,
                error=(str(r.error)[:200] if r.error else None),
            )
        )

    return AiLogListResponse(total=total, items=items)


@router.get("/logs/{log_id}", response_model=AiLogDetailResponse)
def get_ai_log_detail(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_can_view_monitor(current_user)

    row = db.query(AiCallLog).filter(AiCallLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="日志不存在")

    cfg = load_ai_config(db)
    pricing = _normalize_pricing(get_pricing_config(cfg))
    est = _estimate_cost(
        pricing=pricing,
        model=row.model,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
    )

    operator_name = None
    if row.operator_id is not None:
        u = db.query(User).filter(User.id == row.operator_id).first()
        if u:
            operator_name = u.full_name or u.username

    return AiLogDetailResponse(
        id=row.id,
        created_at=row.created_at,
        operator_id=row.operator_id,
        operator_name=operator_name,
        operation=row.operation,
        mode=row.mode,
        model=row.model,
        base_url=row.base_url,
        success=bool(row.success),
        duration_ms=row.duration_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        estimated_cost=round(est, 6),
        currency=pricing.currency,
        request_messages=row.request_messages,
        request_input=row.request_input,
        response_content=row.response_content,
        response_raw=row.response_raw,
        error=row.error,
        context=row.context,
    )


@router.get("/stats", response_model=AiStatsResponse)
def ai_stats(
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_can_view_monitor(current_user)

    since = datetime.utcnow() - timedelta(days=int(days))
    base_q = db.query(AiCallLog).filter(AiCallLog.created_at >= since)

    total_calls = base_q.count()
    success_calls = base_q.filter(AiCallLog.success.is_(True)).count()
    fail_calls = total_calls - success_calls

    avg_duration = (
        base_q.with_entities(func.avg(AiCallLog.duration_ms)).scalar() or 0.0
    )
    total_tokens = int(base_q.with_entities(func.sum(AiCallLog.total_tokens)).scalar() or 0)

    cfg = load_ai_config(db)
    pricing = _normalize_pricing(get_pricing_config(cfg))

    # 估算总费用：逐行累加（便于兼容不同模型单价）
    rows_for_cost = base_q.with_entities(
        AiCallLog.model,
        AiCallLog.prompt_tokens,
        AiCallLog.completion_tokens,
        AiCallLog.total_tokens,
    ).all()
    total_cost = 0.0
    for model, ptk, ctk, ttk in rows_for_cost:
        total_cost += _estimate_cost(
            pricing=pricing,
            model=model,
            prompt_tokens=ptk,
            completion_tokens=ctk,
            total_tokens=ttk,
        )

    # daily
    daily_rows = (
        base_q.with_entities(
            func.date(AiCallLog.created_at).label("d"),
            func.count(AiCallLog.id).label("calls"),
            func.sum(case((AiCallLog.success.is_(True), 1), else_=0)).label("success_calls"),
            func.sum(func.coalesce(AiCallLog.total_tokens, 0)).label("total_tokens"),
        )
        .group_by(func.date(AiCallLog.created_at))
        .order_by(func.date(AiCallLog.created_at))
        .all()
    )

    daily = []
    for d, calls, succ, tokens in daily_rows:
        calls_i = int(calls or 0)
        succ_i = int(succ or 0)
        fail_i = calls_i - succ_i
        # 成本按当日明细加总
        day_q = base_q.filter(func.date(AiCallLog.created_at) == d)
        day_cost = 0.0
        for model, ptk, ctk, ttk in day_q.with_entities(
            AiCallLog.model,
            AiCallLog.prompt_tokens,
            AiCallLog.completion_tokens,
            AiCallLog.total_tokens,
        ).all():
            day_cost += _estimate_cost(pricing=pricing, model=model, prompt_tokens=ptk, completion_tokens=ctk, total_tokens=ttk)
        daily.append(
            AiStatsDailyItem(
                date=str(d),
                calls=calls_i,
                success_calls=succ_i,
                fail_calls=fail_i,
                total_tokens=int(tokens or 0),
                estimated_cost=round(day_cost, 6),
            )
        )

    def build_breakdown(field) -> list[AiStatsBreakdownItem]:
        group_rows = (
            base_q.with_entities(
                field.label("k"),
                func.count(AiCallLog.id).label("calls"),
                func.sum(case((AiCallLog.success.is_(True), 1), else_=0)).label("success_calls"),
                func.sum(func.coalesce(AiCallLog.total_tokens, 0)).label("total_tokens"),
            )
            .group_by(field)
            .order_by(func.count(AiCallLog.id).desc())
            .all()
        )
        out = []
        for k, calls, succ, tokens in group_rows:
            key = str(k or "")
            calls_i = int(calls or 0)
            succ_i = int(succ or 0)
            fail_i = calls_i - succ_i
            # 成本：按该分组明细加总（避免不同模型混价导致误差）
            if field is AiCallLog.model:
                cost = 0.0
                for model, ptk, ctk, ttk in base_q.filter(AiCallLog.model == k).with_entities(
                    AiCallLog.model,
                    AiCallLog.prompt_tokens,
                    AiCallLog.completion_tokens,
                    AiCallLog.total_tokens,
                ).all():
                    cost += _estimate_cost(pricing=pricing, model=model, prompt_tokens=ptk, completion_tokens=ctk, total_tokens=ttk)
            else:
                cost = 0.0
                for model, ptk, ctk, ttk in base_q.filter(field == k).with_entities(
                    AiCallLog.model,
                    AiCallLog.prompt_tokens,
                    AiCallLog.completion_tokens,
                    AiCallLog.total_tokens,
                ).all():
                    cost += _estimate_cost(pricing=pricing, model=model, prompt_tokens=ptk, completion_tokens=ctk, total_tokens=ttk)
            out.append(
                AiStatsBreakdownItem(
                    key=key,
                    calls=calls_i,
                    success_calls=succ_i,
                    fail_calls=fail_i,
                    total_tokens=int(tokens or 0),
                    estimated_cost=round(cost, 6),
                )
            )
        return out

    summary = AiStatsSummary(
        calls=total_calls,
        success_calls=success_calls,
        fail_calls=fail_calls,
        success_rate=round((success_calls / total_calls) if total_calls else 0.0, 6),
        avg_duration_ms=round(float(avg_duration or 0.0), 2),
        total_tokens=total_tokens,
        estimated_cost=round(total_cost, 6),
        currency=pricing.currency,
    )

    return AiStatsResponse(
        summary=summary,
        daily=daily,
        by_model=build_breakdown(AiCallLog.model),
        by_operation=build_breakdown(AiCallLog.operation),
        by_mode=build_breakdown(AiCallLog.mode),
    )
