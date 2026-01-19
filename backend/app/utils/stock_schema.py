from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _dedupe_inventory_records(conn) -> None:
    rows = (
        conn.execute(
            text(
                """
                SELECT
                    warehouse_id,
                    equipment_id,
                    MIN(id) AS keep_id,
                    SUM(COALESCE(current_stock, 0)) AS sum_current_stock,
                    SUM(COALESCE(available_stock, 0)) AS sum_available_stock,
                    SUM(COALESCE(reserved_stock, 0)) AS sum_reserved_stock,
                    SUM(COALESCE(allocated_stock, 0)) AS sum_allocated_stock
                FROM inventory
                GROUP BY warehouse_id, equipment_id
                HAVING COUNT(*) > 1
                """
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        conn.execute(
            text(
                """
                UPDATE inventory
                SET
                    current_stock = :current_stock,
                    available_stock = :available_stock,
                    reserved_stock = :reserved_stock,
                    allocated_stock = :allocated_stock
                WHERE id = :keep_id
                """
            ),
            {
                "current_stock": int(row["sum_current_stock"] or 0),
                "available_stock": int(row["sum_available_stock"] or 0),
                "reserved_stock": int(row["sum_reserved_stock"] or 0),
                "allocated_stock": int(row["sum_allocated_stock"] or 0),
                "keep_id": row["keep_id"],
            },
        )
        conn.execute(
            text(
                """
                DELETE FROM inventory
                WHERE
                    warehouse_id = :warehouse_id
                    AND equipment_id = :equipment_id
                    AND id <> :keep_id
                """
            ),
            {
                "warehouse_id": row["warehouse_id"],
                "equipment_id": row["equipment_id"],
                "keep_id": row["keep_id"],
            },
        )


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
        "stock_transactions": {
            "related_transaction_id": "related_transaction_id VARCHAR(36)",
            "issued_to": "issued_to INTEGER",
        },
        "stock_transaction_items": {
            "vendor": "vendor VARCHAR(100)",
            "item_notes": "item_notes TEXT",
            "received_qty": "received_qty INTEGER DEFAULT 0",
        },
        "pickup_records": {
            "mac_address_3": "mac_address_3 VARCHAR(50)",
            "mac_address_4": "mac_address_4 VARCHAR(50)",
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

        # 防止 inventory 出现重复行（仓库+设备），导致库存判断/回滚命中错误记录
        try:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_warehouse_equipment
                    ON inventory (warehouse_id, equipment_id)
                    """
                )
            )
        except Exception:
            try:
                _dedupe_inventory_records(conn)
                conn.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_warehouse_equipment
                        ON inventory (warehouse_id, equipment_id)
                        """
                    )
                )
            except Exception:
                return
