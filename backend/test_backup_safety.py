import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.services import backup_service
from app.services.backup_scheduler import _get_next_run_time


def record(record_id, trigger_type, created_at):
    return SimpleNamespace(
        id=record_id,
        trigger_type=trigger_type,
        created_at=created_at,
    )


class BackupSafetyTest(unittest.TestCase):
    def test_failed_attempt_uses_retry_interval(self):
        now = datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc)
        attempted_at = now - timedelta(minutes=10)
        config = {
            "enabled": True,
            "mode": "days",
            "interval": 1,
            "last_run_at": "2026-08-03T02:00:00Z",
            "last_attempt_at": attempted_at.isoformat().replace("+00:00", "Z"),
            "last_attempt_status": "failed",
            "failure_retry_minutes": 60,
        }

        self.assertEqual(
            _get_next_run_time(config, now),
            attempted_at + timedelta(minutes=60),
        )

    def test_interrupted_running_attempt_uses_retry_interval(self):
        now = datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc)
        attempted_at = now - timedelta(minutes=10)
        config = {
            "enabled": True,
            "last_attempt_at": attempted_at.isoformat().replace("+00:00", "Z"),
            "last_attempt_status": "running",
            "failure_retry_minutes": 60,
        }

        self.assertEqual(
            _get_next_run_time(config, now),
            attempted_at + timedelta(minutes=60),
        )

    def test_retention_keeps_latest_monthly_manual_and_restore_reference(self):
        records = [
            record(1, "scheduled", datetime(2026, 6, 30, 2, 0)),
            record(2, "scheduled", datetime(2026, 7, 30, 2, 0)),
            record(3, "scheduled", datetime(2026, 7, 31, 2, 0)),
            record(4, "scheduled", datetime(2026, 8, 1, 2, 0)),
            record(5, "scheduled", datetime(2026, 8, 2, 2, 0)),
            record(6, "scheduled", datetime(2026, 8, 3, 2, 0)),
            record(7, "manual", datetime(2026, 5, 1, 2, 0)),
        ]

        keep_ids = backup_service._select_retained_backup_ids(
            records,
            {2},
            latest_scheduled=3,
            keep_monthly_checkpoints=True,
            keep_manual=True,
        )

        self.assertEqual(keep_ids, {1, 2, 3, 4, 5, 6, 7})

    def test_capacity_check_rejects_before_backup_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = os.path.join(temp_dir, "site_manager.db")
            with open(db_file, "wb") as handle:
                handle.truncate(1024)

            with patch.object(
                backup_service.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=1024),
            ):
                with self.assertRaisesRegex(RuntimeError, "磁盘空间不足"):
                    backup_service._ensure_backup_capacity([db_file], temp_dir)

    def test_parallel_backup_is_rejected(self):
        backup_service._BACKUP_RUN_LOCK.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "已有备份任务"):
                backup_service.perform_backup(SimpleNamespace(), "manual")
        finally:
            backup_service._BACKUP_RUN_LOCK.release()


if __name__ == "__main__":
    unittest.main()
