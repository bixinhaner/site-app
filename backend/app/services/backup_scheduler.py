import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from app.core.database import SessionLocal
from app.models.system_config import SystemConfig
from app.services.backup_service import (
    BACKUP_CONFIG_KEY,
    get_default_backup_config,
    load_backup_config,
    save_backup_config,
    perform_backup,
)
from app.utils.timezone import to_utc_iso


_scheduler_started = False
logger = logging.getLogger(__name__)


def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # to_utc_iso 使用的是 UTC ISO，支持带 Z
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _get_next_run_time(config: Dict[str, Any], now_utc: datetime) -> Optional[datetime]:
    """根据配置和 last_run_at 计算下一次应运行的时间。"""
    if not config.get("enabled"):
        return None

    interval = max(int(config.get("interval") or 1), 1)
    mode = config.get("mode") or "days"

    last_run_at = _parse_iso(config.get("last_run_at"))
    if not last_run_at:
        # 从未执行过，则立即执行
        return now_utc

    if mode == "hours":
        return last_run_at + timedelta(hours=interval)
    else:
        return last_run_at + timedelta(days=interval)


def _backup_scheduler_loop():
    """
    简单的轮询调度器：
    - 每 60 秒检查一次配置
    - 若到达下次执行时间则触发一次定时备份
    """
    logger.info("数据备份调度器已启动（轮询间隔 60 秒）")
    while True:
        try:
            db = SessionLocal()
            try:
                config = load_backup_config(db)
                now_utc = datetime.now(timezone.utc)
                next_run_at = _get_next_run_time(config, now_utc)

                if not config.get("enabled") or not next_run_at:
                    # 未启用或无法计算下次运行时间，休眠一会儿
                    time.sleep(60)
                    continue

                # 尚未到达下次运行时间
                if now_utc < next_run_at:
                    time.sleep(60)
                    continue

                # 到达或超过下次运行时间，执行一次定时备份
                try:
                    logger.info(
                        "触发定时备份：now=%s next_run_at=%s",
                        to_utc_iso(now_utc),
                        to_utc_iso(next_run_at),
                    )
                    result = perform_backup(db, trigger_type="scheduled", trigger_user=None)
                    if result.get("status") == "success":
                        # 仅在成功时记录 last_run_at / last_success_at
                        finished_at = result.get("finished_at") or result.get("started_at") or now_utc
                        config["last_run_at"] = to_utc_iso(finished_at)
                        config["last_success_at"] = config["last_run_at"]
                        save_backup_config(db, config)
                        db.commit()
                        logger.info("定时备份成功：backup_file=%s", result.get("backup_file"))
                except Exception:
                    # 定时任务失败在 perform_backup 内部已写入日志，这里仅忽略
                    logger.exception("定时备份执行失败")

            finally:
                db.close()

        except Exception:
            # 调度器自身异常不应终止循环
            logger.exception("数据备份调度器循环异常")
            time.sleep(60)


def start_backup_scheduler():
    """启动备份调度线程（确保只启动一次）。"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    t = threading.Thread(
        target=_backup_scheduler_loop,
        name="DataBackupScheduler",
        daemon=True,
    )
    t.start()
