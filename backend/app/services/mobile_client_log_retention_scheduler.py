import logging
import threading
import time

from app.core.database import SessionLocal
from app.services.mobile_client_log_service import cleanup_expired_mobile_client_logs, cleanup_mobile_client_logs_by_tag


_scheduler_started = False
logger = logging.getLogger(__name__)


def _retention_loop():
    """
    移动端日志保留清理线程：
    - 每 1 小时检查一次并执行清理（内部按批删除，避免长时间锁表）
    """
    logger.info("移动端日志保留清理调度器已启动（轮询间隔 1 小时）")
    while True:
        try:
            db = SessionLocal()
            try:
                # 一次性/兜底：清理历史 request 日志（移动端不再采集请求日志）
                cleanup_mobile_client_logs_by_tag(db, "request")
                deleted = cleanup_expired_mobile_client_logs(db)
                if deleted:
                    logger.info("移动端日志清理完成：deleted=%s", deleted)
            finally:
                db.close()
        except Exception:
            logger.exception("移动端日志清理调度器异常")

        time.sleep(60 * 60)


def start_mobile_client_log_retention_scheduler():
    """启动移动端日志清理线程（确保只启动一次）。"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    t = threading.Thread(
        target=_retention_loop,
        name="MobileClientLogRetentionScheduler",
        daemon=True,
    )
    t.start()
