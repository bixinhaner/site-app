import io
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.operation_log import OperationLog
from app.models.system_config import SystemConfig
from app.models.user import User
from app.schemas.operation_log import (
    OperationLogCleanupPayload,
    OperationLogDetail,
    OperationLogOptionsResponse,
    OperationLogPageResponse,
    OperationLogSettings,
)


router = APIRouter()

_SETTINGS_KEY = "operation_log_settings"
_DEFAULT_SETTINGS = {"retention_days": 90}


def _require_admin(current_user: User) -> None:
    # get_current_user 会把 manager 映射成 admin，满足“admin/manager可用”的要求
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")


def _load_settings(db: Session) -> dict:
    row = db.query(SystemConfig).filter(SystemConfig.key == _SETTINGS_KEY).first()
    if not row or not isinstance(row.value, dict):
        return dict(_DEFAULT_SETTINGS)
    settings = dict(_DEFAULT_SETTINGS)
    settings.update(row.value or {})
    return settings


def _save_settings(db: Session, settings: dict) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == _SETTINGS_KEY).first()
    if not row:
        row = SystemConfig(key=_SETTINGS_KEY, value=settings)
        db.add(row)
    else:
        row.value = settings
        flag_modified(row, "value")
    db.commit()


@router.get("/operation-logs/settings", response_model=OperationLogSettings)
async def get_operation_log_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    data = _load_settings(db)
    return OperationLogSettings(**data)


@router.put("/operation-logs/settings", response_model=OperationLogSettings)
async def update_operation_log_settings(
    payload: OperationLogSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    data = _load_settings(db)
    data["retention_days"] = int(payload.retention_days)
    _save_settings(db, data)
    return OperationLogSettings(**data)


@router.get("/operation-logs/options", response_model=OperationLogOptionsResponse)
async def get_operation_log_options(
    days: int = Query(90, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(OperationLog).filter(OperationLog.occurred_at >= cutoff)

    modules = [
        r[0]
        for r in (
            base.with_entities(OperationLog.module)
            .filter(OperationLog.module.isnot(None))
            .distinct()
            .order_by(OperationLog.module.asc())
            .limit(200)
            .all()
        )
        if r and r[0]
    ]
    actions = [
        r[0]
        for r in (
            base.with_entities(OperationLog.action)
            .filter(OperationLog.action.isnot(None))
            .distinct()
            .order_by(OperationLog.action.asc())
            .limit(200)
            .all()
        )
        if r and r[0]
    ]
    clients = [
        r[0]
        for r in (
            base.with_entities(OperationLog.client)
            .filter(OperationLog.client.isnot(None))
            .distinct()
            .order_by(OperationLog.client.asc())
            .limit(50)
            .all()
        )
        if r and r[0]
    ]

    return OperationLogOptionsResponse(modules=modules, actions=actions, clients=clients)


@router.get("/operation-logs/page", response_model=OperationLogPageResponse)
async def page_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    is_success: Optional[bool] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    query = db.query(OperationLog)

    if module:
        query = query.filter(OperationLog.module == module)
    if action:
        query = query.filter(OperationLog.action == action)
    if client:
        query = query.filter(OperationLog.client == client)
    if user_id is not None:
        query = query.filter(OperationLog.user_id == user_id)
    if is_success is not None:
        query = query.filter(OperationLog.is_success == is_success)
    if object_type:
        query = query.filter(OperationLog.object_type == object_type)
    if object_id:
        query = query.filter(OperationLog.object_id == object_id)
    if date_from:
        query = query.filter(OperationLog.occurred_at >= date_from)
    if date_to:
        query = query.filter(OperationLog.occurred_at <= date_to)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                OperationLog.operation_desc.like(kw),
                OperationLog.username.like(kw),
                OperationLog.object_name.like(kw),
                OperationLog.request_path.like(kw),
            )
        )

    total = query.with_entities(func.count(OperationLog.id)).scalar() or 0

    rows = (
        query.order_by(desc(OperationLog.occurred_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return OperationLogPageResponse(items=rows, total=total, page=page, page_size=page_size)


@router.post("/operation-logs/cleanup", response_model=dict)
async def cleanup_operation_logs(
    payload: OperationLogCleanupPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    query = db.query(OperationLog)
    filters = []

    if payload.retention_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(payload.retention_days))
        filters.append(OperationLog.occurred_at < cutoff)

    if payload.date_from:
        filters.append(OperationLog.occurred_at >= payload.date_from)
    if payload.date_to:
        filters.append(OperationLog.occurred_at <= payload.date_to)

    if payload.module:
        filters.append(OperationLog.module == payload.module)
    if payload.action:
        filters.append(OperationLog.action == payload.action)
    if payload.client:
        filters.append(OperationLog.client == payload.client)
    if payload.user_id is not None:
        filters.append(OperationLog.user_id == payload.user_id)
    if payload.is_success is not None:
        filters.append(OperationLog.is_success == payload.is_success)
    if payload.object_type:
        filters.append(OperationLog.object_type == payload.object_type)
    if payload.object_id:
        filters.append(OperationLog.object_id == payload.object_id)

    if payload.keyword:
        kw = f"%{payload.keyword}%"
        filters.append(
            or_(
                OperationLog.operation_desc.like(kw),
                OperationLog.username.like(kw),
                OperationLog.object_name.like(kw),
                OperationLog.request_path.like(kw),
            )
        )

    if filters:
        query = query.filter(and_(*filters))

    deleted_count = query.delete(synchronize_session=False)
    db.commit()

    return {"success": True, "deleted_count": deleted_count}


def _safe_excel_cell(value, max_len: int = 30000) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
    if len(s) > max_len:
        return s[: max_len - 20] + "...(truncated)"
    return s


@router.get("/operation-logs/export")
async def export_operation_logs(
    keyword: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    is_success: Optional[bool] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50000, ge=1, le=200000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    query = db.query(OperationLog)

    if module:
        query = query.filter(OperationLog.module == module)
    if action:
        query = query.filter(OperationLog.action == action)
    if client:
        query = query.filter(OperationLog.client == client)
    if user_id is not None:
        query = query.filter(OperationLog.user_id == user_id)
    if is_success is not None:
        query = query.filter(OperationLog.is_success == is_success)
    if object_type:
        query = query.filter(OperationLog.object_type == object_type)
    if object_id:
        query = query.filter(OperationLog.object_id == object_id)
    if date_from:
        query = query.filter(OperationLog.occurred_at >= date_from)
    if date_to:
        query = query.filter(OperationLog.occurred_at <= date_to)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                OperationLog.operation_desc.like(kw),
                OperationLog.username.like(kw),
                OperationLog.object_name.like(kw),
                OperationLog.request_path.like(kw),
            )
        )

    total = query.with_entities(func.count(OperationLog.id)).scalar() or 0
    if total > limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"匹配记录过多（{total}条），请缩小筛选范围或提高 limit（最大 200000）",
        )

    rows = query.order_by(desc(OperationLog.occurred_at)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "操作日志"

    headers = [
        "时间",
        "用户ID",
        "用户名",
        "角色",
        "来源端",
        "模块",
        "动作",
        "对象类型",
        "对象ID",
        "对象名称",
        "结果",
        "状态码",
        "可读描述",
        "请求方法",
        "请求路径",
        "IP",
        "路径参数",
        "查询参数",
        "提交变更值",
        "错误信息",
    ]
    ws.append(headers)

    for r in rows:
        ws.append(
            [
                _safe_excel_cell(getattr(r, "occurred_at", None)),
                _safe_excel_cell(getattr(r, "user_id", None)),
                _safe_excel_cell(getattr(r, "username", None)),
                _safe_excel_cell(getattr(r, "user_role", None)),
                _safe_excel_cell(getattr(r, "client", None)),
                _safe_excel_cell(getattr(r, "module", None)),
                _safe_excel_cell(getattr(r, "action", None)),
                _safe_excel_cell(getattr(r, "object_type", None)),
                _safe_excel_cell(getattr(r, "object_id", None)),
                _safe_excel_cell(getattr(r, "object_name", None)),
                "成功" if getattr(r, "is_success", False) else "失败",
                _safe_excel_cell(getattr(r, "status_code", None)),
                _safe_excel_cell(getattr(r, "operation_desc", None)),
                _safe_excel_cell(getattr(r, "request_method", None)),
                _safe_excel_cell(getattr(r, "request_path", None)),
                _safe_excel_cell(getattr(r, "ip", None)),
                _safe_excel_cell(getattr(r, "path_params", None)),
                _safe_excel_cell(getattr(r, "query_params", None)),
                _safe_excel_cell(getattr(r, "request_body", None)),
                _safe_excel_cell(getattr(r, "error_message", None)),
            ]
        )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"operation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/operation-logs/{log_id}", response_model=OperationLogDetail)
async def get_operation_log_detail(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = db.query(OperationLog).filter(OperationLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志不存在")
    return row
