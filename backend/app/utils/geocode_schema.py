from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def ensure_geocode_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查 geocode_cache 缺失列并用 ALTER TABLE ADD COLUMN 补齐
    """
    required_columns = {
        "geocode_cache": {
            "address": "address TEXT",
            "sematic_description": "sematic_description TEXT",
            "hit_count": "hit_count INTEGER DEFAULT 0",
            "last_hit_at": "last_hit_at DATETIME",
        }
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

        # 索引（旧表可能缺失）
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_geocode_cache_expires_at ON geocode_cache(expires_at)"))
        except Exception:
            pass

    # 兼容历史数据：若新增列为空，尝试从 payload 回填 address/sematic_description/hit_count
    try:
        from app.models.geocode_cache import GeocodeCache

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            rows = db.query(GeocodeCache).filter(
                (GeocodeCache.address.is_(None)) | (GeocodeCache.sematic_description.is_(None)) | (GeocodeCache.hit_count.is_(None))
            ).all()
            changed = False
            for row in rows:
                payload = row.payload or {}
                if row.address is None:
                    row.address = str(payload.get("address") or "")
                    changed = True
                if row.sematic_description is None:
                    row.sematic_description = str(payload.get("sematic_description") or "")
                    changed = True
                if row.hit_count is None:
                    row.hit_count = 0
                    changed = True
            if changed:
                db.commit()
        finally:
            db.close()
    except Exception:
        # 回填失败不影响业务
        pass
