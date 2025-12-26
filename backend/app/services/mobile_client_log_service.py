from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import String, cast, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.mobile_client_log import MobileClientLog
from app.models.system_config import SystemConfig


SETTINGS_KEY = "mobile_client_log_settings"
DEFAULT_SETTINGS = {"retention_days": 7}


def load_mobile_client_log_settings(db: Session) -> Dict:
    row = db.query(SystemConfig).filter(SystemConfig.key == SETTINGS_KEY).first()
    if not row or not isinstance(row.value, dict):
        return dict(DEFAULT_SETTINGS)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(row.value or {})
    return settings


def save_mobile_client_log_settings(db: Session, settings: Dict) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == SETTINGS_KEY).first()
    if not row:
        row = SystemConfig(key=SETTINGS_KEY, value=settings)
        db.add(row)
    else:
        row.value = settings
        flag_modified(row, "value")
    db.commit()


def cleanup_expired_mobile_client_logs(db: Session, retention_days: int = None) -> int:
    """
    按 retention_days 清理过期日志（基于 created_at）。

    - 为避免一次性删除过多导致锁表，使用分批删除
    - 返回删除的总行数
    """
    if retention_days is None:
        settings = load_mobile_client_log_settings(db)
        retention_days = int(settings.get("retention_days") or DEFAULT_SETTINGS["retention_days"])

    retention_days = max(1, int(retention_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    batch_size = 20000
    deleted_total = 0

    while True:
        res = db.execute(
            text(
                """
                DELETE FROM mobile_client_logs
                WHERE id IN (
                    SELECT id FROM mobile_client_logs
                    WHERE created_at < :cutoff
                    ORDER BY id
                    LIMIT :limit
                )
                """
            ),
            {"cutoff": cutoff, "limit": batch_size},
        )
        db.commit()
        deleted = int(res.rowcount or 0)
        deleted_total += deleted
        if deleted < batch_size:
            break

    return deleted_total


def cleanup_mobile_client_logs_by_tag(db: Session, tag: str) -> int:
    """
    按 tag 批量清理日志（用于一次性移除历史 request 日志等）。

    - 返回删除的总行数
    """
    tag_val = str(tag or "").strip()
    if not tag_val:
        return 0

    batch_size = 20000
    deleted_total = 0

    while True:
        res = db.execute(
            text(
                """
                DELETE FROM mobile_client_logs
                WHERE id IN (
                    SELECT id FROM mobile_client_logs
                    WHERE tag = :tag
                    ORDER BY id
                    LIMIT :limit
                )
                """
            ),
            {"tag": tag_val, "limit": batch_size},
        )
        db.commit()
        deleted = int(res.rowcount or 0)
        deleted_total += deleted
        if deleted < batch_size:
            break

    return deleted_total


def cleanup_mobile_client_logs_by_filters(
    db: Session,
    *,
    retention_days: Optional[int] = None,
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    device_id: Optional[str] = None,
    route: Optional[str] = None,
    tag: Optional[str] = None,
    app_version_code: Optional[int] = None,
    api_status: Optional[int] = None,
    api_url: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> int:
    """
    按筛选条件批量清理移动端日志（分批删除，降低 SQLite 锁表风险）。

    说明：
    - retention_days 基于 created_at（服务端入库时间）
    - date_from/date_to 基于 occurred_at（客户端上报时间）
    - keyword 会同时匹配 message/tag/route/api_url/username/error_msg/context
    """

    query = db.query(MobileClientLog.id)

    if retention_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(retention_days)))
        query = query.filter(MobileClientLog.created_at < cutoff)

    if user_id is not None:
        query = query.filter(MobileClientLog.user_id == int(user_id))
    if username:
        query = query.filter(MobileClientLog.username == str(username))
    if level:
        query = query.filter(MobileClientLog.level == str(level).strip().upper())
    if device_id:
        query = query.filter(MobileClientLog.device_id == str(device_id))
    if route:
        query = query.filter(MobileClientLog.route.like(f"%{route}%"))
    if tag:
        query = query.filter(MobileClientLog.tag == str(tag))
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

    batch_size = 20000
    deleted_total = 0

    while True:
        ids = [row[0] for row in query.order_by(MobileClientLog.id).limit(batch_size).all()]
        if not ids:
            break

        deleted = (
            db.query(MobileClientLog)
            .filter(MobileClientLog.id.in_(ids))
            .delete(synchronize_session=False)
        )
        db.commit()

        deleted_total += int(deleted or 0)
        if len(ids) < batch_size:
            break

    return deleted_total
