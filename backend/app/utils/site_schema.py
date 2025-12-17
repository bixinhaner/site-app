from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_site_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - 由于项目未引入 Alembic，Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查缺失列并用 ALTER TABLE ADD COLUMN 补齐
    """
    required_columns = {
        "sites": {
            # SQLite 中 Boolean 通常存为 INTEGER(0/1)
            "survey_required": "survey_required INTEGER DEFAULT 1",
            "survey_skip_reason": "survey_skip_reason TEXT",
            "survey_skipped_at": "survey_skipped_at DATETIME",
            "survey_skipped_by": "survey_skipped_by INTEGER",
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
                except Exception:
                    # 兼容并发启动/重复执行等场景：若已存在则忽略
                    continue

        # 兼容旧数据：补列后将历史记录的 survey_required 置为 1
        try:
            conn.execute(text("UPDATE sites SET survey_required = 1 WHERE survey_required IS NULL"))
        except Exception:
            pass
