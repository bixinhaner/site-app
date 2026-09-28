from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查 work_orders 缺失列并用 ALTER TABLE ADD COLUMN 补齐
    """
    required_columns = {
        "work_orders": {
            "review_comments_i18n": "review_comments_i18n TEXT",
            "void_reason": "void_reason TEXT",
            "voided_by": "voided_by INTEGER",
            "voided_at": "voided_at DATETIME",
            "settlement_status": "settlement_status VARCHAR(20) DEFAULT 'unsettled'",
            "settlement_batch_no": "settlement_batch_no VARCHAR(100)",
            "settled_at": "settled_at DATETIME",
            "settlement_notes": "settlement_notes TEXT",
            "settlement_updated_by": "settlement_updated_by INTEGER",
            "settlement_updated_at": "settlement_updated_at DATETIME",
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

        try:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_work_orders_settlement_status ON work_orders (settlement_status)")
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index ix_work_orders_settlement_status: {e}")

        if engine.dialect.name == "mysql":
            # 工单类型为原生 ENUM 时补充新增类型（存储值为枚举名）；非 ENUM 列不做修改
            try:
                type_row = conn.execute(text("SHOW COLUMNS FROM work_orders LIKE 'type'")).fetchone()
                type_def = str(type_row[1] if type_row else "").lower()
                if type_def.startswith("enum(") and "'other'" not in type_def:
                    conn.execute(
                        text(
                            """
                            ALTER TABLE work_orders
                            MODIFY COLUMN type ENUM(
                                'OPENING_INSPECTION', 'SSV', 'MAINTENANCE', 'EQUIPMENT_REPLACEMENT', 'CELL_EXPANSION',
                                'POWER_ISSUE', 'TRANSMISSION_ISSUE', 'GPS_ISSUE', 'SIGNAL_ISSUE', 'SITE_SURVEY', 'OTHER'
                            ) NOT NULL
                            """
                        )
                    )
            except Exception as e:
                print(f"[Schema Migration] Skipped enum alter for work_orders.type: {e}")
            try:
                conn.execute(
                    text(
                        """
                        ALTER TABLE work_orders
                        MODIFY COLUMN status ENUM(
                            'PENDING', 'ACTIVE', 'SUBMITTED', 'UNDER_REVIEW',
                            'APPROVED', 'ACTIVATED', 'REJECTED', 'COMPLETED', 'VOIDED'
                        ) NOT NULL DEFAULT 'PENDING'
                        """
                    )
                )
            except Exception as e:
                print(f"[Schema Migration] Skipped enum alter for work_orders.status: {e}")
