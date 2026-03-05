import io
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from sqlalchemy import String, cast, desc, func, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.mobile_client_log import MobileClientLog
from app.models.user import User
from app.schemas.mobile_client_log import (
    MobileClientLogBatchCreate,
    MobileClientLogCleanupPayload,
    MobileClientLogDetail,
    MobileClientLogItem,
    MobileClientLogPageResponse,
    MobileClientLogSettings,
)
from app.services.authz_service import user_has_any_role_or_permission
from app.services.mobile_client_log_service import (
    cleanup_mobile_client_logs_by_filters,
    load_mobile_client_log_settings,
    save_mobile_client_log_settings,
)


router = APIRouter()


def _require_logs_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin"],
        permission_codes=["system:logs:read"],
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


def _can_view_all_logs(current_user: User) -> bool:
    return user_has_any_role_or_permission(
        current_user,
        role_codes=["admin"],
        permission_codes=["system:logs:read"],
    )


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_client_tz(tz_name: Optional[str], tz_offset: Optional[int]):
    if tz_name:
        try:
            return ZoneInfo(str(tz_name))
        except Exception:
            pass
    if tz_offset is not None:
        try:
            offset_minutes = int(tz_offset)
            # JS: getTimezoneOffset() = UTC - local (minutes)
            return timezone(timedelta(minutes=-offset_minutes))
        except Exception:
            pass
    return None


def _safe_excel_cell(value, max_len: int = 30000) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
    s = ILLEGAL_CHARACTERS_RE.sub("", s)
    if len(s) > max_len:
        return s[: max_len - 20] + "...(truncated)"
    return s


@router.get("/mobile-logs/settings", response_model=MobileClientLogSettings)
async def get_mobile_client_log_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_logs_access(current_user)
    data = load_mobile_client_log_settings(db)
    return MobileClientLogSettings(**data)


@router.put("/mobile-logs/settings", response_model=MobileClientLogSettings)
async def update_mobile_client_log_settings(
    payload: MobileClientLogSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_logs_access(current_user)
    data = load_mobile_client_log_settings(db)
    data["retention_days"] = int(payload.retention_days)
    save_mobile_client_log_settings(db, data)
    return MobileClientLogSettings(**data)


@router.post("/mobile-logs/batch", response_model=dict)
async def create_mobile_logs_batch(
    payload: MobileClientLogBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移动端批量上报日志（仅登录后调用）。"""

    logs = payload.logs or []
    if not logs:
        return {"success": True, "created_count": 0}

    rows = []
    for item in logs:
        # 移动端不再采集请求日志：为兼容旧版本客户端，这里直接丢弃 tag=request 的上报
        if str(item.tag or "").strip().lower() == "request":
            continue

        occurred_at = item.ts
        if occurred_at is not None and occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        row = MobileClientLog(
            occurred_at=occurred_at,
            level=item.level,
            tag=item.tag,
            message=item.message,
            route=item.route,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", None),
            device_id=item.device_id,
            app_version_name=item.app_version_name,
            app_version_code=item.app_version_code,
            platform=item.platform,
            network_type=item.network_type,
            env=item.env,
            api_url=item.api_url,
            api_method=item.api_method,
            api_status=item.api_status,
            duration_ms=item.duration_ms,
            error_msg=item.error_msg,
            context=item.context,
        )
        rows.append(row)

    db.bulk_save_objects(rows)
    db.commit()

    return {"success": True, "created_count": len(rows)}


@router.get("/mobile-logs/page", response_model=MobileClientLogPageResponse)
async def get_mobile_logs_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    username: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    route: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    app_version_code: Optional[int] = Query(None),
    api_status: Optional[int] = Query(None),
    api_url: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 普通用户只能查看自己的日志
    if not _can_view_all_logs(current_user):
        user_id = getattr(current_user, "id", None)

    query = db.query(MobileClientLog)

    if user_id is not None:
        query = query.filter(MobileClientLog.user_id == user_id)
    if username:
        query = query.filter(MobileClientLog.username == username)
    if level:
        query = query.filter(MobileClientLog.level == str(level).strip().upper())
    if device_id:
        query = query.filter(MobileClientLog.device_id == device_id)
    if route:
        query = query.filter(MobileClientLog.route.like(f"%{route}%"))
    if tag:
        query = query.filter(MobileClientLog.tag == tag)
    if app_version_code is not None:
        query = query.filter(MobileClientLog.app_version_code == int(app_version_code))
    if api_status is not None:
        query = query.filter(MobileClientLog.api_status == int(api_status))
    if api_url:
        query = query.filter(MobileClientLog.api_url.like(f"%{api_url}%"))
    if date_from:
        query = query.filter(MobileClientLog.occurred_at >= date_from)
    if date_to:
        query = query.filter(MobileClientLog.occurred_at <= date_to)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                MobileClientLog.message.like(kw),
                MobileClientLog.tag.like(kw),
                MobileClientLog.route.like(kw),
                MobileClientLog.api_url.like(kw),
                MobileClientLog.username.like(kw),
                MobileClientLog.error_msg.like(kw),
                cast(MobileClientLog.context, String).like(kw),
            )
        )

    total = query.with_entities(func.count(MobileClientLog.id)).scalar() or 0
    rows = (
        query.order_by(desc(MobileClientLog.occurred_at), desc(MobileClientLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [MobileClientLogItem.model_validate(r) for r in rows]
    return MobileClientLogPageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/mobile-logs/export")
async def export_mobile_logs(
    keyword: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    username: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    route: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    app_version_code: Optional[int] = Query(None),
    api_status: Optional[int] = Query(None),
    api_url: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    tz: Optional[str] = Query(None),
    tz_offset: Optional[int] = Query(None),
    limit: int = Query(50000, ge=1, le=200000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client_tz = _resolve_client_tz(tz, tz_offset)

    # 普通用户只能导出自己的日志
    if not _can_view_all_logs(current_user):
        user_id = getattr(current_user, "id", None)

    query = db.query(MobileClientLog)

    if user_id is not None:
        query = query.filter(MobileClientLog.user_id == user_id)
    if username:
        query = query.filter(MobileClientLog.username == username)
    if level:
        query = query.filter(MobileClientLog.level == str(level).strip().upper())
    if device_id:
        query = query.filter(MobileClientLog.device_id == device_id)
    if route:
        query = query.filter(MobileClientLog.route.like(f"%{route}%"))
    if tag:
        query = query.filter(MobileClientLog.tag == tag)
    if app_version_code is not None:
        query = query.filter(MobileClientLog.app_version_code == int(app_version_code))
    if api_status is not None:
        query = query.filter(MobileClientLog.api_status == int(api_status))
    if api_url:
        query = query.filter(MobileClientLog.api_url.like(f"%{api_url}%"))
    if date_from:
        query = query.filter(MobileClientLog.occurred_at >= date_from)
    if date_to:
        query = query.filter(MobileClientLog.occurred_at <= date_to)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                MobileClientLog.message.like(kw),
                MobileClientLog.tag.like(kw),
                MobileClientLog.route.like(kw),
                MobileClientLog.api_url.like(kw),
                MobileClientLog.username.like(kw),
                MobileClientLog.error_msg.like(kw),
                cast(MobileClientLog.context, String).like(kw),
            )
        )

    total = query.with_entities(func.count(MobileClientLog.id)).scalar() or 0
    if total > limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"匹配记录过多（{total}条），请缩小筛选范围或提高 limit（最大 200000）",
        )

    rows = query.order_by(desc(MobileClientLog.occurred_at), desc(MobileClientLog.id)).all()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("移动端日志")

    headers = [
        "ID",
        "客户端时间",
        "入库时间",
        "级别",
        "标签",
        "用户ID",
        "用户名",
        "设备ID",
        "App版本名",
        "App版本号",
        "平台",
        "网络",
        "环境",
        "页面",
        "位置",
        "内容",
        "API URL",
        "API Method",
        "API Status",
        "耗时(ms)",
        "错误信息",
        "Context",
    ]
    ws.append(headers)

    for r in rows:
        occurred_at = _ensure_utc(getattr(r, "occurred_at", None))
        created_at = _ensure_utc(getattr(r, "created_at", None))

        occurred_str = ""
        if occurred_at:
            local_dt = occurred_at.astimezone(client_tz) if client_tz else occurred_at
            occurred_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        created_str = ""
        if created_at:
            local_dt = created_at.astimezone(client_tz) if client_tz else created_at
            created_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        ws.append(
            [
                _safe_excel_cell(getattr(r, "id", None)),
                _safe_excel_cell(occurred_str),
                _safe_excel_cell(created_str),
                _safe_excel_cell(getattr(r, "level", None)),
                _safe_excel_cell(getattr(r, "tag", None)),
                _safe_excel_cell(getattr(r, "user_id", None)),
                _safe_excel_cell(getattr(r, "username", None)),
                _safe_excel_cell(getattr(r, "device_id", None)),
                _safe_excel_cell(getattr(r, "app_version_name", None)),
                _safe_excel_cell(getattr(r, "app_version_code", None)),
                _safe_excel_cell(getattr(r, "platform", None)),
                _safe_excel_cell(getattr(r, "network_type", None)),
                _safe_excel_cell(getattr(r, "env", None)),
                _safe_excel_cell(getattr(r, "route", None)),
                _safe_excel_cell(getattr(r, "at", None)),
                _safe_excel_cell(getattr(r, "message", None)),
                _safe_excel_cell(getattr(r, "api_url", None)),
                _safe_excel_cell(getattr(r, "api_method", None)),
                _safe_excel_cell(getattr(r, "api_status", None)),
                _safe_excel_cell(getattr(r, "duration_ms", None)),
                _safe_excel_cell(getattr(r, "error_msg", None)),
                _safe_excel_cell(getattr(r, "context", None)),
            ]
        )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"mobile_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/mobile-logs/cleanup", response_model=dict)
async def cleanup_mobile_logs(
    payload: MobileClientLogCleanupPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_logs_access(current_user)

    deleted_count = cleanup_mobile_client_logs_by_filters(
        db,
        retention_days=payload.retention_days,
        keyword=payload.keyword,
        level=payload.level,
        user_id=payload.user_id,
        username=payload.username,
        device_id=payload.device_id,
        route=payload.route,
        tag=payload.tag,
        app_version_code=payload.app_version_code,
        api_status=payload.api_status,
        api_url=payload.api_url,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )

    return {"success": True, "deleted_count": deleted_count}


@router.get("/mobile-logs/{log_id}", response_model=MobileClientLogDetail)
async def get_mobile_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MobileClientLog).filter(MobileClientLog.id == int(log_id)).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志不存在")

    if not _can_view_all_logs(current_user):
        if getattr(row, "user_id", None) != getattr(current_user, "id", None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    return MobileClientLogDetail.model_validate(row)
