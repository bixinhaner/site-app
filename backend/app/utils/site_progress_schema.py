from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_site_progress_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 为站点生命周期快照补齐设备事实口径相关字段
    """
    required_columns = {
        "site_progress_snapshots": {
            "online_at_device_fact": "online_at_device_fact DATETIME",
            "activated_at_device_fact": "activated_at_device_fact DATETIME",
            "snapshot_version": "snapshot_version INTEGER DEFAULT 1",
        },
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            try:
                existing = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                continue

            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
                    print(f"[Schema Migration] Added column {column_name} to {table_name}")
                except Exception as e:
                    print(f"[Schema Migration] Skipped {column_name} on {table_name}: {e}")
                    continue

        try:
            conn.execute(
                text(
                    "UPDATE site_progress_snapshots "
                    "SET snapshot_version = 1 "
                    "WHERE snapshot_version IS NULL OR snapshot_version <= 0"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill site_progress_snapshots.snapshot_version: {e}")
