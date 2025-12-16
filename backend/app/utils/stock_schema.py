from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_stock_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - 由于项目未引入 Alembic，Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查缺失列并用 ALTER TABLE ADD COLUMN 补齐
    """
    required_columns = {
        "equipment_instances": {
            "original_serial_number": "original_serial_number VARCHAR(100)",
            "is_voided": "is_voided INTEGER DEFAULT 0",
            "voided_at": "voided_at DATETIME",
            "voided_by": "voided_by INTEGER",
            "void_reason": "void_reason TEXT",
        },
        "stock_transaction_items": {
            "vendor": "vendor VARCHAR(100)",
            "item_notes": "item_notes TEXT",
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

