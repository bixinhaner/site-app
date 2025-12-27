from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_inspection_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查 inspection_check_items / inspection_photos 缺失列并用 ALTER TABLE ADD COLUMN 补齐
    """
    required_columns = {
        "inspection_check_items": {
            "notes": "notes TEXT",
        },
        "inspection_photos": {
            "field_id": "field_id TEXT",
        },
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            if not columns:
                continue
            try:
                existing = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                # 表不存在，跳过（create_all 会创建）
                continue

            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
                    print(f"[Schema Migration] Added column {column_name} to {table_name}")
                except Exception as e:
                    # 兼容并发启动/重复执行等场景：若已存在则忽略
                    print(f"[Schema Migration] Skipped {column_name} on {table_name}: {e}")
                    continue
