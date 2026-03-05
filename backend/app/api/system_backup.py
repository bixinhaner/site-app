from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user_log import UserLog
from app.core.backup_meta import MetaSessionLocal
from app.models.backup_meta import BackupMetaRecord
from app.services.backup_service import (
    load_backup_config,
    save_backup_config,
    get_default_backup_config,
    perform_backup,
    restore_backup,
)
from app.services.authz_service import user_has_any_role_or_permission
from app.utils.timezone import to_utc_iso


router = APIRouter()


def _require_admin_or_manager(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["system:backup:write"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员或项目经理可以访问数据备份功能",
        )


@router.get("/config")
async def get_backup_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前数据备份配置与下一次执行时间。"""
    _require_admin_or_manager(current_user)

    config = load_backup_config(db)
    now_utc = datetime.utcnow()

    # 计算下一次执行时间
    next_run_at: Optional[str] = None
    if config.get("enabled"):
        interval = max(int(config.get("interval") or 1), 1)
        mode = config.get("mode") or "days"
        last_run_str = config.get("last_run_at")

        last_run_dt: Optional[datetime] = None
        if last_run_str:
            try:
                last_run_dt = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
            except Exception:
                last_run_dt = None

        if last_run_dt:
            if mode == "hours":
                next_dt = last_run_dt + timedelta(hours=interval)
            else:
                next_dt = last_run_dt + timedelta(days=interval)
        else:
            next_dt = now_utc

        next_run_at = to_utc_iso(next_dt)

    return {
        "enabled": bool(config.get("enabled")),
        "mode": config.get("mode") or "days",
        "interval": int(config.get("interval") or 1),
        "last_run_at": config.get("last_run_at"),
        "last_success_at": config.get("last_success_at"),
        "next_run_at": next_run_at,
    }


@router.put("/config")
async def update_backup_config(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新数据备份配置（启用/禁用、周期类型与间隔）。"""
    _require_admin_or_manager(current_user)

    enabled = bool(payload.get("enabled", False))
    mode = payload.get("mode") or "days"
    interval = int(payload.get("interval") or 1)

    if mode not in ("hours", "days"):
        raise HTTPException(status_code=400, detail="mode 仅支持 hours 或 days")
    if interval < 1:
        raise HTTPException(status_code=400, detail="interval 必须为正整数")

    config = load_backup_config(db)
    config["enabled"] = enabled
    config["mode"] = mode
    config["interval"] = interval
    # last_run_at / last_success_at 保留原值

    save_backup_config(db, config)
    db.commit()

    # 返回最新配置
    return await get_backup_config(db, current_user)  # type: ignore[arg-type]


@router.post("/run")
async def run_manual_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发一次数据备份。"""
    _require_admin_or_manager(current_user)

    try:
        result = perform_backup(db, trigger_type="manual", trigger_user=current_user)
        return {
            "success": result.get("status") == "success",
            "record": result,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "record": None,
        }


@router.get("/history")
async def get_backup_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询备份历史记录。"""
    _require_admin_or_manager(current_user)

    meta_db = MetaSessionLocal()
    try:
        base_q = meta_db.query(BackupMetaRecord).filter(BackupMetaRecord.kind == "backup")
        total = base_q.count()
        offset = (page - 1) * page_size

        records: List[BackupMetaRecord] = (
            base_q.order_by(BackupMetaRecord.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        items = []
        for r in records:
            extra = r.extra or {}
            items.append(
                {
                    "id": r.id,
                    "kind": r.kind,
                    "backup_record_id": r.backup_record_id,
                    "trigger_type": r.trigger_type,
                    "trigger_user_id": r.user_id,
                    "trigger_user_name": r.username,
                    "status": r.status,
                    "backup_file": r.backup_file,
                    "error_message": r.error_message,
                    "created_at": to_utc_iso(r.created_at) if r.created_at else None,
                    "started_at": extra.get("started_at"),
                    "finished_at": extra.get("finished_at"),
                    "duration_seconds": extra.get("duration_seconds"),
                }
            )
    finally:
        meta_db.close()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{backup_id}/restore")
async def restore_from_backup(
    backup_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    从指定备份记录恢复数据库。

    - 此操作会用备份中的 .db 文件覆盖当前数据库文件，具有破坏性。
    - 需要在前端严格确认（输入 RESTORE）。
    """
    _require_admin_or_manager(current_user)

    confirm = str(payload.get("confirm", "")).strip()
    if confirm != "RESTORE":
        raise HTTPException(
            status_code=400,
            detail="恢复操作前，请在确认框中输入大写 RESTORE",
        )

    try:
        # backup_id 为 backup_meta_records.id（kind='backup'）
        restore_backup(db, backup_id, trigger_user=current_user)
        return {
            "success": True,
            "record": None,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"恢复失败: {exc}",
        )


@router.get("/restore-history")
async def get_restore_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    分页查询恢复操作的日志记录。

    来源于 UserLog，action 为 data_backup_restore_success / data_backup_restore_failed。
    """
    _require_admin_or_manager(current_user)

    meta_db = MetaSessionLocal()
    try:
        base_q = meta_db.query(BackupMetaRecord).filter(BackupMetaRecord.kind == "restore")
        total = base_q.count()
        offset = (page - 1) * page_size

        logs: List[BackupMetaRecord] = (
            base_q.order_by(BackupMetaRecord.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        items = []
        for r in logs:
            items.append(
                {
                    "id": r.id,
                    "action": "data_backup_restore_success" if r.status == "success" else "data_backup_restore_failed",
                    "level": "INFO" if r.status == "success" else "ERROR",
                    "user_id": r.user_id,
                    "username": r.username,
                    "record_id": r.backup_record_id,
                    "backup_file": r.backup_file,
                    "error": r.error_message,
                    "timestamp": to_utc_iso(r.created_at) if r.created_at else None,
                }
            )
    finally:
        meta_db.close()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
