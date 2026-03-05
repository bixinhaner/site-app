from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _rebuild_users_without_role_for_sqlite(conn) -> None:
    # 仅用于 SQLite 在不支持 DROP COLUMN 或失败时兜底。
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS users__new (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                phone VARCHAR(20),
                is_active BOOLEAN,
                avatar VARCHAR(255),
                department VARCHAR(100),
                position VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO users__new (
                id, username, email, hashed_password, full_name, phone,
                is_active, avatar, department, position, created_at, updated_at
            )
            SELECT
                id, username, email, hashed_password, full_name, phone,
                is_active, avatar, department, position, created_at, updated_at
            FROM users
            """
        )
    )
    conn.execute(text("DROP TABLE users"))
    conn.execute(text("ALTER TABLE users__new RENAME TO users"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _migrate_legacy_users_role(conn) -> None:
    cols = {r["name"] for r in conn.execute(text("PRAGMA table_info(users)")).mappings().all()}
    if "role" not in cols:
        return

    # 读取 legacy role
    rows = conn.execute(
        text(
            """
            SELECT id, COALESCE(NULLIF(TRIM(role), ''), 'user') AS role_code
            FROM users
            """
        )
    ).mappings().all()

    role_codes = sorted({str(r["role_code"]).strip() for r in rows if str(r["role_code"]).strip()})
    if "user" not in role_codes:
        role_codes.append("user")

    # 确保 roles 存在
    for code in role_codes:
        conn.execute(
            text(
                """
                INSERT INTO roles (code, name, description, is_system, is_active)
                SELECT :code, :name, :desc, 0, 1
                WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = :code)
                """
            ),
            {"code": code, "name": code, "desc": "legacy role migrated from users.role"},
        )

    role_map_rows = conn.execute(text("SELECT id, code FROM roles")).mappings().all()
    role_id_by_code = {str(r["code"]): int(r["id"]) for r in role_map_rows}

    for r in rows:
        uid = int(r["id"])
        code = str(r["role_code"]).strip() or "user"
        role_id = role_id_by_code.get(code)
        if not role_id:
            continue
        conn.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT :uid, :rid
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_roles WHERE user_id = :uid AND role_id = :rid
                )
                """
            ),
            {"uid": uid, "rid": role_id},
        )

    # 删除 legacy 列
    try:
        conn.execute(text("ALTER TABLE users DROP COLUMN role"))
    except Exception:
        _rebuild_users_without_role_for_sqlite(conn)


def ensure_authz_schema(engine: Engine) -> None:
    """
    RBAC 轻量迁移：
    1. 基础表由 Base.metadata.create_all 创建；
    2. 启动时把 users.role 迁移到 user_roles；
    3. 迁移完成后删除 users.role。
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required = {"roles", "permissions", "user_roles", "role_permissions", "users"}
    if not required.issubset(tables):
        return

    with engine.begin() as conn:
        _migrate_legacy_users_role(conn)
