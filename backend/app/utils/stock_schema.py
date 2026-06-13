import json

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


def _parse_scan_location(raw_value):
    if isinstance(raw_value, dict):
        return raw_value
    if not raw_value:
        return {}
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _backfill_stock_transaction_request_links(conn) -> None:
    rows = (
        conn.execute(
            text(
                """
                SELECT id, scan_location
                FROM stock_transactions
                WHERE
                    (material_request_id IS NULL OR material_request_no IS NULL
                     OR issue_draft_id IS NULL OR issue_draft_no IS NULL)
                    AND scan_location IS NOT NULL
                """
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        loc = _parse_scan_location(row["scan_location"])
        if loc.get("_source") != "issue_draft_confirm":
            continue

        request_id = str(loc.get("request_id") or "").strip()
        draft_id = str(loc.get("issue_draft_id") or "").strip()
        if not request_id and not draft_id:
            continue

        source = None
        if draft_id:
            source = (
                conn.execute(
                    text(
                        """
                        SELECT
                            issue_drafts.id AS issue_draft_id,
                            issue_drafts.draft_no AS issue_draft_no,
                            material_requests.id AS material_request_id,
                            material_requests.request_no AS material_request_no
                        FROM issue_drafts
                        JOIN material_requests ON material_requests.id = issue_drafts.request_id
                        WHERE issue_drafts.id = :draft_id
                        LIMIT 1
                        """
                    ),
                    {"draft_id": draft_id},
                )
                .mappings()
                .first()
            )
        if not source and request_id:
            source = (
                conn.execute(
                    text(
                        """
                        SELECT
                            NULL AS issue_draft_id,
                            NULL AS issue_draft_no,
                            id AS material_request_id,
                            request_no AS material_request_no
                        FROM material_requests
                        WHERE id = :request_id
                        LIMIT 1
                        """
                    ),
                    {"request_id": request_id},
                )
                .mappings()
                .first()
            )
        if not source:
            continue

        conn.execute(
            text(
                """
                UPDATE stock_transactions
                SET
                    material_request_id = COALESCE(material_request_id, :material_request_id),
                    material_request_no = COALESCE(material_request_no, :material_request_no),
                    issue_draft_id = COALESCE(issue_draft_id, :issue_draft_id),
                    issue_draft_no = COALESCE(issue_draft_no, :issue_draft_no)
                WHERE id = :transaction_id
                """
            ),
            {
                "transaction_id": row["id"],
                "material_request_id": source["material_request_id"],
                "material_request_no": source["material_request_no"],
                "issue_draft_id": source["issue_draft_id"],
                "issue_draft_no": source["issue_draft_no"],
            },
        )

    return_rows = (
        conn.execute(
            text(
                """
                SELECT
                    ret.id AS return_id,
                    out.material_request_id,
                    out.material_request_no,
                    out.issue_draft_id,
                    out.issue_draft_no
                FROM stock_transactions AS ret
                JOIN stock_transactions AS out ON out.id = ret.related_transaction_id
                WHERE
                    ret.transaction_type = 'RETURN'
                    AND out.material_request_id IS NOT NULL
                    AND (
                        ret.material_request_id IS NULL OR ret.material_request_no IS NULL
                        OR ret.issue_draft_id IS NULL OR ret.issue_draft_no IS NULL
                    )
                """
            )
        )
        .mappings()
        .all()
    )

    for row in return_rows:
        conn.execute(
            text(
                """
                UPDATE stock_transactions
                SET
                    material_request_id = COALESCE(material_request_id, :material_request_id),
                    material_request_no = COALESCE(material_request_no, :material_request_no),
                    issue_draft_id = COALESCE(issue_draft_id, :issue_draft_id),
                    issue_draft_no = COALESCE(issue_draft_no, :issue_draft_no)
                WHERE id = :return_id
                """
            ),
            {
                "return_id": row["return_id"],
                "material_request_id": row["material_request_id"],
                "material_request_no": row["material_request_no"],
                "issue_draft_id": row["issue_draft_id"],
                "issue_draft_no": row["issue_draft_no"],
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
            "offline_document_id": "offline_document_id VARCHAR(32)",
            "material_request_id": "material_request_id VARCHAR(32)",
            "material_request_no": "material_request_no VARCHAR(50)",
            "issue_draft_id": "issue_draft_id VARCHAR(32)",
            "issue_draft_no": "issue_draft_no VARCHAR(50)",
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

        stock_indexes = {
            "ix_stock_transactions_material_request_id": "material_request_id",
            "ix_stock_transactions_material_request_no": "material_request_no",
            "ix_stock_transactions_issue_draft_id": "issue_draft_id",
            "ix_stock_transactions_issue_draft_no": "issue_draft_no",
        }
        for index_name, column_name in stock_indexes.items():
            try:
                conn.execute(
                    text(
                        f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON stock_transactions ({column_name})
                        """
                    )
                )
            except Exception:
                continue

        try:
            _backfill_stock_transaction_request_links(conn)
        except Exception:
            pass

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
