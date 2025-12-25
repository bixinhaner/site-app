from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

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
