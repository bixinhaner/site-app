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
        "inspection_templates": {
            "revision": "revision INTEGER DEFAULT 1",
        },
        "site_inspections": {
            "review_comments_i18n": "review_comments_i18n TEXT",
            "applied_template_revision": "applied_template_revision INTEGER DEFAULT 1",
        },
        "inspection_check_items": {
            "template_item_id": "template_item_id TEXT",
            "notes": "notes TEXT",
            "is_active": "is_active INTEGER DEFAULT 1",
            "removed_by_template": "removed_by_template INTEGER DEFAULT 0",
            "removed_at": "removed_at DATETIME",
            "review_comments_manual": "review_comments_manual TEXT",
            "review_comments_i18n": "review_comments_i18n TEXT",
            "field_issue_comments": "field_issue_comments TEXT",
            "field_review_results": "field_review_results TEXT",
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
            "original_content_hash": "original_content_hash TEXT",
            "content_phash": "content_phash TEXT",
            "content_vector": "content_vector TEXT",
            "content_vector_backend": "content_vector_backend TEXT",
            "is_duplicate_global": "is_duplicate_global INTEGER DEFAULT 0",
            "duplicate_info": "duplicate_info TEXT",
            "is_similar_risk": "is_similar_risk INTEGER DEFAULT 0",
            "similar_info": "similar_info TEXT",
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
            conn.execute(text("UPDATE inspection_templates SET revision = 1 WHERE revision IS NULL OR revision <= 0"))
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill inspection_templates.revision: {e}")

        try:
            conn.execute(
                text(
                    "UPDATE site_inspections "
                    "SET applied_template_revision = 1 "
                    "WHERE applied_template_revision IS NULL OR applied_template_revision <= 0"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill site_inspections.applied_template_revision: {e}")

        try:
            conn.execute(
                text(
                    "UPDATE inspection_check_items "
                    "SET is_active = 1 "
                    "WHERE is_active IS NULL"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill inspection_check_items.is_active: {e}")

        try:
            conn.execute(
                text(
                    "UPDATE inspection_check_items "
                    "SET removed_by_template = 0 "
                    "WHERE removed_by_template IS NULL"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill inspection_check_items.removed_by_template: {e}")

        try:
            conn.execute(
                text(
                    "UPDATE inspection_check_items "
                    "SET template_item_id = CASE "
                    "WHEN instr(item_id, '_sector_') > 0 THEN substr(item_id, 1, instr(item_id, '_sector_') - 1) "
                    "WHEN instr(item_id, '_cell_') > 0 THEN substr(item_id, 1, instr(item_id, '_cell_') - 1) "
                    "ELSE item_id "
                    "END "
                    "WHERE template_item_id IS NULL OR template_item_id = ''"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped backfill inspection_check_items.template_item_id: {e}")

        if engine.dialect.name == "mysql":
            try:
                conn.execute(
                    text(
                        """
                        ALTER TABLE site_inspections
                        MODIFY COLUMN status ENUM(
                            'draft', 'in_progress', 'submitted', 'under_review',
                            'approved', 'rejected', 'completed', 'voided'
                        ) DEFAULT 'draft'
                        """
                    )
                )
            except Exception as e:
                print(f"[Schema Migration] Skipped enum alter for site_inspections.status: {e}")

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

        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_photos_original_content_hash "
                    "ON inspection_photos (original_content_hash)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_photos_original_content_hash: {e}")

        # 相似度查询相关索引
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_photos_content_phash "
                    "ON inspection_photos (content_phash)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_photos_content_phash: {e}")

        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_photos_created_at "
                    "ON inspection_photos (created_at)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_photos_created_at: {e}")

        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_photos_is_similar_risk "
                    "ON inspection_photos (is_similar_risk)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_photos_is_similar_risk: {e}")

        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_inspection_check_items_inspection_active "
                    "ON inspection_check_items (inspection_id, is_active)"
                )
            )
        except Exception as e:
            print(f"[Schema Migration] Skipped index idx_inspection_check_items_inspection_active: {e}")
