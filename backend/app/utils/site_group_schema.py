from sqlalchemy import JSON, String, column, inspect, or_, table, text
from sqlalchemy.engine import Engine


def ensure_site_group_schema(engine: Engine) -> None:
    """
    站点分组轻量迁移。

    新表由 Base.metadata.create_all 创建；这里负责旧环境兼容和必要索引兜底。
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "site_group_assignments" not in existing_tables:
        return

    with engine.begin() as conn:
        required_columns = {
            "site_group_categories": {
                "assignment_mode": "assignment_mode VARCHAR(20) DEFAULT 'manual' NOT NULL",
                "source_type": "source_type VARCHAR(50)",
                "source_field": "source_field VARCHAR(80)",
                "source_config": "source_config JSON",
            },
        }
        for table_name, columns in required_columns.items():
            try:
                existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                continue
            for column_name, ddl in columns.items():
                if column_name in existing_columns:
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
                    "UPDATE site_group_categories "
                    "SET assignment_mode = 'manual' "
                    "WHERE assignment_mode IS NULL OR assignment_mode = ''"
                )
            )
        except Exception:
            pass

        try:
            categories_table = table(
                "site_group_categories",
                column("code", String),
                column("assignment_mode", String),
                column("source_type", String),
                column("source_field", String),
                column("source_config", JSON),
            )
            conn.execute(
                categories_table.update()
                .where(
                    categories_table.c.code == "delivery_scope",
                    or_(
                        categories_table.c.source_type.is_(None),
                        categories_table.c.source_type == "",
                        categories_table.c.source_field.is_(None),
                        categories_table.c.source_field == "",
                    ),
                )
                .values(
                    assignment_mode="derived",
                    source_type="lld_cell_field",
                    source_field="duplex_mode",
                    source_config={
                        "strategy": "rules",
                        "create_missing_options": False,
                        "rules": [
                            {"option_name": "TDD", "keywords": ["TDD"], "match": "contains"},
                            {"option_name": "FDD", "keywords": ["FDD"], "match": "contains"},
                        ],
                    },
                )
            )
        except Exception:
            pass

        index_sql = [
            "CREATE INDEX IF NOT EXISTS ix_site_group_categories_active_default "
            "ON site_group_categories(is_active, is_default)",
            "CREATE INDEX IF NOT EXISTS ix_site_group_categories_assignment_mode "
            "ON site_group_categories(assignment_mode)",
            "CREATE INDEX IF NOT EXISTS ix_site_group_options_category_active "
            "ON site_group_options(category_id, is_active)",
            "CREATE INDEX IF NOT EXISTS ix_site_group_assignments_category_option "
            "ON site_group_assignments(category_id, option_id)",
        ]
        for sql in index_sql:
            try:
                conn.execute(text(sql))
            except Exception:
                continue
