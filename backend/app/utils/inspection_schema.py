from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_inspection_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查 site_inspections / inspection_check_items / inspection_photos 缺失列并用 ALTER TABLE ADD COLUMN 补齐
    - 清理旧版“检查项范围唯一索引”，避免在“只提醒不阻断”模式下误拦截
    """
    required_columns = {
        "site_inspections": {
            "review_comments_i18n": "review_comments_i18n TEXT",
        },
        "inspection_check_items": {
            "notes": "notes TEXT",
            "review_comments_i18n": "review_comments_i18n TEXT",
            "ai_status": "ai_status TEXT",
            "ai_mode": "ai_mode TEXT",
            "ai_model": "ai_model TEXT",
            "ai_input_hash": "ai_input_hash TEXT",
            "ai_result": "ai_result TEXT",
            "ai_error": "ai_error TEXT",
            "ai_checked_by": "ai_checked_by INTEGER",
            "ai_checked_at": "ai_checked_at DATETIME",
            "ai_applied_by": "ai_applied_by INTEGER",
            "ai_applied_at": "ai_applied_at DATETIME",
        },
        "inspection_photos": {
            "field_id": "field_id TEXT",
            "content_hash": "content_hash TEXT",
            "is_duplicate_global": "is_duplicate_global INTEGER DEFAULT 0",
            "duplicate_info": "duplicate_info TEXT",
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

        # 兼容新规则：关闭阻断时允许重复上传，因此移除旧版强制唯一索引
        try:
            conn.execute(text("DROP INDEX IF EXISTS uq_inspection_photos_scope_content_hash"))
        except Exception as e:
            print(f"[Schema Migration] Skipped drop index uq_inspection_photos_scope_content_hash: {e}")

        # 提升哈希查询性能（用于全局重复识别）
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_photos_content_hash "
                    "ON inspection_photos (content_hash)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_photos_content_hash: {e}")
